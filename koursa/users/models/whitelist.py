from django.db import models

class EnseignantWhitelist(models.Model):
    email = models.EmailField(
        unique=True,
        verbose_name="Email de l'enseignant autorisé",
        help_text="L'adresse email institutionnelle de l'enseignant qui a le droit de créer un compte."
    )
    
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email Enseignant Autorisé"
        verbose_name_plural = "Emails Enseignants Autorisés"
        ordering = ['email']

    def __str__(self):
        return self.email