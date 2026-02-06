from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from users.permissions import IsSuperAdmin
from .models import Faculte, Departement, Filiere, Niveau
from .serializers import FaculteSerializer, DepartementSerializer, FiliereSerializer, NiveauSerializer

class FaculteViewSet(viewsets.ModelViewSet):
    queryset = Faculte.objects.all()
    serializer_class = FaculteSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else: 
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]


class DepartementViewSet(viewsets.ModelViewSet):
    queryset = Departement.objects.select_related('faculte', 'chef_departement').all()
    serializer_class = DepartementSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else: 
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

class FiliereViewSet(viewsets.ModelViewSet):
    queryset = Filiere.objects.select_related('departement').all()
    serializer_class = FiliereSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

class NiveauViewSet(viewsets.ModelViewSet):
    queryset = Niveau.objects.select_related('filiere').all()
    serializer_class = NiveauSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]