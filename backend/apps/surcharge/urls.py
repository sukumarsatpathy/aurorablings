from django.urls import path
from . import views

app_name = "surcharge"

urlpatterns = [
    # ── Calculation ───────────────────────────────────────────
    path("calculate/", views.CartSurchargeView.as_view(), name="calculate"),
    path("shipping-summary/", views.ShippingSummaryView.as_view(), name="shipping-summary"),

    # ── Tax rules ─────────────────────────────────────────────
    path("tax/",           views.TaxRuleListCreateView.as_view(),  name="tax-list"),
    path("tax/<uuid:pk>/", views.TaxRuleDetailView.as_view(),      name="tax-detail"),

    # ── Shipping rules ────────────────────────────────────────
    path("shipping/",           views.ShippingRuleListCreateView.as_view(), name="shipping-list"),
    path("shipping/<uuid:pk>/", views.ShippingRuleDetailView.as_view(),     name="shipping-detail"),

    # ── Fee rules ─────────────────────────────────────────────
    path("fees/",           views.FeeRuleListCreateView.as_view(),  name="fee-list"),
    path("fees/<uuid:pk>/", views.FeeRuleDetailView.as_view(),      name="fee-detail"),
]
