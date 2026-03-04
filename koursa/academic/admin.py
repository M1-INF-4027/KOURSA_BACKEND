from django.contrib import admin
from .models import Faculte, Departement, Filiere, Niveau, AnneeAcademique, Semestre, HistoriqueChefDepartement, Salle

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


class SemestreInline(admin.TabularInline):
    model = Semestre
    extra = 0
    max_num = 2


@admin.register(AnneeAcademique)
class AnneeAcademiqueAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'est_active', 'est_configuree', 'date_creation')
    list_filter = ('est_active', 'est_configuree')
    search_fields = ('libelle',)
    inlines = [SemestreInline]


@admin.register(Semestre)
class SemestreAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'date_debut', 'date_fin', 'est_actif')
    list_filter = ('annee_academique', 'est_actif')


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ('nom_salle', 'batiment', 'capacite', 'est_active')
    search_fields = ('nom_salle', 'batiment')
    list_filter = ('est_active', 'batiment')


@admin.register(HistoriqueChefDepartement)
class HistoriqueChefAdmin(admin.ModelAdmin):
    list_display = ('departement', 'utilisateur', 'annee_academique', 'date_debut', 'date_fin')
    list_filter = ('annee_academique', 'departement')