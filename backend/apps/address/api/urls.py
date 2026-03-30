from django.urls import path

from .views import PincodeLookupView, ReverseLookupView

app_name = "address"

urlpatterns = [
    path("pincode/<str:pincode>/", PincodeLookupView.as_view(), name="pincode-lookup"),
    path("reverse/", ReverseLookupView.as_view(), name="reverse-lookup"),
]

