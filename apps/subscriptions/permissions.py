from rest_framework import permissions
from .models import BusinessSubscription, SubscriptionPlan
from apps.billing.models import Invoice

class IsPlanAllowed(permissions.BasePermission):
    """
    Permission class to check if the user's business plan allows a specific feature.
    Usage: Set `required_plan` attribute on the view to specify minimum plan level.
    """
    PLAN_HIERARCHY = {
        'FREE': 0,
        'STARTER': 1,
        'GROWTH': 2,
        'CA_PRO': 3,
    }
    
    def has_permission(self, request, view):
        required_plan = getattr(view, 'required_plan', None)
        if not required_plan:
            return True
        
        business = request.user.business
        if not business:
            return False
        
        try:
            subscription = BusinessSubscription.objects.get(business=business)
            if subscription.status not in ['ACTIVE', 'TRIAL']:
                return False
            
            current_plan = subscription.plan.code if subscription.plan else 'FREE'
            required_level = self.PLAN_HIERARCHY.get(required_plan, 0)
            current_level = self.PLAN_HIERARCHY.get(current_plan, 0)
            
            return current_level >= required_level
        except BusinessSubscription.DoesNotExist:
            # No subscription = Free plan
            return self.PLAN_HIERARCHY.get(required_plan, 0) == 0

class HasInvoiceQuota(permissions.BasePermission):
    """
    Permission to check if the business has remaining invoice quota for their plan.
    """
    message = "Invoice limit exceeded for your current plan. Please upgrade."
    
    def has_permission(self, request, view):
        if request.method not in ['POST']:
            return True
        
        business = request.user.business
        if not business:
            return False
        
        try:
            subscription = BusinessSubscription.objects.get(business=business)
            invoice_limit = subscription.plan.invoice_limit if subscription.plan else 5
        except BusinessSubscription.DoesNotExist:
            # Default to Free plan limit
            invoice_limit = 5
        
        # Count invoices this month
        from django.utils import timezone
        current_month = timezone.now().month
        current_year = timezone.now().year
        invoice_count = Invoice.objects.filter(
            business=business,
            invoice_date__month=current_month,
            invoice_date__year=current_year
        ).count()
        
        return invoice_count < invoice_limit

class HasUserQuota(permissions.BasePermission):
    """
    Permission to check if the business can add more users.
    """
    message = "User limit exceeded for your current plan. Please upgrade."
    
    def has_permission(self, request, view):
        if request.method not in ['POST']:
            return True
        
        business = request.user.business
        if not business:
            return False
        
        try:
            subscription = BusinessSubscription.objects.get(business=business)
            user_limit = subscription.plan.user_limit if subscription.plan else 1
        except BusinessSubscription.DoesNotExist:
            user_limit = 1
        
        current_users = business.users.count()
        return current_users < user_limit

class CanExportGSTReports(permissions.BasePermission):
    """
    Permission to check if the user can export GST reports.
    Free users cannot export.
    """
    message = "GST export is not available on the Free plan. Please upgrade."
    
    def has_permission(self, request, view):
        business = request.user.business
        if not business:
            return False
        
        try:
            subscription = BusinessSubscription.objects.get(business=business)
            current_plan = subscription.plan.code if subscription.plan else 'FREE'
            return current_plan != 'FREE'
        except BusinessSubscription.DoesNotExist:
            return False
