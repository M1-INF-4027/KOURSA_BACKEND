from django.contrib import admin
from .models import *

for model in [Role,Utilisateur]:
    admin.site.register(model)
