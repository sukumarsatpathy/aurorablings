from django.urls import path

from .views import CookieConsentCreateView, CookieConsentCurrentView, CookieConsentWithdrawView

app_name = "privacy"

urlpatterns = [
    path("consent/", CookieConsentCreateView.as_view(), name="consent-create"),
    path("consent/withdraw/", CookieConsentWithdrawView.as_view(), name="consent-withdraw"),
    path("consent/current/", CookieConsentCurrentView.as_view(), name="consent-current"),
]
