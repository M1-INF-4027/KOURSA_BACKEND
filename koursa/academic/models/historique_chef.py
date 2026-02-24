from django.db import models
from django.conf import settings


class HistoriqueChefDepartement(models.Model):
    departement = models.ForeignKey(
        'academic.Departement',
        on_delete=models.CASCADE,
        related_name='historique_chefs'
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='historique_chefs_departements'
    )
    annee_academique = models.ForeignKey(
        'academic.AnneeAcademique',
        on_delete=models.CASCADE,
        related_name='chefs_historique'
    )
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Historique Chef de Departement"
        verbose_name_plural = "Historiques Chefs de Departement"
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.utilisateur} - {self.departement} ({self.annee_academique})"
