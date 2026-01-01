from rest_framework import viewsets
from .models import Utilisateur, Role
from .serializers import UtilisateurSerializer, RoleSerializer

class UtilisateurViewSet(viewsets.ModelViewSet):
    queryset = Utilisateur.objects.all().prefetch_related('roles')
    serializer_class = UtilisateurSerializer

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer