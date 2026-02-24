from django.db import models
from django.conf import settings

class UniteEnseignement(models.Model):
    code_ue = models.CharField(max_length=20, verbose_name="Code de l'UE")
    libelle_ue = models.CharField(max_length=255, verbose_name="Libellé de l'UE")
    semestre = models.PositiveSmallIntegerField(verbose_name="Semestre")

    semestre_obj = models.ForeignKey(
        'academic.Semestre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unites_enseignement',
        verbose_name="Semestre (annee)"
    )

    enseignants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='ues_enseignees',
        blank=True,
        verbose_name="Enseignants"
    )

    niveaux = models.ManyToManyField(
        'academic.Niveau',
        related_name='programme_ues',
        blank=True,
        verbose_name="Niveaux concernés"
    )

    class Meta:
        verbose_name = "Unité d'Enseignement"
        verbose_name_plural = "Unités d'Enseignement"
        ordering = ['code_ue']
        unique_together = ('code_ue', 'semestre_obj')

    def __str__(self):
        return f"{self.code_ue} - {self.libelle_ue}"