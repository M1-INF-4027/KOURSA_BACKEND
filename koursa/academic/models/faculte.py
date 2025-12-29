from django.db import models

class Faculte(models.Model):
    nom_faculte = models.CharField(max_length=100, unique=True, verbose_name="Nom de la Faculté")

    class Meta:
        verbose_name = "Faculté"
        verbose_name_plural = "Facultés"

    def __str__(self):
        return self.nom_faculte