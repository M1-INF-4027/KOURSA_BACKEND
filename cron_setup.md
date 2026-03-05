# Configuration des taches automatiques (cron)

## Rappels automatiques hebdomadaires

La commande `send_weekly_reminders` envoie des notifications et emails aux enseignants et delegues pour les UEs sans fiche de suivi soumise durant la semaine courante.

### Installation cron (Linux/Mac)

```bash
# Rappels automatiques chaque vendredi a 18h
0 18 * * 5 cd /path/to/KOURSA_BACKEND/koursa && python manage.py send_weekly_reminders
```

### Planificateur de taches (Windows)

```
schtasks /create /tn "KoursaWeeklyReminders" /tr "cd C:\path\to\KOURSA_BACKEND\koursa && python manage.py send_weekly_reminders" /sc weekly /d FRI /st 18:00
```

### Execution manuelle

```bash
cd KOURSA_BACKEND/koursa
python manage.py send_weekly_reminders
```
