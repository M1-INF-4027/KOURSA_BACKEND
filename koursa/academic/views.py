from rest_framework import viewsets
from .models import Faculte, Departement, Filiere, Niveau
from .serializers import FaculteSerializer, DepartementSerializer, FiliereSerializer, NiveauSerializer

class FaculteViewSet(viewsets.ModelViewSet):
    queryset = Faculte.objects.all()
    serializer_class = FaculteSerializer

class DepartementViewSet(viewsets.ModelViewSet):
    queryset = Departement.objects.select_related('faculte', 'chef_departement').all()
    serializer_class = DepartementSerializer

class FiliereViewSet(viewsets.ModelViewSet):
    queryset = Filiere.objects.select_related('departement').all()
    serializer_class = FiliereSerializer

class NiveauViewSet(viewsets.ModelViewSet):
    queryset = Niveau.objects.select_related('filiere').all()
    serializer_class = NiveauSerializer