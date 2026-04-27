from django.urls import path
from .views import (
    PlanListView, 
    CurrentSubscriptionView, 
    SubscribeView, 
    VerifyPaymentView, 
    CancelSubscriptionView, 
    RazorpayWebhookView
)

urlpatterns = [
    path('plans/', PlanListView.as_view(), name='plan-list'),
    path('subscription/', CurrentSubscriptionView.as_view(), name='current-subscription'),
    path('subscribe/', SubscribeView.as_view(), name='subscribe'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('cancel/', CancelSubscriptionView.as_view(), name='cancel-subscription'),
    path('webhook/', RazorpayWebhookView.as_view(), name='razorpay-webhook'),
]
