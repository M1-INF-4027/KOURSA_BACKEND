from django.db import models
from users.models.utilisateur import Utilisateur
from .unite_enseignement import UniteEnseignement

class Dispenser(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    ue = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE)
