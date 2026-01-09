import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import os

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            cred_path = os.path.join(settings.BASE_DIR, 'firebase-credentials.json')
            
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print("Firebase a été initialisé avec succès.")
            else:
                print("Le fichier firebase-credentials.json n'a pas été trouvé. Les notifications ne fonctionneront pas.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation de Firebase : {e}")


def send_notification(token, title, body):
    
    if not firebase_admin._apps:
        print("Firebase n'est pas initialisé. Impossible d'envoyer la notification.")
        return False
        
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
        )
        response = messaging.send(message)
        print('Notification envoyée avec succès :', response)
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de la notification : {e}")
        return False

