from django.db import models


class Salle(models.Model):
    nom_salle = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom de la salle"
    )
    capacite = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Capacite"
    )
    batiment = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Batiment"
    )
    est_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )

    class Meta:
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ['nom_salle']

    def __str__(self):
        return self.nom_salle
