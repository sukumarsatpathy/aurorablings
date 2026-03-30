from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = "catalog"

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("brands",     views.BrandViewSet,    basename="brand")
router.register("products",   views.ProductViewSet,  basename="product")
router.register("variants",   views.ProductVariantViewSet, basename="variant")
router.register("attributes", views.AttributeViewSet, basename="attribute")

urlpatterns = [
    path("", include(router.urls)),
]
