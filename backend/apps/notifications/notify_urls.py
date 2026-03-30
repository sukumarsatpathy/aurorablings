from django.urls import path
from .views import NotifySubscriptionCreateView, NotifySubscriptionUnsubscribeView


urlpatterns = [
    path("", NotifySubscriptionCreateView.as_view(), name="notify-create"),
    path("unsubscribe/<uuid:token>/", NotifySubscriptionUnsubscribeView.as_view(), name="notify-unsubscribe"),
]
