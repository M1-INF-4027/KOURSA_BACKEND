from rest_framework.permissions import BasePermission
from .models import Role, StatutCompte
from teaching.models import StatutFiche


def compte_habilite(requete):
    """
    Le compte est-il en mesure d'exercer un role ?

    Les permissions testaient `is_active`, le champ herite de Django, qui vaut
    vrai des la creation et que rien ne relie au circuit d'approbation. Un
    compte EN_ATTENTE franchissait donc toutes les permissions privilegiees :
    l'approbation par le chef n'avait d'effet que sur l'affichage.

    C'est `statut` qui porte cette decision, et c'est lui qu'on lit ici.
    """
    utilisateur = getattr(requete, 'user', None)
    if not utilisateur or not utilisateur.is_authenticated or not utilisateur.is_active:
        return False
    return utilisateur.statut == StatutCompte.ACTIF

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not compte_habilite(request):
            return False
        return request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists()

class IsHoD(BasePermission):
    def has_permission(self, request, view):
        if not compte_habilite(request):
            return False
        return request.user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()

class IsHoDOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not compte_habilite(request):
            return False
        return request.user.roles.filter(
            nom_role__in=[Role.CHEF_DEPARTEMENT, Role.SUPER_ADMIN]
        ).exists()

class IsEnseignant(BasePermission):
    def has_permission(self, request, view):
        if not compte_habilite(request):
            return False
        return request.user.roles.filter(
            nom_role__in=[Role.ENSEIGNANT, Role.CHEF_DEPARTEMENT]
        ).exists()

class IsDelegue(BasePermission):
    def has_permission(self, request, view):
        if not compte_habilite(request):
            return False
        return request.user.roles.filter(nom_role=Role.DELEGUE).exists()
    

class IsEnseignantConcerne(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.enseignant == request.user
    
class IsFicheModifiable(BasePermission):
    message = "Cette fiche a déjà été validée et ne peut plus être modifiée ou supprimée."

    def has_object_permission(self, request, view, obj):
        if not hasattr(obj, 'statut'):
            return True 

        return obj.statut != StatutFiche.VALIDEE
    
class IsAdminOrIsSelf(BasePermission):

    def has_permission(self, request, view):
        # Permettre l'inscription sans authentification
        if view.action == 'create':
            return True

        if view.action == 'list':
            return request.user.is_authenticated

        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        
        if obj == request.user:
            return True

        if request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists():
            return True

        if request.user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists():
            if not hasattr(request.user, 'departement_gere') or not request.user.departement_gere:
                return False

            departement_du_hod = request.user.departement_gere

            if obj.roles.filter(nom_role__in=[Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]).exists():
                return False

            if obj.roles.filter(nom_role=Role.ENSEIGNANT).exists():
                # Verifier que l'enseignant enseigne dans le departement du chef
                from teaching.models import UniteEnseignement
                enseigne_dans_dept = UniteEnseignement.objects.filter(
                    enseignants=obj,
                    niveaux__filiere__departement=departement_du_hod
                ).exists()
                return enseigne_dans_dept

            if obj.roles.filter(nom_role=Role.DELEGUE).exists():
                if obj.niveau_represente and obj.niveau_represente.filiere.departement == departement_du_hod:
                    return True
        
        return False


class IsDelegueAuteur(BasePermission):
    message = "Vous n'êtes pas l'auteur de cette fiche."

    def has_object_permission(self, request, view, obj):
        return obj.delegue == request.user