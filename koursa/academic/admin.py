from django.contrib import admin
from .models import Faculte, Departement, Filiere, Niveau

@admin.register(Faculte)
class FaculteAdmin(admin.ModelAdmin):
    list_display = ('nom_faculte',)
    search_fields = ('nom_faculte',)

@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ('nom_departement', 'faculte', 'chef_departement')
    list_filter = ('faculte',)
    search_fields = ('nom_departement',)
    autocomplete_fields = ['faculte', 'chef_departement']

@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = ('nom_filiere', 'departement')
    list_filter = ('departement__faculte', 'departement')
    search_fields = ('nom_filiere',)
    autocomplete_fields = ['departement']

@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'filiere')
    list_filter = ('filiere__departement', 'filiere')
    search_fields = ('nom_niveau',)
    autocomplete_fields = ['filiere']