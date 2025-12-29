from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('nom_role',)

@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'statut')
    list_filter = ('is_staff', 'is_superuser', 'groups', 'statut')
    
    search_fields = ('email', 'first_name', 'last_name')
    
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Koursa Roles & Status', {'fields': ('roles', 'statut', 'niveau_represente')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    filter_horizontal = ('groups', 'user_permissions', 'roles')