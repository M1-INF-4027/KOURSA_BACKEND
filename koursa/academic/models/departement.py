from django.db import models
from .niveau import Niveau
from users.models.utilisateur import Utilisateur

class Departement(models.Model):
    nom_departement = models.CharField(max_length=100)

    niveau = models.ForeignKey( Niveau, on_delete=models.CASCADE)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
