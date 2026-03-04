from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from users.views import MyTokenObtainPairView, GoogleAuthView
from rest_framework_simplejwt.views import TokenRefreshView
from academic.views_configuration import (
    ConfigurationStatusView,
    CreateAnneeAcademiqueView,
    ActivateAnneeView,
    ActivateSemestreView,
    ReconduireAnneeView,
    MarkConfiguredView,
    SetupChecklistView,
    ChefChecklistView,
)

schema_view = get_schema_view(
   openapi.Info(
      title="Koursa API",
      default_version='v1',
      description="Documentation des API pour Koursa.",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('django-admin/', admin.site.urls),

    path('api/auth/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/google/', GoogleAuthView.as_view(), name='google_auth'),
    
    path('api/dashboard/', include('dashboard.urls')),
    path('api/academic/', include('academic.urls')),
    path('api/teaching/', include('teaching.urls')),
    path('api/users/', include('users.urls')),
    path('api/notifications/', include('notifications.urls')),

    # Configuration endpoints
    path('api/configuration/status/', ConfigurationStatusView.as_view(), name='config-status'),
    path('api/configuration/annee-academique/', CreateAnneeAcademiqueView.as_view(), name='config-create-annee'),
    path('api/configuration/annee-academique/<int:pk>/activer/', ActivateAnneeView.as_view(), name='config-activate-annee'),
    path('api/configuration/annee-academique/<int:pk>/marquer-configuree/', MarkConfiguredView.as_view(), name='config-mark-configured'),
    path('api/configuration/annee-academique/<int:pk>/reconduire/', ReconduireAnneeView.as_view(), name='config-reconduire'),
    path('api/configuration/semestre/<int:pk>/activer/', ActivateSemestreView.as_view(), name='config-activate-semestre'),
    path('api/configuration/checklist/', SetupChecklistView.as_view(), name='config-checklist'),
    path('api/configuration/chef-checklist/', ChefChecklistView.as_view(), name='config-chef-checklist'),

    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]