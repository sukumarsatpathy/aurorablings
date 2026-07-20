from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PromoBannerViewSet
from .bootstrap import bootstrap_fragment

router = DefaultRouter()
router.register(r'', PromoBannerViewSet, basename='promo-banner')

urlpatterns = [
    # Must precede the router include: the router's detail route pattern
    # (^<pk>/$) would otherwise swallow this path as a pk lookup.
    path('bootstrap-fragment/', bootstrap_fragment, name='bootstrap-fragment'),
    path('', include(router.urls)),
]
