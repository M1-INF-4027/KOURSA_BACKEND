from django.db import models
from django.conf import settings


class PlanningCours(models.Model):
    """
    Retient le jour de la semaine et l'horaire habituel d'un cours.
    Cree automatiquement lors de la premiere soumission d'une fiche pour une UE.
    Utilise par le cron de rappels pour detecter les fiches manquantes.
    """
    JOURS_SEMAINE = [
        (0, 'Lundi'),
        (1, 'Mardi'),
        (2, 'Mercredi'),
        (3, 'Jeudi'),
        (4, 'Vendredi'),
        (5, 'Samedi'),
        (6, 'Dimanche'),
    ]

    ue = models.ForeignKey(
        'teaching.UniteEnseignement',
        on_delete=models.CASCADE,
        related_name='plannings',
        verbose_name="Unite d'enseignement",
    )
    semestre = models.ForeignKey(
        'academic.Semestre',
        on_delete=models.CASCADE,
        related_name='plannings_cours',
        verbose_name="Semestre",
    )
    jour_semaine = models.IntegerField(
        choices=JOURS_SEMAINE,
        verbose_name="Jour de la semaine",
    )
    heure_debut = models.TimeField(verbose_name="Heure de debut")
    heure_fin = models.TimeField(verbose_name="Heure de fin")
    type_seance = models.CharField(
        max_length=2,
        default='CM',
        verbose_name="Type de seance",
    )
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Planning de cours"
        verbose_name_plural = "Plannings de cours"
        unique_together = ('ue', 'semestre', 'jour_semaine', 'heure_debut')
        ordering = ['jour_semaine', 'heure_debut']

    def __str__(self):
        jour = dict(self.JOURS_SEMAINE).get(self.jour_semaine, '?')
        return f"{self.ue.code_ue} - {jour} {self.heure_debut}-{self.heure_fin}"
