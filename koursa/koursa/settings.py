from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Charger les variables d'environnement depuis le fichier .env
ENV_FILE = Path(__file__).resolve().parent / '.env'
load_dotenv(ENV_FILE)

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "La variable d'environnement SECRET_KEY est obligatoire. "
        "Ajoutez-la dans votre fichier .env ou vos variables d'environnement."
    )

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
ALLOWED_HOSTS_ENV = os.environ.get('ALLOWED_HOSTS', '')

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
elif ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(',')]
else:
    ALLOWED_HOSTS.extend(['127.0.0.1', 'localhost'])

# En mode DEBUG, autoriser l'acces depuis le reseau local (appareils physiques)
if DEBUG:
    ALLOWED_HOSTS.extend(['0.0.0.0', '192.168.1.198', '10.0.2.2'])

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'django_filters',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_yasg',

    # Local apps

    'users',
    'academic',
    'teaching',
    'dashboard'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# En developpement, autoriser les origines locales supplementaires
if DEBUG:
    CORS_ALLOWED_ORIGINS.extend([
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:19006",
        "http://10.0.2.2:8000",
    ])

# Configuration CSRF pour accès via IP (utiliser les variables d'environnement en production)
CSRF_TRUSTED_ORIGINS = []
CSRF_TRUSTED_ORIGINS_ENV = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if CSRF_TRUSTED_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in CSRF_TRUSTED_ORIGINS_ENV.split(',')]
else:
    CSRF_TRUSTED_ORIGINS = [
        'http://127.0.0.1:8082',
        'http://localhost:8082',
    ]

ROOT_URLCONF = 'koursa.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'koursa.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '100/minute',
        'login': '5/minute',
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60), 
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),   
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY, 
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",

    "JTI_CLAIM": "jti",

    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

LANGUAGE_CODE = 'fr-fr' 
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise pour les fichiers statiques
if DEBUG:
    # En developpement, utiliser le stockage simple
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
else:
    # En production, utiliser le manifest pour le cache
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

AUTH_USER_MODEL = 'users.Utilisateur'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'koursa.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'koursa': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'koursa.notifications': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Repertoire des fichiers statiques supplementaires
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# ─────────────────────────────────────────────
# JAZZMIN - Theme admin moderne
# ─────────────────────────────────────────────

JAZZMIN_SETTINGS = {
    # Titre et branding
    "site_title": "Koursa Admin",
    "site_header": "Koursa",
    "site_brand": "Koursa",
    "site_logo": None,
    "login_logo": None,
    "site_logo_classes": "img-circle",
    "site_icon": None,
    "welcome_sign": "Bienvenue sur Koursa Admin",
    "copyright": "Koursa",

    # Recherche dans les modeles
    "search_model": ["users.Utilisateur", "academic.Faculte"],

    # Lien utilisateur en haut
    "user_avatar": None,

    # Navigation superieure
    "topmenu_links": [
        {"name": "Accueil", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "API Docs", "url": "/swagger/", "new_window": True},
        {"app": "users"},
    ],

    # Navigation sidebar - menus personnalises
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    # Icones pour chaque app et modele
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "users": "fas fa-user-shield",
        "users.Utilisateur": "fas fa-user-graduate",
        "users.Role": "fas fa-user-tag",
        "academic": "fas fa-university",
        "academic.Faculte": "fas fa-building-columns",
        "academic.Departement": "fas fa-sitemap",
        "academic.Filiere": "fas fa-graduation-cap",
        "academic.Niveau": "fas fa-layer-group",
        "teaching": "fas fa-chalkboard-teacher",
        "teaching.UniteEnseignement": "fas fa-book",
        "teaching.FicheSuivi": "fas fa-clipboard-check",
        "dashboard": "fas fa-chart-line",
        "rest_framework_simplejwt.token_blacklist": "fas fa-ban",
    },

    # Icone par defaut
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # Liens en bas du menu
    "related_modal_active": False,

    # UI Tweaks
    "custom_css": "admin/css/koursa_admin.css",
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    # Changer le texte du lien de retour
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "users.Utilisateur": "collapsible",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "flatly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}