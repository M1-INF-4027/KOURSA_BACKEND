from django.db import models

class Role(models.TextChoices):
    DELEGUE = "DELEGUE","Delegue"
    ENSEIGNANT = "ENSEIGNANT", "Enseignant"
    CHEFDEPARTEMENT = "CHEFDEPARTEMENT", "Chefdepartement"
    ADMIN = "ADMIN", "Admin"

class StatutCompte(models.TextChoices):
    ACTIF = 'ACTIF', 'Actif'
    INACTIF = 'INACTIF', 'Inactif'
    SUSPENDU = 'SUSPENDU', 'Suspendu'