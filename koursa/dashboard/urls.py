from django.urls import path
from .views import DashboardStatsView, ExportHeuresView

urlpatterns = [
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('export-heures/', ExportHeuresView.as_view(), name='export-heures'),
]