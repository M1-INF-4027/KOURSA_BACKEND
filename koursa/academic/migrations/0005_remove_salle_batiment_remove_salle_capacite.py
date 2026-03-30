from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0004_create_salle_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='salle',
            name='batiment',
        ),
        migrations.RemoveField(
            model_name='salle',
            name='capacite',
        ),
    ]
