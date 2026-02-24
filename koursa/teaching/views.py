from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from users.models import Role
from users.permissions import IsEnseignantConcerne, IsFicheModifiable, IsDelegueAuteur, IsDelegue
from .models import UniteEnseignement, FicheSuivi, StatutFiche
from .serializers import (
    UniteEnseignementSerializer,
    FicheSuiviSerializer,
    ValidationTokenSerializer,
    ValidationFicheSerializer
)
from koursa.firebase_config import send_notification


class UniteEnseignementViewSet(viewsets.ModelViewSet):
    queryset = UniteEnseignement.objects.prefetch_related('enseignants', 'niveaux').select_related('semestre_obj__annee_academique').all()
    serializer_class = UniteEnseignementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return UniteEnseignement.objects.none()

        qs = self.queryset

        # Scoper par semestre/annee si parametre fourni
        semestre_id = self.request.query_params.get('semestre_id')
        annee_id = self.request.query_params.get('annee_academique')
        if semestre_id:
            qs = qs.filter(semestre_obj_id=semestre_id)
        elif annee_id:
            qs = qs.filter(semestre_obj__annee_academique_id=annee_id)
        else:
            # Pour enseignant/delegue : scoper par defaut a l'annee active
            is_admin_or_chef = user.roles.filter(
                nom_role__in=[Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]
            ).exists() or user.is_superuser
            if not is_admin_or_chef:
                from academic.models import AnneeAcademique
                annee_active = AnneeAcademique.objects.filter(est_active=True).first()
                if annee_active:
                    qs = qs.filter(semestre_obj__annee_academique=annee_active)

        # Super admin et chef voient toutes les UEs (du scope)
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser:
            return qs
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists() and hasattr(user, 'departement_gere'):
            return qs.filter(niveaux__filiere__departement=user.departement_gere).distinct()

        if user.roles.filter(nom_role=Role.DELEGUE).exists():
            return qs.filter(niveaux=user.niveau_represente)

        if user.roles.filter(nom_role=Role.ENSEIGNANT).exists():
            return qs.filter(enseignants=user)

        return UniteEnseignement.objects.none()


class FicheSuiviViewSet(viewsets.ModelViewSet):
    queryset = FicheSuivi.objects.select_related('ue', 'delegue', 'enseignant').prefetch_related('ue__niveaux__filiere').all()
    serializer_class = FicheSuiviSerializer

    filterset_fields = ['statut', 'date_cours', 'enseignant', 'delegue', 'ue']

    def get_permissions(self):
        permission_classes = [IsAuthenticated]

        if self.action == 'create':
            permission_classes.append(IsDelegue)

        elif self.action in ['update', 'partial_update']:
            permission_classes.extend([IsDelegueAuteur, IsFicheModifiable])

        elif self.action == 'destroy':
            permission_classes.extend([IsDelegueAuteur, IsFicheModifiable])

        elif self.action in ['valider', 'refuser']:
            permission_classes.append(IsEnseignantConcerne)

        elif self.action == 'resoumettre':
            permission_classes.append(IsDelegueAuteur)

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return FicheSuivi.objects.none()

        qs = self.queryset

        # Filtrage par semestre/annee
        semestre_id = self.request.query_params.get('semestre_id')
        annee_id = self.request.query_params.get('annee_academique')
        if semestre_id:
            qs = qs.filter(semestre_id=semestre_id)
        elif annee_id:
            qs = qs.filter(semestre__annee_academique_id=annee_id)
        else:
            # Pour enseignant/delegue : scoper par defaut a l'annee active
            is_admin_or_chef = user.roles.filter(
                nom_role__in=[Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]
            ).exists() or user.is_superuser
            if not is_admin_or_chef:
                from academic.models import AnneeAcademique
                annee_active = AnneeAcademique.objects.filter(est_active=True).first()
                if annee_active:
                    qs = qs.filter(semestre__annee_academique=annee_active)

        # Filtrage par role
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists():
            return qs

        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists() and user.departement_gere:
            return qs.filter(ue__niveaux__filiere__departement=user.departement_gere).distinct()

        return qs.filter(Q(delegue=user) | Q(enseignant=user))

    def perform_create(self, serializer):
        from academic.models import Semestre
        from rest_framework.exceptions import ValidationError
        semestre_actif = Semestre.objects.filter(est_actif=True).first()
        if not semestre_actif:
            raise ValidationError(
                {"detail": "Aucun semestre actif. Veuillez contacter l'administrateur."}
            )
        serializer.save(delegue=self.request.user, semestre=semestre_actif)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valider une fiche de suivi"""
        fiche = self.get_object()

        if fiche.statut != StatutFiche.SOUMISE:
            return Response(
                {"detail": "Cette fiche ne peut plus être validée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        token_serializer = ValidationTokenSerializer(data=request.data)
        if not token_serializer.is_valid():
            return Response(token_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            untyped_token = UntypedToken(token_serializer.validated_data['validation_token'])

            if int(untyped_token['user_id']) != request.user.id:
                raise InvalidToken("Ce token ne vous appartient pas.")

            if untyped_token.get('token_class') != 'validation':
                raise InvalidToken("Ce n'est pas un token de validation.")

        except (InvalidToken, TokenError, TypeError, KeyError) as e:
            return Response(
                {"detail": f"Token de validation invalide ou expiré. Veuillez reconfirmer votre mot de passe."},
                status=status.HTTP_403_FORBIDDEN
            )

        fiche.statut = StatutFiche.VALIDEE
        fiche.date_validation = timezone.now()
        fiche.motif_refus = ""
        fiche.save()

        if fiche.delegue and fiche.delegue.fcm_token:
            send_notification(
                fiche.delegue.fcm_token,
                "Fiche validee",
                f"Votre fiche pour {fiche.ue.code_ue} a ete validee."
            )

        return Response(self.get_serializer(fiche).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        """Refuser une fiche de suivi"""
        fiche = self.get_object()

        if fiche.statut != StatutFiche.SOUMISE:
            return Response(
                {"detail": "Cette fiche ne peut plus être refusée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        motif = request.data.get('motif') or request.data.get('motif_refus')
        if not motif:
            return Response(
                {"motif": ["Ce champ est obligatoire."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        fiche.statut = StatutFiche.REFUSEE
        fiche.motif_refus = motif
        fiche.date_validation = timezone.now()
        fiche.save()

        if fiche.delegue and fiche.delegue.fcm_token:
            send_notification(
                fiche.delegue.fcm_token,
                "Fiche refusee",
                f"Votre fiche pour {fiche.ue.code_ue} a ete refusee. Motif: {motif}"
            )

        return Response(self.get_serializer(fiche).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='resoumettre')
    def resoumettre(self, request, pk=None):
        """Resoumettre une fiche refusee"""
        fiche = self.get_object()

        if fiche.statut != StatutFiche.REFUSEE:
            return Response(
                {"detail": "Seule une fiche refusee peut etre resoumise."},
                status=status.HTTP_400_BAD_REQUEST
            )

        fiche.statut = StatutFiche.SOUMISE
        fiche.motif_refus = ""
        fiche.date_validation = None
        fiche.save()

        if fiche.enseignant and fiche.enseignant.fcm_token:
            delegue_name = fiche.delegue.get_full_name() if fiche.delegue else "Un delegue"
            send_notification(
                fiche.enseignant.fcm_token,
                "Fiche resoumise",
                f"{delegue_name} a resoumis une fiche pour {fiche.ue.code_ue}."
            )

        return Response(self.get_serializer(fiche).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='en-attente')
    def en_attente(self, request):
        """Lister les fiches en attente de validation"""
        fiches = self.get_queryset().filter(statut=StatutFiche.SOUMISE)
        serializer = self.get_serializer(fiches, many=True)
        return Response(serializer.data)
