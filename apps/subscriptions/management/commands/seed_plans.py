from django.core.management.base import BaseCommand
from apps.subscriptions.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Seed subscription plans into the database'

    def handle(self, *args, **options):
        plans = [
            {
                'code': 'FREE',
                'name': 'Free',
                'price_monthly': 0,
                'price_yearly': 0,
                'invoice_limit': 5,
                'user_limit': 1,
                'features': {
                    'gst_export': False,
                    'e_invoice': False,
                    'priority_support': False,
                    'api_access': False
                }
            },
            {
                'code': 'STARTER',
                'name': 'Starter',
                'price_monthly': 499,
                'price_yearly': 4799,
                'invoice_limit': 50,
                'user_limit': 3,
                'features': {
                    'gst_export': True,
                    'e_invoice': False,
                    'priority_support': False,
                    'api_access': False,
                    'rzp_plan_monthly_id': '',  # Add your Razorpay plan ID
                    'rzp_plan_yearly_id': ''
                }
            },
            {
                'code': 'GROWTH',
                'name': 'Growth',
                'price_monthly': 999,
                'price_yearly': 9599,
                'invoice_limit': 200,
                'user_limit': 10,
                'features': {
                    'gst_export': True,
                    'e_invoice': True,
                    'priority_support': True,
                    'api_access': False,
                    'rzp_plan_monthly_id': '',
                    'rzp_plan_yearly_id': ''
                }
            },
            {
                'code': 'CA_PRO',
                'name': 'CA Pro',
                'price_monthly': 2499,
                'price_yearly': 23999,
                'invoice_limit': 999999,
                'user_limit': 50,
                'features': {
                    'gst_export': True,
                    'e_invoice': True,
                    'priority_support': True,
                    'api_access': True,
                    'multi_business': True,
                    'rzp_plan_monthly_id': '',
                    'rzp_plan_yearly_id': ''
                }
            },
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                code=plan_data['code'],
                defaults=plan_data
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(f'{status} plan: {plan.name}')
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded all subscription plans!'))
