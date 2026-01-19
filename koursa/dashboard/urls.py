from django.urls import path
from .views import DashboardStatsView, ExportHeuresView, DashboardRootView

urlpatterns = [
    path('', DashboardRootView.as_view(), name='dashboard-root'),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('export-heures/', ExportHeuresView.as_view(), name='export-heures'),
]