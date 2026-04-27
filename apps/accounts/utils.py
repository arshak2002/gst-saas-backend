from .models import ActivityLog

def log_activity(request, action, model_name, object_id=None, details=None):
    """
    Utility to log business/user activity.
    """
    if not request.user.is_authenticated:
        return

    # Get IP Address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    ActivityLog.objects.create(
        user=request.user,
        business=request.user.business,
        action=action,
        model_name=model_name,
        object_id=str(object_id) if object_id else None,
        ip_address=ip,
        details=details
    )
