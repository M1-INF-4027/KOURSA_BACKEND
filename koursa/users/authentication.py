"""
Authentification JWT, avec l'obligation de changer un mot de passe provisoire.

Les comptes enseignants crees par import recoivent leur propre adresse email
comme mot de passe, et `doit_changer_mot_de_passe` est pose a vrai. Ce drapeau
n'etait lu que par les interfaces, qui redirigeaient vers l'ecran de
changement : l'API, elle, repondait normalement. Il suffisait donc d'appeler
l'API directement, avec l'adresse connue d'un enseignant pour mot de passe,
pour agir en son nom — valider ses fiches, lire ses delegues, exporter ses
rapports.

Le drapeau est desormais applique ici, c'est-a-dire une fois pour toutes les
vues, plutot qu'endpoint par endpoint.
"""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

# Seuls chemins praticables tant que le mot de passe provisoire n'a pas change.
# Le profil reste lisible : c'est lui qui dit a l'interface pourquoi elle est
# bloquee, et le changement de mot de passe est la seule sortie.
CHEMINS_AUTORISES = (
    '/api/users/utilisateurs/change-password/',
    '/api/users/utilisateurs/me/',
)


class JWTAvecMotDePasseAJour(JWTAuthentication):

    def authenticate(self, request):
        resultat = super().authenticate(request)
        if resultat is None:
            return None

        utilisateur, jeton = resultat
        if not getattr(utilisateur, 'doit_changer_mot_de_passe', False):
            return resultat

        chemin = request.path
        if any(chemin.startswith(autorise) for autorise in CHEMINS_AUTORISES):
            return resultat

        raise AuthenticationFailed(
            "Votre mot de passe provisoire doit etre change avant toute autre "
            "action.",
            code='mot_de_passe_provisoire',
        )
