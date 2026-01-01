from django.db import models

class Role(models.Model):
    SUPER_ADMIN = 'Super Administrateur'
    CHEF_DEPARTEMENT = 'Chef de Département'
    ENSEIGNANT = 'Enseignant'
    DELEGUE = 'Délégué'

    ROLE_CHOICES = [
        (SUPER_ADMIN, SUPER_ADMIN),
        (CHEF_DEPARTEMENT, CHEF_DEPARTEMENT),
        (ENSEIGNANT, ENSEIGNANT),
        (DELEGUE, DELEGUE),
    ]

    nom_role = models.CharField(
        max_length=50,
        unique=True,
        choices=ROLE_CHOICES,
        verbose_name="Nom du Rôle"
    )

    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"

    def __str__(self):
        return self.nom_role