# KOURSA Backend

Backend API REST pour la plateforme **Koursa** - Systeme de gestion academique et de suivi pedagogique.

## Technologies utilisees

| Technologie | Version | Description |
|-------------|---------|-------------|
| Python | 3.10+ | Langage de programmation |
| Django | 6.0 | Framework web |
| Django REST Framework | 3.16.1 | API REST |
| Django Filter | 25.2 | Filtrage des querysets |
| Django CORS Headers | 4.3.1 | Gestion CORS |
| Simple JWT | 5.5.1 | Authentification JWT |
| PostgreSQL | - | Base de donnees (production) |
| SQLite | - | Base de donnees (developpement) |
| drf-yasg | 1.21.11 | Documentation Swagger/OpenAPI |
| WhiteNoise | 6.11.0 | Gestion des fichiers statiques |
| Gunicorn | 23.0.0 | Serveur WSGI (production) |
| ReportLab | 4.4.0 | Generation de PDF |
| openpyxl | 3.1.5 | Export/Import Excel |

## Structure du projet

```
koursa/
├── koursa/              # Configuration Django
│   ├── .env             # Variables d'environnement (non versionne)
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── firebase_config.py  # Configuration Firebase (FCM)
├── users/               # Application Utilisateurs
├── academic/            # Application Academique
├── teaching/            # Application Enseignement
│   └── pdf_export.py    # Generation PDF des fiches de suivi
├── notifications/       # Application Notifications (FCM + rappels)
├── dashboard/           # Application Dashboard
├── .env/                # Environnement virtuel Python
├── manage.py
├── requirements.txt
└── build.sh
```

---

## Authentification

L'API utilise **JWT (JSON Web Tokens)** pour l'authentification.

### Endpoints d'authentification

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/token/` | Obtenir un token JWT (login) |
| POST | `/api/auth/token/refresh/` | Rafraichir le token |

### Exemple de login

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "motdepasse"}'
```

**Reponse:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "roles": [{"id": 1, "nom_role": "Enseignant"}]
  }
}
```

### Utilisation du token

```bash
curl -X GET http://localhost:8000/api/users/utilisateurs/ \
  -H "Authorization: Bearer <access_token>"
```

---

## Applications

### 1. Users (Gestion des utilisateurs)

#### Modeles

**Role** (`users/models/role.py`)
- Roles disponibles :
  - `Super Administrateur`
  - `Chef de Departement`
  - `Enseignant`
  - `Delegue`

**Utilisateur** (`users/models/utilisateur.py`)
- Modele utilisateur personnalise (herite de `AbstractUser`)
- Authentification par email (pas de username)
- Champs :
  - `email` : Adresse email (unique, identifiant principal)
  - `first_name` / `last_name` : Nom complet
  - `statut` : Statut du compte (`EN_ATTENTE`, `ACTIF`, `INACTIF`)
  - `roles` : Relation ManyToMany vers Role
  - `niveau_represente` : ForeignKey vers Niveau (pour les delegues)
  - `fcm_token` : Token Firebase pour notifications push

#### Logique metier
- **Enseignants** : Statut `ACTIF` automatiquement a l'inscription
- **Autres roles** : Statut `EN_ATTENTE` (activation par admin requise)
- **Delegues** : `niveau_represente` obligatoire

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/users/utilisateurs/` | Liste des utilisateurs |
| POST | `/api/users/utilisateurs/` | Creer un utilisateur |
| GET | `/api/users/utilisateurs/{id}/` | Detail d'un utilisateur |
| PUT/PATCH | `/api/users/utilisateurs/{id}/` | Modifier un utilisateur |
| DELETE | `/api/users/utilisateurs/{id}/` | Supprimer un utilisateur |
| GET | `/api/users/utilisateurs/me/` | Profil de l'utilisateur connecte |
| POST | `/api/users/utilisateurs/{id}/approuver/` | Approuver un utilisateur |
| POST | `/api/users/utilisateurs/changer-niveau/` | Changer le niveau du delegue |
| POST | `/api/users/utilisateurs/register-fcm-token/` | Enregistrer le token FCM |
| GET | `/api/users/utilisateurs/mes-utilisateurs/` | Utilisateurs lies au delegue |
| GET/POST | `/api/users/roles/` | Liste/Creation des roles |
| GET/POST | `/api/users/whitelist/` | Liste/Creation whitelist emails |
| POST | `/api/users/whitelist/bulk/` | Import bulk d'emails en whitelist |

---

### 2. Academic (Structure academique)

#### Modeles

**Faculte** (`academic/models/faculte.py`)
- `nom_faculte` : Nom de la faculte (unique)

**Departement** (`academic/models/departement.py`)
- `nom_departement` : Nom du departement
- `faculte` : ForeignKey vers Faculte
- `chef_departement` : OneToOneField vers Utilisateur

**Filiere** (`academic/models/filiere.py`)
- `nom_filiere` : Nom de la filiere
- `departement` : ForeignKey vers Departement

**Niveau** (`academic/models/niveau.py`)
- `nom_niveau` : Nom du niveau (ex: L1, L2, M1...)
- `filiere` : ForeignKey vers Filiere

#### Hierarchie
```
Faculte
└── Departement (avec chef de departement)
    └── Filiere
        └── Niveau (avec delegues)
```

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/academic/facultes/` | Liste/Creation facultes |
| GET/PUT/PATCH/DELETE | `/api/academic/facultes/{id}/` | CRUD faculte |
| GET/POST | `/api/academic/departements/` | Liste/Creation departements |
| GET/PUT/PATCH/DELETE | `/api/academic/departements/{id}/` | CRUD departement |
| GET/POST | `/api/academic/filieres/` | Liste/Creation filieres |
| GET/PUT/PATCH/DELETE | `/api/academic/filieres/{id}/` | CRUD filiere |
| GET/POST | `/api/academic/niveaux/` | Liste/Creation niveaux |
| GET/PUT/PATCH/DELETE | `/api/academic/niveaux/{id}/` | CRUD niveau |

---

### 3. Teaching (Gestion pedagogique)

#### Modeles

**UniteEnseignement** (`teaching/models/unite_enseignement.py`)
- `code_ue` : Code de l'UE (unique)
- `libelle_ue` : Libelle de l'UE
- `semestre` : Numero du semestre
- `enseignants` : ManyToMany vers Utilisateur
- `niveaux` : ManyToMany vers Niveau

**FicheSuivi** (`teaching/models/fiche_suivi.py`)
- `ue` : ForeignKey vers UniteEnseignement
- `delegue` : ForeignKey vers Utilisateur (qui soumet)
- `enseignant` : ForeignKey vers Utilisateur (qui valide)
- `date_cours` : Date du cours
- `heure_debut` / `heure_fin` : Horaires
- `duree` : Calculee automatiquement
- `salle` : Salle de cours
- `type_seance` : Type (`CM`, `TD`, `TP`)
- `titre_chapitre` : Titre du chapitre aborde
- `contenu_aborde` : Contenu detaille
- `statut` : Statut de validation (`SOUMISE`, `VALIDEE`, `REFUSEE`)
- `motif_refus` : Motif en cas de refus
- `date_soumission` / `date_validation` : Timestamps

#### Types de seances
| Code | Description |
|------|-------------|
| `CM` | Cours Magistral |
| `TD` | Travaux Diriges |
| `TP` | Travaux Pratiques |

#### Statuts des fiches
| Statut | Description |
|--------|-------------|
| `SOUMISE` | En attente de validation |
| `VALIDEE` | Validee par l'enseignant |
| `REFUSEE` | Refusee (avec motif) |

#### Permissions

| Permission | Description |
|------------|-------------|
| `IsAuthenticated` | Utilisateur authentifie |
| `IsDelegue` | Role Delegue requis |
| `IsDelegueAuteur` | Auteur de la fiche |
| `IsEnseignantConcerne` | Enseignant assigne a l'UE |
| `IsFicheModifiable` | Fiche en statut SOUMISE |

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/teaching/unites-enseignement/` | Liste/Creation UEs |
| GET/PUT/PATCH/DELETE | `/api/teaching/unites-enseignement/{id}/` | CRUD UE |
| GET/POST | `/api/teaching/fiches-suivi/` | Liste/Creation fiches |
| GET/PUT/PATCH/DELETE | `/api/teaching/fiches-suivi/{id}/` | CRUD fiche |
| POST | `/api/teaching/fiches-suivi/{id}/valider/` | Valider une fiche |
| POST | `/api/teaching/fiches-suivi/{id}/refuser/` | Refuser une fiche |
| POST | `/api/teaching/fiches-suivi/{id}/resoumettre/` | Resoumettre une fiche refusee |
| GET | `/api/teaching/fiches-suivi/{id}/export-pdf/` | Telecharger la fiche en PDF |
| GET | `/api/teaching/fiches-suivi/en-attente/` | Fiches en attente |
| POST | `/api/teaching/fiches-suivi/check-conflicts/` | Detecter conflits de salle/enseignant |
| GET | `/api/teaching/unites-enseignement/mes-delegues/` | Delegues par matiere (enseignant) |

#### Filtres disponibles

Les fiches de suivi peuvent etre filtrees par:
- `statut` : SOUMISE, VALIDEE, REFUSEE
- `date_cours` : Date du cours
- `enseignant` : ID de l'enseignant
- `delegue` : ID du delegue
- `ue` : ID de l'unite d'enseignement

Exemple: `/api/teaching/fiches-suivi/?statut=SOUMISE&ue=1`

---

### 4. Notifications (Notifications push)

#### Fonctionnalites
- Notifications push via Firebase Cloud Messaging (FCM)
- Son par defaut sur Android (`channel_id: koursa_default`) et iOS (`sound: default`)
- Types de notifications : `FICHE_SOUMISE`, `FICHE_VALIDEE`, `FICHE_REFUSEE`, `FICHE_RESOUMISE`, `ALERTE_CHEF`, `RAPPEL_ENSEIGNANT`, `RAPPEL_AUTO`, `COMPTE_APPROUVE`
- Rappels automatiques escalatifs (3 niveaux) pour les fiches manquantes

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/notifications/` | Liste des notifications |
| POST | `/api/notifications/{id}/mark-read/` | Marquer comme lue |
| POST | `/api/notifications/mark-all-read/` | Tout marquer comme lu |
| GET | `/api/notifications/unread-count/` | Nombre de non-lues |
| POST | `/api/notifications/alert-enseignant/` | Alerter un enseignant |
| POST | `/api/notifications/alert-delegue/` | Alerter un delegue |

---

### 5. Export PDF des fiches de suivi

Les fiches de suivi validees peuvent etre telechargees en PDF au format officiel de l'universite.

**Endpoint :** `GET /api/teaching/fiches-suivi/{id}/export-pdf/`

Le PDF reproduit la fiche papier officielle :
- En-tete bilingue (Republique du Cameroun / Republic of Cameroon)
- Universite, Faculte, Departement (dynamiques)
- Grille d'informations : Semestre, Date, UE, Horaires, Enseignant, Salle, Type de seance, Titre
- Zone "Contenu" avec le contenu aborde
- Signatures delegue et enseignant

**Regles d'acces :**
| Role | Condition |
|------|-----------|
| Delegue / Enseignant | Fiche VALIDEE uniquement |
| Chef de Departement / Super Admin | Quel que soit le statut |

**Authentification :** Header `Authorization: Bearer <token>` ou query param `?token=<jwt>` (pour ouverture navigateur mobile).

---

### 6. Dashboard

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/dashboard/` | Statistiques du dashboard |

---

## Interface d'administration

Accessible via `/admin/`

### Fonctionnalites admin implementees

- **Utilisateurs** : Gestion complete avec filtres par statut et role
- **Roles** : CRUD simple
- **Facultes** : Recherche par nom
- **Departements** : Filtrage par faculte, autocompletion
- **Filieres** : Filtrage par departement/faculte
- **Niveaux** : Filtrage par filiere/departement
- **Unites d'enseignement** : Gestion des enseignants et niveaux
- **Fiches de suivi** : Filtrage par statut, date, enseignant

---

## Documentation API

| URL | Description |
|-----|-------------|
| `/swagger/` | Interface Swagger UI (interactive) |
| `/redoc/` | Interface ReDoc (documentation) |

---

## Installation

### Prerequis
- Python 3.10+
- pip
- virtualenv (recommande)

### Etapes

1. **Cloner le repository**
```bash
git clone https://github.com/M1-INF-4027/KOURSA_BACKEND.git
cd KOURSA_BACKEND/koursa
```

2. **Creer un environnement virtuel**
```bash
python -m venv .env
source .env/bin/activate  # Linux/Mac
.env\Scripts\activate     # Windows
```

3. **Installer les dependances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**
```bash
# Creer un fichier .env dans le dossier koursa/
# Emplacement: koursa/koursa/.env

SECRET_KEY=votre-cle-secrete-generee
DEBUG=True
# DATABASE_URL=sqlite:///db.sqlite3  # Optionnel, SQLite par defaut
```

5. **Appliquer les migrations**
```bash
python manage.py migrate
```

6. **Creer un superutilisateur**
```bash
python manage.py createsuperuser
```

7. **Lancer le serveur**
```bash
python manage.py runserver
```

Le serveur sera accessible sur http://127.0.0.1:8000/

---

## Configuration CORS

Le backend est configure pour accepter les requetes cross-origin. En mode developpement (`DEBUG=True`), toutes les origines sont autorisees.

En production, configurez `CORS_ALLOWED_ORIGINS` dans settings.py.

---

## Deploiement (Render)

Le projet est configure pour le deploiement sur Render avec :
- Script de build : `build.sh`
- Serveur : Gunicorn
- Fichiers statiques : WhiteNoise
- Base de donnees : PostgreSQL (via `DATABASE_URL`)

### Variables d'environnement requises
```
SECRET_KEY=<cle-secrete-production>
DEBUG=False
DATABASE_URL=<url-postgresql>
RENDER_EXTERNAL_HOSTNAME=<hostname-render>
```

---

## Dependances principales

```
Django==6.0
djangorestframework==3.16.1
djangorestframework-simplejwt==5.5.1
django-filter==25.2
django-cors-headers==4.3.1
drf-yasg==1.21.11
dj-database-url==3.0.1
psycopg2-binary==2.9.11
gunicorn==23.0.0
whitenoise==6.11.0
python-dotenv==1.2.1
firebase_admin==7.1.0
openpyxl==3.1.5
reportlab==4.4.0
```

---

## Licence

Apache License 2.0 - Copyright (c) 2025 M1 INF 4027
