"""
Tests du mandat de delegue.

Le mandat rattache a une annee la classe qu'un delegue represente. Avant lui,
cette information tenait dans un seul champ sans annee : au changement
d'annee le delegue restait inscrit dans sa classe de l'an passe, et le filtre
des unites d'enseignement lui montrait les cours de la nouvelle annee mais de
son ancien niveau, sans qu'aucune erreur ne s'affiche.
"""
import pytest
from rest_framework import status

from academic.models import AnneeAcademique, MandatDelegue, StatutMandat
from conftest import auth_client
from teaching.models import UniteEnseignement


URL_DECLARER = '/api/users/utilisateurs/changer-niveau/'
URL_EN_ATTENTE = '/api/users/utilisateurs/mandats-en-attente/'
URL_UES = '/api/teaching/unites-enseignement/'


@pytest.fixture
def mandat_approuve(delegue_user, annee_active):
    """Le delegue a declare sa classe et le chef l'a validee."""
    return MandatDelegue.objects.create(
        utilisateur=delegue_user,
        niveau=delegue_user.niveau_represente,
        annee_academique=annee_active['annee'],
        statut=StatutMandat.APPROUVE,
    )


class TestClasseSansMandat:
    """Sans mandat pour l'annee en cours, le delegue ne voit aucun cours."""

    def test_aucune_ue_sans_mandat(self, api, delegue_user, annee_active, ue):
        # niveau_represente est renseigne, mais aucun mandat ne le rattache a
        # l'annee : c'est exactement la situation du lendemain d'un changement
        # d'annee. Rien ne doit etre renvoye.
        ue.niveaux.add(delegue_user.niveau_represente)
        c = auth_client(api, delegue_user)
        res = c.get(URL_UES)
        assert res.status_code == status.HTTP_200_OK
        resultats = res.data.get('results', res.data)
        assert resultats == []

    def test_les_ues_apparaissent_une_fois_le_mandat_approuve(
        self, api, delegue_user, annee_active, ue, mandat_approuve
    ):
        ue.niveaux.add(delegue_user.niveau_represente)
        c = auth_client(api, delegue_user)
        res = c.get(URL_UES)
        resultats = res.data.get('results', res.data)
        assert [u['code_ue'] for u in resultats] == [ue.code_ue]

    def test_le_profil_annonce_le_renouvellement(self, api, delegue_user, annee_active):
        c = auth_client(api, delegue_user)
        res = c.get('/api/users/utilisateurs/me/')
        assert res.data['mandat']['a_renouveler'] is True
        assert res.data['classe'] is None


class TestDeclarationDeClasse:
    """Declarer sa classe est une demande, non une affectation."""

    def test_la_declaration_attend_une_validation(self, api, delegue_user, annee_active, structure):
        c = auth_client(api, delegue_user)
        res = c.post(URL_DECLARER, {'niveau_id': structure['niveaux']['M1'].id}, format='json')

        assert res.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        mandat = MandatDelegue.objects.get(
            utilisateur=delegue_user, annee_academique=annee_active['annee']
        )
        assert mandat.statut == StatutMandat.EN_ATTENTE
        assert mandat.niveau == structure['niveaux']['M1']

    def test_une_declaration_en_attente_ne_donne_acces_a_rien(
        self, api, delegue_user, annee_active, structure, ue
    ):
        ue.niveaux.add(structure['niveaux']['M1'])
        c = auth_client(api, delegue_user)
        c.post(URL_DECLARER, {'niveau_id': structure['niveaux']['M1'].id}, format='json')

        res = c.get(URL_UES)
        assert res.data.get('results', res.data) == []

    def test_redeclarer_corrige_la_demande_sans_en_creer_une_seconde(
        self, api, delegue_user, annee_active, structure
    ):
        c = auth_client(api, delegue_user)
        c.post(URL_DECLARER, {'niveau_id': structure['niveaux']['M1'].id}, format='json')
        c.post(URL_DECLARER, {'niveau_id': structure['niveaux']['M2'].id}, format='json')

        mandats = MandatDelegue.objects.filter(
            utilisateur=delegue_user, annee_academique=annee_active['annee']
        )
        assert mandats.count() == 1
        assert mandats.first().niveau == structure['niveaux']['M2']


class TestValidationParLeChef:

    def test_le_chef_voit_la_demande(self, api, chef_user, delegue_user, annee_active, structure):
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M1'],
            annee_academique=annee_active['annee'],
        )
        c = auth_client(api, chef_user)
        res = c.get(URL_EN_ATTENTE)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 1
        assert res.data[0]['utilisateur_id'] == delegue_user.id

    def test_l_approbation_ouvre_l_acces_et_met_le_champ_a_jour(
        self, api, chef_user, delegue_user, annee_active, structure
    ):
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M1'],
            annee_academique=annee_active['annee'],
        )
        c = auth_client(api, chef_user)
        res = c.post(f'/api/users/utilisateurs/{delegue_user.id}/approuver-mandat/', {}, format='json')

        assert res.status_code == status.HTTP_200_OK
        delegue_user.refresh_from_db()
        assert delegue_user.niveau_represente == structure['niveaux']['M1']
        assert delegue_user.classe_actuelle() == structure['niveaux']['M1']

    def test_le_refus_exige_un_motif(self, api, chef_user, delegue_user, annee_active, structure):
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M1'],
            annee_academique=annee_active['annee'],
        )
        c = auth_client(api, chef_user)
        res = c.post(f'/api/users/utilisateurs/{delegue_user.id}/refuser-mandat/', {}, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_le_motif_du_refus_revient_au_delegue(
        self, api, chef_user, delegue_user, annee_active, structure
    ):
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M1'],
            annee_academique=annee_active['annee'],
        )
        auth_client(api, chef_user).post(
            f'/api/users/utilisateurs/{delegue_user.id}/refuser-mandat/',
            {'motif': 'Cette classe a deja un delegue.'}, format='json',
        )
        res = auth_client(api, delegue_user).get('/api/users/utilisateurs/me/')
        assert res.data['mandat']['statut'] == 'REFUSE'
        assert res.data['mandat']['a_renouveler'] is True
        assert 'deja un delegue' in res.data['mandat']['motif_refus']

    def test_un_delegue_ne_peut_pas_s_approuver(self, api, delegue_user, annee_active, structure):
        MandatDelegue.objects.create(
            utilisateur=delegue_user, niveau=structure['niveaux']['M1'],
            annee_academique=annee_active['annee'],
        )
        c = auth_client(api, delegue_user)
        res = c.post(f'/api/users/utilisateurs/{delegue_user.id}/approuver-mandat/', {}, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN


class TestChargeDEnseignement:
    """La charge annoncee ne doit couvrir que l'annee en cours."""

    def test_les_ues_des_annees_passees_ne_sont_pas_comptees(
        self, api, enseignant_user, annee_active, ue
    ):
        ancienne = AnneeAcademique.objects.create(libelle='2024-2025', est_active=False)
        from academic.models import Semestre
        from datetime import date
        sem = Semestre.objects.create(
            annee_academique=ancienne, numero=1, est_actif=False,
            date_debut=date(2024, 10, 1), date_fin=date(2025, 2, 28),
        )
        copie = UniteEnseignement.objects.create(
            code_ue=ue.code_ue, libelle_ue=ue.libelle_ue, semestre=1, semestre_obj=sem,
        )
        copie.enseignants.add(enseignant_user)

        res = auth_client(api, enseignant_user).get('/api/users/utilisateurs/me/')
        codes = [u['code'] for u in res.data['enseignements']['ues']]
        # L'UE n'est comptee qu'une fois, celle de l'annee active.
        assert codes.count(ue.code_ue) == 1
