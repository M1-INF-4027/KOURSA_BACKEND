from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Role
from .forms import UtilisateurCreationForm, UtilisateurChangeForm

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('nom_role',)

@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):

    add_form = UtilisateurCreationForm
    form = UtilisateurChangeForm

    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'statut')
    list_filter = ('is_staff', 'is_superuser', 'statut', 'roles')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    filter_horizontal = ('groups', 'user_permissions', 'roles')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations Personnelles', {'fields': ('first_name', 'last_name')}),
        ('Permissions & Statut', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'statut', 'groups', 'user_permissions'),
        }),
        ('Rôles et Affiliation Koursa', {'fields': ('roles', 'niveau_represente')}),
        ('Dates Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
        ('Rôles et Affiliation Koursa', {
            'classes': ('wide',),
            'fields': ('roles', 'niveau_represente', 'statut'),
        }),
    )

