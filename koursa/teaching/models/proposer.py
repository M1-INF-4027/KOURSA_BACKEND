from django.db import models
from academic.models.niveau import Niveau
from .unite_enseignement import UniteEnseignement

class Proposer(models.Model):
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE)
    ue = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE)
