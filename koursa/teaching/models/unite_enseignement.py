from django.db import models
from academic.models.niveau import Niveau
from users.models.utilisateur import Utilisateur

class UniteEnseignement(models.Model):
    code_ue = models.CharField(max_length=20, unique=True, verbose_name="Code de l'UE")
    libelle_ue = models.CharField(max_length=255, verbose_name="Libellé de l'UE")
    semestre = models.PositiveSmallIntegerField(verbose_name="Semestre")

    
    enseignants = models.ManyToManyField(
        Utilisateur,
        related_name='ues_enseignees',
        limit_choices_to={'roles__nom_role': 'Enseignant'},
        verbose_name="Enseignants"
    )

    niveaux = models.ManyToManyField(
        Niveau,
        related_name='ues_proposees',
        verbose_name="Niveaux concernés"
    )

    class Meta:
        verbose_name = "Unité d'Enseignement"
        verbose_name_plural = "Unités d'Enseignement"
        ordering = ['code_ue']

    def __str__(self):
        return f"{self.code_ue} - {self.libelle_ue}"