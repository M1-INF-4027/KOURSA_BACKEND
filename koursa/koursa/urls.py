from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from users.views import MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

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
    
    path('api/dashboard/', include('dashboard.urls')),
    path('api/academic/', include('academic.urls')),
    path('api/teaching/', include('teaching.urls')),
    path('api/users/', include('users.urls')),

    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]