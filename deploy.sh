#!/bin/bash

# Script de déploiement pour Koursa Backend
# Ce script doit être exécuté sur le serveur VPS

set -e

echo "Début du déploiement de Koursa Backend..."

# Variables
PROJECT_DIR="/var/www/koursa-backend"
VENV_DIR="$PROJECT_DIR/venv"
APP_DIR="$PROJECT_DIR/koursa"

# Activer l'environnement virtuel
echo "Activation de l'environnement virtuel..."
source $VENV_DIR/bin/activate

# Installer/Mettre à jour les dépendances
echo "Installation des dépendances..."
pip install -r $APP_DIR/requirements.txt

# Collecter les fichiers statiques
echo "Collecte des fichiers statiques..."
cd $APP_DIR
python manage.py collectstatic --noinput

# Exécuter les migrations
echo "Exécution des migrations..."
python manage.py migrate --noinput

# Redémarrer le service
echo "Redémarrage du service..."
sudo systemctl restart koursa-backend

echo "Déploiement terminé avec succès!"
