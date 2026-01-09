from rest_framework import viewsets
from .models import Utilisateur, Role, StatutCompte, EnseignantWhitelist
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
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
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists():
            if not instance.roles.filter(nom_role=Role.DELEGUE).exists():
                pass
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
    
    @action(detail=True, methods=['post'], permission_classes=[IsHoD], url_path='approuver-delegue')
    def approuver_delegue(self, request, pk=None):
        
        hod = request.user
        
        try:
            delegue_a_approuver = self.get_object()
        except Utilisateur.DoesNotExist:
            return Response({"detail": "Utilisateur non trouvé."}, status=status.HTTP_404_NOT_FOUND)

        if not delegue_a_approuver.roles.filter(nom_role=Role.DELEGUE).exists() or delegue_a_approuver.statut != StatutCompte.EN_ATTENTE:
            return Response({"detail": "Cet utilisateur n'est pas un délégué en attente de validation."}, status=status.HTTP_400_BAD_REQUEST)

        if delegue_a_approuver.niveau_represente.filiere.departement != hod.departement_gere:
            return Response({"detail": "Vous n'avez pas la permission d'approuver un délégué de ce département."}, status=status.HTTP_403_FORBIDDEN)
        
        delegue_a_approuver.statut = StatutCompte.ACTIF
        delegue_a_approuver.save()
                
        serializer = self.get_serializer(delegue_a_approuver)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email')
        roles_ids = [role.id for role in serializer.validated_data.get('roles')]
        
        try:
            role_enseignant_id = Role.objects.get(nom_role=Role.ENSEIGNANT).id
        except Role.DoesNotExist:
            return Response({"detail": "Le rôle 'Enseignant' n'est pas configuré."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        if role_enseignant_id in roles_ids:
            if not EnseignantWhitelist.objects.filter(email__iexact=email).exists():
                return Response(
                    {"detail": f"L'email '{email}' n'est pas autorisé à s'inscrire en tant qu'enseignant."},
                    status=status.HTTP_403_FORBIDDEN
                )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
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
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]
    

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer