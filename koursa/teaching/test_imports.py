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
