from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FicheSuivi, StatutFiche
from koursa.firebase_config import send_notification

@receiver(post_save, sender=FicheSuivi)
def envoyer_notification_nouvelle_fiche(sender, instance, created, **kwargs):
    if created:
        fiche = instance
        enseignant = fiche.enseignant
        delegue = fiche.delegue
        
        if enseignant and enseignant.fcm_token:
            print(f"Tentative d'envoi de notification à {enseignant.email} sur l'appareil {enseignant.fcm_token}")
            
            title = "Nouvelle Fiche à Valider"
            body = f"Le délégué {delegue.get_full_name()} a soumis une fiche pour le cours de {fiche.ue.code_ue}."
            
            send_notification(enseignant.fcm_token, title, body)
        else:
            print(f"L'enseignant {enseignant.email} n'a pas de token d'appareil, notification non envoyée.")