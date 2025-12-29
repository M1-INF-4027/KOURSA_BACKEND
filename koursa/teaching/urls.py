from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UniteEnseignementViewSet, FicheSuiviViewSet

router = DefaultRouter()
router.register(r'unites-enseignement', UniteEnseignementViewSet, basename='uniteenseignement')
router.register(r'fiches-suivi', FicheSuiviViewSet, basename='fichesuivi')

urlpatterns = [
    path('', include(router.urls)),
]