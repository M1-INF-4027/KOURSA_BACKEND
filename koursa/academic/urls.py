from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FaculteViewSet, DepartementViewSet, FiliereViewSet, NiveauViewSet

router = DefaultRouter()
router.register(r'facultes', FaculteViewSet, basename='faculte')
router.register(r'departements', DepartementViewSet, basename='departement')
router.register(r'filieres', FiliereViewSet, basename='filiere')
router.register(r'niveaux', NiveauViewSet, basename='niveau')

urlpatterns = [
    path('', include(router.urls)),
]