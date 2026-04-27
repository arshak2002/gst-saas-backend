from rest_framework import serializers
from .models import Customer, Product, Invoice, InvoiceItem, InvoiceTemplate
from .services import calculate_gst
from decimal import Decimal

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ('business',)

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('business',)

class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    class Meta:
        model = InvoiceItem
        fields = ('id', 'product', 'product_name', 'quantity', 'rate', 'taxable_value', 'cgst', 'sgst', 'igst')
        read_only_fields = ('taxable_value', 'cgst', 'sgst', 'igst')

class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)
    customer_name = serializers.ReadOnlyField(source='customer.name')

    class Meta:
        model = Invoice
        fields = ('id', 'customer', 'customer_name', 'invoice_number', 'invoice_date', 'due_date',
                  'financial_year', 'status', 'type', 'parent_invoice', 'is_rcm_applicable', 'place_of_supply',
                  'subtotal', 'cgst', 'sgst', 'igst', 'rounding_adjustment', 'total', 
                  'payment_status', 'amount_paid', 'pdf_file', 'notes', 'terms', 
                  'irn', 'ack_number', 'ack_date', 'public_token', 'items')
        read_only_fields = ('business', 'invoice_number', 'financial_year', 'subtotal', 
                            'cgst', 'sgst', 'igst', 'total', 'pdf_file', 'rounding_adjustment', 'public_token')

    def validate(self, data):
        if self.instance and self.instance.status == 'FINAL':
            raise serializers.ValidationError("Cannot edit a finalized invoice")
        return data

    def get_financial_year(self, date):
        year = date.year
        if date.month <= 3: # Jan-Mar
            return f"{year-1}-{str(year)[2:]}"
        else: # Apr-Dec
            return f"{year}-{str(year+1)[2:]}"

    def create(self, validated_data):
        from datetime import timedelta
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        business = user.business
        customer = validated_data['customer']
        date = validated_data.get('invoice_date')
        
        # Populate defaults
        if not validated_data.get('notes'):
            validated_data['notes'] = business.default_notes
        if not validated_data.get('terms'):
            validated_data['terms'] = business.default_terms
        if not validated_data.get('due_date'):
            validated_data['due_date'] = date + timedelta(days=15)
        if not validated_data.get('place_of_supply'):
             validated_data['place_of_supply'] = customer.state

        # Generate Financial Year
        fy = self.get_financial_year(date)
        
        last_invoice = Invoice.objects.filter(business=business, financial_year=fy).order_by('id').last()
        next_id = 1
        if last_invoice:
            try:
                next_id = int(last_invoice.invoice_number.split('/')[-1]) + 1
            except:
                next_id = Invoice.objects.filter(business=business).count() + 1
        
        invoice_no = f"INV/{fy}/{next_id:04d}"

        invoice = Invoice.objects.create(
            business=business, 
            invoice_number=invoice_no,
            financial_year=fy,
            **validated_data
        )
        
        subtotal = Decimal('0')
        total_cgst = Decimal('0')
        total_sgst = Decimal('0')
        total_igst = Decimal('0')

        for item_data in items_data:
            product = item_data['product']
            qty = Decimal(str(item_data['quantity']))
            rate = Decimal(str(item_data['rate']))
            taxable_val = qty * rate
            
            cgst, sgst, igst = calculate_gst(
                business.state, 
                customer.state, 
                taxable_val, 
                product.gst_rate
            )
            
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=qty,
                rate=rate,
                taxable_value=taxable_val,
                cgst=cgst,
                sgst=sgst,
                igst=igst
            )
            
            subtotal += taxable_val
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst

        # Rounding Logic (nearest rupee)
        raw_total = subtotal + total_cgst + total_sgst + total_igst
        rounded_total = raw_total.quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        adjustment = rounded_total - raw_total

        invoice.subtotal = subtotal
        invoice.cgst = total_cgst
        invoice.sgst = total_sgst
        invoice.igst = total_igst
        invoice.rounding_adjustment = adjustment
        invoice.total = rounded_total
        invoice.save()
        
        return invoice

class InvoiceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceTemplate
        fields = '__all__'
        read_only_fields = ('business',)
