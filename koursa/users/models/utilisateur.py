from django.db import models

from users.models.enum import StatutCompte


class Utilisateur(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)

    statutCompte = models.CharField(
        max_length=20,
        choices=StatutCompte.choices,
        default=StatutCompte.ACTIF
    )


    def __str__(self):
        return f"{self.prenom} {self.nom}"