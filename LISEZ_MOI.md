# Configuration CI/CD - Koursa Backend

## Ce qui a été fait

J'ai configuré tout le nécessaire pour le déploiement automatique de votre backend Django sur votre VPS.

### Fichiers créés:

1. **`.github/workflows/deploy.yml`** - Workflow GitHub Actions pour le déploiement automatique
2. **`deploy.sh`** - Script de déploiement à exécuter sur le serveur
3. **`deployment/koursa-backend.service`** - Configuration systemd pour gérer l'application
4. **`deployment/nginx.conf`** - Configuration Nginx pour le reverse proxy
5. **`koursa/.env.example`** - Exemple de fichier de configuration
6. **`INSTRUCTIONS_VPS.md`** - Instructions détaillées étape par étape
7. **`DEPLOYMENT.md`** - Guide de déploiement complet (générique)

### Modifications apportées:

- **`koursa/koursa/settings.py`** - Ajout du support de la variable d'environnement `ALLOWED_HOSTS`

## Ce que vous devez faire maintenant

### Étape 1: Configuration GitHub (5 minutes)

1. Générer une paire de clés SSH pour GitHub Actions
2. Ajouter 4 secrets dans votre repository GitHub:
   - `VPS_HOST`: 84.247.172.198
   - `VPS_USERNAME`: softengine
   - `VPS_SSH_KEY`: (votre clé privée SSH)
   - `VPS_PORT`: 22

### Étape 2: Push du code

```bash
git add .
git commit -m "Configuration CI/CD"
git push origin main
```

### Étape 3: Configuration du serveur VPS (30 minutes)

1. Connectez-vous à votre VPS: `ssh koursa@84.247.172.198`
2. Suivez les instructions détaillées dans **`INSTRUCTIONS_VPS.md`**

Le fichier **INSTRUCTIONS_VPS.md** contient toutes les commandes à copier-coller étape par étape.

## Après la configuration

Une fois tout configuré:

1. **Déploiement automatique**: À chaque `git push origin main`, votre application se déploie automatiquement
2. **Accès à l'API**: `http://84.247.172.198:8082`
3. **Admin Django**: `http://84.247.172.198:8082/admin/`
4. **Documentation**: `http://84.247.172.198:8082/swagger/` (si configuré)

## Architecture du déploiement

```
┌─────────────────┐
│  Vous (local)   │
│   git push      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GitHub Actions  │
│   CI/CD         │
└────────┬────────┘
         │
         ▼ (SSH)
┌─────────────────┐
│   VPS Server    │
│  84.247.172.198 │
├─────────────────┤
│   Nginx :8082   │ ← Vous accédez ici
│       ↓         │
│  Gunicorn :8002 │
│       ↓         │
│ Django App      │
│       ↓         │
│   PostgreSQL    │
└─────────────────┘
```

## Commandes utiles

### Sur votre VPS:

```bash
# Voir les logs en temps réel
sudo journalctl -u koursa-backend -f

# Redémarrer l'application
sudo systemctl restart koursa-backend

# Voir le statut
sudo systemctl status koursa-backend

# Déploiement manuel
cd /var/www/koursa-backend && ./deploy.sh
```

## Support

Pour toute question ou problème:

1. Consultez **INSTRUCTIONS_VPS.md** pour les instructions détaillées
2. Consultez la section "Dépannage" dans **DEPLOYMENT.md**
3. Vérifiez les logs avec `sudo journalctl -u koursa-backend -f`

## Workflow de développement

```bash
# 1. Développer localement
# Faire vos modifications...

# 2. Tester localement
python manage.py runserver

# 3. Commiter et pusher
git add .
git commit -m "Description des changements"
git push origin main

# 4. GitHub Actions déploie automatiquement sur le VPS
# Vérifier sur: GitHub → Actions

# 5. Vérifier le déploiement
curl http://84.247.172.198:8082
```

**C'est tout! Bon déploiement!** 🚀
