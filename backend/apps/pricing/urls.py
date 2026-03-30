from django.urls import path
from . import views

app_name = "pricing"

urlpatterns = [
    path("coupons/", views.CouponListView.as_view(), name="coupon-list"),
    path("coupons/<uuid:coupon_id>/", views.CouponDetailView.as_view(), name="coupon-detail"),
]
