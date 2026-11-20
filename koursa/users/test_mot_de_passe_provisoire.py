"""
Un mot de passe provisoire ne donne acces a rien d'autre qu'a son changement.

Les comptes crees par import ont leur propre adresse email pour mot de passe.
Le drapeau `doit_changer_mot_de_passe` n'etait lu que par les interfaces :
l'API repondait normalement, si bien qu'un appel direct avec l'adresse connue
d'un enseignant suffisait a agir en son nom.
"""
import pytest
from rest_framework import status

from conftest import auth_client
from users.models import Role, StatutCompte, Utilisateur


def client_avec_jeton(api, utilisateur, mot_de_passe):
    """
    Client authentifie par un vrai jeton, comme le ferait un appelant reel.

    `force_authenticate` de DRF pose directement request.user et court-circuite
    les classes d'authentification : il ne peut donc pas servir a verifier ce
    qui se joue a ce niveau-la.
    """
    reponse = api.post('/api/auth/token/', {
        'email': utilisateur.email, 'password': mot_de_passe,
    }, format='json')
    assert reponse.status_code == status.HTTP_200_OK, reponse.data
    api.credentials(HTTP_AUTHORIZATION='Bearer %s' % reponse.data['access'])
    return api


@pytest.fixture
def enseignant_importe(roles):
    """Compte tel que l'import le cree : actif, mot de passe = son email."""
    utilisateur = Utilisateur.objects.create_user(
        email='importe@facsciences.cm', password='importe@facsciences.cm',
        first_name='Ima', last_name='Porte', statut=StatutCompte.ACTIF,
    )
    utilisateur.doit_changer_mot_de_passe = True
    utilisateur.save()
    utilisateur.roles.add(Role.objects.get(nom_role=Role.ENSEIGNANT))
    return utilisateur


class TestMotDePasseProvisoire:

    def test_la_connexion_reste_possible(self, api, enseignant_importe):
        # Se connecter doit marcher : c'est par la que l'enseignant arrive sur
        # l'ecran de changement.
        res = api.post('/api/auth/token/', {
            'email': enseignant_importe.email,
            'password': enseignant_importe.email,
        }, format='json')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['user']['doit_changer_mot_de_passe'] is True

    def test_aucun_acces_aux_donnees_avant_le_changement(self, api, enseignant_importe):
        client = client_avec_jeton(api, enseignant_importe, enseignant_importe.email)
        res = client.get('/api/teaching/fiches-suivi/')
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_aucune_validation_de_fiche_avant_le_changement(
        self, api, enseignant_importe, ue, annee_active
    ):
        client = client_avec_jeton(api, enseignant_importe, enseignant_importe.email)
        res = client.post('/api/teaching/fiches-suivi/1/valider/', {}, format='json')
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_le_profil_reste_lisible(self, api, enseignant_importe):
        # L'interface a besoin de savoir pourquoi elle est bloquee.
        client = client_avec_jeton(api, enseignant_importe, enseignant_importe.email)
        res = client.get('/api/users/utilisateurs/me/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['doit_changer_mot_de_passe'] is True

    def test_le_changement_de_mot_de_passe_reste_ouvert_et_libere(
        self, api, enseignant_importe
    ):
        client = client_avec_jeton(api, enseignant_importe, enseignant_importe.email)
        res = client.post('/api/users/utilisateurs/change-password/', {
            'old_password': enseignant_importe.email,
            'new_password': 'UnMotDePasseSolide1',
        }, format='json')
        assert res.status_code == status.HTTP_200_OK

        enseignant_importe.refresh_from_db()
        assert enseignant_importe.doit_changer_mot_de_passe is False

        # Une fois le mot de passe change, le compte retrouve ses acces.
        client = client_avec_jeton(api, enseignant_importe, 'UnMotDePasseSolide1')
        res = client.get('/api/teaching/fiches-suivi/')
        assert res.status_code == status.HTTP_200_OK

    def test_un_compte_ordinaire_n_est_pas_gene(self, api, enseignant_user):
        res = auth_client(api, enseignant_user).get('/api/teaching/fiches-suivi/')
        assert res.status_code == status.HTTP_200_OK
