from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UtilisateurViewSet, RoleViewSet

router = DefaultRouter()
router.register(r'utilisateurs', UtilisateurViewSet, basename='utilisateur')
router.register(r'roles', RoleViewSet, basename='role')

urlpatterns = [
    path('', include(router.urls)),
]