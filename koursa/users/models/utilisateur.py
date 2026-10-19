from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from .role import Role


class StatutCompte(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
    ACTIF = 'ACTIF', 'Actif'
    INACTIF = 'INACTIF', 'Inactif'

class AuthProvider(models.TextChoices):
    PASSWORD = 'password', 'Mot de passe'
    GOOGLE = 'google', 'Google'

class UtilisateurManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('statut', StatutCompte.ACTIF)

        if not extra_fields.get('is_staff'):
            raise ValueError('Le Superuser doit avoir is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Le Superuser doit avoir is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class Utilisateur(AbstractUser):
    username = None 
    email = models.EmailField(unique=True, verbose_name="Adresse email")

    statut = models.CharField(
        max_length=20,
        choices=StatutCompte.choices,
        default=StatutCompte.EN_ATTENTE,
        verbose_name="Statut du compte"
    )

    roles = models.ManyToManyField(
        Role,
        related_name='utilisateurs',
        blank=True
    )

    niveau_represente = models.ForeignKey(
        'academic.Niveau',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegues'
    )

    auth_provider = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.PASSWORD,
        verbose_name="Methode d'authentification"
    )

    fcm_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Token de l'appareil pour les notifs"
    )

    # Positionne a la creation d'un compte par import : le mot de passe initial
    # etant l'adresse email, il doit etre change des la premiere connexion.
    doit_changer_mot_de_passe = models.BooleanField(
        default=False,
        verbose_name="Doit changer son mot de passe"
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UtilisateurManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.get_full_name() or self.email

    def mandat_actif(self):
        """
        Mandat de delegue approuve pour l'annee en cours, s'il existe.

        C'est par lui que passe desormais la classe d'un delegue, et non plus
        par niveau_represente seul : ce champ ne portait aucune annee, si bien
        qu'au changement d'annee le delegue restait inscrit dans sa classe de
        l'an passe sans que rien ne le signale.
        """
        from academic.models import AnneeAcademique, MandatDelegue, StatutMandat

        annee = AnneeAcademique.objects.filter(est_active=True).first()
        if not annee:
            return None
        return (
            MandatDelegue.objects
            .filter(utilisateur=self, annee_academique=annee,
                    statut=StatutMandat.APPROUVE)
            .select_related('niveau__filiere__departement', 'annee_academique')
            .first()
        )

    def classe_actuelle(self):
        """Niveau represente cette annee, ou None s'il reste a declarer."""
        mandat = self.mandat_actif()
        return mandat.niveau if mandat else None