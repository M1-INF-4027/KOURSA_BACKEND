"""
Tests des failles d'autorisation trouvees avant la mise en production.

Chacun de ces tests echoue sur le code d'avant : ils ne decrivent pas des
precautions theoriques mais des chemins qui etaient reellement ouverts.
"""
from datetime import date, timedelta

import pytest
from rest_framework import status

from academic.models import MandatDelegue, StatutMandat
from conftest import auth_client
from teaching.models import FicheSuivi, StatutFiche, UniteEnseignement
from users.models import Role, StatutCompte, Utilisateur


class TestElevationDePrivileges:
    """
    Un compte libre ne doit pas pouvoir se nommer administrateur.

    L'inscription Google acceptait les identifiants de role envoyes par le
    client et les attribuait tels quels, et la liste des roles etait publique :
    il suffisait de lire l'identifiant du role Super Administrateur et de le
    passer a l'inscription pour obtenir le systeme entier, jeton compris.
    """

    def test_la_liste_publique_des_roles_cache_les_roles_privilegies(self, api, roles):
        res = api.get('/api/users/roles/')
        assert res.status_code == status.HTTP_200_OK
        noms = {r['nom_role'] for r in res.data.get('results', res.data)}
        assert Role.SUPER_ADMIN not in noms
        assert Role.CHEF_DEPARTEMENT not in noms
        # Les deux roles qui s'auto-attribuent restent visibles : le formulaire
        # d'inscription en a besoin avant toute connexion.
        assert Role.DELEGUE in noms or Role.ENSEIGNANT in noms

    def test_un_super_admin_voit_tous_les_roles(self, api, admin_user, roles):
        res = auth_client(api, admin_user).get('/api/users/roles/')
        noms = {r['nom_role'] for r in res.data.get('results', res.data)}
        assert Role.SUPER_ADMIN in noms

    def test_inscription_google_refuse_un_role_privilegie(self, api, roles, monkeypatch):
        from users import views

        # On court-circuite la verification Firebase : ce n'est pas elle que
        # ce test interroge, mais ce que le serveur fait du role demande.
        monkeypatch.setattr(
            views.GoogleAuthView, '_verify_firebase_token',
            lambda self, token: {'email': 'intrus@exemple.cm', 'name': 'Intrus Malveillant'},
        )
        role_admin = Role.objects.get(nom_role=Role.SUPER_ADMIN)
        res = api.post('/api/auth/google/', {
            'id_token': 'peu importe',
            'roles_ids': [role_admin.id],
        }, format='json')

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert not Utilisateur.objects.filter(email='intrus@exemple.cm').exists()


class TestStatutDuCompte:
    """
    Les permissions lisaient `is_active`, jamais `statut`.

    Un compte en attente de validation franchissait donc toutes les
    permissions privilegiees : l'approbation par le chef ne changeait rien
    d'autre que l'affichage.
    """

    @pytest.fixture
    def chef_en_attente(self, roles, structure):
        utilisateur = Utilisateur.objects.create_user(
            email='chef.attente@test.cm', password='MotDePasse123!',
            first_name='Chef', last_name='EnAttente',
            statut=StatutCompte.EN_ATTENTE,
        )
        utilisateur.roles.add(Role.objects.get(nom_role=Role.CHEF_DEPARTEMENT))
        structure['departement'].chef_departement = utilisateur
        structure['departement'].save()
        return utilisateur

    def test_un_chef_en_attente_n_approuve_personne(
        self, api, chef_en_attente, delegue_user
    ):
        delegue_user.statut = StatutCompte.EN_ATTENTE
        delegue_user.save()
        res = auth_client(api, chef_en_attente).post(
            f'/api/users/utilisateurs/{delegue_user.id}/approuver/', {}, format='json')
        assert res.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
        delegue_user.refresh_from_db()
        assert delegue_user.statut != StatutCompte.ACTIF

    def test_un_compte_inactif_perd_ses_privileges(self, api, admin_user, structure):
        admin_user.statut = StatutCompte.INACTIF
        admin_user.save()
        res = auth_client(api, admin_user).delete(
            '/api/teaching/unites-enseignement/delete-all/')
        assert res.status_code == status.HTTP_403_FORBIDDEN


class TestEcritureSurLesCours:
    """
    Seul IsAuthenticated gardait l'ecriture des unites d'enseignement.

    Un delegue pouvait donc creer un cours, en supprimer un, ou s'y inscrire
    lui-meme comme enseignant — puis valider ses propres fiches, la permission
    de validation ne verifiant que « etre l'enseignant de l'UE ».
    """

    def test_un_delegue_ne_cree_pas_de_cours(self, api, delegue_user, annee_active):
        res = auth_client(api, delegue_user).post('/api/teaching/unites-enseignement/', {
            'code_ue': 'PIRATE1', 'libelle_ue': 'Cours cree par un delegue',
            'semestre': 1, 'semestre_obj': annee_active['s1'].id,
        }, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert not UniteEnseignement.objects.filter(code_ue='PIRATE1').exists()

    def test_un_delegue_ne_s_inscrit_pas_comme_enseignant(
        self, api, delegue_user, ue, annee_active
    ):
        ue.niveaux.add(delegue_user.niveau_represente)
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=delegue_user.niveau_represente,
            annee_academique=annee_active['annee'], statut=StatutMandat.APPROUVE,
        )
        res = auth_client(api, delegue_user).patch(
            f'/api/teaching/unites-enseignement/{ue.id}/',
            {'enseignants': [delegue_user.id]}, format='json')

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert delegue_user not in ue.enseignants.all()

    def test_un_delegue_ne_supprime_pas_un_cours(
        self, api, delegue_user, ue, annee_active
    ):
        ue.niveaux.add(delegue_user.niveau_represente)
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=delegue_user.niveau_represente,
            annee_academique=annee_active['annee'], statut=StatutMandat.APPROUVE,
        )
        res = auth_client(api, delegue_user).delete(
            f'/api/teaching/unites-enseignement/{ue.id}/')
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert UniteEnseignement.objects.filter(pk=ue.pk).exists()

    def test_le_chef_garde_la_main_sur_les_cours(
        self, api, chef_user, ue, annee_active
    ):
        res = auth_client(api, chef_user).patch(
            f'/api/teaching/unites-enseignement/{ue.id}/',
            {'libelle_ue': 'Intitule corrige'}, format='json')
        assert res.status_code == status.HTTP_200_OK


class TestCreationDeFiche:
    """
    Un delegue ne declare que pour sa classe, et seulement une fois son
    mandat approuve. Ni l'un ni l'autre n'etait verifie.
    """

    def _charge_utile(self, ue, enseignant, salle):
        return {
            'ue': ue.id, 'enseignant': enseignant.id, 'salle': salle.id,
            'date_cours': date.today().isoformat(),
            'heure_debut': '08:00', 'heure_fin': '10:00',
            'type_seance': 'CM', 'titre_chapitre': 'Chapitre',
            'contenu_aborde': 'Contenu de la seance.',
        }

    def test_sans_mandat_approuve_aucune_fiche(
        self, api, delegue_user, ue, enseignant_user, salle, annee_active
    ):
        ue.niveaux.add(delegue_user.niveau_represente)
        res = auth_client(api, delegue_user).post(
            '/api/teaching/fiches-suivi/',
            self._charge_utile(ue, enseignant_user, salle), format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert FicheSuivi.objects.count() == 0

    def test_pas_de_fiche_sur_le_cours_d_une_autre_classe(
        self, api, delegue_user, ue, enseignant_user, salle, annee_active, structure
    ):
        # Le mandat porte sur M2 ; l'unite visee ne concerne que L1.
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M2'],
            annee_academique=annee_active['annee'], statut=StatutMandat.APPROUVE,
        )
        ue.niveaux.set([structure['niveaux']['L1']])
        res = auth_client(api, delegue_user).post(
            '/api/teaching/fiches-suivi/',
            self._charge_utile(ue, enseignant_user, salle), format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert FicheSuivi.objects.count() == 0

    def test_le_parcours_nominal_reste_ouvert(
        self, api, delegue_user, ue, enseignant_user, salle, annee_active, structure
    ):
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M2'],
            annee_academique=annee_active['annee'], statut=StatutMandat.APPROUVE,
        )
        ue.niveaux.add(structure['niveaux']['M2'])
        ue.enseignants.add(enseignant_user)
        res = auth_client(api, delegue_user).post(
            '/api/teaching/fiches-suivi/',
            self._charge_utile(ue, enseignant_user, salle), format='json')
        assert res.status_code == status.HTTP_201_CREATED, res.data


class TestExportPdfDeFiche:
    """
    L'export PDF interrogeait la base directement, hors du queryset qui
    cloisonne par delegue, par enseignant et par departement.
    """

    @pytest.fixture
    def fiche_d_autrui(self, structure, annee_active, enseignant_user, salle, roles):
        autre_delegue = Utilisateur.objects.create_user(
            email='autre.delegue@test.cm', password='MotDePasse123!',
            first_name='Autre', last_name='Delegue', statut=StatutCompte.ACTIF,
            niveau_represente=structure['niveaux']['L1'],
        )
        autre_delegue.roles.add(Role.objects.get(nom_role=Role.DELEGUE))
        autre_ue = UniteEnseignement.objects.create(
            code_ue='AUTRE1', libelle_ue='Cours d une autre classe',
            semestre=1, semestre_obj=annee_active['s1'],
        )
        autre_ue.niveaux.add(structure['niveaux']['L1'])
        from datetime import time
        return FicheSuivi.objects.create(
            ue=autre_ue, delegue=autre_delegue, enseignant=enseignant_user,
            date_cours=date.today(), heure_debut=time(8, 0), heure_fin=time(10, 0),
            salle=salle, type_seance='CM', titre_chapitre='Chapitre',
            contenu_aborde='Contenu.', statut=StatutFiche.VALIDEE,
            semestre=annee_active['s1'],
        )

    def test_un_delegue_ne_telecharge_pas_la_fiche_d_une_autre_classe(
        self, api, delegue_user, fiche_d_autrui
    ):
        res = auth_client(api, delegue_user).get(
            f'/api/teaching/fiches-suivi/{fiche_d_autrui.id}/export-pdf/')
        assert res.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    def test_un_identifiant_inconnu_ne_provoque_pas_d_erreur_serveur(
        self, api, delegue_user
    ):
        res = auth_client(api, delegue_user).get(
            '/api/teaching/fiches-suivi/999999/export-pdf/')
        assert res.status_code == status.HTTP_404_NOT_FOUND
