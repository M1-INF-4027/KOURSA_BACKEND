import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FicheSuivi, StatutFiche
from notifications.services import create_and_send_notification
from notifications.models import NotificationType

logger = logging.getLogger('koursa.notifications')

@receiver(post_save, sender=FicheSuivi)
def envoyer_notification_nouvelle_fiche(sender, instance, created, **kwargs):
    if not created:
        return

    fiche = instance
    enseignant = fiche.enseignant
    delegue = fiche.delegue

    if not enseignant:
        logger.warning("Fiche %s creee sans enseignant assigne.", fiche.id)
        return

    try:
        delegue_name = delegue.get_full_name() if delegue else "Un delegue"
        title = "Nouvelle Fiche a Valider"
        body = f"Le delegue {delegue_name} a soumis une fiche pour le cours de {fiche.ue.code_ue}."

        create_and_send_notification(
            recipient=enseignant,
            title=title,
            body=body,
            notification_type=NotificationType.FICHE_SOUMISE,
            related_object_id=fiche.id,
        )
    except Exception as e:
        # Ne jamais laisser une erreur de notification bloquer la creation de fiche
        logger.error(
            "Erreur lors de l'envoi de notification pour la fiche %s: %s",
            fiche.id, str(e),
            exc_info=True
        )
