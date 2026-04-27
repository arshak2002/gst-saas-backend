import json
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from apps.accounts.models import User, Business
from apps.subscriptions.models import SubscriptionPlan, BusinessSubscription, PaymentTransaction

class SubscriptionPlanTestCase(TestCase):
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            code='STARTER',
            name='Starter Plan',
            price_monthly=499,
            price_yearly=4999,
            invoice_limit=50,
            user_limit=3,
            features={'gst_export': True}
        )

    def test_plan_creation(self):
        self.assertEqual(self.plan.code, 'STARTER')
        self.assertEqual(self.plan.price_monthly, 499)
        self.assertEqual(str(self.plan), 'Starter Plan')

class BusinessSubscriptionTestCase(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name='Test Business',
            gstin='29ABCDE1234F1Z5',
            state='Karnataka',
            address='Bangalore'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            business=self.business
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.free_plan = SubscriptionPlan.objects.create(
            code='FREE',
            name='Free Plan',
            price_monthly=0,
            price_yearly=0,
            invoice_limit=5,
            user_limit=1
        )
        self.starter_plan = SubscriptionPlan.objects.create(
            code='STARTER',
            name='Starter Plan',
            price_monthly=499,
            price_yearly=4999,
            invoice_limit=50,
            user_limit=3,
            features={'rzp_plan_monthly_id': 'plan_test123', 'gst_export': True}
        )

    def test_list_plans(self):
        response = self.client.get('/api/billing/plans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_current_subscription(self):
        response = self.client.get('/api/billing/subscription/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('apps.payments.services.razorpay_client.RazorpayClient.create_customer')
    @patch('apps.payments.services.razorpay_client.RazorpayClient.create_subscription')
    def test_subscribe_flow(self, mock_create_sub, mock_create_customer):
        mock_create_customer.return_value = {'id': 'cust_test123'}
        mock_create_sub.return_value = {'id': 'sub_test123'}
        
        response = self.client.post('/api/billing/subscribe/', {
            'plan_id': self.starter_plan.id,
            'interval': 'monthly'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('subscription_id', response.data)

class WebhookTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.business = Business.objects.create(
            name='Test Business',
            gstin='29ABCDE1234F1Z5',
            state='Karnataka',
            address='Bangalore'
        )
        self.plan = SubscriptionPlan.objects.create(
            code='STARTER',
            name='Starter Plan',
            price_monthly=499,
            price_yearly=4999,
            invoice_limit=50,
            user_limit=3
        )
        self.subscription = BusinessSubscription.objects.create(
            business=self.business,
            plan=self.plan,
            status='TRIAL',
            razorpay_subscription_id='sub_test123',
            razorpay_customer_id='cust_test123'
        )

    @patch('apps.payments.services.razorpay_client.RazorpayClient.verify_webhook_signature')
    def test_subscription_activated_webhook(self, mock_verify):
        mock_verify.return_value = True
        
        payload = {
            'event': 'subscription.activated',
            'payload': {
                'subscription': {
                    'entity': {
                        'id': 'sub_test123',
                        'current_start': 1703500800,
                        'current_end': 1706179200
                    }
                }
            }
        }
        
        response = self.client.post(
            '/api/billing/webhook/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='test_signature'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'ACTIVE')

    @patch('apps.payments.services.razorpay_client.RazorpayClient.verify_webhook_signature')
    def test_subscription_charged_webhook(self, mock_verify):
        mock_verify.return_value = True
        
        payload = {
            'event': 'subscription.charged',
            'payload': {
                'subscription': {
                    'entity': {
                        'id': 'sub_test123',
                        'current_start': 1703500800,
                        'current_end': 1706179200
                    }
                },
                'payment': {
                    'entity': {
                        'id': 'pay_test123',
                        'order_id': 'order_test123',
                        'amount': 49900,
                        'currency': 'INR'
                    }
                }
            }
        }
        
        response = self.client.post(
            '/api/billing/webhook/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='test_signature'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check transaction was created
        transaction = PaymentTransaction.objects.filter(razorpay_payment_id='pay_test123').first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, 499)
        self.assertEqual(transaction.status, 'SUCCESS')

    @patch('apps.payments.services.razorpay_client.RazorpayClient.verify_webhook_signature')
    def test_subscription_cancelled_webhook(self, mock_verify):
        mock_verify.return_value = True
        self.subscription.status = 'ACTIVE'
        self.subscription.save()
        
        payload = {
            'event': 'subscription.cancelled',
            'payload': {
                'subscription': {
                    'entity': {
                        'id': 'sub_test123'
                    }
                }
            }
        }
        
        response = self.client.post(
            '/api/billing/webhook/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='test_signature'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'CANCELLED')

    @patch('apps.payments.services.razorpay_client.RazorpayClient.verify_webhook_signature')
    def test_invalid_webhook_signature(self, mock_verify):
        mock_verify.return_value = False
        
        response = self.client.post(
            '/api/billing/webhook/',
            data=json.dumps({'event': 'test'}),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='invalid_signature'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class PermissionsTestCase(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name='Test Business',
            gstin='29ABCDE1234F1Z5',
            state='Karnataka',
            address='Bangalore'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            business=self.business
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.free_plan = SubscriptionPlan.objects.create(
            code='FREE',
            name='Free Plan',
            price_monthly=0,
            price_yearly=0,
            invoice_limit=5,
            user_limit=1
        )
        BusinessSubscription.objects.create(
            business=self.business,
            plan=self.free_plan,
            status='ACTIVE'
        )

    def test_invoice_quota_check(self):
        from apps.subscriptions.permissions import HasInvoiceQuota
        from apps.billing.models import Invoice, Customer
        from django.utils import timezone
        
        customer = Customer.objects.create(
            business=self.business,
            name='Test Customer',
            state='Karnataka',
            address='Test Address'
        )
        
        # Create 5 invoices (at limit)
        for i in range(5):
            Invoice.objects.create(
                business=self.business,
                customer=customer,
                invoice_number=f'INV-{i}',
                invoice_date=timezone.now().date()
            )
        
        # Mock request
        class MockRequest:
            method = 'POST'
            user = self.user
        
        class MockView:
            pass
        
        permission = HasInvoiceQuota()
        self.assertFalse(permission.has_permission(MockRequest(), MockView()))


# Mock Razorpay Payloads for Testing
MOCK_RAZORPAY_PAYLOADS = {
    'subscription_activated': {
        'event': 'subscription.activated',
        'payload': {
            'subscription': {
                'entity': {
                    'id': 'sub_test123',
                    'plan_id': 'plan_test123',
                    'customer_id': 'cust_test123',
                    'status': 'active',
                    'current_start': 1703500800,
                    'current_end': 1706179200,
                    'quantity': 1
                }
            }
        }
    },
    'subscription_charged': {
        'event': 'subscription.charged',
        'payload': {
            'subscription': {
                'entity': {
                    'id': 'sub_test123',
                    'plan_id': 'plan_test123',
                    'customer_id': 'cust_test123',
                    'status': 'active',
                    'current_start': 1703500800,
                    'current_end': 1706179200
                }
            },
            'payment': {
                'entity': {
                    'id': 'pay_test123',
                    'order_id': 'order_test123',
                    'amount': 49900,
                    'currency': 'INR',
                    'status': 'captured',
                    'method': 'upi'
                }
            }
        }
    },
    'subscription_cancelled': {
        'event': 'subscription.cancelled',
        'payload': {
            'subscription': {
                'entity': {
                    'id': 'sub_test123',
                    'status': 'cancelled'
                }
            }
        }
    },
    'payment_failed': {
        'event': 'payment.failed',
        'payload': {
            'payment': {
                'entity': {
                    'id': 'pay_failed123',
                    'order_id': 'order_test456',
                    'amount': 49900,
                    'currency': 'INR',
                    'status': 'failed',
                    'error_code': 'BAD_REQUEST_ERROR',
                    'error_description': 'Payment failed due to insufficient balance'
                }
            }
        }
    }
}
