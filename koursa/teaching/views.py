from rest_framework import viewsets
from .models import UniteEnseignement, FicheSuivi
from .serializers import UniteEnseignementSerializer, FicheSuiviSerializer

class UniteEnseignementViewSet(viewsets.ModelViewSet):
    queryset = UniteEnseignement.objects.prefetch_related('enseignants', 'niveaux').all()
    serializer_class = UniteEnseignementSerializer

class FicheSuiviViewSet(viewsets.ModelViewSet):
    queryset = FicheSuivi.objects.select_related('ue', 'delegue', 'enseignant').all()
    serializer_class = FicheSuiviSerializer