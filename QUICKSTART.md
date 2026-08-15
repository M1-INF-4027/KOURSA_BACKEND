# Quick Start - Déploiement en 3 étapes

## 1️⃣ SUR VOTRE ORDINATEUR

### A. Générer la clé SSH

```bash
ssh-keygen -t ed25519 -C "github-actions-koursa" -f ~/.ssh/koursa_deploy
```

Appuyez sur Entrée 2 fois (pas de passphrase).

### B. Afficher les clés

```bash
# Clé publique (pour le VPS)
cat ~/.ssh/koursa_deploy.pub

# Clé privée (pour GitHub)
cat ~/.ssh/koursa_deploy
```

**Copiez ces deux clés quelque part.**

### C. Configurer GitHub

Allez sur: **GitHub → Votre Repo → Settings → Secrets and variables → Actions**

Créez 4 secrets:

| Secret | Valeur |
|--------|--------|
| VPS_HOST | 84.247.172.198 |
| VPS_USERNAME | softengine |
| VPS_SSH_KEY | Contenu de `~/.ssh/koursa_deploy` |
| VPS_PORT | 22 |

### D. Push le code

```bash
git add .
git commit -m "Setup CI/CD"
git push origin main
```

---

## 2️⃣ SUR LE SERVEUR VPS

Connectez-vous:

```bash
ssh koursa@84.247.172.198
```

### Copier-coller ce script complet:

```bash
#!/bin/bash

# 1. Ajouter la clé SSH
mkdir -p ~/.ssh
echo "COLLEZ_VOTRE_CLE_PUBLIQUE_ICI" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# 2. Installer les dépendances
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git

# 3. Configurer PostgreSQL
sudo -u postgres psql << EOF
CREATE DATABASE koursa_db;
CREATE USER koursa_user WITH PASSWORD '<MOT_DE_PASSE_BD>';
ALTER ROLE koursa_user SET client_encoding TO 'utf8';
ALTER ROLE koursa_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE koursa_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE koursa_db TO koursa_user;
EOF

# 4. Cloner le projet
sudo mkdir -p /var/www/koursa-backend
sudo chown softengine:softengine /var/www/koursa-backend
cd /var/www/koursa-backend
git clone https://github.com/VOTRE_USERNAME/VOTRE_REPO.git .

# 5. Environnement virtuel et dépendances
python3 -m venv venv
source venv/bin/activate
pip install -r koursa/requirements.txt

# 6. Créer le fichier .env
cat > /var/www/koursa-backend/koursa/.env << 'EOF'
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
DEBUG=False
DATABASE_URL=postgresql://koursa_user:<MOT_DE_PASSE_BD>@localhost:5432/koursa_db
ALLOWED_HOSTS=84.247.172.198
EOF

# 7. Migrations et static
cd koursa
python manage.py migrate
python manage.py collectstatic --noinput
cd ..

# 8. Logs
sudo mkdir -p /var/log/koursa-backend
sudo chown www-data:www-data /var/log/koursa-backend

# 9. Service systemd
sudo cp deployment/koursa-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable koursa-backend
sudo systemctl start koursa-backend

# 10. Nginx
sudo cp deployment/nginx.conf /etc/nginx/sites-available/koursa-backend
sudo ln -s /etc/nginx/sites-available/koursa-backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 11. Pare-feu
sudo ufw allow 22/tcp
sudo ufw allow 8080/tcp
echo "y" | sudo ufw enable

# 12. Permissions sudo
echo "softengine ALL=(ALL) NOPASSWD: /bin/systemctl restart koursa-backend" | sudo EDITOR='tee -a' visudo

# 13. Permissions finales
sudo chown -R www-data:www-data /var/www/koursa-backend
sudo chmod +x /var/www/koursa-backend/deploy.sh
sudo usermod -a -G www-data softengine
sudo chmod 755 /home/softengine

echo "✅ Installation terminée!"
echo "🌐 Votre API est disponible sur: http://84.247.172.198:8080"
```

**IMPORTANT**:
- Remplacez `COLLEZ_VOTRE_CLE_PUBLIQUE_ICI` par votre clé publique
- Remplacez `VOTRE_USERNAME/VOTRE_REPO` par votre URL GitHub

### Alternative: Installation manuelle

Si le script ne fonctionne pas, suivez **INSTRUCTIONS_VPS.md** étape par étape.

---

## 3️⃣ TEST

### A. Tester l'API

```bash
curl http://84.247.172.198:8080/
```

### B. Tester le CI/CD

Sur votre ordinateur:

```bash
# Faire un changement
echo "# Test" >> README.md
git add .
git commit -m "Test CI/CD"
git push origin main
```

Allez sur: **GitHub → Actions** pour voir le déploiement.

### C. Accès à l'admin

```
http://84.247.172.198:8080/admin/
```

---

## ✅ C'est terminé!

Désormais, chaque `git push origin main` déploie automatiquement sur votre VPS.

### Commandes utiles:

```bash
# Logs en direct
sudo journalctl -u koursa-backend -f

# Redémarrer
sudo systemctl restart koursa-backend

# Status
sudo systemctl status koursa-backend
```

---

## 🆘 Problèmes?

1. Consultez **INSTRUCTIONS_VPS.md** pour le détail
2. Vérifiez les logs: `sudo journalctl -u koursa-backend -n 50`
3. Vérifiez nginx: `sudo systemctl status nginx`
4. Vérifiez la base de données: `sudo systemctl status postgresql`
