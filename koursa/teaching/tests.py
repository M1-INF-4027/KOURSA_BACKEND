"""
Tests P0 — Fiche de Suivi Workflow & UE Management
"""
import pytest
from datetime import date, timedelta
from rest_framework import status
from teaching.models import FicheSuivi, StatutFiche, UniteEnseignement
from conftest import auth_client

TODAY = date.today().isoformat()


# ═══════════════════════════════════════════════════════
#  UE : CRUD
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUE:

    def test_create_ue(self, api, admin_user, annee_active, structure):
        c = auth_client(api, admin_user)
        res = c.post('/api/teaching/unites-enseignement/', {
            'code_ue': 'INF222',
            'libelle_ue': 'Structures de donnees',
            'semestre': 1,
            'semestre_obj': annee_active['s1'].id,
            'niveaux': [structure['niveaux']['L2'].id],
        }, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        assert UniteEnseignement.objects.filter(code_ue='INF222').exists()

    def test_ue_code_uppercase(self, api, admin_user, annee_active):
        c = auth_client(api, admin_user)
        res = c.post('/api/teaching/unites-enseignement/', {
            'code_ue': 'inf333',
            'libelle_ue': 'Test lowercase',
            'semestre': 1,
            'semestre_obj': annee_active['s1'].id,
        }, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data['code_ue'] == 'INF333'

    def test_duplicate_ue_same_semestre(self, api, admin_user, ue, annee_active):
        c = auth_client(api, admin_user)
        res = c.post('/api/teaching/unites-enseignement/', {
            'code_ue': 'INF111',
            'libelle_ue': 'Duplicate',
            'semestre': 1,
            'semestre_obj': annee_active['s1'].id,
        }, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_enseignant_sees_own_ues(self, api, enseignant_user, ue, annee_active):
        c = auth_client(api, enseignant_user)
        res = c.get('/api/teaching/unites-enseignement/')
        assert res.status_code == status.HTTP_200_OK
        codes = [u['code_ue'] for u in res.data]
        assert 'INF111' in codes

    def test_delegue_sees_own_niveau_ues(self, api, delegue_user, ue, annee_active):
        c = auth_client(api, delegue_user)
        res = c.get('/api/teaching/unites-enseignement/')
        assert res.status_code == status.HTTP_200_OK
        codes = [u['code_ue'] for u in res.data]
        assert 'INF111' in codes


# ═══════════════════════════════════════════════════════
#  FICHE DE SUIVI : Full Workflow
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFicheWorkflow:
    """Test the complete lifecycle: Create → Submit → Validate/Refuse → Resubmit"""

    @pytest.fixture
    def fiche_data(self, ue, enseignant_user, salle):
        return {
            'ue': ue.id,
            'enseignant': enseignant_user.id,
            'date_cours': TODAY,
            'heure_debut': '08:00',
            'heure_fin': '10:00',
            'type_seance': 'CM',
            'titre_chapitre': 'Introduction aux algorithmes',
            'contenu_aborde': 'Tri par selection, tri par insertion',
            'salle': salle.id,
        }

    def test_delegue_creates_fiche(self, api, delegue_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        assert res.status_code == status.HTTP_201_CREATED, f"Expected 201, got {res.status_code}: {res.data}"
        assert res.data['statut'] == 'SOUMISE'
        assert res.data['delegue'] == delegue_user.id

    def test_enseignant_validates_fiche(self, api, delegue_user, enseignant_user, annee_active, fiche_data):
        """L'enseignant concerne (pas le chef) valide la fiche."""
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        assert create_res.status_code == status.HTTP_201_CREATED
        fiche_id = create_res.data['id']

        # Enseignant validates (IsEnseignantConcerne permission)
        c = auth_client(api, enseignant_user)
        res = c.post(f'/api/teaching/fiches-suivi/{fiche_id}/valider/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['statut'] == 'VALIDEE'

        fiche = FicheSuivi.objects.get(id=fiche_id)
        assert fiche.statut == StatutFiche.VALIDEE
        assert fiche.date_validation is not None

    def test_enseignant_refuses_fiche_with_reason(self, api, delegue_user, enseignant_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        fiche_id = create_res.data['id']

        c = auth_client(api, enseignant_user)
        res = c.post(f'/api/teaching/fiches-suivi/{fiche_id}/refuser/', {
            'motif_refus': 'Contenu incomplet, veuillez detailler le chapitre.',
        })
        assert res.status_code == status.HTTP_200_OK
        assert res.data['statut'] == 'REFUSEE'

        fiche = FicheSuivi.objects.get(id=fiche_id)
        assert fiche.motif_refus == 'Contenu incomplet, veuillez detailler le chapitre.'

    def test_refuse_without_reason_fails(self, api, delegue_user, enseignant_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        fiche_id = create_res.data['id']

        c = auth_client(api, enseignant_user)
        res = c.post(f'/api/teaching/fiches-suivi/{fiche_id}/refuser/', {})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_delegue_resubmits_refused_fiche(self, api, delegue_user, enseignant_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        fiche_id = create_res.data['id']

        # Enseignant refuses
        c = auth_client(api, enseignant_user)
        c.post(f'/api/teaching/fiches-suivi/{fiche_id}/refuser/', {'motif_refus': 'Incomplet'})

        # Delegue edits and resubmits
        c = auth_client(api, delegue_user)
        res = c.patch(f'/api/teaching/fiches-suivi/{fiche_id}/', {
            'contenu_aborde': 'Tri par selection, tri par insertion, complexite O(n^2)',
        }, format='json')
        assert res.status_code == status.HTTP_200_OK

        res = c.post(f'/api/teaching/fiches-suivi/{fiche_id}/resoumettre/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['statut'] == 'SOUMISE'

    def test_cannot_validate_already_validated(self, api, delegue_user, enseignant_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        fiche_id = create_res.data['id']

        c = auth_client(api, enseignant_user)
        c.post(f'/api/teaching/fiches-suivi/{fiche_id}/valider/')
        res = c.post(f'/api/teaching/fiches-suivi/{fiche_id}/valider/')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_edit_validated_fiche(self, api, delegue_user, enseignant_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        fiche_id = create_res.data['id']

        c = auth_client(api, enseignant_user)
        c.post(f'/api/teaching/fiches-suivi/{fiche_id}/valider/')

        c = auth_client(api, delegue_user)
        res = c.patch(f'/api/teaching/fiches-suivi/{fiche_id}/', {
            'contenu_aborde': 'Hack',
        }, format='json')
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_chef_cannot_validate_not_his_enseignant(self, api, delegue_user, chef_user, annee_active, fiche_data, structure):
        """Le chef ne peut pas valider car IsEnseignantConcerne verifie enseignant==user."""
        c = auth_client(api, delegue_user)
        create_res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        fiche_id = create_res.data['id']

        c = auth_client(api, chef_user)
        res = c.post(f'/api/teaching/fiches-suivi/{fiche_id}/valider/')
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_enseignant_cannot_create_fiche(self, api, enseignant_user, annee_active, fiche_data):
        c = auth_client(api, enseignant_user)
        res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        # Enseignant alone should not be able to create fiches
        assert res.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST]

    def test_heure_fin_before_debut_fails(self, api, delegue_user, annee_active, fiche_data):
        c = auth_client(api, delegue_user)
        fiche_data['heure_debut'] = '14:00'
        fiche_data['heure_fin'] = '10:00'
        res = c.post('/api/teaching/fiches-suivi/', fiche_data, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════
#  FICHE : Visibility per role
# ═══════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFicheVisibility:

    def test_delegue_sees_own_fiches(self, api, delegue_user, enseignant_user, ue, salle, annee_active):
        c = auth_client(api, delegue_user)
        c.post('/api/teaching/fiches-suivi/', {
            'ue': ue.id, 'enseignant': enseignant_user.id,
            'date_cours': TODAY, 'heure_debut': '08:00', 'heure_fin': '10:00',
            'type_seance': 'CM', 'titre_chapitre': 'Ch1', 'contenu_aborde': 'Intro',
            'salle': salle.id,
        }, format='json')
        res = c.get('/api/teaching/fiches-suivi/')
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) >= 1

    def test_enseignant_sees_fiches_for_own_ues(self, api, delegue_user, enseignant_user, ue, salle, annee_active):
        # Delegue creates
        c = auth_client(api, delegue_user)
        c.post('/api/teaching/fiches-suivi/', {
            'ue': ue.id, 'enseignant': enseignant_user.id,
            'date_cours': TODAY, 'heure_debut': '08:00', 'heure_fin': '10:00',
            'type_seance': 'TD', 'titre_chapitre': 'Ch2', 'contenu_aborde': 'Suite',
            'salle': salle.id,
        }, format='json')

        # Enseignant lists
        c = auth_client(api, enseignant_user)
        res = c.get('/api/teaching/fiches-suivi/')
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) >= 1

    def test_admin_sees_all_fiches(self, api, admin_user, delegue_user, enseignant_user, ue, salle, annee_active):
        c = auth_client(api, delegue_user)
        c.post('/api/teaching/fiches-suivi/', {
            'ue': ue.id, 'enseignant': enseignant_user.id,
            'date_cours': TODAY, 'heure_debut': '08:00', 'heure_fin': '10:00',
            'type_seance': 'TP', 'titre_chapitre': 'TP1', 'contenu_aborde': 'Pratique',
            'salle': salle.id,
        }, format='json')

        c = auth_client(api, admin_user)
        res = c.get('/api/teaching/fiches-suivi/')
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) >= 1
