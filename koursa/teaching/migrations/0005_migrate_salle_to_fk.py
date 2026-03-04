"""
Migration en 3 etapes pour convertir FicheSuivi.salle de CharField vers ForeignKey(Salle).

1. Renomme salle -> salle_text
2. Ajoute salle comme ForeignKey
3. Data migration : pour chaque salle_text non vide, get_or_create une Salle et assigner le FK
4. Supprime salle_text
"""
import django.db.models.deletion
from django.db import migrations, models


def migrate_salle_data(apps, schema_editor):
    """Convertit les valeurs texte en FK vers Salle."""
    FicheSuivi = apps.get_model('teaching', 'FicheSuivi')
    Salle = apps.get_model('academic', 'Salle')

    for fiche in FicheSuivi.objects.exclude(salle_text='').exclude(salle_text__isnull=True):
        salle_text = fiche.salle_text.strip()
        if salle_text:
            salle, _ = Salle.objects.get_or_create(
                nom_salle__iexact=salle_text,
                defaults={'nom_salle': salle_text, 'est_active': True},
            )
            fiche.salle = salle
            fiche.save(update_fields=['salle'])


def reverse_migrate(apps, schema_editor):
    """Inverse : copie le nom de salle FK vers salle_text."""
    FicheSuivi = apps.get_model('teaching', 'FicheSuivi')
    for fiche in FicheSuivi.objects.filter(salle__isnull=False):
        fiche.salle_text = fiche.salle.nom_salle
        fiche.save(update_fields=['salle_text'])


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0004_create_salle_model'),
        ('teaching', '0004_populate_semestre_data'),
    ]

    operations = [
        # 1. Renommer salle -> salle_text
        migrations.RenameField(
            model_name='fichesuivi',
            old_name='salle',
            new_name='salle_text',
        ),
        # 2. Ajouter salle comme ForeignKey
        migrations.AddField(
            model_name='fichesuivi',
            name='salle',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='fiches_suivi',
                to='academic.salle',
                verbose_name='Salle',
            ),
        ),
        # 3. Data migration
        migrations.RunPython(migrate_salle_data, reverse_migrate),
        # 4. Supprimer salle_text
        migrations.RemoveField(
            model_name='fichesuivi',
            name='salle_text',
        ),
    ]
