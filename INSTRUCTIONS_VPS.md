# Instructions de Déploiement - Koursa Backend
## Configuration spécifique pour votre VPS

**Serveur VPS:** softengine@84.247.183.206

---

## PARTIE 1: À FAIRE SUR VOTRE ORDINATEUR LOCAL

### 1. Générer la clé SSH pour GitHub Actions

```bash
ssh-keygen -t ed25519 -C "github-actions-koursa" -f ~/.ssh/koursa_deploy
```

Appuyez sur Entrée pour accepter l'emplacement par défaut et ne mettez pas de passphrase.

### 2. Afficher la clé publique (à ajouter sur le serveur)

```bash
cat ~/.ssh/koursa_deploy.pub
```

**Copiez cette clé publique, vous en aurez besoin dans la partie 2.**

### 3. Afficher la clé privée (à ajouter dans GitHub)

```bash
cat ~/.ssh/koursa_deploy
```

**Copiez cette clé privée, vous en aurez besoin pour GitHub.**

### 4. Configurer les secrets GitHub

Allez sur votre repository GitHub:
- **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Créez ces 4 secrets:

| Nom du secret | Valeur |
|---------------|--------|
| `VPS_HOST` | `84.247.183.206` |
| `VPS_USERNAME` | `softengine` |
| `VPS_SSH_KEY` | Le contenu de `~/.ssh/koursa_deploy` (clé privée complète) |
| `VPS_PORT` | `22` |

### 5. Push votre code

```bash
cd KOURSA_BACKEND
git add .
git commit -m "Configuration CI/CD"
git push origin main
```

---

## PARTIE 2: À FAIRE SUR VOTRE SERVEUR VPS

### 1. Connexion au serveur

```bash
ssh softengine@84.247.183.206
```

### 2. Ajouter la clé publique SSH

```bash
# Créer le répertoire .ssh si nécessaire
mkdir -p ~/.ssh

# Ouvrir le fichier authorized_keys
nano ~/.ssh/authorized_keys

# Collez la clé publique générée à l'étape 1.2 (PARTIE 1)
# Sauvegardez avec Ctrl+O puis Entrée, et quittez avec Ctrl+X

# Définir les bonnes permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### 3. Installation des dépendances

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation de Python, PostgreSQL, Nginx et Git
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git
```

### 4. Configuration de PostgreSQL

```bash
# Connexion à PostgreSQL
sudo -u postgres psql
```

Dans le shell PostgreSQL, copiez et exécutez ligne par ligne:

```sql
CREATE DATABASE koursa_db;
CREATE USER koursa_user WITH PASSWORD 'koursa2026';
ALTER ROLE koursa_user SET client_encoding TO 'utf8';
ALTER ROLE koursa_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE koursa_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE koursa_db TO koursa_user;
\q
```

### 5. Cloner le projet

```bash
# Créer le répertoire pour l'application
sudo mkdir -p /var/www/koursa-backend
sudo chown softengine:softengine /var/www/koursa-backend
cd /var/www/koursa-backend

# Cloner votre repository (remplacez par votre URL GitHub)
git clone https://github.com/VOTRE_USERNAME/VOTRE_REPO.git .

# Créer l'environnement virtuel Python
python3 -m venv venv

# Activer l'environnement virtuel
source venv/bin/activate

# Installer les dépendances
pip install -r koursa/requirements.txt
```

### 6. Créer le fichier .env

```bash
# Générer une SECRET_KEY
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Créer le fichier .env
nano /var/www/koursa-backend/koursa/.env
```

Copiez et modifiez ceci (remplacez YOUR_SECRET_KEY par celle générée):

```env
SECRET_KEY=m9xcx(r$4^dhl1d1c^*l8jq(^_@m@$7&ek1bv$112r4+pfit=e
DEBUG=False
DATABASE_URL=postgresql://koursa_user:Koursa2026@Secure!@localhost:5432/koursa_db
ALLOWED_HOSTS=84.247.183.206
```

Sauvegardez avec `Ctrl+O` puis `Entrée`, et quittez avec `Ctrl+X`.

### 7. Migrations et fichiers statiques

```bash
cd /var/www/koursa-backend/koursa
source ../venv/bin/activate

# Exécuter les migrations
python manage.py migrate

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Créer un superuser (optionnel - pour accéder à l'admin)
python manage.py createsuperuser
```

### 8. Créer les répertoires de logs

```bash
sudo mkdir -p /var/log/koursa-backend
sudo chown www-data:www-data /var/log/koursa-backend
```

### 9. Configurer le service systemd

```bash
# Copier le fichier de service
sudo cp /var/www/koursa-backend/deployment/koursa-backend.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable koursa-backend

# Démarrer le service
sudo systemctl start koursa-backend

# Vérifier le statut
sudo systemctl status koursa-backend
```

Si tout est OK, vous devriez voir "active (running)" en vert.

### 10. Configurer Nginx

```bash
# Copier la configuration nginx
sudo cp /var/www/koursa-backend/deployment/nginx.conf /etc/nginx/sites-available/koursa-backend

# Créer un lien symbolique
sudo ln -s /etc/nginx/sites-available/koursa-backend /etc/nginx/sites-enabled/

# Supprimer la config par défaut si elle existe
sudo rm -f /etc/nginx/sites-enabled/default

# Tester la configuration
sudo nginx -t

# Redémarrer nginx
sudo systemctl restart nginx
```

### 11. Configurer le pare-feu

```bash
# Autoriser SSH et le port 8080 pour l'API
sudo ufw allow 22/tcp
sudo ufw allow 8080/tcp
sudo ufw enable
```

Tapez `y` pour confirmer.

### 12. Permissions sudo pour le déploiement automatique

```bash
# Éditer le fichier sudoers
sudo visudo
```

Ajoutez cette ligne à la fin du fichier:

```
softengine ALL=(ALL) NOPASSWD: /bin/systemctl restart koursa-backend
```

Sauvegardez avec `Ctrl+O` puis `Entrée`, et quittez avec `Ctrl+X`.

### 13. Permissions du projet

```bash
# Donner les bonnes permissions
sudo chown -R www-data:www-data /var/www/koursa-backend
sudo chmod +x /var/www/koursa-backend/deploy.sh

# Permettre à softengine d'écrire dans le répertoire
sudo usermod -a -G www-data softengine

# Permettre à www-data de lire le répertoire home de softengine
sudo chmod 755 /home/softengine

# Appliquer les changements de groupe (redémarrer votre session SSH)
exit
```

Reconnectez-vous au serveur:

```bash
ssh softengine@84.247.183.206
```

---

## PARTIE 3: TEST

### 1. Test de l'API

```bash
curl http://84.247.183.206:8080/
```

Vous devriez voir une réponse de votre API.

### 2. Test de l'admin Django

Ouvrez dans votre navigateur:
```
http://84.247.183.206:8080/admin/
```

### 3. Test du déploiement automatique

Sur votre ordinateur local:

```bash
cd KOURSA_BACKEND
# Faites un petit changement (ex: ajouter un commentaire)
git add .
git commit -m "Test CI/CD"
git push origin main
```

Allez sur GitHub → votre repository → Actions

Vous devriez voir le workflow "Deploy to VPS" en cours d'exécution.

---

## Accès à votre API

Votre API est accessible à:

```
http://84.247.183.206:8080
```

Endpoints probables:
- Admin: `http://84.247.183.206:8080/admin/`
- API: `http://84.247.183.206:8080/api/`
- Swagger: `http://84.247.183.206:8080/swagger/`

---

## Commandes utiles

### Voir les logs du service
```bash
sudo journalctl -u koursa-backend -f
```

### Voir les logs Gunicorn
```bash
sudo tail -f /var/log/koursa-backend/error.log
```

### Redémarrer le service
```bash
sudo systemctl restart koursa-backend
```

### Redémarrer Nginx
```bash
sudo systemctl restart nginx
```

### Voir le statut
```bash
sudo systemctl status koursa-backend
sudo systemctl status nginx
```

### Déploiement manuel
```bash
cd /var/www/koursa-backend
git pull origin main
./deploy.sh
```

---

## Dépannage

### Le service ne démarre pas

```bash
sudo journalctl -u koursa-backend -n 50
```

### Erreur 502 Bad Gateway

```bash
sudo systemctl status koursa-backend
sudo netstat -tlnp | grep 8001
```

### Problème de base de données

```bash
psql -U koursa_user -d koursa_db -h localhost
# Mot de passe: Koursa2026@Secure!
```

### Permission denied sur le déploiement

```bash
sudo chown -R www-data:www-data /var/www/koursa-backend
sudo chmod -R 755 /var/www/koursa-backend
sudo chmod +x /var/www/koursa-backend/deploy.sh
```

---

## Résumé rapide

**Ce qui a été configuré:**

1. GitHub Actions CI/CD → Déploiement automatique sur push main
2. Service systemd → Gère l'application Django/Gunicorn
3. Nginx → Reverse proxy sur le port 8080
4. PostgreSQL → Base de données
5. Scripts de déploiement → Automatise les mises à jour

**Workflow de déploiement:**

```
git push origin main
     ↓
GitHub Actions s'exécute
     ↓
SSH vers le VPS
     ↓
git pull + pip install + migrate + collectstatic
     ↓
Redémarrage du service
     ↓
API disponible sur http://84.247.183.206:8080
```

**Vous n'avez plus qu'à faire `git push` et tout se déploie automatiquement!**
