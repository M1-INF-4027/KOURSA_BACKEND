# KOURSA Backend

Backend API REST pour la plateforme **Koursa** - Systeme de gestion academique et de suivi pedagogique.

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
│   ├── academic/            # Application Structure Academique
│   ├── teaching/            # Application Enseignement
│   ├── dashboard/           # Application Dashboard
│   ├── manage.py
│   └── requirements.txt
├── .github/workflows/       # CI/CD GitHub Actions
└── README.md
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

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/dashboard/` | Page d'accueil dashboard |
| GET | `/api/dashboard/stats/` | Statistiques du departement |
| GET | `/api/dashboard/export-heures/` | Export des heures (Excel) |

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

## Licence

Apache License 2.0 - Copyright (c) 2025 M1 INF 4027
