from django.urls import path

from . import deploy_views

app_name = "public_health"

urlpatterns = [
    path("server", deploy_views.PublicServerHealthView.as_view(), name="server"),
    path("db", deploy_views.PublicDBHealthView.as_view(), name="db"),
    path("cache", deploy_views.PublicCacheHealthView.as_view(), name="cache"),
    path("payment", deploy_views.PublicPaymentHealthView.as_view(), name="payment"),
]
