from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import UtilisateurViewSet

router = DefaultRouter()
router.register(r'utilisateurs', UtilisateurViewSet, basename='utilisateur')

urlpatterns = router.urls