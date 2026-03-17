"""
Commande de rappels escalatifs pour les fiches manquantes.

Basee sur le PlanningCours (jour/heure habituels d'un cours),
cette commande envoie 3 niveaux de rappel aux delegues :

  Jour J   (jour du cours)   → Rappel 1 : "Tu n'as pas soumis la fiche de INF111"
  Jour J+1                   → Rappel 2 : "Rappel : fiche de INF111 toujours manquante"
  Jour J+2                   → Rappel 3 : "Dernier delai pour soumettre la fiche"

A executer quotidiennement via cron : 0 18 * * * python manage.py send_fiche_reminders
"""
import logging
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from academic.models import Semestre
from teaching.models import PlanningCours, FicheSuivi, StatutFiche
from notifications.models import Notification, NotificationType
from notifications.services import create_and_send_notification
from users.models import Utilisateur, Role

logger = logging.getLogger('koursa.notifications')


class Command(BaseCommand):
    help = 'Envoie des rappels escalatifs aux delegues pour les fiches manquantes basees sur le planning.'

    def handle(self, *args, **options):
        semestre_actif = Semestre.objects.filter(est_actif=True).first()
        if not semestre_actif:
            self.stdout.write(self.style.WARNING('Aucun semestre actif. Aucun rappel envoye.'))
            return

        today = date.today()
        today_weekday = today.weekday()  # 0=Lundi ... 6=Dimanche

        # Calculer la semaine courante (lundi-dimanche)
        monday = today - timedelta(days=today_weekday)
        sunday = monday + timedelta(days=6)

        self.stdout.write(f'Date: {today} | Semaine du {monday} au {sunday}')

        # Recuperer tous les plannings actifs du semestre
        plannings = PlanningCours.objects.filter(
            semestre=semestre_actif,
            est_actif=True,
        ).select_related('ue')

        rappels_envoyes = 0

        for planning in plannings:
            # Calculer le jour du cours cette semaine
            jour_cours = monday + timedelta(days=planning.jour_semaine)

            # Si le jour du cours est dans le futur, on ne fait rien
            if jour_cours > today:
                continue

            # Delta entre aujourd'hui et le jour du cours
            delta = (today - jour_cours).days

            # On envoie uniquement pour les jours 0, 1 et 2
            if delta > 2:
                continue

            # Verifier si une fiche existe deja pour cette UE cette semaine
            has_fiche = FicheSuivi.objects.filter(
                ue=planning.ue,
                date_cours__gte=monday,
                date_cours__lte=sunday,
                statut__in=[StatutFiche.SOUMISE, StatutFiche.VALIDEE],
            ).exists()

            if has_fiche:
                continue

            # Trouver les delegues concernes (ceux qui representent les niveaux de l'UE)
            niveaux_ids = planning.ue.niveaux.values_list('id', flat=True)
            delegues = Utilisateur.objects.filter(
                niveau_represente_id__in=niveaux_ids,
                roles__nom_role=Role.DELEGUE,
                statut='ACTIF',
            ).distinct()

            for delegue in delegues:
                # Construire un identifiant unique pour eviter les doublons
                # On utilise le related_object_id = planning.id * 100 + delta
                # pour distinguer rappel 1/2/3 de la meme semaine
                rappel_id = planning.id * 100 + delta

                already_sent = Notification.objects.filter(
                    recipient=delegue,
                    notification_type=NotificationType.RAPPEL_FICHE,
                    related_object_id=rappel_id,
                    created_at__date=today,
                ).exists()

                if already_sent:
                    continue

                # Determiner le niveau du rappel
                if delta == 0:
                    title = f"Fiche manquante - {planning.ue.code_ue}"
                    body = (
                        f"Vous n'avez pas encore soumis la fiche de suivi pour "
                        f"{planning.ue.code_ue} ({planning.ue.libelle_ue}) "
                        f"prevue aujourd'hui. Veuillez la soumettre."
                    )
                elif delta == 1:
                    title = f"Rappel - Fiche {planning.ue.code_ue} non soumise"
                    body = (
                        f"La fiche de suivi pour {planning.ue.code_ue} ({planning.ue.libelle_ue}) "
                        f"n'a toujours pas ete soumise. "
                        f"Veuillez la soumettre avant demain."
                    )
                else:  # delta == 2
                    title = f"Dernier delai - {planning.ue.code_ue}"
                    body = (
                        f"ATTENTION : Dernier jour pour soumettre la fiche de suivi "
                        f"de {planning.ue.code_ue} ({planning.ue.libelle_ue}). "
                        f"Apres aujourd'hui, vous ne pourrez plus la soumettre. "
                        f"Contactez votre chef de departement si necessaire."
                    )

                try:
                    create_and_send_notification(
                        recipient=delegue,
                        title=title,
                        body=body,
                        notification_type=NotificationType.RAPPEL_FICHE,
                        related_object_id=rappel_id,
                        send_email=(delta == 2),  # Email uniquement pour le dernier rappel
                    )
                    rappels_envoyes += 1
                    logger.info(
                        "Rappel %d/3 envoye a %s pour %s",
                        delta + 1, delegue.email, planning.ue.code_ue,
                    )
                except Exception as e:
                    logger.error(
                        "Erreur envoi rappel a %s pour %s: %s",
                        delegue.email, planning.ue.code_ue, str(e),
                    )

        self.stdout.write(self.style.SUCCESS(f'{rappels_envoyes} rappel(s) envoye(s).'))
