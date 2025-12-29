from django.contrib import admin
from .models import *

for model in [Dispenser, FicheSuivi, Soumettre, UniteEnseignement]:
    admin.site.register(model)
