from django.conf import settings
from django.db import models


class StatutMandat(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
    APPROUVE = 'APPROUVE', 'Approuve'
    REFUSE = 'REFUSE', 'Refuse'


class MandatDelegue(models.Model):
    """
    La classe qu'un delegue represente, pour une annee donnee.

    Jusqu'ici cette information tenait dans un seul champ de l'utilisateur,
    sans annee. Au changement d'annee le delegue restait donc inscrit dans sa
    classe de l'an passe, et le filtre des unites d'enseignement croisait
    « niveau du delegue » et « annee active » : il voyait les cours de la
    nouvelle annee, mais de son ancien niveau, sans qu'aucune erreur ne
    s'affiche. Plus personne ne pouvait repondre non plus a « qui representait
    la L3 en 2026-2027 ».

    Le mandat porte l'annee, ce qui regle les deux : la classe redevient une
    question a laquelle on repond annee par annee, et l'historique se
    conserve. Le modele reprend le patron de HistoriqueChefDepartement, deja
    en place pour les chefs de departement.

    Une classe reelit son delegue chaque annee : les mandats ne sont donc pas
    reconduits automatiquement. Un mandat declare par le delegue naît
    EN_ATTENTE et n'a d'effet qu'une fois approuve par le chef.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mandats_delegue',
        verbose_name="Delegue",
    )
    niveau = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.CASCADE,
        related_name='mandats',
        verbose_name="Classe representee",
    )
    annee_academique = models.ForeignKey(
        'academic.AnneeAcademique',
        on_delete=models.CASCADE,
        related_name='mandats_delegues',
        verbose_name="Annee academique",
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutMandat.choices,
        default=StatutMandat.EN_ATTENTE,
        verbose_name="Statut du mandat",
    )
    date_debut = models.DateField(auto_now_add=True)
    date_fin = models.DateField(
        null=True, blank=True,
        verbose_name="Cloture du mandat",
        help_text="Renseignee lorsqu'une annee suivante est ouverte.",
    )
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mandats_approuves',
    )
    motif_refus = models.TextField(blank=True)

    class Meta:
        verbose_name = "Mandat de delegue"
        verbose_name_plural = "Mandats de delegues"
        ordering = ['-annee_academique__libelle', 'niveau__nom_niveau']
        # Un delegue ne represente qu'une classe par annee. Redeclarer revient
        # a corriger sa demande, non a en ouvrir une seconde.
        constraints = [
            models.UniqueConstraint(
                fields=['utilisateur', 'annee_academique'],
                name='un_mandat_par_delegue_et_par_annee',
            ),
        ]

    def __str__(self):
        return f"{self.utilisateur} - {self.niveau} ({self.annee_academique})"
