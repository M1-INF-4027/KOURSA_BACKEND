from django.db import models

class EnumNiveau (models.TextChoices):
    L1 = 'L1', 'Licence 1'
    L2 = 'L2', 'Licence 2'
    L3 = 'L3', 'Licence 3'
    M1 = 'M1', 'Master 1'
    M2 = 'M2', 'Master 2'