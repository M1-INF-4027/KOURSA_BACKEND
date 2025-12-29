from django.db import models

from users.models import Utilisateur


class FicheSuivi(models.Model):
    date_soummission = models.DateField()
    date_validation = models.DateField()

    debut = models.TimeField()
    fin = models.TimeField()
    salle = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    statut_fiche = models.CharField(max_length=50)

    soumetteur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='soumetteur')
    validateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='validateur')

    def __str__(self):
        return f"{self.date} - {self.salle}"
