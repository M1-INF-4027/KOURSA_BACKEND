from django.db import models
from .faculte import Faculte
from django.conf import settings

class Departement(models.Model):
    nom_departement = models.CharField(
        max_length=100, 
        verbose_name="Nom du Département"
    )
    
    faculte = models.ForeignKey(
        Faculte, 
        on_delete=models.CASCADE, 
        related_name='departements'
    )

    chef_departement = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,                 
        blank=True,
        related_name='departement_gere'
    )

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        unique_together = ('nom_departement', 'faculte')
        ordering = ['nom_departement']

    def __str__(self):
        return f"{self.nom_departement}"