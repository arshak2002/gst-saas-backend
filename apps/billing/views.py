import csv
import threading
from datetime import date, timedelta
from rest_framework import viewsets, permissions, status, response, decorators, renderers
from .models import Customer, Product, Invoice, InvoiceTemplate
from .serializers import CustomerSerializer, ProductSerializer, InvoiceSerializer, InvoiceTemplateSerializer
from .services import generate_invoice_pdf
from apps.accounts.utils import log_activity
from django.db.models import Sum, Q, F
from django.template.loader import render_to_string
from django.http import HttpResponse, FileResponse
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404
import zipfile
import io

from apps.subscriptions.permissions import IsPlanAllowed, HasInvoiceQuota, CanExportGSTReports

class IsAdminOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'STAFF']

class BaseBusinessViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return self.queryset.filter(business=self.request.user.business, is_active=True)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminOrStaff()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        instance = serializer.save(business=self.request.user.business)
        log_activity(self.request, f"Created {self.queryset.model.__name__}", self.queryset.model.__name__, instance.id)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(self.request, f"Updated {self.queryset.model.__name__}", self.queryset.model.__name__, instance.id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        log_activity(self.request, f"Soft-deleted {self.queryset.model.__name__}", self.queryset.model.__name__, instance.id)
        return response.Response(status=status.HTTP_204_NO_CONTENT)

class CustomerViewSet(BaseBusinessViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @decorators.action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        customer = self.get_object()
        invoices = Invoice.objects.filter(customer=customer, business=request.user.business, status='FINAL').order_by('invoice_date')
        
        ledger_entries = []
        balance = 0
        
        for inv in invoices:
            sign = -1 if inv.type == 'CREDIT_NOTE' else 1
            amount = inv.total * sign
            balance += amount
            
            ledger_entries.append({
                'date': inv.invoice_date,
                'type': inv.get_type_display(),
                'number': inv.invoice_number,
                'amount': amount,
                'balance': balance,
                'id': inv.id
            })
            
            if inv.amount_paid > 0:
                balance -= inv.amount_paid
                ledger_entries.append({
                    'date': inv.invoice_date, # Or payment date if we had one
                    'type': 'Payment Received',
                    'number': f"PAY-{inv.invoice_number}",
                    'amount': -inv.amount_paid,
                    'balance': balance,
                    'id': f"P{inv.id}"
                })
                
        return response.Response({
            'customer': customer.name,
            'current_balance': balance,
            'entries': ledger_entries
        })

class ProductViewSet(BaseBusinessViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return self.queryset.filter(business=self.request.user.business, is_active=True)

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsAdminOrStaff(), HasInvoiceQuota()]
        if self.action in ['update', 'partial_update', 'destroy', 'finalize', 'email', 'bulk_mark_paid']:
            return [permissions.IsAuthenticated(), IsAdminOrStaff()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = InvoiceSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            instance = serializer.save()
            log_activity(request, "Created Invoice", "Invoice", instance.id)
            return response.Response(serializer.data, status=status.HTTP_201_CREATED)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        log_activity(self.request, "Soft-deleted Invoice", "Invoice", instance.id)

    @decorators.action(detail=True, methods=['get'], renderer_classes=[renderers.StaticHTMLRenderer])
    def preview(self, request, pk=None):
        invoice = self.get_object()
        context = {
            'invoice': invoice,
            'business': invoice.business,
            'customer': invoice.customer,
            'items': invoice.items.all(),
        }
        html = render_to_string('invoices/invoice_template.html', context)
        return HttpResponse(html)

    @decorators.action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == 'FINAL':
            return response.Response({'error': 'Invoice already finalized'}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice.status = 'FINAL'
        invoice.save()
        generate_invoice_pdf(invoice)
        log_activity(request, "Finalized Invoice", "Invoice", invoice.id)
        return response.Response({'status': 'FINAL'})

    @decorators.action(detail=True, methods=['post'])
    def print(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != 'FINAL':
             return response.Response({'error': 'Invoice must be finalized before printing'}, status=status.HTTP_400_BAD_REQUEST)
        
        pdf_url = generate_invoice_pdf(invoice)
        return response.Response({'pdf_url': pdf_url})

    @decorators.action(detail=True, methods=['post'])
    def email(self, request, pk=None):
        invoice = self.get_object()
        if not invoice.customer.email:
            return response.Response({'error': 'Customer email not found'}, status=400)
        
        def send_async_email(inv):
            generate_invoice_pdf(inv)
            email = EmailMessage(
                f'Invoice {inv.invoice_number} from {inv.business.name}',
                'Please find the attached invoice.',
                None,
                [inv.customer.email],
            )
            email.attach_file(inv.pdf_file.path)
            email.send()

        threading.Thread(target=send_async_email, args=(invoice,)).start()
        log_activity(request, "Emailed Invoice", "Invoice", invoice.id)
        return response.Response({'message': 'Email job started in background'})

    @decorators.action(detail=False, methods=['post'], url_path='bulk-mark-paid')
    def bulk_mark_paid(self, request):
        ids = request.data.get('ids', [])
        Invoice.objects.filter(id__in=ids, business=request.user.business).update(payment_status='PAID', amount_paid=F('total'))
        log_activity(request, f"Bulk-marked {len(ids)} invoices as paid", "Invoice")
        return response.Response({'message': f'Marked {len(ids)} invoices as paid'})

    @decorators.action(detail=False, methods=['post'], url_path='bulk-download')
    def bulk_download(self, request):
        ids = request.data.get('ids', [])
        invoices = Invoice.objects.filter(id__in=ids, business=request.user.business, status='FINAL')
        
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zip_file:
            for inv in invoices:
                if not inv.pdf_file:
                    generate_invoice_pdf(inv)
                zip_file.write(inv.pdf_file.path, f"{inv.invoice_number.replace('/', '_')}.pdf")
        
        buffer.seek(0)
        log_activity(request, f"Bulk-downloaded {len(ids)} invoices", "Invoice")
        return FileResponse(buffer, as_attachment=True, filename="invoices_export.zip")

class InvoiceTemplateViewSet(BaseBusinessViewSet):
    queryset = InvoiceTemplate.objects.all()
    serializer_class = InvoiceTemplateSerializer

    def get_queryset(self):
        return self.queryset.filter(business=self.request.user.business)

class ReportView(viewsets.ViewSet):
    def get_permissions(self):
        if self.action in ['gst_summary', 'export']:
            return [permissions.IsAuthenticated(), CanExportGSTReports()]
        return [permissions.IsAuthenticated()]

    @decorators.action(detail=False, methods=['get'], url_path='gst-summary')
    def gst_summary(self, request):
        month_str = request.query_params.get('month') # YYYY-MM
        if not month_str:
            return response.Response({'error': 'Month is required'}, status=400)
        
        try:
            year, month = map(int, month_str.split('-'))
            base_qs = Invoice.objects.filter(
                business=request.user.business,
                invoice_date__year=year,
                invoice_date__month=month,
                status='FINAL'
            )
            
            invoices = base_qs.filter(type='INVOICE')
            credit_notes = base_qs.filter(type='CREDIT_NOTE')
            
            inv_sum = invoices.aggregate(
                total=Sum('total'), taxable=Sum('subtotal'), cgst=Sum('cgst'), sgst=Sum('sgst'), igst=Sum('igst')
            )
            cn_sum = credit_notes.aggregate(
                total=Sum('total'), taxable=Sum('subtotal'), cgst=Sum('cgst'), sgst=Sum('sgst'), igst=Sum('igst')
            )
            
            def get_val(d, k): return d.get(k) or 0
            
            summary = {
                'total_sales': get_val(inv_sum, 'total') - get_val(cn_sum, 'total'),
                'total_taxable': get_val(inv_sum, 'taxable') - get_val(cn_sum, 'taxable'),
                'total_cgst': get_val(inv_sum, 'cgst') - get_val(cn_sum, 'cgst'),
                'total_sgst': get_val(inv_sum, 'sgst') - get_val(cn_sum, 'sgst'),
                'total_igst': get_val(inv_sum, 'igst') - get_val(cn_sum, 'igst'),
            }
            
            return response.Response(summary)
        except Exception as e:
            return response.Response({'error': str(e)}, status=400)

    @decorators.action(detail=False, methods=['get'])
    def export(self, request):
        month_str = request.query_params.get('month')
        year, month = map(int, month_str.split('-'))
        invoices = Invoice.objects.filter(
            business=request.user.business,
            invoice_date__year=year,
            invoice_date__month=month,
            status='FINAL'
        ).order_by('invoice_date')

        res = HttpResponse(content_type='text/csv')
        res['Content-Disposition'] = f'attachment; filename="invoices_{month_str}.csv"'
        writer = csv.writer(res)
        writer.writerow(['Type', 'Invoice No', 'Date', 'Customer', 'Taxable', 'CGST', 'SGST', 'IGST', 'Total'])
        
        for inv in invoices:
            sign = -1 if inv.type == 'CREDIT_NOTE' else 1
            writer.writerow([
                inv.get_type_display(), 
                inv.invoice_number, 
                inv.invoice_date, 
                inv.customer.name, 
                inv.subtotal * sign, 
                inv.cgst * sign, 
                inv.sgst * sign, 
                inv.igst * sign, 
                inv.total * sign
            ])
            
        return res

    @decorators.action(detail=False, methods=['get'], url_path='aging')
    def aging_summary(self, request):
        today = date.today()
        unpaid = Invoice.objects.filter(
            business=request.user.business,
            payment_status__in=['UNPAID', 'PARTIAL'],
            status='FINAL',
            type='INVOICE'
        )
        
        aging = {
            '0_30': unpaid.filter(invoice_date__gte=today - timedelta(days=30)).aggregate(s=Sum('total'))['s'] or 0,
            '31_60': unpaid.filter(invoice_date__lt=today - timedelta(days=30), invoice_date__gte=today - timedelta(days=60)).aggregate(s=Sum('total'))['s'] or 0,
            '61_plus': unpaid.filter(invoice_date__lt=today - timedelta(days=60)).aggregate(s=Sum('total'))['s'] or 0,
            'total_outstanding': unpaid.aggregate(s=Sum('total'))['s'] or 0
        }
        return response.Response(aging)

class PublicInvoiceView(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    
    @decorators.action(detail=True, methods=['get'], url_path='view', renderer_classes=[renderers.StaticHTMLRenderer])
    def public_view(self, request, pk=None):
        invoice = get_object_or_404(Invoice, public_token=pk, is_active=True)
        context = {
            'invoice': invoice,
            'business': invoice.business,
            'customer': invoice.customer,
            'items': invoice.items.all(),
        }
        html = render_to_string('invoices/invoice_template.html', context)
        return HttpResponse(html)
