"""
Tests P0 — Authentication & User Management
"""
import pytest
from rest_framework import status
from users.models import Utilisateur, Role, StatutCompte, EmailWhitelist
from conftest import auth_client


# ═══════════════════════════════════════════════════════
#  AUTH : Login / Token
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAuth:

    def test_login_success(self, api, admin_user):
        res = api.post('/api/auth/token/', {'email': 'admin@test.cm', 'password': 'TestPass123!'})
        assert res.status_code == status.HTTP_200_OK
        assert 'access' in res.data
        assert 'refresh' in res.data

    def test_login_wrong_password(self, api, admin_user):
        res = api.post('/api/auth/token/', {'email': 'admin@test.cm', 'password': 'wrong'})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, api):
        res = api.post('/api/auth/token/', {'email': 'nope@test.cm', 'password': 'x'})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api, admin_user):
        login = api.post('/api/auth/token/', {'email': 'admin@test.cm', 'password': 'TestPass123!'})
        refresh = login.data['refresh']
        res = api.post('/api/auth/token/refresh/', {'refresh': refresh})
        assert res.status_code == status.HTTP_200_OK
        assert 'access' in res.data

    def test_protected_endpoint_without_token(self, api):
        res = api.get('/api/users/utilisateurs/')
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════
#  INSCRIPTION : Registration
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRegistration:

    def test_register_enseignant(self, api, roles):
        res = api.post('/api/users/utilisateurs/', {
            'email': 'new.prof@test.cm',
            'password': 'SecurePass123!',
            'first_name': 'Nouveau',
            'last_name': 'Prof',
            'roles_ids': [roles['enseignant'].id],
        })
        assert res.status_code == status.HTTP_201_CREATED
        user = Utilisateur.objects.get(email='new.prof@test.cm')
        assert user.statut == StatutCompte.EN_ATTENTE

    def test_register_duplicate_email(self, api, roles, admin_user):
        res = api.post('/api/users/utilisateurs/', {
            'email': 'admin@test.cm',
            'password': 'SecurePass123!',
            'first_name': 'Dup',
            'last_name': 'User',
            'roles_ids': [roles['enseignant'].id],
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_auto_activation_via_whitelist(self, api, roles, structure, admin_user):
        EmailWhitelist.objects.create(
            email='whitelisted@test.cm',
            role_type='ENSEIGNANT',
            departement=structure['departement'],
            ajoute_par=admin_user,
        )
        res = api.post('/api/users/utilisateurs/', {
            'email': 'whitelisted@test.cm',
            'password': 'SecurePass123!',
            'first_name': 'White',
            'last_name': 'Listed',
            'roles_ids': [roles['enseignant'].id],
        })
        assert res.status_code == status.HTTP_201_CREATED
        user = Utilisateur.objects.get(email='whitelisted@test.cm')
        assert user.statut == StatutCompte.ACTIF


# ═══════════════════════════════════════════════════════
#  PERMISSIONS : Role-based access
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPermissions:

    def test_admin_can_list_users(self, api, admin_user):
        c = auth_client(api, admin_user)
        res = c.get('/api/users/utilisateurs/')
        assert res.status_code == status.HTTP_200_OK

    def test_enseignant_cannot_create_salle(self, api, enseignant_user):
        c = auth_client(api, enseignant_user)
        res = c.post('/api/academic/salles/', {'nom_salle': 'Hack'})
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_create_salle(self, api, admin_user):
        c = auth_client(api, admin_user)
        res = c.post('/api/academic/salles/', {'nom_salle': 'NewRoom'})
        assert res.status_code == status.HTTP_201_CREATED

    def test_chef_can_list_users(self, api, chef_user, structure):
        c = auth_client(api, chef_user)
        res = c.get('/api/users/utilisateurs/')
        assert res.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════
#  WHITELIST : Bulk import
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWhitelist:

    def test_bulk_create_whitelist(self, api, admin_user, structure):
        c = auth_client(api, admin_user)
        res = c.post('/api/users/whitelist/bulk/', {
            'emails': ['prof1@test.cm', 'prof2@test.cm'],
            'role_type': 'ENSEIGNANT',
            'departement': structure['departement'].id,
        }, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        assert len(res.data['created']) == 2
        assert EmailWhitelist.objects.count() == 2

    def test_bulk_create_skip_duplicates(self, api, admin_user, structure):
        c = auth_client(api, admin_user)
        EmailWhitelist.objects.create(
            email='existing@test.cm', role_type='ENSEIGNANT',
            departement=structure['departement'], ajoute_par=admin_user,
        )
        res = c.post('/api/users/whitelist/bulk/', {
            'emails': ['existing@test.cm', 'new@test.cm'],
            'role_type': 'ENSEIGNANT',
            'departement': structure['departement'].id,
        }, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        assert len(res.data['created']) == 1
        assert len(res.data['skipped']) == 1

    def test_enseignant_cannot_manage_whitelist(self, api, enseignant_user, structure):
        c = auth_client(api, enseignant_user)
        res = c.post('/api/users/whitelist/bulk/', {
            'emails': ['hack@test.cm'],
            'role_type': 'ENSEIGNANT',
            'departement': structure['departement'].id,
        }, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUserManagement:

    def test_admin_can_get_me(self, api, admin_user):
        c = auth_client(api, admin_user)
        res = c.get('/api/users/utilisateurs/me/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['email'] == 'admin@test.cm'

    def test_admin_can_update_user_status(self, api, admin_user, enseignant_user):
        c = auth_client(api, admin_user)
        res = c.patch(f'/api/users/utilisateurs/{enseignant_user.id}/', {
            'statut': 'ACTIF',
        }, format='json')
        assert res.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════
#  RESET DATABASE
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestResetDatabase:

    def test_reset_requires_password(self, api, admin_user):
        c = auth_client(api, admin_user)
        res = c.post('/api/users/utilisateurs/reset-database/', {})
        assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_reset_wrong_password(self, api, admin_user):
        c = auth_client(api, admin_user)
        res = c.post('/api/users/utilisateurs/reset-database/', {'password': 'wrong'})
        assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]

    def test_enseignant_cannot_reset(self, api, enseignant_user):
        c = auth_client(api, enseignant_user)
        res = c.post('/api/users/utilisateurs/reset-database/', {'password': 'TestPass123!'})
        assert res.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════
#  Detail d'un delegue et d'un enseignant
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDetailUtilisateur:
    """Un chef examinant une demande doit savoir de quelle classe releve le delegue."""

    def test_classe_du_delegue_exposee(self, api, admin_user, delegue_user, structure):
        from conftest import auth_client

        c = auth_client(api, admin_user)
        res = c.get(f'/api/users/utilisateurs/{delegue_user.id}/')

        assert res.status_code == 200
        classe = res.data['classe']
        assert classe is not None, "le delegue doit porter sa classe"
        assert classe['niveau'] == delegue_user.niveau_represente.nom_niveau
        assert classe['filiere'] == structure['filiere'].nom_filiere
        assert classe['departement'] == structure['departement'].nom_departement
        assert '>' in classe['libelle']

    def test_classe_absente_pour_les_autres_roles(self, api, admin_user, enseignant_user):
        from conftest import auth_client

        c = auth_client(api, admin_user)
        res = c.get(f'/api/users/utilisateurs/{enseignant_user.id}/')
        assert res.data['classe'] is None

    def test_enseignements_exposes(self, api, admin_user, enseignant_user, annee_active, structure):
        from conftest import auth_client
        from teaching.models import UniteEnseignement

        ue = UniteEnseignement.objects.create(
            code_ue='INF3111', libelle_ue='Compilation',
            semestre=1, semestre_obj=annee_active['s1'],
        )
        ue.enseignants.add(enseignant_user)
        ue.niveaux.add(structure['niveaux']['L3'])

        c = auth_client(api, admin_user)
        res = c.get(f'/api/users/utilisateurs/{enseignant_user.id}/')

        ens = res.data['enseignements']
        assert ens['nombre_ues'] == 1
        assert ens['ues'][0]['code'] == 'INF3111'
        assert ens['niveaux'] == ['L3']

    def test_chef_peut_changer_la_classe_de_son_delegue(
        self, api, chef_user, delegue_user, structure
    ):
        from conftest import auth_client

        cible = structure['niveaux']['M1']
        c = auth_client(api, chef_user)
        res = c.patch(
            f'/api/users/utilisateurs/{delegue_user.id}/',
            {'niveau_represente': cible.id}, format='json',
        )

        assert res.status_code == 200, res.data
        delegue_user.refresh_from_db()
        assert delegue_user.niveau_represente == cible
        assert res.data['classe']['niveau'] == 'M1'
