from django.db import models
from django.core.exceptions import ValidationError
from .unite_enseignement import UniteEnseignement
from users.models.utilisateur import Utilisateur

class TypeSeance(models.TextChoices):
    CM = 'CM', 'Cours Magistral'
    TD = 'TD', 'Travaux Dirigés'
    TP = 'TP', 'Travaux Pratiques'

class StatutFiche(models.TextChoices):
    SOUMISE = 'SOUMISE', 'Soumise'
    VALIDEE = 'VALIDEE', 'Validée'
    REFUSEE = 'REFUSEE', 'Refusée'

class FicheSuivi(models.Model):
    
    ue = models.ForeignKey(
        UniteEnseignement, 
        on_delete=models.PROTECT,
        related_name='fiches_suivi',
        verbose_name="Unité d'Enseignement"
    )
    
    delegue_soumetteur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        related_name='fiches_soumises',
        limit_choices_to={'roles__nom_role': 'Délégué'},
        verbose_name="Délégué"
    )

    enseignant_validateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        related_name='fiches_validees',
        limit_choices_to={'roles__nom_role': 'Enseignant'},
        verbose_name="Enseignant"
    )

    date_cours = models.DateField(verbose_name="Date du cours")
    heure_debut = models.TimeField(verbose_name="Heure de début")
    heure_fin = models.TimeField(verbose_name="Heure de fin")
    duree_calculee = models.DurationField(blank=True, null=True, verbose_name="Durée")
    salle = models.CharField(max_length=50, blank=True, verbose_name="Salle")
    type_seance = models.CharField(max_length=2, choices=TypeSeance.choices, verbose_name="Type de séance")   
    titre_chapitre = models.CharField(max_length=255, verbose_name="Titre du chapitre/cours")
    contenu_aborde = models.TextField(verbose_name="Contenu et notions abordées")
    statut = models.CharField(max_length=10, choices=StatutFiche.choices, default=StatutFiche.SOUMISE, verbose_name="Statut")
    motif_refus = models.TextField(blank=True, null=True, verbose_name="Motif du refus")
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.heure_fin and self.heure_debut and self.heure_fin <= self.heure_debut:
            raise ValidationError("L'heure de fin doit être postérieure à l'heure de début.")

    def save(self, *args, **kwargs):
        if self.heure_debut and self.heure_fin:
            from datetime import datetime, timedelta
            start = datetime.combine(self.date_cours, self.heure_debut)
            end = datetime.combine(self.date_cours, self.heure_fin)
            self.duree_calculee = end - start
        
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Fiche de Suivi"
        verbose_name_plural = "Fiches de Suivi"
        ordering = ['-date_cours', '-heure_debut']

    def __str__(self):
        return f"Fiche pour {self.ue.code_ue} du {self.date_cours}"