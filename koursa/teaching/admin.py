from django.contrib import admin
from .models import UniteEnseignement, FicheSuivi

@admin.register(UniteEnseignement)
class UniteEnseignementAdmin(admin.ModelAdmin):
    list_display = ('code_ue', 'libelle_ue', 'semestre')
    search_fields = ('code_ue', 'libelle_ue')
    filter_horizontal = ('enseignants', 'niveaux')

@admin.register(FicheSuivi)
class FicheSuiviAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'enseignant', 'delegue', 'statut', 'date_cours')
    list_filter = ('statut', 'date_cours', 'enseignant', 'ue')
    search_fields = ('ue__code_ue', 'ue__libelle_ue', 'titre_chapitre')
    autocomplete_fields = ['ue', 'delegue', 'enseignant']
    readonly_fields = ('duree', 'date_soumission', 'date_validation')