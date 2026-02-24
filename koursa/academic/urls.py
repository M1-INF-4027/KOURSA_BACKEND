from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FaculteViewSet, DepartementViewSet, FiliereViewSet, NiveauViewSet,
    AnneeAcademiqueViewSet, SemestreViewSet, HistoriqueChefViewSet,
)

router = DefaultRouter()
router.register(r'facultes', FaculteViewSet, basename='faculte')
router.register(r'departements', DepartementViewSet, basename='departement')
router.register(r'filieres', FiliereViewSet, basename='filiere')
router.register(r'niveaux', NiveauViewSet, basename='niveau')
router.register(r'annees-academiques', AnneeAcademiqueViewSet, basename='annee-academique')
router.register(r'semestres', SemestreViewSet, basename='semestre')
router.register(r'historique-chefs', HistoriqueChefViewSet, basename='historique-chef')

urlpatterns = [
    path('', include(router.urls)),
]
