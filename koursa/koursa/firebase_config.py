import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import os
import logging

logger = logging.getLogger('koursa.firebase')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            cred_path = os.path.join(settings.BASE_DIR, 'firebase-credentials.json')

            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialise avec succes.")
            else:
                logger.warning("firebase-credentials.json introuvable. Les notifications ne fonctionneront pas.")
        except Exception as e:
            logger.error(f"Erreur initialisation Firebase : {e}")


def send_notification(token, title, body):

    if not firebase_admin._apps:
        logger.warning("Firebase non initialise. Notification non envoyee.")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(
                    channel_id='koursa_default',
                    sound='default',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default'),
                ),
            ),
            token=token,
        )
        response = messaging.send(message)
        logger.info(f'Notification envoyee : {response}')
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification : {e}")
        return False


def send_notification_with_data(token, title, body, data=None):
    if not firebase_admin._apps:
        logger.warning("Firebase non initialise. Notification non envoyee.")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(
                    channel_id='koursa_default',
                    sound='default',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default'),
                ),
            ),
            data=data or {},
            token=token,
        )
        response = messaging.send(message)
        logger.info(f'Notification envoyee : {response}')
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification : {e}")
        return False

