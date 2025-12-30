from django.shortcuts import render
from rest_framework.viewsets import  ModelViewSet
from .models import Utilisateur
from .serializers import UtilisateurSerializer


class UtilisateurViewSet(ModelViewSet):
    queryset = Utilisateur.objects.all()
    serializer_class = UtilisateurSerializer
