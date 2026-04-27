import razorpay
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class RazorpayClient:
    def __init__(self):
        self.client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    def create_customer(self, name, email, contact=None):
        try:
            customer_data = {
                "name": name,
                "email": email,
            }
            if contact:
                customer_data["contact"] = contact
            
            customer = self.client.customer.create(data=customer_data)
            return customer
        except Exception as e:
            logger.error(f"Error creating Razorpay customer: {e}")
            return None

    def create_subscription(self, plan_id, customer_id, total_count=12):
        try:
            subscription = self.client.subscription.create(data={
                "plan_id": plan_id,
                "customer_id": customer_id,
                "total_count": total_count,
                "quantity": 1,
            })
            return subscription
        except Exception as e:
            logger.error(f"Error creating Razorpay subscription: {e}")
            return None

    def verify_payment_signature(self, params):
        try:
            return self.client.utility.verify_payment_signature(params)
        except Exception:
            return False

    def verify_subscription_signature(self, params):
        try:
            return self.client.utility.verify_subscription_payment_signature(params)
        except Exception:
            return False

    def verify_webhook_signature(self, body, signature):
        try:
            self.client.utility.verify_webhook_signature(
                body, 
                signature, 
                settings.RAZORPAY_WEBHOOK_SECRET
            )
            return True
        except Exception:
            return False

    def cancel_subscription(self, subscription_id, at_end=True):
        try:
            data = {'cancel_at_cycle_end': 1 if at_end else 0}
            return self.client.subscription.cancel(subscription_id, data=data)
        except Exception as e:
            logger.error(f"Error cancelling Razorpay subscription: {e}")
            return None

    def get_subscription(self, subscription_id):
        try:
            return self.client.subscription.fetch(subscription_id)
        except Exception as e:
            logger.error(f"Error fetching Razorpay subscription: {e}")
            return None
