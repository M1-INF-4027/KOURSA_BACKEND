from django.db import models

class FicheSuivi(models.Model):
    date = models.DateField()
    debut = models.TimeField()
    fin = models.TimeField()
    salle = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    statut_fiche = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.date} - {self.salle}"
