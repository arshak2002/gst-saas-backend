import uuid
from django.db import models
from apps.accounts.models import Business

class Customer(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    gstin = models.CharField(max_length=15, null=True, blank=True)
    state = models.CharField(max_length=100)
    address = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    hsn_sac = models.CharField(max_length=20)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2) # e.g. 18.00
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('FINAL', 'Final'),
    ]
    TYPE_CHOICES = [
        ('INVOICE', 'Tax Invoice'),
        ('CREDIT_NOTE', 'Credit Note'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Partial'),
        ('PAID', 'Paid'),
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=100)
    financial_year = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='INVOICE')
    parent_invoice = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_notes')
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    # RCM & POS
    is_rcm_applicable = models.BooleanField(default=False)
    place_of_supply = models.CharField(max_length=100, null=True, blank=True)

    # Financials
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    rounding_adjustment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Tracking
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # E-Invoice Roadmap
    irn = models.CharField(max_length=100, null=True, blank=True)
    ack_number = models.CharField(max_length=50, null=True, blank=True)
    ack_date = models.DateTimeField(null=True, blank=True)

    # Public View
    public_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    notes = models.TextField(blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('business', 'invoice_number')

    def __str__(self):
        return f"{self.invoice_number} - {self.business.name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    @property
    def total(self):
        return self.taxable_value + self.cgst + self.sgst + self.igst

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"

class InvoiceTemplate(models.Model):
    name = models.CharField(max_length=100)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    # Stored as JSON to be flexible
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
