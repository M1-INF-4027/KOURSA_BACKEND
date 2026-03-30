import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from users.permissions import IsSuperAdmin
from users.models import Role

logger = logging.getLogger('koursa')
from .models import Faculte, Departement, Filiere, Niveau, AnneeAcademique, Semestre, HistoriqueChefDepartement, Salle
from .serializers import (
    FaculteSerializer, DepartementSerializer, FiliereSerializer, NiveauSerializer,
    AnneeAcademiqueSerializer, SemestreSerializer, HistoriqueChefSerializer,
    SalleSerializer,
)

class FaculteViewSet(viewsets.ModelViewSet):
    queryset = Faculte.objects.all()
    serializer_class = FaculteSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]


class DepartementViewSet(viewsets.ModelViewSet):
    queryset = Departement.objects.select_related('faculte', 'chef_departement').all()
    serializer_class = DepartementSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    def _sync_chef_role(self, old_chef, new_chef):
        """Ajoute/retire le role Chef de Departement automatiquement."""
        chef_role = Role.objects.filter(nom_role=Role.CHEF_DEPARTEMENT).first()
        if not chef_role:
            return

        # Retirer le role de l'ancien chef s'il ne gere plus aucun departement
        if old_chef and old_chef != new_chef:
            still_chef = Departement.objects.filter(chef_departement=old_chef).exists()
            if not still_chef:
                old_chef.roles.remove(chef_role)

        # Ajouter le role au nouveau chef
        if new_chef and new_chef != old_chef:
            new_chef.roles.add(chef_role)
            new_chef.statut = 'ACTIF'
            new_chef.save(update_fields=['statut'])

    def perform_create(self, serializer):
        instance = serializer.save()
        self._sync_chef_role(None, instance.chef_departement)

    def perform_update(self, serializer):
        old_chef = self.get_object().chef_departement
        instance = serializer.save()
        self._sync_chef_role(old_chef, instance.chef_departement)

class FiliereViewSet(viewsets.ModelViewSet):
    queryset = Filiere.objects.select_related('departement', 'departement__faculte').all()
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

    def get_queryset(self):
        qs = super().get_queryset()
        departement_id = self.request.query_params.get('departement')
        if departement_id:
            qs = qs.filter(filiere__departement_id=departement_id)
        return qs


class SalleViewSet(viewsets.ModelViewSet):
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all(self, request):
        """Supprimer toutes les salles."""
        count = Salle.objects.count()
        Salle.objects.all().delete()
        logger.warning(f'Toutes les salles supprimees ({count}) par {request.user.email}')
        return Response({'deleted': count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='import',
            parser_classes=[MultiPartParser, FormParser])
    def import_salles(self, request):
        """Importer des salles depuis un fichier Excel (.xlsx)."""
        import openpyxl

        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier fourni.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
        except Exception:
            return Response({'detail': 'Fichier Excel invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        skipped = 0
        errors = []

        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            nom = row[0] if row else None
            if not nom or not str(nom).strip():
                continue
            nom = str(nom).strip()
            _, was_created = Salle.objects.get_or_create(nom_salle=nom)
            if was_created:
                created += 1
            else:
                skipped += 1

        logger.info(f'Import salles par {request.user.email}: {created} creees, {skipped} existantes')
        return Response({
            'created': created,
            'skipped': skipped,
            'errors': errors,
        }, status=status.HTTP_200_OK)


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