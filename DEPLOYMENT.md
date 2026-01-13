# Guide de Déploiement - Koursa Backend

Ce guide vous explique comment déployer le backend Koursa sur votre VPS avec CI/CD automatique.

## Prérequis sur votre VPS

- Ubuntu/Debian (ou distribution similaire)
- Python 3.9+
- PostgreSQL
- Nginx
- Git
- Accès SSH root ou sudo

## Étape 1: Configuration de GitHub (À faire sur votre ordinateur)

### 1.1 Générer une clé SSH pour GitHub Actions

```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/koursa_deploy
```

### 1.2 Ajouter les secrets GitHub

Allez sur votre repo GitHub → Settings → Secrets and variables → Actions → New repository secret

Ajoutez ces secrets:

- **VPS_HOST**: L'adresse IP de votre VPS (ex: 192.168.1.100)
- **VPS_USERNAME**: Votre nom d'utilisateur SSH (ex: root ou ubuntu)
- **VPS_SSH_KEY**: Le contenu du fichier `~/.ssh/koursa_deploy` (clé privée)
- **VPS_PORT**: Le port SSH de votre VPS (généralement 22)

## Étape 2: Configuration du VPS (À faire sur votre serveur)

### 2.1 Connexion au VPS

```bash
ssh root@VOTRE_IP_VPS
```

### 2.2 Installation des dépendances système

```bash
# Mise à jour du système
apt update && apt upgrade -y

# Installation de Python, PostgreSQL, Nginx et autres outils
apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git

# Installation de gunicorn globalement (optionnel)
pip3 install gunicorn
```

### 2.3 Configuration de PostgreSQL

```bash
# Connexion à PostgreSQL
sudo -u postgres psql

# Dans le shell PostgreSQL, exécutez:
CREATE DATABASE koursa_db;
CREATE USER koursa_user WITH PASSWORD 'votre_mot_de_passe_securise';
ALTER ROLE koursa_user SET client_encoding TO 'utf8';
ALTER ROLE koursa_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE koursa_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE koursa_db TO koursa_user;
\q
```

### 2.4 Création du répertoire du projet

```bash
# Créer le répertoire pour l'application
mkdir -p /var/www/koursa-backend
cd /var/www/koursa-backend

# Cloner le repository
git clone VOTRE_URL_GITHUB.git .

# Créer l'environnement virtuel Python
python3 -m venv venv

# Activer l'environnement virtuel
source venv/bin/activate

# Installer les dépendances
pip install -r koursa/requirements.txt
```

### 2.5 Configuration du fichier .env

```bash
# Créer le fichier .env
nano /var/www/koursa-backend/koursa/.env
```

Copiez et modifiez le contenu suivant:

```env
SECRET_KEY=votre-secret-key-a-generer-avec-python
DEBUG=False
DATABASE_URL=postgresql://koursa_user:votre_mot_de_passe_securise@localhost:5432/koursa_db
ALLOWED_HOSTS=VOTRE_IP_VPS
```

**Pour générer une SECRET_KEY sécurisée:**

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2.6 Migrations et fichiers statiques

```bash
cd /var/www/koursa-backend/koursa
source ../venv/bin/activate

# Exécuter les migrations
python manage.py migrate

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Créer un superuser (optionnel)
python manage.py createsuperuser
```

### 2.7 Créer les répertoires de logs

```bash
mkdir -p /var/log/koursa-backend
chown www-data:www-data /var/log/koursa-backend
```

### 2.8 Configuration du service systemd

```bash
# Copier le fichier de service
cp /var/www/koursa-backend/deployment/koursa-backend.service /etc/systemd/system/

# Recharger systemd
systemctl daemon-reload

# Activer le service au démarrage
systemctl enable koursa-backend

# Démarrer le service
systemctl start koursa-backend

# Vérifier le statut
systemctl status koursa-backend
```

### 2.9 Configuration de Nginx

```bash
# Copier la configuration nginx
cp /var/www/koursa-backend/deployment/nginx.conf /etc/nginx/sites-available/koursa-backend

# Créer un lien symbolique
ln -s /etc/nginx/sites-available/koursa-backend /etc/nginx/sites-enabled/

# Tester la configuration
nginx -t

# Redémarrer nginx
systemctl restart nginx
```

### 2.10 Configuration du pare-feu (Optionnel mais recommandé)

```bash
# Autoriser SSH, HTTP et le port de votre API
ufw allow 22/tcp
ufw allow 8080/tcp
ufw enable
```

### 2.11 Ajout de la clé publique SSH pour GitHub Actions

```bash
# Créer le répertoire .ssh si nécessaire
mkdir -p ~/.ssh

# Ajouter la clé publique générée à l'étape 1.1
nano ~/.ssh/authorized_keys
# Collez le contenu de ~/.ssh/koursa_deploy.pub (depuis votre ordinateur local)

# Définir les bonnes permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### 2.12 Donner les permissions sudo au script de déploiement

```bash
# Éditer le fichier sudoers
visudo
```

Ajoutez cette ligne (remplacez `root` par votre nom d'utilisateur si différent):

```
root ALL=(ALL) NOPASSWD: /bin/systemctl restart koursa-backend
```

### 2.13 Permissions pour le répertoire du projet

```bash
# Donner les bonnes permissions
chown -R www-data:www-data /var/www/koursa-backend
chmod +x /var/www/koursa-backend/deploy.sh

# Permettre à votre utilisateur SSH d'écrire dans le répertoire
usermod -a -G www-data $USER
```

## Étape 3: Test du déploiement

### 3.1 Test manuel

Sur votre VPS:

```bash
cd /var/www/koursa-backend
git pull origin main
./deploy.sh
```

### 3.2 Test de l'API

```bash
curl http://VOTRE_IP_VPS:8080/
```

Vous devriez voir une réponse de votre API Django.

### 3.3 Test du CI/CD

Sur votre ordinateur:

```bash
cd KOURSA_BACKEND
git add .
git commit -m "Test CI/CD deployment"
git push origin main
```

Le déploiement devrait se faire automatiquement. Vérifiez sur GitHub Actions que le workflow s'est bien exécuté.

## Étape 4: Accès à votre API

Votre API est maintenant accessible à l'adresse:

```
http://VOTRE_IP_VPS:8080
```

Exemples d'endpoints:

- Admin Django: `http://VOTRE_IP_VPS:8080/admin/`
- API: `http://VOTRE_IP_VPS:8080/api/`
- Documentation Swagger: `http://VOTRE_IP_VPS:8080/swagger/`

## Commandes utiles sur le VPS

```bash
# Voir les logs du service
journalctl -u koursa-backend -f

# Voir les logs gunicorn
tail -f /var/log/koursa-backend/error.log
tail -f /var/log/koursa-backend/access.log

# Voir les logs nginx
tail -f /var/log/nginx/koursa-backend-error.log

# Redémarrer le service
systemctl restart koursa-backend

# Redémarrer nginx
systemctl restart nginx

# Vérifier le statut
systemctl status koursa-backend
systemctl status nginx
```

## Dépannage

### Le service ne démarre pas

```bash
# Vérifier les logs
journalctl -u koursa-backend -n 50

# Vérifier la configuration
source /var/www/koursa-backend/venv/bin/activate
cd /var/www/koursa-backend/koursa
python manage.py check
```

### Erreur 502 Bad Gateway

- Vérifiez que le service koursa-backend est bien démarré: `systemctl status koursa-backend`
- Vérifiez que gunicorn écoute bien sur le port 8001: `netstat -tlnp | grep 8001`

### Erreur de base de données

- Vérifiez que PostgreSQL est démarré: `systemctl status postgresql`
- Vérifiez la variable DATABASE_URL dans le fichier .env
- Testez la connexion: `psql -U koursa_user -d koursa_db -h localhost`

### Les fichiers statiques ne se chargent pas

```bash
cd /var/www/koursa-backend/koursa
source ../venv/bin/activate
python manage.py collectstatic --noinput
systemctl restart koursa-backend
```

## Configuration Firebase (si nécessaire)

Si votre application utilise Firebase pour les notifications:

1. Téléchargez votre fichier de credentials Firebase (firebase-credentials.json)
2. Uploadez-le sur votre VPS dans `/var/www/koursa-backend/koursa/`
3. Ajoutez dans votre `.env`:

```env
FIREBASE_CREDENTIALS_PATH=/var/www/koursa-backend/koursa/firebase-credentials.json
```

## Mise à jour du déploiement

Désormais, à chaque fois que vous faites un `git push origin main`, le déploiement se fera automatiquement sur votre VPS!

Pour forcer un déploiement manuel:

```bash
ssh root@VOTRE_IP_VPS "cd /var/www/koursa-backend && git pull && ./deploy.sh"
```

## Sécurité additionnelle (Recommandé)

### 1. Changer le port SSH par défaut

```bash
nano /etc/ssh/sshd_config
# Changez la ligne: Port 22 → Port 2222
systemctl restart sshd
```

N'oubliez pas de mettre à jour le secret `VPS_PORT` dans GitHub et le pare-feu.

### 2. Désactiver l'authentification par mot de passe SSH

```bash
nano /etc/ssh/sshd_config
# Changez: PasswordAuthentication yes → PasswordAuthentication no
systemctl restart sshd
```

### 3. Configurer fail2ban

```bash
apt install fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

## Support

Si vous rencontrez des problèmes:

1. Vérifiez les logs (voir "Commandes utiles")
2. Assurez-vous que toutes les étapes ont été suivies
3. Vérifiez que les permissions sont correctes
4. Testez manuellement le déploiement avant de tester le CI/CD

Bonne chance avec votre déploiement!
