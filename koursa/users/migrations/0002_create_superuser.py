from django.db import migrations
import os 

def create_superuser(apps, schema_editor):
    Utilisateur = apps.get_model('users', 'Utilisateur')

    
    SUPERUSER_EMAIL = os.environ.get('SUPERUSER_EMAIL')
    SUPERUSER_PASSWORD = os.environ.get('SUPERUSER_PASSWORD')

    if SUPERUSER_EMAIL and SUPERUSER_PASSWORD:
        if not Utilisateur.objects.filter(email=SUPERUSER_EMAIL).exists():
            print(f"Création du super-utilisateur avec l'email : {SUPERUSER_EMAIL}")
            Utilisateur.objects.create_superuser(
                email=SUPERUSER_EMAIL,
                password=SUPERUSER_PASSWORD,
                first_name='Admin', 
                last_name='Koursa'  
            )
        else:
            print(f"Le super-utilisateur avec l'email {SUPERUSER_EMAIL} existe déjà.")
    else:
        print("Variables d'environnement SUPERUSER_EMAIL ou SUPERUSER_PASSWORD non définies. Création du super-utilisateur ignorée.")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]