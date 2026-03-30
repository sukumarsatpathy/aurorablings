from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "inventory"

router = DefaultRouter()
router.register("warehouses", views.WarehouseViewSet, basename="warehouse")

urlpatterns = [
    path("", include(router.urls)),

    # ── Stock levels ──────────────────────────────────────────
    path("stock/",                           views.StockRecordListView.as_view(),    name="stock-list"),
    path("stock/<uuid:pk>/",                 views.StockRecordDetailView.as_view(),  name="stock-detail"),
    path("stock/variant/<uuid:variant_id>/", views.StockLevelView.as_view(),      name="stock-level"),
    path("stock/variants/",                  views.VariantOptionsView.as_view(),     name="stock-variants"),
    path("stock/low-stock/",                 views.LowStockView.as_view(),         name="low-stock"),
    path("stock/availability/",              views.AvailabilityCheckView.as_view(), name="availability"),

    # ── Operations ────────────────────────────────────────────
    path("stock/receive/",                   views.ReceiveStockView.as_view(),     name="receive"),
    path("stock/adjust/",                    views.AdjustStockView.as_view(),      name="adjust"),
    path("stock/transfer/",                  views.TransferStockView.as_view(),    name="transfer"),
    path("stock/reserve/",                   views.ReserveStockView.as_view(),     name="reserve"),
    path("stock/release/",                   views.ReleaseReservationView.as_view(), name="release"),
    path("stock/return/",                    views.ProcessReturnView.as_view(),    name="return"),
    path("stock/exchange/",                  views.ProcessExchangeView.as_view(),  name="exchange"),

    # ── Ledger & admin ────────────────────────────────────────
    path("stock/ledger/",                    views.StockLedgerView.as_view(),      name="ledger"),
    path("stock/recompute/<uuid:pk>/",       views.RecomputeStockView.as_view(),   name="recompute"),
]
