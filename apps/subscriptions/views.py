from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import views, status, response, permissions
from .models import SubscriptionPlan, BusinessSubscription, PaymentTransaction
from .serializers import SubscriptionPlanSerializer, BusinessSubscriptionSerializer
from apps.payments.services.razorpay_client import RazorpayClient
import logging

logger = logging.getLogger(__name__)

class PlanListView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return response.Response(serializer.data)

class CurrentSubscriptionView(views.APIView):
    def get(self, request):
        business = request.user.business
        if not business:
            return response.Response({"error": "User not associated with a business"}, status=status.HTTP_400_BAD_REQUEST)
        subscription, created = BusinessSubscription.objects.get_or_create(business=business)
        serializer = BusinessSubscriptionSerializer(subscription)
        return response.Response(serializer.data)

class SubscribeView(views.APIView):
    def post(self, request):
        business = request.user.business
        plan_id = request.data.get('plan_id')
        interval = request.data.get('interval', 'monthly') # 'monthly' or 'yearly'
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            return response.Response({"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)

        rzp = RazorpayClient()
        
        subscription_record, _ = BusinessSubscription.objects.get_or_create(business=business)
        if not subscription_record.razorpay_customer_id:
            customer = rzp.create_customer(business.name, request.user.email)
            if customer:
                subscription_record.razorpay_customer_id = customer['id']
                subscription_record.save()
            else:
                return response.Response({"error": "Failed to create Razorpay customer"}, status=status.HTTP_400_BAD_REQUEST)

        rzp_plan_id = plan.features.get(f'rzp_plan_{interval}_id')
        if not rzp_plan_id:
             # If not in features, try to use a default or error out
             # For testing/demo, we might use a dummy plan ID if provided in request
             rzp_plan_id = request.data.get('rzp_plan_id')
             if not rzp_plan_id:
                return response.Response({"error": "Plan ID not configured for this interval"}, status=status.HTTP_400_BAD_REQUEST)

        rzp_sub = rzp.create_subscription(rzp_plan_id, subscription_record.razorpay_customer_id)
        if rzp_sub:
            subscription_record.razorpay_subscription_id = rzp_sub['id']
            subscription_record.plan = plan
            subscription_record.save()
            
            return response.Response({
                "subscription_id": rzp_sub['id'],
                "razorpay_key": settings.RAZORPAY_KEY_ID
            })
        
        return response.Response({"error": "Failed to initiate subscription"}, status=status.HTTP_400_BAD_REQUEST)

class VerifyPaymentView(views.APIView):
    def post(self, request):
        rzp = RazorpayClient()
        params = {
            'razorpay_payment_id': request.data.get('razorpay_payment_id'),
            'razorpay_subscription_id': request.data.get('razorpay_subscription_id'),
            'razorpay_signature': request.data.get('razorpay_signature')
        }
        
        if rzp.verify_subscription_signature(params):
            # Success! Update local subscription status
            sub_id = params['razorpay_subscription_id']
            try:
                subscription = BusinessSubscription.objects.get(razorpay_subscription_id=sub_id)
                subscription.status = 'ACTIVE'
                # Sync period from Razorpay
                rzp_sub = rzp.get_subscription(sub_id)
                if rzp_sub:
                    subscription.current_period_start = timezone.datetime.fromtimestamp(rzp_sub['current_start'])
                    subscription.current_period_end = timezone.datetime.fromtimestamp(rzp_sub['current_end'])
                subscription.save()
                
                # Update user's business plan shortcut
                business = subscription.business
                business.plan = subscription.plan.code
                business.save()

                return response.Response({"status": "Payment verified and subscription activated"})
            except BusinessSubscription.DoesNotExist:
                return response.Response({"error": "Subscription record not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return response.Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

class CancelSubscriptionView(views.APIView):
    def post(self, request):
        business = request.user.business
        try:
            subscription = BusinessSubscription.objects.get(business=business)
            if not subscription.razorpay_subscription_id:
                return response.Response({"error": "No active subscription found"}, status=status.HTTP_400_BAD_REQUEST)
            
            rzp = RazorpayClient()
            rzp.cancel_subscription(subscription.razorpay_subscription_id)
            
            subscription.cancel_at_period_end = True
            subscription.save()
            
            return response.Response({"status": "Subscription scheduled for cancellation at period end"})
        except BusinessSubscription.DoesNotExist:
            return response.Response({"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND)

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(views.APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature')
        body = request.body.decode('utf-8')
        
        rzp = RazorpayClient()
        if not rzp.verify_webhook_signature(body, signature):
            logger.warning("Invalid Razorpay Webhook Signature")
            return response.Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        
        payload = request.data
        event = payload.get('event')
        
        logger.info(f"Handling Razorpay Webhook Event: {event}")
        
        # Dispatch event
        if event == 'subscription.activated':
            self._handle_subscription_activated(payload)
        elif event == 'subscription.charged':
            self._handle_subscription_charged(payload)
        elif event == 'subscription.cancelled':
            self._handle_subscription_cancelled(payload)
        elif event == 'payment.failed':
            self._handle_payment_failed(payload)
            
        return response.Response({"status": "ok"})

    def _handle_subscription_activated(self, payload):
        sub_data = payload['payload']['subscription']['entity']
        sub_id = sub_data['id']
        try:
            subscription = BusinessSubscription.objects.get(razorpay_subscription_id=sub_id)
            subscription.status = 'ACTIVE'
            subscription.current_period_start = timezone.datetime.fromtimestamp(sub_data['current_start'])
            subscription.current_period_end = timezone.datetime.fromtimestamp(sub_data['current_end'])
            subscription.save()
            
            business = subscription.business
            business.plan = subscription.plan.code
            business.save()
        except BusinessSubscription.DoesNotExist:
            pass

    def _handle_subscription_charged(self, payload):
        sub_data = payload['payload']['subscription']['entity']
        payment_data = payload['payload']['payment']['entity']
        sub_id = sub_data['id']
        
        try:
            subscription = BusinessSubscription.objects.get(razorpay_subscription_id=sub_id)
            subscription.status = 'ACTIVE'
            subscription.current_period_start = timezone.datetime.fromtimestamp(sub_data['current_start'])
            subscription.current_period_end = timezone.datetime.fromtimestamp(sub_data['current_end'])
            subscription.save()
            
            # Log Transaction
            PaymentTransaction.objects.create(
                business=subscription.business,
                amount=payment_data['amount'] / 100,
                currency=payment_data['currency'],
                razorpay_payment_id=payment_data['id'],
                razorpay_order_id=payment_data['order_id'],
                status='SUCCESS',
                raw_payload=payload
            )
        except BusinessSubscription.DoesNotExist:
            pass

    def _handle_subscription_cancelled(self, payload):
        sub_data = payload['payload']['subscription']['entity']
        sub_id = sub_data['id']
        try:
            subscription = BusinessSubscription.objects.get(razorpay_subscription_id=sub_id)
            subscription.status = 'CANCELLED'
            subscription.save()
            
            business = subscription.business
            business.plan = 'FREE'
            business.save()
        except BusinessSubscription.DoesNotExist:
            pass

    def _handle_payment_failed(self, payload):
        payment_data = payload['payload']['payment']['entity']
        # You might want to match by order_id or subscription_id if present
        # ... logic to notify user or mark sub as PAST_DUE
        pass
