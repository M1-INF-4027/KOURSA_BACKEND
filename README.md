# KOURSA Backend

Backend API REST pour la plateforme **Koursa** - Systeme de gestion academique et de suivi pedagogique.

## Technologies utilisees

| Technologie | Version | Description |
|-------------|---------|-------------|
| Python | 3.x | Langage de programmation |
| Django | 6.0 | Framework web |
| Django REST Framework | 3.16.1 | API REST |
| PostgreSQL | - | Base de donnees (production) |
| SQLite | - | Base de donnees (developpement) |
| drf-yasg | 1.21.11 | Documentation Swagger/OpenAPI |
| WhiteNoise | 6.11.0 | Gestion des fichiers statiques |
| Gunicorn | 23.0.0 | Serveur WSGI (production) |

## Structure du projet

```
KOURSA_BACKEND/
├── koursa/
│   ├── koursa/              # Configuration Django
│   │   ├── .env             # Variables d'environnement (non versionne)
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── users/               # Application Utilisateurs
│   ├── academic/            # Application Academique
│   ├── teaching/            # Application Enseignement
│   ├── .env/                # Environnement virtuel Python
│   ├── manage.py
│   ├── requirements.txt
│   └── build.sh
├── LICENSE
└── README.md
```

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

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/users/utilisateurs/` | Liste des utilisateurs |
| POST | `/api/users/utilisateurs/` | Creer un utilisateur |
| GET | `/api/users/utilisateurs/{id}/` | Detail d'un utilisateur |
| PUT/PATCH | `/api/users/utilisateurs/{id}/` | Modifier un utilisateur |
| DELETE | `/api/users/utilisateurs/{id}/` | Supprimer un utilisateur |
| GET | `/api/users/roles/` | Liste des roles |
| POST | `/api/users/roles/` | Creer un role |
| GET | `/api/users/roles/{id}/` | Detail d'un role |
| PUT/PATCH | `/api/users/roles/{id}/` | Modifier un role |
| DELETE | `/api/users/roles/{id}/` | Supprimer un role |

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
- `CM` : Cours Magistral
- `TD` : Travaux Diriges
- `TP` : Travaux Pratiques

#### Statuts des fiches
- `SOUMISE` : En attente de validation
- `VALIDEE` : Validee par l'enseignant
- `REFUSEE` : Refusee (avec motif)

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | `/api/teaching/unites-enseignement/` | Liste/Creation UEs |
| GET/PUT/PATCH/DELETE | `/api/teaching/unites-enseignement/{id}/` | CRUD UE |
| GET/POST | `/api/teaching/fiches-suivi/` | Liste/Creation fiches |
| GET/PUT/PATCH/DELETE | `/api/teaching/fiches-suivi/{id}/` | CRUD fiche |
| POST | `/api/teaching/fiches-suivi/{id}/valider/` | Valider une fiche |
| POST | `/api/teaching/fiches-suivi/{id}/refuser/` | Refuser une fiche (avec motif) |
| GET | `/api/teaching/fiches-suivi/en-attente/` | Fiches en attente de validation |

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
| `/swagger/` | Interface Swagger UI |
| `/redoc/` | Interface ReDoc |

---

## Installation

### Prerequis
- Python 3.10+
- pip
- virtualenv (recommande)

### Etapes

1. **Cloner le repository**
```bash
git clone <url-du-repo>
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
# Creer un fichier .env dans le dossier koursa/koursa/
# Emplacement: KOURSA_BACKEND/koursa/koursa/.env

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
drf-yasg==1.21.11
dj-database-url==3.0.1
psycopg2-binary==2.9.11
gunicorn==23.0.0
whitenoise==6.11.0
python-dotenv==1.2.1
simplejwt==2.0.1
```

---

## Licence

MIT License - Copyright (c) 2025 M1 INF 4027

Voir le fichier [LICENSE](LICENSE) pour plus de details.
