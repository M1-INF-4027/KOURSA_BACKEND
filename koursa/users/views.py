from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Utilisateur, Role, StatutCompte
from .permissions import IsHoD, IsSuperAdmin, IsAdminOrIsSelf
from datetime import timedelta
from .serializers import UtilisateurSerializer, RoleSerializer, PasswordConfirmationSerializer, MyTokenObtainPairSerializer
from teaching.models import UniteEnseignement

class UtilisateurViewSet(viewsets.ModelViewSet):
    queryset = Utilisateur.objects.all().prefetch_related('roles')
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAdminOrIsSelf]

    filterset_fields = ['roles', 'statut']

    def get_queryset(self):
        user = self.request.user
        
        if not user.is_authenticated:
            return Utilisateur.objects.none()
            
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists():
            return self.queryset
        
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists() and user.departement_gere:
            departement = user.departement_gere
            delegues_ids = Utilisateur.objects.filter(niveau_represente__filiere__departement=departement).values_list('id', flat=True)
            enseignants_ids = Utilisateur.objects.filter(roles__nom_role=Role.ENSEIGNANT).values_list('id', flat=True)
            return self.queryset.filter(id__in=list(set(list(delegues_ids) + list(enseignants_ids)) | {user.id}))
        
        
        return self.queryset.filter(pk=user.pk)

    def perform_destroy(self, instance):
        user = self.request.user
        # Un Chef de Département ne peut supprimer que des délégués de son département
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists():
            if not instance.roles.filter(nom_role=Role.DELEGUE).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Vous ne pouvez supprimer que des délégués.")
            # Vérifier que le délégué appartient au département du chef
            if hasattr(user, 'departement_gere') and user.departement_gere:
                if instance.niveau_represente and instance.niveau_represente.filiere.departement != user.departement_gere:
                    raise PermissionDenied("Ce délégué n'appartient pas à votre département.")
        instance.delete()

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='confirm-password')
    def confirm_password(self, request):
        user = request.user
        serializer = PasswordConfirmationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        password = serializer.validated_data['password']
        
        if not user.check_password(password):
            return Response({"detail": "Mot de passe incorrect."}, status=status.HTTP_403_FORBIDDEN)
        
        validation_token = AccessToken.for_user(user)
        validation_token.set_exp(lifetime=timedelta(minutes=20)) 
        
        validation_token['token_class'] = 'validation'
        
        return Response({
            'validation_token': str(validation_token)
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='approuver')
    def approuver(self, request, pk=None):
        """Approuver un utilisateur en attente (délégué ou enseignant)"""
        approbateur = request.user

        # Seuls le Super Admin et le Chef de Département peuvent approuver
        is_super_admin = approbateur.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or approbateur.is_superuser
        is_hod = approbateur.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists()

        if not is_super_admin and not is_hod:
            return Response({"detail": "Vous n'avez pas la permission d'approuver des utilisateurs."}, status=status.HTTP_403_FORBIDDEN)

        utilisateur = self.get_object()

        # Vérifier que l'utilisateur est en attente
        if utilisateur.statut != StatutCompte.EN_ATTENTE:
            return Response({"detail": "Cet utilisateur n'est pas en attente de validation."}, status=status.HTTP_400_BAD_REQUEST)

        is_delegue = utilisateur.roles.filter(nom_role=Role.DELEGUE).exists()
        is_enseignant = utilisateur.roles.filter(nom_role=Role.ENSEIGNANT).exists()

        if not is_delegue and not is_enseignant:
            return Response({"detail": "Seuls les délégués et enseignants peuvent être approuvés."}, status=status.HTTP_400_BAD_REQUEST)

        # Vérifications spécifiques au Chef de Département
        if is_hod and not is_super_admin:
            if not hasattr(approbateur, 'departement_gere') or not approbateur.departement_gere:
                return Response({"detail": "Vous n'êtes assigné à aucun département."}, status=status.HTTP_403_FORBIDDEN)

            # Pour un délégué, vérifier qu'il appartient au département du chef
            if is_delegue:
                if not utilisateur.niveau_represente:
                    return Response({"detail": "Ce délégué n'a pas de niveau représenté assigné."}, status=status.HTTP_400_BAD_REQUEST)
                if utilisateur.niveau_represente.filiere.departement != approbateur.departement_gere:
                    return Response({"detail": "Cet utilisateur n'appartient pas à votre département."}, status=status.HTTP_403_FORBIDDEN)

        utilisateur.statut = StatutCompte.ACTIF
        utilisateur.save()

        serializer = self.get_serializer(utilisateur)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Garder l'ancien endpoint pour compatibilité mobile
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='approuver-delegue')
    def approuver_delegue(self, request, pk=None):
        return self.approuver(request, pk)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='me')
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='register-fcm-token')
    def register_fcm_token(self, request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({"detail": "Le champ 'fcm_token' est requis."}, status=status.HTTP_400_BAD_REQUEST)
        
        request.user.fcm_token = fcm_token
        request.user.save()
        
        return Response({"detail": "Token enregistré avec succès."}, status=status.HTTP_200_OK)



class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]
    

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer