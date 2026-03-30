from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PromoBannerViewSet

router = DefaultRouter()
router.register(r'', PromoBannerViewSet, basename='promo-banner')

urlpatterns = [
    path('', include(router.urls)),
]
