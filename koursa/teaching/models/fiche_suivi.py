from django.db import models
from django.core.exceptions import ValidationError
from .unite_enseignement import UniteEnseignement
from django.conf import settings
from datetime import datetime

class TypeSeance(models.TextChoices):
    CM = 'CM', 'Cours Magistral'
    TD = 'TD', 'Travaux Dirigés'
    TP = 'TP', 'Travaux Pratiques'

class StatutFiche(models.TextChoices):
    SOUMISE = 'SOUMISE', 'Soumise'
    VALIDEE = 'VALIDEE', 'Validée'
    REFUSEE = 'REFUSEE', 'Refusée'

class FicheSuivi(models.Model):
    ue = models.ForeignKey(UniteEnseignement, on_delete=models.PROTECT, related_name='fiches')

    delegue = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='fiches_soumises'
    )

    enseignant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='fiches_a_valider'
    )

    date_cours = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    duree = models.DurationField(blank=True, editable=False) # Calculée automatiquement
    salle = models.CharField(max_length=50, blank=True)
    type_seance = models.CharField(max_length=2, choices=TypeSeance.choices)
    
    titre_chapitre = models.CharField(max_length=255)
    contenu_aborde = models.TextField()

    statut = models.CharField(max_length=10, choices=StatutFiche.choices, default=StatutFiche.SOUMISE)
    motif_refus = models.TextField(blank=True)
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.heure_fin <= self.heure_debut:
            raise ValidationError("L'heure de fin doit être après l'heure de début.")

    def save(self, *args, **kwargs):
        start = datetime.combine(self.date_cours, self.heure_debut)
        end = datetime.combine(self.date_cours, self.heure_fin)
        self.duree = end - start
        
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_cours', '-heure_debut']

    def __str__(self):
        return f"Fiche du {self.date_cours} pour {self.ue.code_ue}"