import os
from django.core.wsgi import get_wsgi_application
from .firebase_config import initialize_firebase 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koursa.settings')
initialize_firebase()

application = get_wsgi_application()
