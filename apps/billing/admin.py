from django.contrib import admin
from .models import Customer, Product, Invoice, InvoiceItem, InvoiceTemplate

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'gstin', 'state', 'is_active')
    list_filter = ('business', 'state', 'is_active')
    search_fields = ('name', 'gstin')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'hsn_sac', 'unit_price', 'gst_rate', 'is_active')
    list_filter = ('business', 'gst_rate', 'is_active')
    search_fields = ('name', 'hsn_sac')

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'business', 'customer', 'invoice_date', 'total', 'status', 'payment_status')
    list_filter = ('business', 'status', 'payment_status', 'invoice_date', 'is_rcm_applicable')
    search_fields = ('invoice_number', 'customer__name', 'irn')
    inlines = [InvoiceItemInline]
    readonly_fields = ('public_token', 'invoice_number', 'financial_year')

@admin.register(InvoiceTemplate)
class InvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'created_at')
    list_filter = ('business', 'created_at')
    search_fields = ('name',)

@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'product', 'quantity', 'rate', 'taxable_value')
