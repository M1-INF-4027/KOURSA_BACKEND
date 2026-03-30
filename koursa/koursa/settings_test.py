"""
Settings for running tests against PostgreSQL (same engine as production).
Inherits everything from main settings, overrides only the database.
"""
from .settings import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'koursa_db_test',
        'USER': 'koursa_user',
        'PASSWORD': 'koursa2026',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
