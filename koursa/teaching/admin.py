from django.contrib import admin
from .models import *

for model in [Dispenser, FicheSuivi, Proposer, Soumettre, Valider, UniteEnseignement]:
    admin.site.register(model)
