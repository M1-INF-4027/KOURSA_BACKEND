from django.db import models
from .utilisateur import Utilisateur
from .role import Role

class Attribuer(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)