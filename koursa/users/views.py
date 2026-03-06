import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
import firebase_admin
from firebase_admin import auth as firebase_auth
from .models import Utilisateur, Role, StatutCompte, AuthProvider, EmailWhitelist
from .permissions import IsHoD, IsSuperAdmin, IsHoDOrSuperAdmin, IsAdminOrIsSelf
from datetime import timedelta
from .serializers import UtilisateurSerializer, RoleSerializer, PasswordConfirmationSerializer, ChangePasswordSerializer, MyTokenObtainPairSerializer, EmailWhitelistSerializer
from django.db.models.functions import Lower
from teaching.models import UniteEnseignement
from academic.models import Departement
from notifications.services import create_and_send_notification
from notifications.models import NotificationType

logger = logging.getLogger('koursa')

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
            # Enseignants qui ont des UEs dans les niveaux du departement
            enseignants_avec_ues = Utilisateur.objects.filter(
                roles__nom_role=Role.ENSEIGNANT,
                ues_enseignees__niveaux__filiere__departement=departement
            ).values_list('id', flat=True)
            # Enseignants whitelistes dans ce departement (pas encore d'UEs assignees)
            whitelisted_emails = list(
                EmailWhitelist.objects.filter(
                    departement=departement, role_type='ENSEIGNANT'
                ).values_list('email', flat=True)
            )
            whitelisted_emails_lower = [e.lower() for e in whitelisted_emails]
            enseignants_whitelistes = Utilisateur.objects.filter(
                roles__nom_role=Role.ENSEIGNANT,
            ).annotate(
                email_lower=Lower('email')
            ).filter(
                email_lower__in=whitelisted_emails_lower
            ).values_list('id', flat=True)
            all_ids = set(list(delegues_ids) + list(enseignants_avec_ues) + list(enseignants_whitelistes)) | {user.id}
            return self.queryset.filter(id__in=list(all_ids))
        
        
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

        # Le Chef de Département ne peut approuver que les délégués et enseignants
        if is_hod and not is_super_admin and not is_delegue and not is_enseignant:
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

        create_and_send_notification(
            recipient=utilisateur,
            title="Compte approuve",
            body="Votre compte a ete approuve. Vous pouvez maintenant acceder a toutes les fonctionnalites.",
            notification_type=NotificationType.COMPTE_APPROUVE,
            related_object_id=utilisateur.id,
        )

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

        user = serializer.instance

        # Si un admin crée le compte, l'activer directement
        if request.user.is_authenticated:
            is_admin = request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or request.user.is_superuser
            if is_admin:
                user.statut = StatutCompte.ACTIF
                user.save()

        # Auto-activation si l'email est dans la whitelist
        if user.statut != StatutCompte.ACTIF:
            entry = EmailWhitelist.objects.filter(email__iexact=user.email).first()
            if entry:
                user.statut = StatutCompte.ACTIF
                user.save()

        headers = self.get_success_headers(serializer.data)
        # Re-serialize pour inclure le statut mis à jour
        data = self.get_serializer(serializer.instance).data
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='me')
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.check_password(serializer.validated_data['old_password']):
            return Response({"detail": "Ancien mot de passe incorrect."}, status=status.HTTP_403_FORBIDDEN)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({"detail": "Mot de passe modifié avec succès."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='register-fcm-token')
    def register_fcm_token(self, request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({"detail": "Le champ 'fcm_token' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.fcm_token = fcm_token
        request.user.save()

        return Response({"detail": "Token enregistré avec succès."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='mes-utilisateurs')
    def mes_utilisateurs(self, request):
        """Retourne les utilisateurs pertinents pour un délégué: chef, enseignants (avec UEs), co-délégués."""
        user = request.user

        if not user.roles.filter(nom_role=Role.DELEGUE).exists():
            return Response({"detail": "Réservé aux délégués."}, status=status.HTTP_403_FORBIDDEN)

        niveau = user.niveau_represente
        if not niveau:
            return Response({"detail": "Aucun niveau représenté assigné."}, status=status.HTTP_400_BAD_REQUEST)

        # Nom de la classe
        classe_nom = f"{niveau.filiere.nom_filiere} {niveau.nom_niveau}"

        # Chef de département
        departement = niveau.filiere.departement
        chef = departement.chef_departement
        chef_data = None
        if chef:
            chef_data = {
                "id": chef.id,
                "nom_complet": chef.get_full_name(),
                "email": chef.email,
            }

        # Enseignants qui ont des UEs dans ce niveau, avec leurs UEs
        ues_du_niveau = UniteEnseignement.objects.filter(niveaux=niveau).prefetch_related('enseignants')
        enseignants_map = {}
        for ue in ues_du_niveau:
            for enseignant in ue.enseignants.all():
                if enseignant.id not in enseignants_map:
                    enseignants_map[enseignant.id] = {
                        "id": enseignant.id,
                        "nom_complet": enseignant.get_full_name(),
                        "email": enseignant.email,
                        "ues": [],
                    }
                enseignants_map[enseignant.id]["ues"].append({
                    "id": ue.id,
                    "code_ue": ue.code_ue,
                    "libelle_ue": ue.libelle_ue,
                })
        enseignants_data = list(enseignants_map.values())

        # Co-délégués du même niveau
        delegues = Utilisateur.objects.filter(
            niveau_represente=niveau,
            roles__nom_role=Role.DELEGUE,
            statut=StatutCompte.ACTIF,
        ).exclude(pk=user.pk)
        delegues_data = [
            {"id": d.id, "nom_complet": d.get_full_name(), "email": d.email}
            for d in delegues
        ]

        return Response({
            "classe": classe_nom,
            "chef": chef_data,
            "enseignants": enseignants_data,
            "delegues": delegues_data,
        })


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsSuperAdmin]
        return [permission() for permission in permission_classes]
    

class EmailWhitelistViewSet(viewsets.ModelViewSet):
    serializer_class = EmailWhitelistSerializer
    permission_classes = [IsHoDOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser:
            qs = EmailWhitelist.objects.all()
            dept = self.request.query_params.get('departement')
            if dept:
                qs = qs.filter(departement_id=dept)
            return qs
        # Chef de département → filtre par son département
        if hasattr(user, 'departement_gere') and user.departement_gere:
            return EmailWhitelist.objects.filter(departement=user.departement_gere)
        return EmailWhitelist.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {'ajoute_par': user}
        # Si chef, forcer le département au sien
        if not (user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser):
            if hasattr(user, 'departement_gere') and user.departement_gere:
                kwargs['departement'] = user.departement_gere
        serializer.save(**kwargs)

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_create(self, request):
        emails = request.data.get('emails', [])
        role_type = request.data.get('role_type')
        departement_id = request.data.get('departement')

        if not emails or not role_type:
            return Response(
                {'detail': 'Les champs emails et role_type sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        # Déterminer le département
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser:
            if not departement_id:
                return Response(
                    {'detail': 'Le champ departement est requis pour un admin.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if hasattr(user, 'departement_gere') and user.departement_gere:
                departement_id = user.departement_gere.id
            else:
                return Response(
                    {'detail': "Vous n'êtes assigné à aucun département."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        created = []
        skipped = []
        for email in emails:
            email = email.strip().lower()
            if not email:
                continue
            if EmailWhitelist.objects.filter(email__iexact=email).exists():
                skipped.append(email)
                continue
            entry = EmailWhitelist.objects.create(
                email=email,
                role_type=role_type,
                departement_id=departement_id,
                ajoute_par=user,
            )
            created.append(email)

        return Response(
            {'created': created, 'skipped': skipped},
            status=status.HTTP_201_CREATED,
        )


class LoginRateThrottle(AnonRateThrottle):
    """Limite les tentatives de login a 5/minute"""
    scope = 'login'


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


class GoogleAuthView(APIView):
    """
    Endpoint unique pour l'authentification Google.
    - POST { id_token } : login si l'utilisateur existe, sinon 404
    - POST { id_token, roles_ids, niveau_represente } : inscription + login
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def _verify_firebase_token(self, token):
        """Verifie le token Firebase et retourne les infos utilisateur."""
        try:
            decoded = firebase_auth.verify_id_token(token)
            return decoded
        except firebase_auth.ExpiredIdTokenError:
            logger.warning('Firebase ID token expire')
            return None
        except firebase_auth.RevokedIdTokenError:
            logger.warning('Firebase ID token revoque')
            return None
        except firebase_auth.InvalidIdTokenError:
            logger.warning('Firebase ID token invalide')
            return None
        except Exception as e:
            logger.error(f'Erreur verification Firebase token: {e}')
            return None

    def _generate_tokens(self, user):
        """Genere les tokens JWT pour un utilisateur."""
        refresh = RefreshToken.for_user(user)
        serializer = UtilisateurSerializer(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': serializer.data,
        }

    def post(self, request):
        token = request.data.get('id_token')
        if not token:
            return Response(
                {'detail': "Le champ 'id_token' est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        decoded = self._verify_firebase_token(token)
        if not decoded:
            return Response(
                {'detail': 'Token Firebase invalide.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = decoded.get('email', '').lower()
        firebase_name = decoded.get('name', '')
        # Firebase stocke le nom complet dans 'name', on le split
        name_parts = firebase_name.split(' ', 1) if firebase_name else ['', '']
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        if not email:
            return Response(
                {'detail': "Impossible de recuperer l'email depuis le token Google."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifier si l'utilisateur existe
        try:
            user = Utilisateur.objects.get(email=email)
            # Utilisateur existant -> login
            data = self._generate_tokens(user)
            return Response(data, status=status.HTTP_200_OK)
        except Utilisateur.DoesNotExist:
            pass

        # Utilisateur n'existe pas
        roles_ids = request.data.get('roles_ids')

        if not roles_ids:
            # Pas de donnees d'inscription -> indiquer que l'utilisateur n'existe pas
            return Response(
                {
                    'status': 'user_not_found',
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Inscription Google
        niveau_represente = request.data.get('niveau_represente')

        try:
            roles = Role.objects.filter(id__in=roles_ids)
            if not roles.exists():
                return Response(
                    {'detail': 'Roles invalides.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validation: delegue doit avoir un niveau
            is_delegue = roles.filter(nom_role=Role.DELEGUE).exists()
            if is_delegue and not niveau_represente:
                return Response(
                    {'niveau_represente': 'Ce champ est obligatoire pour un delegue.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = Utilisateur(
                email=email,
                first_name=first_name,
                last_name=last_name,
                statut=StatutCompte.EN_ATTENTE,
                auth_provider=AuthProvider.GOOGLE,
                niveau_represente_id=niveau_represente,
            )
            user.set_unusable_password()
            user.save()
            user.roles.set(roles)

            # Auto-activation si l'email est dans la whitelist
            entry = EmailWhitelist.objects.filter(email__iexact=user.email).first()
            if entry:
                user.statut = StatutCompte.ACTIF
                user.save()

            data = self._generate_tokens(user)
            return Response(data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f'Erreur inscription Google: {e}')
            return Response(
                {'detail': "Erreur lors de la creation du compte."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )