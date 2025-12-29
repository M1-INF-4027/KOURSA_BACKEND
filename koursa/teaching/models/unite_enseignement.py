from django.db import models
from .fiche_suivi import FicheSuivi

class UniteEnseignement(models.Model):
    code_ue = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=100)
    semestre = models.CharField(max_length=20)
    fiche = models.ForeignKey(FicheSuivi, on_delete=models.SET_NULL, null=True)
