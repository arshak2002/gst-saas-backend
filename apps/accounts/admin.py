from django.contrib import admin
from .models import Business, User, ActivityLog

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'gstin', 'state', 'plan', 'plan_expiry')
    list_filter = ('plan', 'state')
    search_fields = ('name', 'gstin')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'business', 'role', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'business', 'role')
    search_fields = ('email',)

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'business', 'action', 'model_name')
    list_filter = ('business', 'model_name', 'timestamp')
    search_fields = ('action', 'user__email', 'details')
    readonly_fields = ('timestamp',)
