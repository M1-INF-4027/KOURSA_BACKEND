from django.db import models


class EmailWhitelist(models.Model):
    ROLE_CHOICES = [
        ('ENSEIGNANT', 'Enseignant'),
        ('DELEGUE', 'Délégué'),
    ]

    email = models.EmailField(
        unique=True,
        verbose_name="Email autorisé",
    )
    role_type = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name="Type de rôle",
    )
    departement = models.ForeignKey(
        'academic.Departement',
        on_delete=models.CASCADE,
        related_name='emails_whitelist',
        verbose_name="Département",
    )
    ajoute_par = models.ForeignKey(
        'users.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emails_whitelistes',
        verbose_name="Ajouté par",
    )
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email Autorisé"
        verbose_name_plural = "Emails Autorisés"
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.email} ({self.get_role_type_display()})"
