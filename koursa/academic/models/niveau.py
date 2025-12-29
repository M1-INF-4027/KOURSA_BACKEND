from django.db import models
from .enum import EnumNiveau
from .departement import Departement

class Niveau(models.Model):
    nom_niveau = models.CharField(
        max_length=10,
        choices=EnumNiveau.choices,
        verbose_name="Nom du Niveau"
    )
    
    departement = models.ForeignKey(
        Departement, 
        on_delete=models.CASCADE, 
        related_name='niveaux',
        verbose_name="Département de rattachement"
    )

    class Meta:
        verbose_name = "Niveau"
        verbose_name_plural = "Niveaux"
        unique_together = ('nom_niveau', 'departement')

    def __str__(self):
        return f"{self.get_nom_niveau_display()} - {self.departement.nom_departement}"