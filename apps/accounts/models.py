from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class Business(models.Model):
    PLAN_CHOICES = [
        ('FREE', 'Free'),
        ('BASIC', 'Basic (Growth)'),
        ('PRO', 'Professional'),
    ]
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15)
    state = models.CharField(max_length=100)
    address = models.TextField()
    invoice_prefix = models.CharField(max_length=10, default='INV')
    default_notes = models.TextField(blank=True, null=True)
    default_terms = models.TextField(blank=True, null=True)
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default='FREE')
    plan_expiry = models.DateField(null=True, blank=True)
    logo = models.ImageField(upload_to='business_logos/', null=True, blank=True)

    def __str__(self):
        return self.name

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('STAFF', 'Staff'),
        ('VIEWER', 'Viewer'),
    ]
    username = None
    email = models.EmailField(unique=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, related_name='users')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='ADMIN')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    action = models.CharField(max_length=255) # e.g. "Created Invoice", "Deleted Customer"
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
