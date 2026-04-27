from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, ProductViewSet, InvoiceViewSet, ReportView, PublicInvoiceView, InvoiceTemplateViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'products', ProductViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'templates', InvoiceTemplateViewSet, basename='templates')
router.register(r'reports', ReportView, basename='reports')
router.register(r'public/invoices', PublicInvoiceView, basename='public-invoices')

from apps.accounts.views import BusinessView

urlpatterns = [
    path('', include(router.urls)),
    path('business/', BusinessView.as_view(), name='business'),
]
