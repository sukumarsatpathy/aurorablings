from django.urls import path

from . import views

app_name = "shipping"

urlpatterns = [
    path("shipments/", views.ShipmentListView.as_view(), name="shipment-list"),
    path("orders/<uuid:order_id>/shipment/", views.OrderShipmentDetailView.as_view(), name="order-shipment-detail"),
    path("orders/<uuid:order_id>/shipping-status/", views.MyOrderShipmentDetailView.as_view(), name="my-order-shipping-status"),
    path("orders/<uuid:order_id>/shipping/approve/", views.ShippingApprovalView.as_view(), name="shipping-approve"),
    path("orders/<uuid:order_id>/shipment/create/", views.ShipmentCreateView.as_view(), name="shipment-create"),
    path("orders/<uuid:order_id>/shipment/preflight/", views.ShipmentPreflightView.as_view(), name="shipment-preflight"),
    path("shipments/<uuid:shipment_id>/pickup/", views.ShipmentPickupView.as_view(), name="shipment-pickup"),
    path("shipments/<uuid:shipment_id>/refresh-tracking/", views.ShipmentTrackingRefreshView.as_view(), name="shipment-refresh-tracking"),
    path("shipments/<uuid:shipment_id>/cancel/", views.ShipmentCancelView.as_view(), name="shipment-cancel"),
    path("shipments/<uuid:shipment_id>/local-status/", views.LocalDeliveryStatusUpdateView.as_view(), name="shipment-local-status"),
    path("tracking-update/", views.TrackingWebhookView.as_view(), name="tracking-update"),
    path("webhooks/nimbuspost/", views.NimbusPostWebhookView.as_view(), name="nimbuspost-webhook"),
]
