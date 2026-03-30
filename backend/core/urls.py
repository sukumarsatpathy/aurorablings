from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.api_root, name='v1-root'),
    path('health-check/', views.health_check, name='v1-health'),
    path('admin/dashboard/', views.admin_dashboard, name='admin-dashboard'),
]
