from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from .role import Role
from academic.models.departement import Departement
from academic.models.niveau import Niveau

class StatutCompte(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
    ACTIF = 'ACTIF', 'Actif'
    INACTIF = 'INACTIF', 'Inactif'

class UtilisateurManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        extra_fields.setdefault('statut', StatutCompte.ACTIF)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le Superuser doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le Superuser doit avoir is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class Utilisateur(AbstractUser):
    username = None
    email = models.EmailField(unique=True, verbose_name="Adresse email")
    
    roles = models.ManyToManyField(
        Role,
        related_name='utilisateurs',
        blank=True,
        verbose_name="Rôles"
    )

    statut = models.CharField(
        max_length=20, 
        choices=StatutCompte.choices, 
        default=StatutCompte.ACTIF,
        verbose_name="Statut du compte"
    )


    departement_dirige = models.OneToOneField(
        Departement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chef',
        verbose_name="Département dirigé"
    )

    niveau_represente = models.ForeignKey(
        Niveau,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegues',
        verbose_name="Niveau représenté"
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UtilisateurManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"