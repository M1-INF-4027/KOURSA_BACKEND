from django.db import models
from .filiere import Filiere

class Niveau(models.Model):
    nom_niveau = models.CharField(
        max_length=50,
        verbose_name="Nom du Niveau"
    )

    filiere = models.ForeignKey(
        Filiere, 
        on_delete=models.CASCADE, 
        related_name='niveaux'
    )

    class Meta:
        verbose_name = "Niveau"
        verbose_name_plural = "Niveaux"
        unique_together = ('nom_niveau', 'filiere')
        ordering = ['nom_niveau']

    def __str__(self):
        return f"{self.nom_niveau} - {self.filiere.nom_filiere}"