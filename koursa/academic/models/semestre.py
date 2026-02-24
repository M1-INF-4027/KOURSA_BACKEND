from django.db import models


class Semestre(models.Model):
    annee_academique = models.ForeignKey(
        'academic.AnneeAcademique',
        on_delete=models.CASCADE,
        related_name='semestres'
    )
    numero = models.PositiveSmallIntegerField(
        verbose_name="Numero du semestre"
    )
    date_debut = models.DateField(verbose_name="Date de debut")
    date_fin = models.DateField(verbose_name="Date de fin")
    est_actif = models.BooleanField(
        default=False,
        verbose_name="Semestre actif"
    )

    class Meta:
        verbose_name = "Semestre"
        verbose_name_plural = "Semestres"
        unique_together = ('annee_academique', 'numero')
        ordering = ['annee_academique', 'numero']

    def __str__(self):
        return f"S{self.numero} - {self.annee_academique.libelle}"

    def save(self, *args, **kwargs):
        if self.est_actif:
            # Un seul semestre actif dans tout le systeme
            Semestre.objects.filter(
                est_actif=True
            ).exclude(pk=self.pk).update(est_actif=False)
        super().save(*args, **kwargs)
