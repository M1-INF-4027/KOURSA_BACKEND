import logging
from django.core.mail import send_mail
from django.conf import settings
from .models import Notification
from koursa.firebase_config import send_notification_with_data

logger = logging.getLogger('koursa.notifications')


def send_email_notification(recipient_email, subject, body):
    """Envoie un email de notification."""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info("Email envoye a %s : %s", recipient_email, subject)
        return True
    except Exception as e:
        logger.warning("Echec envoi email a %s : %s", recipient_email, str(e))
        return False


def create_and_send_notification(recipient, title, body, notification_type, related_object_id=None, send_email=False):
    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        body=body,
        notification_type=notification_type,
        related_object_id=related_object_id,
    )

    if recipient.fcm_token:
        data = {
            'notification_id': str(notification.id),
            'type': notification_type,
            'related_object_id': str(related_object_id) if related_object_id else '',
        }
        success = send_notification_with_data(recipient.fcm_token, title, body, data)
        if success:
            logger.info("Notification envoyee a %s (id=%s).", recipient.email, notification.id)
        else:
            logger.warning("Echec envoi FCM a %s (id=%s).", recipient.email, notification.id)
    else:
        logger.info("Pas de token FCM pour %s, notification sauvegardee en BDD uniquement.", recipient.email)

    if send_email and recipient.email:
        send_email_notification(recipient.email, title, body)

    return notification
