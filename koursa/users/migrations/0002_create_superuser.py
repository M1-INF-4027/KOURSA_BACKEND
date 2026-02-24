from django.db import migrations
import os
from django.contrib.auth.hashers import make_password


def create_roles_and_superuser(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    Utilisateur = apps.get_model('users', 'Utilisateur')

    # Creer les 4 roles de base
    role_names = [
        'Super Administrateur',
        'Chef de Département',
        'Enseignant',
        'Délégué',
    ]
    for nom in role_names:
        Role.objects.get_or_create(nom_role=nom)
    print(f"Roles crees : {', '.join(role_names)}")

    # Creer le super admin
    SUPERUSER_EMAIL = os.environ.get('SUPERUSER_EMAIL')
    SUPERUSER_PASSWORD = os.environ.get('SUPERUSER_PASSWORD')

    if SUPERUSER_EMAIL and SUPERUSER_PASSWORD:
        if not Utilisateur.objects.filter(email=SUPERUSER_EMAIL).exists():
            print(f"Création du super-utilisateur avec l'email : {SUPERUSER_EMAIL}")

            hashed_password = make_password(SUPERUSER_PASSWORD)

            user = Utilisateur.objects.create(
                email=SUPERUSER_EMAIL,
                password=hashed_password,
                first_name='Admin',
                last_name='Koursa',
                is_staff=True,
                is_superuser=True,
                statut='ACTIF'
            )

            # Assigner le role Super Administrateur
            super_admin_role = Role.objects.get(nom_role='Super Administrateur')
            user.roles.add(super_admin_role)
            print(f"Role 'Super Administrateur' assigne a {SUPERUSER_EMAIL}")

        else:
            print(f"Le super-utilisateur avec l'email {SUPERUSER_EMAIL} existe déjà.")
    else:
        print("Variables d'environnement SUPERUSER_EMAIL ou SUPERUSER_PASSWORD non définies. Création du super-utilisateur ignorée.")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_roles_and_superuser),
    ]