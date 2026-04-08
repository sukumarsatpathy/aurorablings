from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    # ── Cart ──────────────────────────────────────────────────
    path("",           views.CartView.as_view(),      name="cart"),

    # ── Items ─────────────────────────────────────────────────
    path("items/",                       views.CartItemAddView.as_view(),    name="item-add"),
    path("items/<uuid:item_id>/",        views.CartItemDetailView.as_view(), name="item-detail"),

    # ── Merge + Validate ──────────────────────────────────────
    path("merge/",    views.CartMergeView.as_view(),    name="merge"),
    path("validate/", views.CartValidateView.as_view(), name="validate"),
    path("apply-coupon/", views.CartApplyCouponView.as_view(), name="apply-coupon"),
]
