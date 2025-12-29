from django.db import models

from teaching.models.fiche_suivi import FicheSuivi
from users.models.utilisateur import Utilisateur


class Soumettre(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    fiche_suivi = models.ForeignKey(FicheSuivi, on_delete=models.CASCADE)
    date = models.DateField()