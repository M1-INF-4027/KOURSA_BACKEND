from django.db import models
from .departement import Departement

class Filiere(models.Model):
    nom_filiere = models.CharField(max_length=150, verbose_name="Nom de la Filière")
    
    departement = models.ForeignKey(
        Departement, 
        on_delete=models.CASCADE, 
        related_name='filieres'
    )

    class Meta:
        verbose_name = "Filière"
        verbose_name_plural = "Filières"
        unique_together = ('nom_filiere', 'departement')
        ordering = ['nom_filiere']