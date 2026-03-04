from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsHoDOrSuperAdmin
from .models import Notification, NotificationType
from .serializers import NotificationSerializer
from .services import create_and_send_notification
from teaching.models import UniteEnseignement
from academic.models import Departement
from users.models import Utilisateur, Role


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'detail': 'Toutes les notifications ont ete marquees comme lues.'})


class AlertEnseignantView(APIView):
    """Chef de departement alerte un enseignant sur une fiche manquante."""
    permission_classes = [IsAuthenticated, IsHoDOrSuperAdmin]

    def post(self, request):
        enseignant_id = request.data.get('enseignant_id')
        ue_id = request.data.get('ue_id')
        semaine = request.data.get('semaine')
        message = request.data.get('message', '')

        if not enseignant_id or not ue_id or not semaine:
            return Response(
                {'detail': 'enseignant_id, ue_id et semaine sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            enseignant = Utilisateur.objects.get(id=enseignant_id)
        except Utilisateur.DoesNotExist:
            return Response({'detail': 'Enseignant introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            ue = UniteEnseignement.objects.get(id=ue_id)
        except UniteEnseignement.DoesNotExist:
            return Response({'detail': 'UE introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Valider que l'enseignant est dans le departement du chef
        is_super = request.user.roles.filter(nom_role=Role.SUPER_ADMIN).exists()
        if not is_super:
            try:
                departement = Departement.objects.get(chef_departement=request.user)
            except Departement.DoesNotExist:
                return Response(
                    {'detail': 'Vous n\'etes assigne a aucun departement.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Verifier que l'UE est dans le departement du chef
            if not ue.niveaux.filter(filiere__departement=departement).exists():
                return Response(
                    {'detail': 'Cette UE n\'appartient pas a votre departement.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        title = f"Fiche manquante - {ue.code_ue}"
        body = (
            f"Le chef de departement vous rappelle qu'aucune fiche de suivi n'a ete soumise "
            f"pour l'UE {ue.code_ue} ({ue.libelle_ue}) pour la semaine du {semaine}."
        )
        if message:
            body += f"\n\nMessage du chef : {message}"

        notification = create_and_send_notification(
            recipient=enseignant,
            title=title,
            body=body,
            notification_type=NotificationType.ALERTE_CHEF,
            related_object_id=ue.id,
            send_email=True,
        )

        return Response(
            {'detail': 'Alerte envoyee avec succes.', 'notification_id': notification.id},
            status=status.HTTP_201_CREATED,
        )


class AlertDelegueView(APIView):
    """Enseignant alerte un delegue sur une fiche manquante."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        delegue_id = request.data.get('delegue_id')
        ue_id = request.data.get('ue_id')
        semaine = request.data.get('semaine')
        message = request.data.get('message', '')

        if not delegue_id or not ue_id or not semaine:
            return Response(
                {'detail': 'delegue_id, ue_id et semaine sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            delegue = Utilisateur.objects.get(id=delegue_id)
        except Utilisateur.DoesNotExist:
            return Response({'detail': 'Delegue introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            ue = UniteEnseignement.objects.get(id=ue_id)
        except UniteEnseignement.DoesNotExist:
            return Response({'detail': 'UE introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Valider que l'enseignant est affecte a cette UE
        if not ue.enseignants.filter(id=request.user.id).exists():
            return Response(
                {'detail': 'Vous n\'etes pas affecte a cette UE.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valider que le delegue represente un niveau lie a cette UE
        if delegue.niveau_represente is None or not ue.niveaux.filter(id=delegue.niveau_represente_id).exists():
            return Response(
                {'detail': 'Ce delegue ne represente pas un niveau lie a cette UE.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        enseignant_nom = f"{request.user.last_name} {request.user.first_name}".strip()
        title = f"Rappel fiche - {ue.code_ue}"
        body = (
            f"L'enseignant {enseignant_nom} vous rappelle de soumettre la fiche de suivi "
            f"pour l'UE {ue.code_ue} ({ue.libelle_ue}) pour la semaine du {semaine}."
        )
        if message:
            body += f"\n\nMessage de l'enseignant : {message}"

        notification = create_and_send_notification(
            recipient=delegue,
            title=title,
            body=body,
            notification_type=NotificationType.RAPPEL_ENSEIGNANT,
            related_object_id=ue.id,
            send_email=True,
        )

        return Response(
            {'detail': 'Rappel envoye avec succes.', 'notification_id': notification.id},
            status=status.HTTP_201_CREATED,
        )
