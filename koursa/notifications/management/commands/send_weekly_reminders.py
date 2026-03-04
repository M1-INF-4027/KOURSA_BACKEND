import logging
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from academic.models import Semestre
from teaching.models import UniteEnseignement, FicheSuivi, StatutFiche
from notifications.models import Notification, NotificationType
from notifications.services import create_and_send_notification
from users.models import Utilisateur

logger = logging.getLogger('koursa.notifications')


class Command(BaseCommand):
    help = 'Envoie des rappels automatiques pour les fiches manquantes de la semaine.'

    def handle(self, *args, **options):
        semestre_actif = Semestre.objects.filter(est_actif=True).first()
        if not semestre_actif:
            self.stdout.write(self.style.WARNING('Aucun semestre actif. Aucun rappel envoye.'))
            return

        # Calculer la semaine courante (lundi-dimanche)
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        semaine_str = str(monday)

        self.stdout.write(f'Semaine du {monday} au {sunday}')

        # Toutes les UEs du semestre actif
        ues = UniteEnseignement.objects.filter(
            semestre_obj=semestre_actif,
        ).prefetch_related('enseignants', 'niveaux').distinct()

        rappels_enseignants = 0
        rappels_delegues = 0

        for ue in ues:
            # Verifier si une fiche SOUMISE ou VALIDEE existe pour cette semaine
            has_fiche = FicheSuivi.objects.filter(
                ue=ue,
                date_cours__gte=monday,
                date_cours__lte=sunday,
                statut__in=[StatutFiche.SOUMISE, StatutFiche.VALIDEE],
            ).exists()

            if has_fiche:
                continue

            # Rappels enseignants
            for enseignant in ue.enseignants.all():
                # Eviter doublon
                already_sent = Notification.objects.filter(
                    recipient=enseignant,
                    notification_type=NotificationType.RAPPEL_AUTO,
                    related_object_id=ue.id,
                    created_at__date__gte=monday,
                ).exists()
                if already_sent:
                    continue

                create_and_send_notification(
                    recipient=enseignant,
                    title=f"Rappel - Fiche manquante {ue.code_ue}",
                    body=(
                        f"Aucune fiche de suivi n'a ete soumise pour l'UE {ue.code_ue} "
                        f"({ue.libelle_ue}) cette semaine ({monday} - {sunday}). "
                        f"Veuillez vous assurer qu'un delegue soumette la fiche."
                    ),
                    notification_type=NotificationType.RAPPEL_AUTO,
                    related_object_id=ue.id,
                    send_email=True,
                )
                rappels_enseignants += 1

            # Rappels delegues (via les niveaux de l'UE)
            for niveau in ue.niveaux.all():
                delegues = Utilisateur.objects.filter(niveau_represente=niveau)
                for delegue in delegues:
                    already_sent = Notification.objects.filter(
                        recipient=delegue,
                        notification_type=NotificationType.RAPPEL_AUTO,
                        related_object_id=ue.id,
                        created_at__date__gte=monday,
                    ).exists()
                    if already_sent:
                        continue

                    create_and_send_notification(
                        recipient=delegue,
                        title=f"Rappel - Fiche a soumettre {ue.code_ue}",
                        body=(
                            f"Aucune fiche de suivi n'a ete soumise pour l'UE {ue.code_ue} "
                            f"({ue.libelle_ue}) cette semaine ({monday} - {sunday}). "
                            f"Veuillez soumettre votre fiche de suivi."
                        ),
                        notification_type=NotificationType.RAPPEL_AUTO,
                        related_object_id=ue.id,
                        send_email=True,
                    )
                    rappels_delegues += 1

        self.stdout.write(self.style.SUCCESS(
            f'Rappels envoyes : {rappels_enseignants} enseignants, {rappels_delegues} delegues.'
        ))
