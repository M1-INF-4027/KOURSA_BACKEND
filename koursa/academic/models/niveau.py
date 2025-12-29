from django.db import models

from academic.models.enum import EnumNiveau
from users.models.utilisateur import Utilisateur

class Niveau(models.Model):
    nom_niveau = models.CharField(
        max_length=10,
        choices=EnumNiveau.choices,
        null=False,
    )

    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
