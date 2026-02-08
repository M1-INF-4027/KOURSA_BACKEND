# KOURSA Backend

Backend API REST pour la plateforme **Koursa** - Systeme de gestion academique et de suivi pedagogique.

## Fonctionnalites principales

- Authentification JWT (access + refresh tokens) avec email comme identifiant
- Gestion des utilisateurs avec systeme d'inscription et approbation multi-niveaux
- Structure academique hierarchique : Faculte → Departement → Filiere → Niveau
- Gestion des Unites d'Enseignement (UE) avec affectation enseignants et niveaux
- Fiches de suivi pedagogique avec workflow de validation (SOUMISE → VALIDEE / REFUSEE)
- Dashboard statistique avec filtrage par filiere, niveau et semestre
- Export Excel (bilan global, par UE, par enseignant) avec openpyxl
- Notifications push via Firebase Cloud Messaging (FCM)
- Documentation API interactive (Swagger / ReDoc)
- Interface d'administration personnalisee (Jazzmin)
- Support multi-roles (un utilisateur peut avoir plusieurs roles)

---

## Deploiement Production

- **URL API:** https://koursa.duckdns.org/api/
- **Admin Django:** https://koursa.duckdns.org/django-admin/
- **Documentation Swagger:** https://koursa.duckdns.org/swagger/
- **Serveur:** 84.247.183.206 (softengine)
- **SSL:** Let's Encrypt (renouvellement automatique via Certbot)
- **Base de donnees:** PostgreSQL (koursa_db / koursa_user)
- **CI/CD:** GitHub Actions (deploiement automatique sur push main)

---

## Technologies utilisees

| Technologie | Version | Description |
|-------------|---------|-------------|
| Python | 3.10+ | Langage de programmation |
| Django | 6.0 | Framework web |
| Django REST Framework | 3.16.1 | API REST |
| Django Filter | 25.2 | Filtrage des querysets |
| Django CORS Headers | 4.3.1 | Gestion CORS |
| Simple JWT | 5.5.1 | Authentification JWT |
| Firebase Admin | 7.1.0 | Notifications push (FCM) |
| PostgreSQL | - | Base de donnees (production) |
| SQLite | - | Base de donnees (developpement) |
| drf-yasg | 1.21.11 | Documentation Swagger/OpenAPI |
| WhiteNoise | 6.11.0 | Gestion des fichiers statiques |
| openpyxl | 3.1.5 | Generation de fichiers Excel |
| Jazzmin | 3.0.1 | Theme d'administration Django |
| Gunicorn | 23.0.0 | Serveur WSGI (production) |
| dj-database-url | 3.0.1 | Configuration base de donnees par URL |
| python-dotenv | 1.2.1 | Variables d'environnement (.env) |

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
│   ├── academic/            # Application Structure Academique
│   ├── teaching/            # Application Enseignement
│   ├── dashboard/           # Application Dashboard
│   ├── manage.py
│   └── requirements.txt
├── .github/workflows/       # CI/CD GitHub Actions
└── README.md
```

---

## Variables d'environnement

Creer un fichier `.env` dans `koursa/koursa/.env` :

| Variable | Description | Defaut |
|----------|-------------|--------|
| `SECRET_KEY` | Cle secrete Django | `django-insecure-...` (dev uniquement) |
| `DEBUG` | Mode debug (`True` / `False`) | `True` |
| `ALLOWED_HOSTS` | Hotes autorises (separes par virgule) | `*` en debug |
| `DATABASE_URL` | URL de connexion PostgreSQL | SQLite (`db.sqlite3`) |
| `RENDER_EXTERNAL_HOSTNAME` | Hostname externe (deploiement Render) | - |

Exemple `.env` pour le developpement :
```env
SECRET_KEY=votre-cle-secrete-de-dev
DEBUG=True
```

Exemple `.env` pour la production :
```env
SECRET_KEY=une-cle-secrete-longue-et-aleatoire
DEBUG=False
ALLOWED_HOSTS=koursa.duckdns.org,84.247.183.206
DATABASE_URL=postgres://koursa_user:motdepasse@localhost:5432/koursa_db
```

---

## Authentification

L'API utilise **JWT (JSON Web Tokens)** pour l'authentification.

### Configuration JWT

| Parametre | Valeur |
|-----------|--------|
| Duree du token d'acces | 60 minutes |
| Duree du token de rafraichissement | 1 jour |
| Algorithme | HS256 |
| Type d'en-tete | `Bearer` |

### Endpoints d'authentification

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/token/` | Obtenir un token JWT (login) |
| POST | `/api/auth/token/refresh/` | Rafraichir le token |

### Exemple de login

```bash
curl -X POST https://koursa.duckdns.org/api/auth/token/ \
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
    "statut": "ACTIF",
    "roles": [{"id": 1, "nom_role": "Enseignant"}]
  }
}
```

### Utilisation du token

```bash
curl -X GET https://koursa.duckdns.org/api/users/utilisateurs/ \
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

#### Systeme d'inscription et approbation

- **Tous les comptes** crees par inscription (web ou mobile) demarrent avec le statut `EN_ATTENTE`
- **Comptes crees par un Super Admin** : statut `ACTIF` directement (pas besoin d'approbation)
- **Approbation** : le Super Admin peut approuver tout role, le Chef de Departement ne peut approuver que les delegues et enseignants
- **Delegues** : `niveau_represente` obligatoire a l'inscription
- **Enseignants** : inscription via le formulaire web, approuves par le Chef de Departement ou le Super Admin
- Un utilisateur peut avoir plusieurs roles (ex: Chef de Departement + Enseignant)

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/users/utilisateurs/` | Liste des utilisateurs |
| POST | `/api/users/utilisateurs/` | Creer un utilisateur |
| GET | `/api/users/utilisateurs/{id}/` | Detail d'un utilisateur |
| PUT/PATCH | `/api/users/utilisateurs/{id}/` | Modifier un utilisateur |
| DELETE | `/api/users/utilisateurs/{id}/` | Supprimer un utilisateur |
| GET | `/api/users/utilisateurs/me/` | Profil de l'utilisateur connecte |
| POST | `/api/users/utilisateurs/{id}/approuver/` | Approuver un utilisateur en attente |
| POST | `/api/users/utilisateurs/{id}/approuver-delegue/` | Alias pour compatibilite mobile |
| POST | `/api/users/utilisateurs/confirm-password/` | Confirmer le mot de passe |
| POST | `/api/users/utilisateurs/register-fcm-token/` | Enregistrer un token FCM |
| GET | `/api/users/roles/` | Liste des roles |

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

L'API retourne aussi les champs calcules suivants :
- `classe` : Label lisible de la classe (ex: "Informatique M1")
- `semestre` : Numero du semestre de l'UE
- `niveaux_details` : Liste `[{nom_niveau, filiere_nom}]`

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
| GET | `/api/teaching/fiches-suivi/en-attente/` | Fiches en attente |

---

### 4. Dashboard

#### Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/dashboard/` | Page d'accueil dashboard |
| GET | `/api/dashboard/stats/` | Statistiques du departement (heures, retards, UEs) |
| GET | `/api/dashboard/recapitulatif/` | Recapitulatif JSON (heures par UE + par enseignant) |
| GET | `/api/dashboard/export-bilan/` | Export bilan global (Excel, format officiel) |
| GET | `/api/dashboard/export-par-ue/` | Export par UE (un onglet par UE + recapitulatif) |
| GET | `/api/dashboard/export-par-enseignant/` | Export par enseignant (un onglet par enseignant) |
| GET | `/api/dashboard/export-heures/` | Export heures par mois (legacy) |

#### Filtres disponibles (query params)

Tous les endpoints dashboard (sauf export-heures) supportent :

| Parametre | Type | Description |
|-----------|------|-------------|
| `date_debut` | YYYY-MM-DD | Date de debut de la periode |
| `date_fin` | YYYY-MM-DD | Date de fin de la periode |
| `filiere` | int | ID de la filiere |
| `niveau` | int | ID du niveau (ex: L1, M1) |
| `semestre` | int | Numero du semestre (1 ou 2) |

Exemple : `/api/dashboard/export-bilan/?filiere=1&niveau=3&semestre=1`

Le fichier Excel genere inclut la filiere/niveau/semestre dans le nom (ex: `BILAN_DES_COURS_Informatique_M1_S1.xlsx`).

Les endpoints `stats` et `recapitulatif` retournent aussi la liste des filieres et niveaux disponibles pour le departement du chef.

---

## Notifications Push (Firebase)

Le systeme utilise **Firebase Cloud Messaging (FCM)** pour envoyer des notifications push aux utilisateurs de l'application mobile.

- Les utilisateurs enregistrent leur token FCM via `/api/users/utilisateurs/register-fcm-token/`
- Le champ `fcm_token` est stocke sur le modele `Utilisateur`
- Le SDK `firebase_admin` (v7.1.0) est utilise cote serveur pour envoyer les notifications

---

## Documentation API

| URL | Description |
|-----|-------------|
| `/swagger/` | Interface Swagger UI (interactive) |
| `/redoc/` | Interface ReDoc (documentation) |

---

## Installation locale

### Prerequis
- Python 3.10+
- pip

### Etapes

1. **Cloner le repository**
```bash
git clone https://github.com/M1-INF-4027/KOURSA_BACKEND.git
cd KOURSA_BACKEND/koursa
```

2. **Creer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. **Installer les dependances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**
```bash
# Creer un fichier .env dans koursa/koursa/.env
SECRET_KEY=votre-cle-secrete
DEBUG=True
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

## Scripts utiles

```bash
# Lancer le serveur de developpement
python manage.py runserver

# Creer les migrations apres modification des modeles
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Creer un superutilisateur
python manage.py createsuperuser

# Collecter les fichiers statiques (production)
python manage.py collectstatic --noinput

# Lancer le serveur de production (Gunicorn)
gunicorn koursa.wsgi:application --bind 0.0.0.0:8000
```

---

## Equipe

Projet realise par **M1 INF 4027** - Master 1 Informatique.

## Licence

Apache License 2.0 - Copyright (c) 2025 M1 INF 4027
