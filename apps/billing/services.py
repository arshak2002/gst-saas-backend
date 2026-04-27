from decimal import Decimal
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from weasyprint import HTML
import os

def calculate_gst(business_state, customer_state, taxable_value, gst_rate):
    """
    Returns (cgst, sgst, igst)
    """
    gst_amount = (taxable_value * gst_rate) / Decimal('100')
    
    if business_state.lower().strip() == customer_state.lower().strip():
        return (gst_amount / 2, gst_amount / 2, Decimal('0'))
    else:
        return (Decimal('0'), Decimal('0'), gst_amount)

def generate_invoice_pdf(invoice):
    """
    Generates a PDF for the invoice using WeasyPrint
    """
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'images', 'logo.png')
    if invoice.business.logo:
        logo_path = invoice.business.logo.path

    context = {
        'invoice': invoice,
        'business': invoice.business,
        'customer': invoice.customer,
        'items': invoice.items.all(),
        'logo_path': logo_path
    }
    html_string = render_to_string('invoices/invoice_template.html', context)
    pdf_file = HTML(string=html_string).write_pdf()
    
    filename = f"invoice_{invoice.invoice_number}.pdf"
    invoice.pdf_file.save(filename, ContentFile(pdf_file), save=True)
    return invoice.pdf_file.url
