"""
Tests des imports Excel guides (salles, enseignants, whitelist, UEs, affectations).

Les cas nominaux s'appuient sur les fichiers reels de Ressources/Fichiers_Import
lorsqu'ils sont disponibles ; sinon des classeurs equivalents sont construits en
memoire, afin que la suite reste executable en integration continue.
"""
import io
import os

import openpyxl
import pytest
from rest_framework import status

from common.import_utils import detect_niveau_from_code, normalize_header, read_sheet, ExcelInvalide
from conftest import auth_client
from teaching.models import UniteEnseignement
from users.models import Role, StatutCompte, Utilisateur


RESSOURCES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    'Ressources', 'Fichiers_Import',
)


def classeur(entetes, lignes):
    """Construit un .xlsx en memoire, pret a etre poste."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(entetes)
    for ligne in lignes:
        ws.append(ligne)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    buf.name = 'import.xlsx'
    return buf


def fichier_reel(nom):
    """Renvoie le chemin d'un fichier de Ressources, ou None s'il est absent."""
    chemin = os.path.join(RESSOURCES, nom)
    return chemin if os.path.exists(chemin) else None


# ═══════════════════════════════════════════════════════
#  Socle : normalisation et deduction
# ═══════════════════════════════════════════════════════

class TestSocleImport:

    @pytest.mark.parametrize('entree,attendu', [
        ('Code UE', 'code'),
        ('code_ue', 'code'),
        ('Libelle', 'libelle'),
        ('Intitule', 'libelle'),
        ('Nom complet', 'nom_complet'),
        ('Email', 'email'),
        ('enseignant_email', 'enseignant_email'),
        ('Colonne Inconnue', 'colonne_inconnue'),
    ])
    def test_normalisation_entetes(self, entree, attendu):
        assert normalize_header(entree) == attendu

    @pytest.mark.parametrize('code,attendu', [
        ('INF3111', 'L3'),
        ('ICT4200', 'M1'),
        ('FBL111', 'L1'),
        ('ENG103-G1', 'L1'),
        ('INF5000', 'M2'),
        ('XX', None),
        ('9ABC', None),
        ('', None),
    ])
    def test_deduction_niveau(self, code, attendu):
        """La regle doit rester identique a celle du navigateur."""
        assert detect_niveau_from_code(code) == attendu

    def test_colonne_requise_absente(self):
        fichier = classeur(['autre'], [['x']])
        with pytest.raises(ExcelInvalide) as exc:
            read_sheet(fichier, required=['code'])
        assert 'code' in str(exc.value)

    def test_lignes_vides_ignorees(self):
        fichier = classeur(['code'], [['INF1'], [None], [''], ['INF2']])
        assert len(read_sheet(fichier)) == 2


# ═══════════════════════════════════════════════════════
#  Enseignants
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImportEnseignants:

    URL = '/api/users/utilisateurs/import-enseignants/'

    def test_creation_avec_email_comme_mot_de_passe(self, api, admin_user):
        c = auth_client(api, admin_user)
        fichier = classeur(
            ['email', 'nom_complet'],
            [['prof.un@test.cm', 'Adamou Hamza'], ['prof.deux@test.cm', 'Aminou Halidou']],
        )
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 2

        user = Utilisateur.objects.get(email='prof.un@test.cm')
        assert user.check_password('prof.un@test.cm'), "le mot de passe initial doit etre l'email"
        assert user.statut == StatutCompte.ACTIF
        assert user.roles.filter(nom_role=Role.ENSEIGNANT).exists()
        assert user.first_name == 'Adamou' and user.last_name == 'Hamza'

    def test_rejoue_sans_doublon(self, api, admin_user):
        c = auth_client(api, admin_user)
        lignes = [['prof@test.cm', 'Jean Test']]
        c.post(self.URL, {'file': classeur(['email', 'nom_complet'], lignes)}, format='multipart')
        res = c.post(self.URL, {'file': classeur(['email', 'nom_complet'], lignes)}, format='multipart')

        assert res.data['created'] == 0
        assert res.data['skipped'] == 1
        assert Utilisateur.objects.filter(email='prof@test.cm').count() == 1

    def test_compte_existant_conserve_son_mot_de_passe(self, api, admin_user, enseignant_user):
        """Un import ne doit pas reinitialiser le mot de passe d'un compte deja actif."""
        c = auth_client(api, admin_user)
        c.post(self.URL, {'file': classeur(['email'], [[enseignant_user.email]])}, format='multipart')

        enseignant_user.refresh_from_db()
        assert enseignant_user.check_password('TestPass123!')

    def test_email_invalide_reporte_avec_sa_ligne(self, api, admin_user):
        c = auth_client(api, admin_user)
        fichier = classeur(['email'], [['valide@test.cm'], ['pas-un-email']])
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.data['created'] == 1
        assert len(res.data['errors']) == 1
        assert res.data['errors'][0]['ligne'] == 3

    def test_fichier_invalide_rejete(self, api, admin_user):
        c = auth_client(api, admin_user)
        faux = io.BytesIO(b'ceci n est pas un classeur')
        faux.name = 'faux.xlsx'
        res = c.post(self.URL, {'file': faux}, format='multipart')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_reserve_au_super_admin(self, api, chef_user):
        c = auth_client(api, chef_user)
        res = c.post(self.URL, {'file': classeur(['email'], [['x@test.cm']])}, format='multipart')
        assert res.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.skipif(not fichier_reel('Import_Emails_Enseignants_Fonda.xlsx'),
                        reason='fichier de Ressources absent')
    def test_fichier_reel_fonda(self, api, admin_user):
        c = auth_client(api, admin_user)
        with open(fichier_reel('Import_Emails_Enseignants_Fonda.xlsx'), 'rb') as f:
            res = c.post(self.URL, {'file': f}, format='multipart')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 25
        assert not res.data['errors']


# ═══════════════════════════════════════════════════════
#  UEs et affectations
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImportUEs:

    URL = '/api/teaching/unites-enseignement/import/'

    def test_creation_et_deduction_du_niveau(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(
            ['code', 'libelle', 'semestre'],
            [['INF3111', 'Compilation', 1], ['ICT4200', 'Reseaux avances', 1]],
        )
        res = c.post(self.URL, {'file': fichier, 'filiere': structure['filiere'].id},
                     format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 2

        ue = UniteEnseignement.objects.get(code_ue='INF3111')
        assert ue.semestre_obj == annee_active['s1']
        # INF3xxx -> L3, deduit du code sans colonne niveau
        assert list(ue.niveaux.values_list('nom_niveau', flat=True)) == ['L3']
        assert UniteEnseignement.objects.get(code_ue='ICT4200').niveaux.first().nom_niveau == 'M1'

    def test_colonne_niveau_prioritaire_sur_le_code(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(['code', 'libelle', 'semestre', 'niveau'],
                           [['INF3111', 'Compilation', 1, 'M2']])
        c.post(self.URL, {'file': fichier, 'filiere': structure['filiere'].id}, format='multipart')

        ue = UniteEnseignement.objects.get(code_ue='INF3111')
        assert ue.niveaux.first().nom_niveau == 'M2'

    def test_rejoue_met_a_jour_sans_dupliquer(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        args = {'filiere': structure['filiere'].id}
        c.post(self.URL, dict(file=classeur(['code', 'libelle', 'semestre'],
                                            [['INF1', 'Ancien libelle', 1]]), **args),
               format='multipart')
        res = c.post(self.URL, dict(file=classeur(['code', 'libelle', 'semestre'],
                                                  [['INF1', 'Nouveau libelle', 1]]), **args),
                     format='multipart')

        assert res.data['created'] == 0
        assert res.data['updated'] == 1
        assert UniteEnseignement.objects.filter(code_ue='INF1').count() == 1
        assert UniteEnseignement.objects.get(code_ue='INF1').libelle_ue == 'Nouveau libelle'

    def test_semestre_inexistant_reporte(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(['code', 'libelle', 'semestre'], [['INF1', 'Test', 9]])
        res = c.post(self.URL, {'file': fichier, 'filiere': structure['filiere'].id},
                     format='multipart')

        assert res.data['created'] == 0
        assert 'Semestre 9' in res.data['errors'][0]['message']

    @pytest.mark.skipif(not fichier_reel('Import_UEs_Fonda.xlsx'),
                        reason='fichier de Ressources absent')
    def test_fichier_reel_fonda(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        with open(fichier_reel('Import_UEs_Fonda.xlsx'), 'rb') as f:
            res = c.post(self.URL, {'file': f, 'filiere': structure['filiere'].id},
                         format='multipart')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 188
        assert not res.data['errors']


@pytest.mark.django_db
class TestImportAffectations:

    URL = '/api/teaching/unites-enseignement/import-affectations/'

    def test_rattachement_par_email(self, api, admin_user, annee_active, structure, enseignant_user):
        c = auth_client(api, admin_user)
        UniteEnseignement.objects.create(
            code_ue='INF3111', libelle_ue='Compilation',
            semestre=1, semestre_obj=annee_active['s1'],
        )
        fichier = classeur(['code_ue', 'enseignant_nom', 'enseignant_email', 'niveau', 'semestre'],
                           [['INF3111', 'PEU IMPORTE', enseignant_user.email, 'L3', 1]])
        res = c.post(self.URL, {'file': fichier, 'filiere': structure['filiere'].id},
                     format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['updated'] == 1
        ue = UniteEnseignement.objects.get(code_ue='INF3111')
        assert enseignant_user in ue.enseignants.all()

    def test_repli_sur_le_nom_sans_email(self, api, admin_user, annee_active, structure, enseignant_user):
        c = auth_client(api, admin_user)
        UniteEnseignement.objects.create(
            code_ue='INF3111', libelle_ue='Compilation',
            semestre=1, semestre_obj=annee_active['s1'],
        )
        # enseignant_user a pour nom 'ATSA'
        fichier = classeur(['code_ue', 'enseignant_nom', 'semestre'], [['INF3111', 'ATSA', 1]])
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.data['updated'] == 1

    def test_ue_absente_reportee(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(['code_ue', 'enseignant_email'], [['INCONNU', 'x@test.cm']])
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.data['updated'] == 0
        assert 'UE introuvable' in res.data['errors'][0]['message']

    def test_enseignant_absent_reporte(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        UniteEnseignement.objects.create(
            code_ue='INF3111', libelle_ue='Compilation',
            semestre=1, semestre_obj=annee_active['s1'],
        )
        fichier = classeur(['code_ue', 'enseignant_email'], [['INF3111', 'absent@test.cm']])
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.data['updated'] == 0
        assert 'Enseignant introuvable' in res.data['errors'][0]['message']


# ═══════════════════════════════════════════════════════
#  Whitelist
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImportWhitelist:

    URL = '/api/users/whitelist/import/'

    def test_import_avec_departement(self, api, admin_user, structure):
        from users.models import EmailWhitelist

        c = auth_client(api, admin_user)
        fichier = classeur(['Email', 'Role', 'Nom complet'],
                           [['a@test.cm', 'ENSEIGNANT', 'Un Nom'],
                            ['b@test.cm', 'DELEGUE', 'Autre Nom']])
        res = c.post(self.URL, {'file': fichier, 'departement': structure['departement'].id},
                     format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 2
        assert EmailWhitelist.objects.filter(email='a@test.cm').first().role_type == 'ENSEIGNANT'

    def test_departement_obligatoire_pour_admin(self, api, admin_user):
        c = auth_client(api, admin_user)
        res = c.post(self.URL, {'file': classeur(['Email'], [['a@test.cm']])}, format='multipart')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_role_inconnu_reporte(self, api, admin_user, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(['Email', 'Role'], [['a@test.cm', 'DIRECTEUR']])
        res = c.post(self.URL, {'file': fichier, 'departement': structure['departement'].id},
                     format='multipart')

        assert res.data['created'] == 0
        assert 'Role inconnu' in res.data['errors'][0]['message']


# ═══════════════════════════════════════════════════════
#  Parametres complementaires (niveaux imposes, role par defaut)
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestParametresImport:

    def test_niveaux_imposes_appliques_a_toutes_les_lignes(
        self, api, admin_user, annee_active, structure
    ):
        """La selection manuelle de niveaux de l'interface s'ajoute a la deduction."""
        c = auth_client(api, admin_user)
        l1 = structure['niveaux']['L1']
        fichier = classeur(['code', 'libelle', 'semestre'], [['INF3111', 'Compilation', 1]])
        c.post('/api/teaching/unites-enseignement/import/',
               {'file': fichier, 'filiere': structure['filiere'].id, 'niveaux': str(l1.id)},
               format='multipart')

        noms = set(
            UniteEnseignement.objects.get(code_ue='INF3111')
            .niveaux.values_list('nom_niveau', flat=True)
        )
        # L3 deduit du code + L1 impose depuis l'interface
        assert noms == {'L3', 'L1'}

    def test_role_defaut_whitelist(self, api, admin_user, structure):
        """Sans colonne role, le role choisi dans l'interface s'applique."""
        from users.models import EmailWhitelist

        c = auth_client(api, admin_user)
        fichier = classeur(['Email'], [['delegue@test.cm']])
        c.post('/api/users/whitelist/import/',
               {'file': fichier, 'departement': structure['departement'].id,
                'role_defaut': 'DELEGUE'},
               format='multipart')

        assert EmailWhitelist.objects.get(email='delegue@test.cm').role_type == 'DELEGUE'

    def test_colonne_role_prioritaire_sur_le_defaut(self, api, admin_user, structure):
        from users.models import EmailWhitelist

        c = auth_client(api, admin_user)
        fichier = classeur(['Email', 'Role'], [['ens@test.cm', 'ENSEIGNANT']])
        c.post('/api/users/whitelist/import/',
               {'file': fichier, 'departement': structure['departement'].id,
                'role_defaut': 'DELEGUE'},
               format='multipart')

        assert EmailWhitelist.objects.get(email='ens@test.cm').role_type == 'ENSEIGNANT'

    def test_checklist_signale_les_enseignants(self, api, admin_user, annee_active, roles):
        """Le drapeau enseignants_crees pilote la reprise du wizard."""
        c = auth_client(api, admin_user)
        avant = c.get('/api/configuration/checklist/').data['checklist']
        assert avant['enseignants_crees'] is False

        c.post('/api/users/utilisateurs/import-enseignants/',
               {'file': classeur(['email'], [['nouveau@test.cm']])}, format='multipart')

        apres = c.get('/api/configuration/checklist/').data['checklist']
        assert apres['enseignants_crees'] is True


# ═══════════════════════════════════════════════════════
#  Structure academique
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImportStructure:

    URL = '/api/academic/structure/import/'

    def test_creation_de_la_hierarchie_complete(self, api, admin_user):
        from academic.models import Faculte, Departement, Filiere, Niveau

        c = auth_client(api, admin_user)
        fichier = classeur(
            ['faculte', 'departement', 'filiere', 'niveau'],
            [
                ['Faculte des Sciences', 'Informatique', 'Informatique Fondamentale', 'L1'],
                ['Faculte des Sciences', 'Informatique', 'Informatique Fondamentale', 'L2'],
                ['Faculte des Sciences', 'Informatique', 'Informatique Professionnelle', 'L1'],
            ],
        )
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 3
        # La faculte et le departement ne sont crees qu'une fois, malgre 3 lignes
        assert Faculte.objects.count() == 1
        assert Departement.objects.count() == 1
        # Fonda et Pro sont bien deux filieres distinctes
        assert Filiere.objects.count() == 2
        assert Niveau.objects.count() == 3

    def test_niveaux_rattaches_a_la_bonne_filiere(self, api, admin_user):
        from academic.models import Filiere

        c = auth_client(api, admin_user)
        fichier = classeur(
            ['faculte', 'departement', 'filiere', 'niveau'],
            [['F', 'D', 'Fonda', 'L1'], ['F', 'D', 'Pro', 'L1']],
        )
        c.post(self.URL, {'file': fichier}, format='multipart')

        fonda = Filiere.objects.get(nom_filiere='Fonda')
        pro = Filiere.objects.get(nom_filiere='Pro')
        assert fonda.niveaux.count() == 1
        assert pro.niveaux.count() == 1
        assert fonda.niveaux.first().id != pro.niveaux.first().id

    def test_rejoue_sans_doublon(self, api, admin_user):
        from academic.models import Niveau

        c = auth_client(api, admin_user)
        lignes = [['F', 'D', 'Fonda', 'L1']]
        entetes = ['faculte', 'departement', 'filiere', 'niveau']
        c.post(self.URL, {'file': classeur(entetes, lignes)}, format='multipart')
        res = c.post(self.URL, {'file': classeur(entetes, lignes)}, format='multipart')

        assert res.data['created'] == 0
        assert res.data['skipped'] == 1
        assert Niveau.objects.count() == 1

    def test_niveau_facultatif(self, api, admin_user):
        """Une ligne sans niveau cree seulement la branche faculte/departement/filiere."""
        from academic.models import Filiere, Niveau

        c = auth_client(api, admin_user)
        fichier = classeur(['faculte', 'departement', 'filiere'], [['F', 'D', 'Fonda']])
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert Filiere.objects.count() == 1
        assert Niveau.objects.count() == 0

    def test_ligne_incomplete_reportee(self, api, admin_user):
        c = auth_client(api, admin_user)
        fichier = classeur(
            ['faculte', 'departement', 'filiere', 'niveau'],
            [['F', 'D', 'Fonda', 'L1'], ['F', '', 'Pro', 'L1']],
        )
        res = c.post(self.URL, {'file': fichier}, format='multipart')

        assert res.data['created'] == 1
        assert len(res.data['errors']) == 1
        assert res.data['errors'][0]['ligne'] == 3

    def test_colonnes_manquantes_rejetees(self, api, admin_user):
        c = auth_client(api, admin_user)
        fichier = classeur(['faculte'], [['F']])
        res = c.post(self.URL, {'file': fichier}, format='multipart')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_reserve_au_super_admin(self, api, chef_user):
        c = auth_client(api, chef_user)
        fichier = classeur(['faculte', 'departement', 'filiere'], [['F', 'D', 'X']])
        res = c.post(self.URL, {'file': fichier}, format='multipart')
        assert res.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════
#  Changement de mot de passe impose
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestChangementImpose:

    IMPORT = '/api/users/utilisateurs/import-enseignants/'
    CHANGE = '/api/users/utilisateurs/change-password/'

    def _importer(self, api, admin_user, email):
        c = auth_client(api, admin_user)
        c.post(self.IMPORT, {'file': classeur(['email'], [[email]])}, format='multipart')
        return Utilisateur.objects.get(email=email)

    def test_drapeau_pose_a_l_import(self, api, admin_user):
        user = self._importer(api, admin_user, 'importe@test.cm')
        assert user.doit_changer_mot_de_passe is True

    def test_compte_ordinaire_non_concerne(self, enseignant_user):
        """Un compte cree normalement ne subit pas l'obligation."""
        assert enseignant_user.doit_changer_mot_de_passe is False

    def test_changement_leve_l_obligation(self, api, admin_user):
        user = self._importer(api, admin_user, 'importe@test.cm')
        c = auth_client(api, user)
        res = c.post(self.CHANGE, {
            'old_password': 'importe@test.cm',
            'new_password': 'MotDePasseSolide!42',
        }, format='json')

        assert res.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.doit_changer_mot_de_passe is False
        assert user.check_password('MotDePasseSolide!42')

    def test_refus_de_reprendre_son_email(self, api, admin_user):
        """Interdit de « changer » pour la valeur provisoire deja connue."""
        user = self._importer(api, admin_user, 'importe@test.cm')
        c = auth_client(api, user)
        res = c.post(self.CHANGE, {
            'old_password': 'importe@test.cm',
            'new_password': 'importe@test.cm',
        }, format='json')

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.doit_changer_mot_de_passe is True

    def test_drapeau_expose_au_client(self, api, admin_user):
        """L'interface s'appuie sur ce champ pour rediriger l'utilisateur."""
        user = self._importer(api, admin_user, 'importe@test.cm')
        c = auth_client(api, user)
        res = c.get('/api/users/utilisateurs/me/')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['doit_changer_mot_de_passe'] is True


# ═══════════════════════════════════════════════════════
#  Configuration deduite de la checklist
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestConfigurationDeduite:

    STATUS = '/api/configuration/status/'
    CHECKLIST = '/api/configuration/checklist/'

    def _marquer(self, api, admin_user, annee_id):
        return auth_client(api, admin_user).post(
            f'/api/configuration/annee-academique/{annee_id}/marquer-configuree/'
        )

    def test_marquage_refuse_si_incomplet(self, api, admin_user, annee_active):
        """Le blocage subi en production : une annee vide ne peut plus etre declaree prete."""
        # La fixture cree l'annee deja marquee : on repart d'un etat non declare.
        annee_active['annee'].est_configuree = False
        annee_active['annee'].save()

        res = self._marquer(api, admin_user, annee_active['annee'].id)

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'etapes_manquantes' in res.data
        assert 'au moins une faculte' in res.data['etapes_manquantes']

        annee_active['annee'].refresh_from_db()
        assert annee_active['annee'].est_configuree is False

    def test_drapeau_seul_ne_suffit_pas(self, api, admin_user, annee_active):
        """Meme forcee en base, une annee sans donnees n'est pas rapportee configuree."""
        annee_active['annee'].est_configuree = True
        annee_active['annee'].save()

        res = auth_client(api, admin_user).get(self.STATUS)
        assert res.data['est_configure'] is False

    def test_marquage_accepte_quand_tout_est_la(self, api, admin_user, annee_active, structure):
        from academic.models import Salle
        from teaching.models import UniteEnseignement

        Salle.objects.create(nom_salle='A100', est_active=True)
        UniteEnseignement.objects.create(
            code_ue='INF1', libelle_ue='Test',
            semestre=1, semestre_obj=annee_active['s1'],
        )

        res = self._marquer(api, admin_user, annee_active['annee'].id)
        assert res.status_code == status.HTTP_200_OK

        annee_active['annee'].refresh_from_db()
        assert annee_active['annee'].est_configuree is True
        assert auth_client(api, admin_user).get(self.STATUS).data['est_configure'] is True

    def test_checklist_annonce_les_etapes_manquantes(self, api, admin_user, annee_active):
        res = auth_client(api, admin_user).get(self.CHECKLIST)

        assert res.status_code == status.HTTP_200_OK
        assert res.data['est_configuree'] is False
        # Annee et semestres sont satisfaits, le reste manque
        assert "l'annee academique" not in res.data['etapes_manquantes']
        assert 'au moins un departement' in res.data['etapes_manquantes']

    def test_enseignants_et_chefs_ne_bloquent_pas(self, api, admin_user, annee_active, structure):
        """Ils sont recommandes, pas obligatoires : une annee peut demarrer sans."""
        from academic.models import Salle
        from teaching.models import UniteEnseignement
        from users.models import Role, Utilisateur

        Salle.objects.create(nom_salle='A100', est_active=True)
        UniteEnseignement.objects.create(
            code_ue='INF1', libelle_ue='Test',
            semestre=1, semestre_obj=annee_active['s1'],
        )
        assert not Utilisateur.objects.filter(roles__nom_role=Role.ENSEIGNANT).exists()

        assert self._marquer(api, admin_user, annee_active['annee'].id).status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════
#  Import en deux temps : simulation puis validation
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSimulationHierarchique:

    FILIERES = '/api/academic/filieres/import/'
    DEPARTEMENTS = '/api/academic/departements/import/'

    def test_simulation_n_ecrit_rien(self, api, admin_user, structure):
        """Le point cardinal : une simulation ne doit laisser aucune trace."""
        from academic.models import Filiere

        avant = Filiere.objects.count()
        c = auth_client(api, admin_user)
        fichier = classeur(['filiere', 'departement'],
                           [['Nouvelle Filiere', 'Informatique']])
        res = c.post(self.FILIERES, {'file': fichier, 'dry_run': '1'}, format='multipart')

        assert res.status_code == status.HTTP_200_OK
        assert Filiere.objects.count() == avant, "la simulation a ecrit en base"
        assert res.data['lignes'][0]['statut'] == 'ok'
        assert res.data['lignes'][0]['parent']['libelle'] == 'Informatique'

    def test_parent_absent_signale(self, api, admin_user, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(['filiere', 'departement'],
                           [['Filiere X', 'Departement Inexistant']])
        res = c.post(self.FILIERES, {'file': fichier, 'dry_run': '1'}, format='multipart')

        ligne = res.data['lignes'][0]
        assert ligne['statut'] == 'parent_absent'
        assert 'Departement Inexistant' in ligne['message']
        assert ligne['parent']['id'] is None

    def test_doublon_signale(self, api, admin_user, structure):
        c = auth_client(api, admin_user)
        fichier = classeur(['filiere', 'departement'],
                           [[structure['filiere'].nom_filiere, 'Informatique']])
        res = c.post(self.FILIERES, {'file': fichier, 'dry_run': '1'}, format='multipart')

        assert res.data['lignes'][0]['statut'] == 'doublon'

    def test_validation_par_lignes_json(self, api, admin_user, structure):
        """Apres arbitrage, l'apercu renvoie des lignes avec un parent explicite."""
        from academic.models import Filiere

        c = auth_client(api, admin_user)
        res = c.post(self.FILIERES, {
            'rows': [{
                'ligne': 2,
                'valeurs': {'filiere': 'Filiere Arbitree'},
                'parent_id': structure['departement'].id,
            }],
        }, format='json')

        assert res.status_code == status.HTTP_200_OK
        assert res.data['created'] == 1
        creee = Filiere.objects.get(nom_filiere='Filiere Arbitree')
        assert creee.departement == structure['departement']

    def test_valeur_corrigee_prise_en_compte(self, api, admin_user, structure):
        """La valeur ecrite est celle de l'apercu, pas celle du fichier d'origine."""
        from academic.models import Filiere

        c = auth_client(api, admin_user)
        c.post(self.FILIERES, {
            'rows': [{
                'valeurs': {'filiere': 'Libelle Corrige'},
                'parent_id': structure['departement'].id,
            }],
        }, format='json')

        assert Filiere.objects.filter(nom_filiere='Libelle Corrige').exists()

    def test_creation_du_parent_sur_autorisation(self, api, admin_user, structure):
        from academic.models import Departement, Filiere

        c = auth_client(api, admin_user)
        res = c.post(self.FILIERES, {
            'rows': [{
                'valeurs': {'filiere': 'Filiere Neuve', 'departement': 'Departement Neuf'},
                'creer_parent': True,
            }],
        }, format='json')

        assert res.status_code == status.HTTP_200_OK
        assert Departement.objects.filter(nom_departement='Departement Neuf').exists()
        assert Filiere.objects.get(nom_filiere='Filiere Neuve').departement.nom_departement == 'Departement Neuf'

    def test_parent_absent_non_arbitre_n_ecrit_pas(self, api, admin_user, structure):
        from academic.models import Filiere

        c = auth_client(api, admin_user)
        res = c.post(self.FILIERES, {
            'rows': [{'valeurs': {'filiere': 'Orpheline', 'departement': 'Absent'}}],
        }, format='json')

        assert res.data['created'] == 0
        assert len(res.data['errors']) == 1
        assert not Filiere.objects.filter(nom_filiere='Orpheline').exists()

    def test_departements_rattaches_a_une_faculte(self, api, admin_user, structure):
        from academic.models import Departement

        c = auth_client(api, admin_user)
        res = c.post(self.DEPARTEMENTS, {
            'rows': [{
                'valeurs': {'departement': 'Mathematiques'},
                'parent_id': structure['faculte'].id,
            }],
        }, format='json')

        assert res.data['created'] == 1
        assert Departement.objects.get(nom_departement='Mathematiques').faculte == structure['faculte']

    def test_reserve_au_super_admin(self, api, chef_user, structure):
        c = auth_client(api, chef_user)
        res = c.post(self.FILIERES, {
            'rows': [{'valeurs': {'filiere': 'X'}, 'parent_id': structure['departement'].id}],
        }, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN
