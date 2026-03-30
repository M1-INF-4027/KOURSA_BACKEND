import pytest
from rest_framework.test import APIClient
from users.models import Utilisateur, Role, StatutCompte
from academic.models import Faculte, Departement, Filiere, Niveau, AnneeAcademique, Semestre, Salle
from teaching.models import UniteEnseignement
from datetime import date


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def roles(db):
    """Get or create the 4 base roles (may already exist from migrations)."""
    return {
        'admin': Role.objects.get_or_create(nom_role=Role.SUPER_ADMIN)[0],
        'chef': Role.objects.get_or_create(nom_role=Role.CHEF_DEPARTEMENT)[0],
        'enseignant': Role.objects.get_or_create(nom_role=Role.ENSEIGNANT)[0],
        'delegue': Role.objects.get_or_create(nom_role=Role.DELEGUE)[0],
    }


@pytest.fixture
def admin_user(roles):
    user = Utilisateur.objects.create_user(
        email='admin@test.cm', password='TestPass123!',
        first_name='Admin', last_name='Koursa',
        statut=StatutCompte.ACTIF, is_staff=True, is_superuser=True,
    )
    user.roles.add(roles['admin'])
    return user


@pytest.fixture
def structure(db):
    """Create a basic academic structure: Faculte > Departement > Filiere > Niveau."""
    fac = Faculte.objects.create(nom_faculte='Faculte des Sciences')
    dept = Departement.objects.create(nom_departement='Informatique', faculte=fac)
    filiere = Filiere.objects.create(nom_filiere='Informatique Fondamentale', departement=dept)
    niveaux = {}
    for name in ['L1', 'L2', 'L3', 'M1', 'M2']:
        niveaux[name] = Niveau.objects.create(nom_niveau=name, filiere=filiere)
    return {'faculte': fac, 'departement': dept, 'filiere': filiere, 'niveaux': niveaux}


@pytest.fixture
def annee_active(db):
    """Create an active academic year with 2 semesters."""
    annee = AnneeAcademique.objects.create(libelle='2025-2026', est_active=True, est_configuree=True)
    s1 = Semestre.objects.create(
        annee_academique=annee, numero=1, est_actif=True,
        date_debut=date(2025, 10, 1), date_fin=date(2026, 2, 28),
    )
    s2 = Semestre.objects.create(
        annee_academique=annee, numero=2, est_actif=False,
        date_debut=date(2026, 3, 1), date_fin=date(2026, 7, 31),
    )
    return {'annee': annee, 's1': s1, 's2': s2}


@pytest.fixture
def chef_user(roles, structure):
    """Create a chef de departement linked to the test department."""
    user = Utilisateur.objects.create_user(
        email='chef@test.cm', password='TestPass123!',
        first_name='Chef', last_name='Dept',
        statut=StatutCompte.ACTIF,
    )
    user.roles.add(roles['chef'])
    structure['departement'].chef_departement = user
    structure['departement'].save()
    return user


@pytest.fixture
def enseignant_user(roles):
    user = Utilisateur.objects.create_user(
        email='prof@test.cm', password='TestPass123!',
        first_name='Jean', last_name='ATSA',
        statut=StatutCompte.ACTIF,
    )
    user.roles.add(roles['enseignant'])
    return user


@pytest.fixture
def delegue_user(roles, structure):
    user = Utilisateur.objects.create_user(
        email='delegue@test.cm', password='TestPass123!',
        first_name='Paul', last_name='NDOM',
        statut=StatutCompte.ACTIF,
    )
    user.roles.add(roles['delegue'])
    user.niveau_represente = structure['niveaux']['L1']
    user.save()
    return user


@pytest.fixture
def ue(structure, annee_active, enseignant_user):
    """Create a test UE with enseignant and niveau."""
    ue = UniteEnseignement.objects.create(
        code_ue='INF111', libelle_ue='Algorithmique',
        semestre=1, semestre_obj=annee_active['s1'],
    )
    ue.enseignants.add(enseignant_user)
    ue.niveaux.add(structure['niveaux']['L1'])
    return ue


@pytest.fixture
def salle(db):
    return Salle.objects.create(nom_salle='A500')


def auth_client(api, user):
    """Helper: return an authenticated API client."""
    api.force_authenticate(user=user)
    return api
