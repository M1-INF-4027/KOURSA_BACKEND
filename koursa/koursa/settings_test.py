"""
Settings for running tests against PostgreSQL (same engine as production).
Inherits everything from main settings, overrides only the database and cache.
"""
import os

from .settings import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('TEST_DB_NAME', 'koursa_db_test'),
        'USER': os.environ.get('TEST_DB_USER', 'koursa_user'),
        'PASSWORD': os.environ.get('TEST_DB_PASSWORD', ''),
        'HOST': os.environ.get('TEST_DB_HOST', 'localhost'),
        'PORT': os.environ.get('TEST_DB_PORT', '5432'),
    }
}

# Use in-memory cache for tests (no Redis dependency)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'koursa-test-cache',
    }
}
