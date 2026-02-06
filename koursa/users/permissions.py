from rest_framework.permissions import BasePermission
from .models import Role
from teaching.models import StatutFiche

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False
        return request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists()

class IsHoD(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False
        return request.user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()

class IsEnseignant(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False
        return request.user.roles.filter(
            nom_role__in=[Role.ENSEIGNANT, Role.CHEF_DEPARTEMENT]
        ).exists()

class IsDelegue(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
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
            hod = request.user
            departement_du_hod = hod.departement_gere
            
            if obj.roles.filter(nom_role__in=[Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]).exists():
                return False

            if obj.roles.filter(nom_role=Role.ENSEIGNANT).exists():
                return True 

            if obj.roles.filter(nom_role=Role.DELEGUE).exists():
                if obj.niveau_represente and obj.niveau_represente.filiere.departement == departement_du_hod:
                    return True
        
        return False


class IsDelegueAuteur(BasePermission):
    message = "Vous n'êtes pas l'auteur de cette fiche."

    def has_object_permission(self, request, view, obj):
        return obj.delegue == request.user