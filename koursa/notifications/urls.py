from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, AlertEnseignantView, AlertDelegueView

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

urlpatterns = [
    path('alert-enseignant/', AlertEnseignantView.as_view(), name='alert-enseignant'),
    path('alert-delegue/', AlertDelegueView.as_view(), name='alert-delegue'),
    path('', include(router.urls)),
]
