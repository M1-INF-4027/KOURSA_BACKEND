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
from notifications.services import create_and_send_notification
from notifications.models import NotificationType


class UniteEnseignementViewSet(viewsets.ModelViewSet):
    queryset = UniteEnseignement.objects.prefetch_related('enseignants', 'niveaux').select_related('semestre_obj__annee_academique').all()
    serializer_class = UniteEnseignementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return UniteEnseignement.objects.none()

        qs = self.queryset.all()

        # Scoper par semestre/annee si parametre fourni
        semestre_id = self.request.query_params.get('semestre_id')
        annee_id = self.request.query_params.get('annee_academique')
        if semestre_id:
            qs = qs.filter(semestre_obj_id=semestre_id)
        elif annee_id:
            qs = qs.filter(semestre_obj__annee_academique_id=annee_id)
        else:
            # Pour enseignant/delegue : scoper par defaut a l'annee active
            # Inclure aussi les UEs sans semestre_obj (pas encore assignees)
            is_admin_or_chef = user.roles.filter(
                nom_role__in=[Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]
            ).exists() or user.is_superuser or user.is_staff
            if not is_admin_or_chef:
                from academic.models import AnneeAcademique
                annee_active = AnneeAcademique.objects.filter(est_active=True).first()
                if annee_active:
                    qs = qs.filter(
                        Q(semestre_obj__annee_academique=annee_active) |
                        Q(semestre_obj__isnull=True)
                    )

        # Super admin et chef voient toutes les UEs (du scope)
        if user.roles.filter(nom_role=Role.SUPER_ADMIN).exists() or user.is_superuser or user.is_staff:
            return qs
        if user.roles.filter(nom_role=Role.CHEF_DEPARTEMENT).exists() and getattr(user, 'departement_gere', None):
            return qs.filter(niveaux__filiere__departement=user.departement_gere).distinct()

        if user.roles.filter(nom_role=Role.DELEGUE).exists():
            if user.niveau_represente:
                return qs.filter(niveaux=user.niveau_represente)
            return UniteEnseignement.objects.none()

        if user.roles.filter(nom_role=Role.ENSEIGNANT).exists():
            return qs.filter(enseignants=user)

        return UniteEnseignement.objects.none()


    @action(detail=False, methods=['get'], url_path='mes-delegues')
    def mes_delegues(self, request):
        """Retourne les delegues actifs des classes de l'enseignant connecte"""
        user = request.user
        if not user.roles.filter(nom_role=Role.ENSEIGNANT).exists():
            return Response(
                {"detail": "Acces reserve aux enseignants."},
                status=status.HTTP_403_FORBIDDEN
            )

        # UEs de cet enseignant
        mes_ues = self.get_queryset().filter(enseignants=user)

        # Niveaux distincts lies a ces UEs
        from academic.models import Niveau
        niveaux_ids = mes_ues.values_list('niveaux', flat=True).distinct()
        niveaux = Niveau.objects.filter(id__in=niveaux_ids).select_related('filiere').distinct()

        result = []
        for niveau in niveaux:
            # UEs de l'enseignant dans ce niveau
            ues_du_niveau = mes_ues.filter(niveaux=niveau)
            # Delegues actifs de ce niveau
            from users.models import Utilisateur, StatutCompte
            delegues = Utilisateur.objects.filter(
                niveau_represente=niveau,
                roles__nom_role=Role.DELEGUE,
                statut=StatutCompte.ACTIF,
            ).distinct()

            result.append({
                'niveau': {
                    'id': niveau.id,
                    'nom_niveau': niveau.nom_niveau,
                    'filiere_nom': niveau.filiere.nom_filiere if niveau.filiere else None,
                },
                'ues': [
                    {'id': ue.id, 'code_ue': ue.code_ue, 'libelle_ue': ue.libelle_ue}
                    for ue in ues_du_niveau
                ],
                'delegues': [
                    {
                        'id': d.id,
                        'nom_complet': f"{d.first_name} {d.last_name}",
                        'email': d.email,
                    }
                    for d in delegues
                ],
            })

        return Response(result)


class FicheSuiviViewSet(viewsets.ModelViewSet):
    queryset = FicheSuivi.objects.select_related('ue', 'delegue', 'enseignant', 'salle').prefetch_related('ue__niveaux__filiere').all()
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
            # Inclure aussi les fiches sans semestre (pas encore assigne)
            is_admin_or_chef = user.roles.filter(
                nom_role__in=[Role.SUPER_ADMIN, Role.CHEF_DEPARTEMENT]
            ).exists() or user.is_superuser
            if not is_admin_or_chef:
                from academic.models import AnneeAcademique
                annee_active = AnneeAcademique.objects.filter(est_active=True).first()
                if annee_active:
                    qs = qs.filter(
                        Q(semestre__annee_academique=annee_active) |
                        Q(semestre__isnull=True)
                    )

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

        if fiche.delegue:
            create_and_send_notification(
                recipient=fiche.delegue,
                title="Fiche validee",
                body=f"Votre fiche pour {fiche.ue.code_ue} a ete validee.",
                notification_type=NotificationType.FICHE_VALIDEE,
                related_object_id=fiche.id,
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

        if fiche.delegue:
            create_and_send_notification(
                recipient=fiche.delegue,
                title="Fiche refusee",
                body=f"Votre fiche pour {fiche.ue.code_ue} a ete refusee. Motif: {motif}",
                notification_type=NotificationType.FICHE_REFUSEE,
                related_object_id=fiche.id,
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

        if fiche.enseignant:
            delegue_name = fiche.delegue.get_full_name() if fiche.delegue else "Un delegue"
            create_and_send_notification(
                recipient=fiche.enseignant,
                title="Fiche resoumise",
                body=f"{delegue_name} a resoumis une fiche pour {fiche.ue.code_ue}.",
                notification_type=NotificationType.FICHE_RESOUMISE,
                related_object_id=fiche.id,
            )

        return Response(self.get_serializer(fiche).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='en-attente')
    def en_attente(self, request):
        """Lister les fiches en attente de validation"""
        fiches = self.get_queryset().filter(statut=StatutFiche.SOUMISE)
        serializer = self.get_serializer(fiches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='check-conflicts')
    def check_conflicts(self, request):
        """Detecter les conflits de salle et d'enseignant pour un creneau donne."""
        salle_id = request.data.get('salle')
        enseignant_id = request.data.get('enseignant')
        date_cours = request.data.get('date_cours')
        heure_debut = request.data.get('heure_debut')
        heure_fin = request.data.get('heure_fin')
        exclude_fiche_id = request.data.get('exclude_fiche_id')

        if not date_cours or not heure_debut or not heure_fin:
            return Response({'conflicts': []})

        # Base queryset : fiches SOUMISE ou VALIDEE, meme date, horaire chevauchant
        base_qs = FicheSuivi.objects.filter(
            date_cours=date_cours,
            statut__in=[StatutFiche.SOUMISE, StatutFiche.VALIDEE],
            heure_debut__lt=heure_fin,
            heure_fin__gt=heure_debut,
        ).select_related('ue', 'enseignant', 'salle')

        if exclude_fiche_id:
            base_qs = base_qs.exclude(pk=exclude_fiche_id)

        conflicts = []

        # Conflit salle
        if salle_id:
            salle_conflicts = base_qs.filter(salle_id=salle_id)
            for fiche in salle_conflicts:
                salle_nom = fiche.salle.nom_salle if fiche.salle else ''
                conflicts.append({
                    'type': 'salle',
                    'message': f"La salle {salle_nom} est deja occupee de {fiche.heure_debut.strftime('%H:%M')} a {fiche.heure_fin.strftime('%H:%M')} ({fiche.ue.code_ue})",
                    'fiche': {
                        'id': fiche.id,
                        'code_ue': fiche.ue.code_ue,
                        'enseignant': f"{fiche.enseignant.first_name} {fiche.enseignant.last_name}" if fiche.enseignant else None,
                        'heure_debut': fiche.heure_debut.strftime('%H:%M'),
                        'heure_fin': fiche.heure_fin.strftime('%H:%M'),
                    }
                })

        # Conflit enseignant
        if enseignant_id:
            enseignant_conflicts = base_qs.filter(enseignant_id=enseignant_id)
            for fiche in enseignant_conflicts:
                salle_nom = fiche.salle.nom_salle if fiche.salle else '?'
                conflicts.append({
                    'type': 'enseignant',
                    'message': f"L'enseignant a deja un cours de {fiche.heure_debut.strftime('%H:%M')} a {fiche.heure_fin.strftime('%H:%M')} ({fiche.ue.code_ue}) en salle {salle_nom}",
                    'fiche': {
                        'id': fiche.id,
                        'code_ue': fiche.ue.code_ue,
                        'salle': salle_nom,
                        'heure_debut': fiche.heure_debut.strftime('%H:%M'),
                        'heure_fin': fiche.heure_fin.strftime('%H:%M'),
                    }
                })

        return Response({'conflicts': conflicts})
