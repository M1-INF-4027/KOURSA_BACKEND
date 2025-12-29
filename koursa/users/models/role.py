from django.db import models
from users.models.enum import Role

class Role(models.Model):
    nom_role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DELEGUE,
    )

    def __str__(self):
        return self.nom_role
