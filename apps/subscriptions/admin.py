from django.contrib import admin
from .models import SubscriptionPlan, BusinessSubscription, PaymentTransaction

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'price_monthly', 'price_yearly', 'invoice_limit', 'user_limit', 'is_active']
    list_filter = ['is_active', 'code']
    search_fields = ['code', 'name']
    ordering = ['price_monthly']

@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['business', 'plan', 'status', 'current_period_end', 'cancel_at_period_end']
    list_filter = ['status', 'plan', 'cancel_at_period_end']
    search_fields = ['business__name', 'razorpay_subscription_id', 'razorpay_customer_id']
    raw_id_fields = ['business', 'plan']
    readonly_fields = ['razorpay_subscription_id', 'razorpay_customer_id']
    
    fieldsets = (
        ('Business Info', {
            'fields': ('business', 'plan', 'status')
        }),
        ('Razorpay Details', {
            'fields': ('razorpay_subscription_id', 'razorpay_customer_id'),
            'classes': ('collapse',)
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end', 'trial_end', 'cancel_at_period_end')
        }),
    )
    
    actions = ['activate_subscription', 'cancel_subscription', 'set_to_free']
    
    @admin.action(description='Activate selected subscriptions')
    def activate_subscription(self, request, queryset):
        queryset.update(status='ACTIVE')
    
    @admin.action(description='Cancel selected subscriptions')
    def cancel_subscription(self, request, queryset):
        queryset.update(status='CANCELLED')
    
    @admin.action(description='Set to Free Plan (for demos)')
    def set_to_free(self, request, queryset):
        free_plan = SubscriptionPlan.objects.filter(code='FREE').first()
        if free_plan:
            queryset.update(plan=free_plan, status='ACTIVE')

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['business', 'amount', 'currency', 'status', 'razorpay_payment_id', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['business__name', 'razorpay_payment_id', 'razorpay_order_id']
    readonly_fields = ['razorpay_payment_id', 'razorpay_order_id', 'raw_payload', 'created_at']
    date_hierarchy = 'created_at'
