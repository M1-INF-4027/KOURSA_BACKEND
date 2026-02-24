from django.db import models


class AnneeAcademique(models.Model):
    libelle = models.CharField(
        max_length=9,
        unique=True,
        verbose_name="Annee academique",
        help_text="Format: YYYY-YYYY (ex: 2025-2026)"
    )
    est_active = models.BooleanField(
        default=False,
        verbose_name="Annee active"
    )
    est_configuree = models.BooleanField(
        default=False,
        verbose_name="Configuration terminee"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Annee Academique"
        verbose_name_plural = "Annees Academiques"
        ordering = ['-libelle']

    def __str__(self):
        return self.libelle

    def save(self, *args, **kwargs):
        if self.est_active:
            AnneeAcademique.objects.filter(
                est_active=True
            ).exclude(pk=self.pk).update(est_active=False)
        super().save(*args, **kwargs)
