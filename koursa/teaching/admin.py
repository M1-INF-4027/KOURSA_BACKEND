from django.contrib import admin
from .models import *

for model in [FicheSuivi, UniteEnseignement]:
    admin.site.register(model)
