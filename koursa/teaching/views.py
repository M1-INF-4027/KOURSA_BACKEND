from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import UniteEnseignement, FicheSuivi, StatutFiche
from .serializers import UniteEnseignementSerializer, FicheSuiviSerializer, ValidationFicheSerializer


class UniteEnseignementViewSet(viewsets.ModelViewSet):
    queryset = UniteEnseignement.objects.prefetch_related('enseignants', 'niveaux').all()
    serializer_class = UniteEnseignementSerializer


class FicheSuiviViewSet(viewsets.ModelViewSet):
    queryset = FicheSuivi.objects.select_related('ue', 'delegue', 'enseignant').all()
    serializer_class = FicheSuiviSerializer

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valider une fiche de suivi"""
        fiche = self.get_object()

        if fiche.statut != StatutFiche.SOUMISE:
            return Response(
                {'error': 'Seules les fiches soumises peuvent etre validees.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        fiche.statut = StatutFiche.VALIDEE
        fiche.date_validation = timezone.now()
        fiche.save()

        serializer = self.get_serializer(fiche)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        """Refuser une fiche de suivi"""
        fiche = self.get_object()

        if fiche.statut != StatutFiche.SOUMISE:
            return Response(
                {'error': 'Seules les fiches soumises peuvent etre refusees.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        motif = request.data.get('motif_refus', '')
        if not motif:
            return Response(
                {'error': 'Le motif de refus est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        fiche.statut = StatutFiche.REFUSEE
        fiche.motif_refus = motif
        fiche.date_validation = timezone.now()
        fiche.save()

        serializer = self.get_serializer(fiche)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='en-attente')
    def en_attente(self, request):
        """Lister les fiches en attente de validation"""
        fiches = self.queryset.filter(statut=StatutFiche.SOUMISE)
        serializer = self.get_serializer(fiches, many=True)
        return Response(serializer.data)