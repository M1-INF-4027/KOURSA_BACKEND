# Instructions Finales de Déploiement - Koursa Backend

## Configuration adaptée à votre serveur

**Serveur VPS:** softengine@84.247.183.206

### Ports configurés (LIBRES sur votre serveur):
- **Port 8002** (interne) : Gunicorn
- **Port 8082** (externe) : Accès à votre API

Vos autres projets (ports 8080, 8081, 3001-3010, etc.) ne seront **PAS** affectés.

---

## Étapes restantes sur le serveur VPS

Vous êtes actuellement ici:
```
(venv) softengine@vmi2625670:/var/www/koursa-backend/KOURSA_BACKEND/koursa$
```

### 1. Créer les répertoires de logs

```bash
sudo mkdir -p /var/log/koursa-backend
sudo chown www-data:www-data /var/log/koursa-backend
```

### 2. Collecter les fichiers statiques

```bash
# Vous êtes déjà dans le bon répertoire
python manage.py collectstatic --noinput
```

### 3. Créer un superuser (optionnel mais recommandé)

```bash
python manage.py createsuperuser
```

Suivez les instructions pour créer votre compte admin.

### 4. Installer et configurer le service systemd

```bash
# Copier le fichier de service
sudo cp /var/www/koursa-backend/KOURSA_BACKEND/deployment/koursa-backend.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable koursa-backend

# Démarrer le service
sudo systemctl start koursa-backend

# Vérifier le statut
sudo systemctl status koursa-backend
```

Vous devriez voir **"active (running)"** en vert. Appuyez sur `q` pour quitter.

### 5. Configurer Nginx

```bash
# Copier la configuration nginx
sudo cp /var/www/koursa-backend/KOURSA_BACKEND/deployment/nginx.conf /etc/nginx/sites-available/koursa-backend

# Créer un lien symbolique
sudo ln -s /etc/nginx/sites-available/koursa-backend /etc/nginx/sites-enabled/

# Tester la configuration
sudo nginx -t

# Redémarrer nginx
sudo systemctl restart nginx
```

### 6. Configurer le pare-feu pour le port 8082

```bash
# Autoriser le port 8082
sudo ufw allow 8082/tcp

# Vérifier le statut
sudo ufw status
```

### 7. Permissions sudo pour le déploiement automatique

```bash
# Éditer le fichier sudoers
sudo visudo
```

Ajoutez cette ligne à la fin du fichier:

```
softengine ALL=(ALL) NOPASSWD: /bin/systemctl restart koursa-backend
```

Sauvegardez avec `Ctrl+O`, puis `Entrée`, et quittez avec `Ctrl+X`.

### 8. Permissions du projet

```bash
# Donner les bonnes permissions
sudo chown -R www-data:www-data /var/www/koursa-backend
sudo chmod +x /var/www/koursa-backend/KOURSA_BACKEND/deploy.sh

# Permettre à softengine d'écrire dans le répertoire
sudo usermod -a -G www-data softengine
sudo chmod 755 /home/softengine
```

### 9. Appliquer les changements de groupe (important!)

```bash
# Déconnectez-vous
exit

# Reconnectez-vous
ssh softengine@84.247.183.206
```

---

## Test de l'API

### Depuis le serveur:

```bash
curl http://127.0.0.1:8082/
```

### Depuis votre ordinateur ou navigateur:

```
http://84.247.183.206:8082/
```

### Admin Django:

```
http://84.247.183.206:8082/admin/
```

### API endpoints (si configurés):

```
http://84.247.183.206:8082/api/
```

### Swagger documentation (si configuré):

```
http://84.247.183.206:8082/swagger/
```

---

## Commandes utiles

### Voir les logs en temps réel:

```bash
sudo journalctl -u koursa-backend -f
```

### Voir les logs Gunicorn:

```bash
sudo tail -f /var/log/koursa-backend/error.log
sudo tail -f /var/log/koursa-backend/access.log
```

### Voir les logs Nginx:

```bash
sudo tail -f /var/log/nginx/koursa-backend-error.log
```

### Redémarrer le service:

```bash
sudo systemctl restart koursa-backend
```

### Voir le statut:

```bash
sudo systemctl status koursa-backend
sudo systemctl status nginx
```

### Déploiement manuel:

```bash
cd /var/www/koursa-backend
git pull origin main
cd KOURSA_BACKEND
./deploy.sh
```

---

## Dépannage

### Le service ne démarre pas:

```bash
sudo journalctl -u koursa-backend -n 50
```

### Erreur 502 Bad Gateway:

```bash
# Vérifier que le service est démarré
sudo systemctl status koursa-backend

# Vérifier que gunicorn écoute sur le port 8002
sudo netstat -tlnp | grep 8002

# Ou avec ss
sudo ss -tlnp | grep 8002
```

### Erreur de permissions:

```bash
sudo chown -R www-data:www-data /var/www/koursa-backend
sudo chmod -R 755 /var/www/koursa-backend
sudo chmod +x /var/www/koursa-backend/KOURSA_BACKEND/deploy.sh
```

### Les fichiers statiques ne se chargent pas:

```bash
cd /var/www/koursa-backend/KOURSA_BACKEND/koursa
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart koursa-backend
```

---

## Vérifications après installation

### 1. Le service est-il actif?

```bash
sudo systemctl status koursa-backend
```

Doit afficher: **active (running)**

### 2. Gunicorn écoute-t-il sur le bon port?

```bash
sudo ss -tlnp | grep 8002
```

Doit afficher une ligne avec `127.0.0.1:8002`

### 3. Nginx écoute-t-il sur le bon port?

```bash
sudo ss -tlnp | grep 8082
```

Doit afficher une ligne avec `0.0.0.0:8082`

### 4. L'API répond-elle?

```bash
curl http://127.0.0.1:8082/
```

Doit retourner une réponse de Django (pas d'erreur 502 ou 404).

---

## Configuration GitHub (À faire après le déploiement sur le serveur)

Une fois que tout fonctionne sur le serveur, configurez GitHub pour le CI/CD:

### 1. Générer une clé SSH (depuis votre ordinateur Windows):

```powershell
mkdir $HOME\.ssh
ssh-keygen -t ed25519 -C "github-actions-koursa" -f $HOME\.ssh\koursa_deploy
```

Appuyez sur Entrée 2 fois (pas de passphrase).

### 2. Copier la clé publique sur le serveur:

```powershell
# Afficher la clé publique
type $HOME\.ssh\koursa_deploy.pub
```

Copiez le contenu, puis sur le serveur VPS:

```bash
nano ~/.ssh/authorized_keys
# Collez la clé publique à la fin du fichier
# Ctrl+O, Entrée, Ctrl+X
```

### 3. Configurer GitHub Secrets:

Allez sur: **GitHub → Votre Repo → Settings → Secrets and variables → Actions**

Créez 4 secrets:

| Secret | Valeur |
|--------|--------|
| VPS_HOST | 84.247.183.206 |
| VPS_USERNAME | softengine |
| VPS_SSH_KEY | Contenu de `$HOME\.ssh\koursa_deploy` (clé privée) |
| VPS_PORT | 22 |

### 4. Push votre code:

```bash
cd KOURSA_BACKEND
git add .
git commit -m "Configuration CI/CD avec ports 8002/8082"
git push origin main
```

Le déploiement devrait se faire automatiquement! Vérifiez sur **GitHub → Actions**.

---

## Résumé

**Architecture finale:**

```
[Git Push] → [GitHub Actions] → [SSH vers VPS]
                                      ↓
                          [git pull + migrations]
                                      ↓
                          [Redémarrage du service]
                                      ↓
            [Nginx :8082] → [Gunicorn :8002] → [Django + PostgreSQL]
                                                        ↓
                                              [Base: koursa_db]
```

**URL de votre API:**
```
http://84.247.183.206:8082
```

**Déploiement automatique:**
- Chaque `git push origin main` → Déploiement automatique
- Les logs sont visibles dans GitHub Actions

**Vos autres projets ne sont PAS affectés!**

---

Bonne chance! 🚀
