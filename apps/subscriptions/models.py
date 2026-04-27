from django.db import models
from apps.accounts.models import Business

class SubscriptionPlan(models.Model):
    PLAN_CODES = [
        ('FREE', 'Free'),
        ('STARTER', 'Starter'),
        ('GROWTH', 'Growth'),
        ('CA_PRO', 'CA Pro'),
    ]
    code = models.CharField(max_length=20, choices=PLAN_CODES, unique=True)
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_limit = models.IntegerField(default=5)
    user_limit = models.IntegerField(default=1)
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_code_display()} Plan"

class BusinessSubscription(models.Model):
    STATUS_CHOICES = [
        ('TRIAL', 'Trial'),
        ('ACTIVE', 'Active'),
        ('PAST_DUE', 'Past Due'),
        ('CANCELLED', 'Cancelled'),
    ]
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='subscription_record')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TRIAL')
    razorpay_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_customer_id = models.CharField(max_length=100, blank=True, null=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.business.name} - {self.plan.code if self.plan else 'No Plan'}"

class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.business.name} - {self.amount} - {self.status}"
