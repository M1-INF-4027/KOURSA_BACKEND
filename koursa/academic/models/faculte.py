from django.db import models

from academic.models.departement import Departement


class Faculte(models.Model):
    nom_faculte = models.CharField(max_length=100)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)

    def __str__(self):
        return self.nom_faculte
