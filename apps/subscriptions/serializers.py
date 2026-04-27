from rest_framework import serializers
from .models import SubscriptionPlan, BusinessSubscription, PaymentTransaction

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'

class BusinessSubscriptionSerializer(serializers.ModelSerializer):
    plan_details = SubscriptionPlanSerializer(source='plan', read_only=True)
    
    class Meta:
        model = BusinessSubscription
        fields = [
            'id', 'plan', 'plan_details', 'status', 
            'current_period_start', 'current_period_end', 
            'trial_end', 'cancel_at_period_end', 'razorpay_subscription_id'
        ]
        read_only_fields = ['status', 'current_period_start', 'current_period_end', 'trial_end']

class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = '__all__'
