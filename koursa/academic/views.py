from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from users.permissions import IsSuperAdmin
from .models import Faculte, Departement, Filiere, Niveau, AnneeAcademique, Semestre, HistoriqueChefDepartement
from .serializers import (
    FaculteSerializer, DepartementSerializer, FiliereSerializer, NiveauSerializer,
    AnneeAcademiqueSerializer, SemestreSerializer, HistoriqueChefSerializer,
)

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


class AnneeAcademiqueViewSet(viewsets.ModelViewSet):
    queryset = AnneeAcademique.objects.prefetch_related('semestres').all()
    serializer_class = AnneeAcademiqueSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


class SemestreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Semestre.objects.select_related('annee_academique').all()
    serializer_class = SemestreSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['annee_academique', 'est_actif']


class HistoriqueChefViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoriqueChefDepartement.objects.select_related(
        'departement', 'utilisateur', 'annee_academique'
    ).all()
    serializer_class = HistoriqueChefSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['departement', 'annee_academique']