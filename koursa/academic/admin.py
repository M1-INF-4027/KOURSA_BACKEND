from django.contrib import admin
from .models import *

for model in [Departement, Faculte,Niveau]:
    admin.site.register(model)

