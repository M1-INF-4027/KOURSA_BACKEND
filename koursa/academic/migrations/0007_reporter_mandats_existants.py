from django.db import migrations


def reporter(apps, schema_editor):
    """
    Donne un mandat aux delegues deja enregistres, sur l'annee active.

    Sans cela, l'arrivee du modele ferait disparaitre la classe de tous les
    delegues existants : leur niveau est dans Utilisateur.niveau_represente,
    mais plus rien ne le rattacherait a une annee. Le mandat est cree
    approuve, puisque ces comptes ont deja ete valides par le chef.
    """
    Utilisateur = apps.get_model('users', 'Utilisateur')
    AnneeAcademique = apps.get_model('academic', 'AnneeAcademique')
    MandatDelegue = apps.get_model('academic', 'MandatDelegue')

    annee = AnneeAcademique.objects.filter(est_active=True).first()
    if not annee:
        # Aucune annee active : rien a rattacher, et rien a perdre non plus.
        return

    delegues = Utilisateur.objects.filter(
        roles__nom_role='Délégué', niveau_represente__isnull=False
    ).distinct()

    for delegue in delegues:
        MandatDelegue.objects.get_or_create(
            utilisateur=delegue,
            annee_academique=annee,
            defaults={'niveau_id': delegue.niveau_represente_id, 'statut': 'APPROUVE'},
        )


def annuler(apps, schema_editor):
    """Le report est rejouable : on retire ce qu'il a cree."""
    MandatDelegue = apps.get_model('academic', 'MandatDelegue')
    MandatDelegue.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0006_mandat_delegue'),
        ('users', '0008_alter_utilisateur_options_and_more'),
    ]

    operations = [
        migrations.RunPython(reporter, annuler),
    ]
