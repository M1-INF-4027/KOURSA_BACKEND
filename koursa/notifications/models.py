from django.db import models
from django.conf import settings


class NotificationType(models.TextChoices):
    FICHE_SOUMISE = 'FICHE_SOUMISE', 'Fiche soumise'
    FICHE_VALIDEE = 'FICHE_VALIDEE', 'Fiche validee'
    FICHE_REFUSEE = 'FICHE_REFUSEE', 'Fiche refusee'
    FICHE_RESOUMISE = 'FICHE_RESOUMISE', 'Fiche resoumise'
    COMPTE_APPROUVE = 'COMPTE_APPROUVE', 'Compte approuve'


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
    )
    related_object_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.recipient}"
