from django.db import models
from .faculte import Faculte

class Departement(models.Model):
    nom_departement = models.CharField(max_length=100, verbose_name="Nom du Département")
    
    faculte = models.ForeignKey(
        Faculte, 
        on_delete=models.CASCADE, 
        related_name='departements',
        verbose_name="Faculté de rattachement"
    )

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        unique_together = ('nom_departement', 'faculte')

    def __str__(self):
        return f"{self.nom_departement}"