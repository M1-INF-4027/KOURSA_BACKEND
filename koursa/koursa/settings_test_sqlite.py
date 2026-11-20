"""
Variante des reglages de test, sur SQLite en memoire.

Les reglages de test visent PostgreSQL, le moteur de production : c'est le bon
defaut, et c'est lui qui doit tourner en integration continue. Mais il exige
un serveur disponible, ce qui n'est pas toujours le cas sur un poste de
developpement.

Cette variante permet de lancer la suite sans aucun service externe :

    python -m pytest --ds=koursa.settings_test_sqlite

Elle convient aux tests de logique metier, d'autorisation et de serialisation.
Elle ne convient PAS pour valider ce qui depend du moteur — contraintes
differees, types specifiques, comportement transactionnel fin : ceux-la se
verifient sur PostgreSQL.
"""
from .settings_test import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
