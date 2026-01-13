# Changelog - Configuration de Déploiement

## Dernières mises à jour - 13 janvier 2026

### ✅ Configurations mises à jour

#### 1. Mot de passe de la base de données
- **Ancien:** `Koursa2026@Secure!` (dans certains fichiers)
- **Nouveau:** `koursa2026` (standardisé partout)
- **Fichiers mis à jour:**
  - `INSTRUCTIONS_VPS.md`
  - `QUICKSTART.md`
  - `koursa/.env.example`

#### 2. Ports configurés
- **Port externe (Nginx):** 8082
- **Port interne (Gunicorn):** 8002
- **Raison:** Les ports 8080 et 8081 étaient déjà utilisés par d'autres projets Docker
- **Fichiers mis à jour:**
  - `deployment/koursa-backend.service`
  - `deployment/nginx.conf`
  - `deploy.sh`
  - `.github/workflows/deploy.yml`
  - `LISEZ_MOI.md`
  - `DEPLOYMENT.md` (note ajoutée)

#### 3. Chemins d'accès
Tous les chemins ont été adaptés à la structure réelle sur le serveur:
```
/var/www/koursa-backend/
└── KOURSA_BACKEND/
    └── koursa/
        ├── venv/
        ├── manage.py
        └── koursa/
```

#### 4. Configuration CSRF
Ajout de `CSRF_TRUSTED_ORIGINS` dans `settings.py`:
```python
CSRF_TRUSTED_ORIGINS = [
    'http://84.247.183.206:8082',
    'http://127.0.0.1:8082',
    'http://localhost:8082',
]
```

### 📝 Nouveaux fichiers créés

1. **INSTRUCTIONS_FINALES.md** - Guide complet avec toutes les commandes
2. **QUICKSTART.md** - Guide rapide en 3 étapes
3. **LISEZ_MOI.md** - Vue d'ensemble en français
4. **CHANGELOG_DEPLOYMENT.md** - Ce fichier

### 🔧 Configuration actuelle du serveur

#### Base de données PostgreSQL
```
Base: koursa_db
Utilisateur: koursa_user
Mot de passe: koursa2026
Host: localhost
Port: 5432
```

#### Serveur VPS
```
IP: 84.247.183.206
Utilisateur: softengine
Port SSH: 22
```

#### Services
```
Service systemd: koursa-backend.service
Port Gunicorn: 8002 (127.0.0.1)
Port Nginx: 8082 (0.0.0.0)
```

#### URLs d'accès
```
API: http://84.247.183.206:8082
Admin: http://84.247.183.206:8082/admin/
Swagger: http://84.247.183.206:8082/swagger/
ReDoc: http://84.247.183.206:8082/redoc/
```

### 🚀 Workflow de déploiement

#### Automatique (CI/CD)
```
git push origin main
  ↓
GitHub Actions
  ↓
SSH vers VPS (84.247.183.206)
  ↓
git pull + pip install + migrations + collectstatic
  ↓
systemctl restart koursa-backend
  ↓
API disponible sur http://84.247.183.206:8082
```

#### Manuel
```bash
cd /var/www/koursa-backend
git pull origin main
cd KOURSA_BACKEND
./deploy.sh
```

### 📊 Structure des fichiers de déploiement

```
KOURSA_BACKEND/
├── .github/
│   └── workflows/
│       └── deploy.yml                 # Workflow GitHub Actions
├── deployment/
│   ├── koursa-backend.service        # Service systemd
│   └── nginx.conf                    # Configuration Nginx
├── koursa/
│   ├── .env.example                  # Template variables d'environnement
│   └── requirements.txt
├── deploy.sh                         # Script de déploiement
├── README.md                         # Documentation principale
├── INSTRUCTIONS_FINALES.md           # Guide complet (RECOMMANDÉ)
├── QUICKSTART.md                     # Guide rapide
├── INSTRUCTIONS_VPS.md               # Instructions détaillées VPS
├── DEPLOYMENT.md                     # Guide générique
├── LISEZ_MOI.md                      # Vue d'ensemble FR
└── CHANGELOG_DEPLOYMENT.md           # Ce fichier
```

### ⚠️ Points d'attention

1. **Permissions sudo:** L'utilisateur `softengine` doit avoir les droits sudo pour `systemctl restart koursa-backend`
2. **Clés SSH:** La clé publique de GitHub Actions doit être dans `~/.ssh/authorized_keys`
3. **Pare-feu:** Le port 8082 doit être ouvert (`sudo ufw allow 8082/tcp`)
4. **Groupe www-data:** L'utilisateur `softengine` doit être dans le groupe `www-data`

### 🔍 Commandes de diagnostic

```bash
# Vérifier le service
sudo systemctl status koursa-backend

# Vérifier les ports
sudo ss -tlnp | grep 8002  # Gunicorn
sudo ss -tlnp | grep 8082  # Nginx

# Voir les logs
sudo journalctl -u koursa-backend -f
sudo tail -f /var/log/koursa-backend/error.log
sudo tail -f /var/log/nginx/koursa-backend-error.log

# Tester l'API
curl http://127.0.0.1:8082/
curl http://84.247.183.206:8082/admin/
```

### 📌 Prochaines étapes

1. **Configurer les secrets GitHub:**
   - VPS_HOST: 84.247.183.206
   - VPS_USERNAME: softengine
   - VPS_SSH_KEY: (clé privée)
   - VPS_PORT: 22

2. **Tester le déploiement manuel:**
   ```bash
   ssh softengine@84.247.183.206
   cd /var/www/koursa-backend
   git pull origin main
   sudo systemctl restart koursa-backend
   ```

3. **Tester l'accès à l'API:**
   - Ouvrir http://84.247.183.206:8082/admin/
   - Se connecter avec un compte admin
   - Vérifier que le CSRF fonctionne

4. **Activer le CI/CD:**
   - Ajouter la clé SSH publique sur le serveur
   - Configurer les secrets GitHub
   - Push du code pour tester le déploiement automatique

### 🎯 Configuration terminée

Tous les fichiers sont maintenant à jour avec:
- ✅ Le bon mot de passe de base de données (koursa2026)
- ✅ Les bons ports (8082/8002)
- ✅ Les bons chemins d'accès
- ✅ La configuration CSRF
- ✅ La documentation complète

Le projet est prêt pour le déploiement!
