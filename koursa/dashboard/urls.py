from django.urls import path
from .views import (
    DashboardRootView,
    DashboardStatsView,
    RecapitulatifView,
    ExportBilanView,
    ExportParUEView,
    ExportParEnseignantView,
    ExportHeuresView,
)

urlpatterns = [
    path('', DashboardRootView.as_view(), name='dashboard-root'),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('recapitulatif/', RecapitulatifView.as_view(), name='dashboard-recapitulatif'),
    path('export-bilan/', ExportBilanView.as_view(), name='export-bilan'),
    path('export-par-ue/', ExportParUEView.as_view(), name='export-par-ue'),
    path('export-par-enseignant/', ExportParEnseignantView.as_view(), name='export-par-enseignant'),
    path('export-heures/', ExportHeuresView.as_view(), name='export-heures'),
]
