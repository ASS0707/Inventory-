from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from sqlalchemy import desc
import datetime
import random
import string
from app import db
from models import Invoice, InvoiceItem, Product, Client, Supplier, Payment, SystemLog
from forms.operations import PaymentForm, InvoiceForm
from routes import admin_required

operations_bp = Blueprint('operations', __name__, url_prefix='/operations')


@operations_bp.route('/')
@login_required
def index():
    # Get all operations with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Filter parameters
    type_filter = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    client_id = request.args.get('client_id', '')
    supplier_id = request.args.get('supplier_id', '')

    # Base query
    query = Invoice.query

    # Apply filters if provided
    if type_filter:
        query = query.filter(Invoice.type == type_filter)

    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Invoice.date >= from_date)
        except ValueError:
            flash('صيغة تاريخ البداية غير صالحة', 'warning')

    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Invoice.date <= to_date)
        except ValueError:
            flash('صيغة تاريخ النهاية غير صالحة', 'warning')

    if client_id:
        query = query.filter(Invoice.client_id == client_id)

    if supplier_id:
        query = query.filter(Invoice.supplier_id == supplier_id)

    # Execute query with pagination
    operations = query.order_by(desc(Invoice.date)).paginate(page=page, per_page=per_page)

    # Get clients and suppliers for filters
    clients = Client.query.order_by(Client.name).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()

    return render_template(
        'operations/index.html',
        operations=operations,
        clients=clients,
        suppliers=suppliers
    )


@operations_bp.route('/create_invoice', methods=['GET', 'POST'])
@login_required
@admin_required
def create_invoice():
    form = InvoiceForm()

    # Populate client and supplier choices
    form.client_id.choices = [(0, 'اختر العميل...')] + [(c.id, c.name) for c in Client.query.order_by(Client.name).all()]
    form.supplier_id.choices = [(0, 'اختر المورد...')] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]

    # Generate invoice number
    today = datetime.datetime.now().strftime('%Y%m%d')
    random_part = ''.join(random.choices(string.digits, k=4))
    form.invoice_number.data = f"INV-{today}-{random_part}"

    if request.method == 'POST':
        # Validate the form
        if form.validate():
            # Create the invoice
            invoice = Invoice(
                invoice_number=form.invoice_number.data,
                type=form.type.data,
                date=form.date.data,
                due_date=form.due_date.data,
                notes=form.notes.data,
                status='pending',
                created_by=current_user.id
            )

            # Set client or supplier based on invoice type
            if form.type.data in ['sale', 'return']:
                if form.client_id.data == 0:
                    flash('يجب اختيار عميل لهذا النوع من الفواتير', 'danger')
                    return render_template('operations/create_invoice.html', form=form)

                invoice.client_id = form.client_id.data
            elif form.type.data in ['purchase', 'supplier_return']:
                if form.supplier_id.data == 0:
                    flash('يجب اختيار مورد لهذا النوع من الفواتير', 'danger')
                    return render_template('operations/create_invoice.html', form=form)

                invoice.supplier_id = form.supplier_id.data

            # Save the invoice
            db.session.add(invoice)
            db.session.flush()  # Get the ID of the invoice

            # Process invoice items from form data (JSON string)
            items_json = request.form.get('itemsJson', '[]')
            try:
                import json
                items_data = json.loads(items_json)
            except Exception as e:
                flash(f'خطأ في قراءة بيانات الأصناف: {str(e)}', 'danger')
                return render_template('operations/create_invoice.html', form=form, products=Product.query.all())

            total_amount = 0

            for item_data in items_data:
                product_id = int(item_data['product_id'])
                quantity = int(item_data['quantity'])
                unit_price = float(item_data['unit_price'])
                total_price = quantity * unit_price

                # Create the invoice item
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                )

                db.session.add(item)
                total_amount += total_price

                # Update product quantity based on operation type
                product = Product.query.get(product_id)

                if form.type.data == 'sale':
                    product.quantity -= quantity
                elif form.type.data == 'purchase':
                    product.quantity += quantity
                elif form.type.data == 'return':
                    product.quantity += quantity
                elif form.type.data == 'supplier_return':
                    product.quantity -= quantity

            # Update invoice total
            invoice.total_amount = total_amount

            # Log the operation
            action = {
                'sale': 'فاتورة بيع',
                'purchase': 'فاتورة شراء',
                'return': 'مرتجع من عميل',
                'supplier_return': 'مرتجع إلى مورد'
            }[form.type.data]

            log = SystemLog(
                action=f'invoice_{form.type.data}',
                details=f'إنشاء {action}: {invoice.invoice_number} بقيمة {total_amount} ج.م',
                user_id=current_user.id
            )

            db.session.add(log)
            db.session.commit()

            flash(f'تم إنشاء الفاتورة {invoice.invoice_number} بنجاح', 'success')
            return redirect(url_for('operations.view_invoice', invoice_id=invoice.id))

    # Get all products for the item form
    products = Product.query.all()

    return render_template(
        'operations/create_invoice.html',
        form=form,
        products=products
    )


@operations_bp.route('/view_invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)

    # Get related client or supplier
    client = None
    supplier = None

    if invoice.client_id:
        client = Client.query.get(invoice.client_id)

    if invoice.supplier_id:
        supplier = Supplier.query.get(invoice.supplier_id)

    # Get invoice items
    items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()

    # Get payments
    payments = Payment.query.filter_by(invoice_id=invoice_id).order_by(Payment.payment_date).all()

    # Calculate total paid and remaining
    total_paid = sum(payment.amount for payment in payments)
    remaining = invoice.total_amount - total_paid

    return render_template(
        'operations/view_invoice.html',
        invoice=invoice,
        client=client,
        supplier=supplier,
        items=items,
        payments=payments,
        total_paid=total_paid,
        remaining=remaining
    )


@operations_bp.route('/edit_invoice/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = InvoiceForm(obj=invoice)

    # Populate client and supplier choices
    form.client_id.choices = [(0, 'اختر العميل...')] + [(c.id, c.name) for c in Client.query.order_by(Client.name).all()]
    form.supplier_id.choices = [(0, 'اختر المورد...')] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]

    if request.method == 'POST':
        # Validate the form
        if form.validate():
            # Update the invoice
            invoice.invoice_number = form.invoice_number.data
            invoice.date = form.date.data
            invoice.due_date = form.due_date.data
            invoice.notes = form.notes.data

            # Set client or supplier based on invoice type
            if form.type.data in ['sale', 'return']:
                if form.client_id.data == 0:
                    flash('يجب اختيار عميل لهذا النوع من الفواتير', 'danger')
                    return render_template('operations/edit_invoice.html', form=form, invoice=invoice)

                invoice.client_id = form.client_id.data
                invoice.supplier_id = None
            elif form.type.data in ['purchase', 'supplier_return']:
                if form.supplier_id.data == 0:
                    flash('يجب اختيار مورد لهذا النوع من الفواتير', 'danger')
                    return render_template('operations/edit_invoice.html', form=form, invoice=invoice)

                invoice.supplier_id = form.supplier_id.data
                invoice.client_id = None

            # Process invoice items from form data (JSON string)
            items_json = request.form.get('itemsJson', '[]')
            try:
                import json
                items_data = json.loads(items_json)
            except Exception as e:
                flash(f'خطأ في قراءة بيانات الأصناف: {str(e)}', 'danger')
                return render_template('operations/edit_invoice.html', form=form, invoice=invoice, items=[], products=Product.query.all())

            # Get old items for inventory adjustment
            old_items = InvoiceItem.query.filter_by(invoice_id=invoice.id).all()

            # Remove old items and adjust inventory
            for item in old_items:
                product = Product.query.get(item.product_id)

                # Reverse the previous quantity change
                if invoice.type == 'sale':
                    product.quantity += item.quantity
                elif invoice.type == 'purchase':
                    product.quantity -= item.quantity
                elif invoice.type == 'return':
                    product.quantity -= item.quantity
                elif invoice.type == 'supplier_return':
                    product.quantity += item.quantity

                db.session.delete(item)

            # Add new items and adjust inventory
            total_amount = 0

            for item_data in items_data:
                product_id = int(item_data['product_id'])
                quantity = int(item_data['quantity'])
                unit_price = float(item_data['unit_price'])
                total_price = quantity * unit_price

                # Create the invoice item
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                )

                db.session.add(item)
                total_amount += total_price

                # Update product quantity based on operation type
                product = Product.query.get(product_id)

                if form.type.data == 'sale':
                    product.quantity -= quantity
                elif form.type.data == 'purchase':
                    product.quantity += quantity
                elif form.type.data == 'return':
                    product.quantity += quantity
                elif form.type.data == 'supplier_return':
                    product.quantity -= quantity

            # Update invoice total
            invoice.total_amount = total_amount

            # Update invoice status
            invoice.update_status()

            # Log the operation
            log = SystemLog(
                action=f'invoice_edit',
                details=f'تعديل فاتورة: {invoice.invoice_number}',
                user_id=current_user.id
            )

            db.session.add(log)
            db.session.commit()

            flash(f'تم تحديث الفاتورة {invoice.invoice_number} بنجاح', 'success')
            return redirect(url_for('operations.view_invoice', invoice_id=invoice.id))

    # Get existing items
    items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()

    # Get all products for the item form
    products = Product.query.all()

    return render_template(
        'operations/edit_invoice.html',
        form=form,
        invoice=invoice,
        items=items,
        products=products
    )


@operations_bp.route('/add_payment/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = PaymentForm()

    # Set default values
    form.invoice_id.data = invoice_id
    if request.method == 'GET':
        form.amount.data = invoice.calculate_remaining_amount()
        form.payment_date.data = datetime.datetime.now()

    if form.validate_on_submit():
        try:
            # Validate payment amount
            payment_amount = round(float(form.amount.data), 2)
            remaining_amount = invoice.calculate_remaining_amount()

            if payment_amount <= 0:
                flash('مبلغ الدفع يجب أن يكون أكبر من 0', 'danger')
                return redirect(url_for('operations.add_payment', invoice_id=invoice_id))

            if payment_amount > remaining_amount:
                flash(f'مبلغ الدفع ({payment_amount:.2f} ج.م) يتجاوز المبلغ المتبقي ({remaining_amount:.2f} ج.م)', 'danger')
                return redirect(url_for('operations.add_payment', invoice_id=invoice_id))

            # Create payment record
            payment = Payment(
                invoice_id=invoice_id,
                amount=payment_amount,
                payment_date=form.payment_date.data,
                payment_method=form.payment_method.data,
                reference_number=form.reference_number.data,
                notes=form.notes.data,
                created_by=current_user.id
            )

            # Set client or supplier based on invoice type
            if invoice.type in ['sale', 'return']:
                payment.client_id = invoice.client_id
            else:
                payment.supplier_id = invoice.supplier_id

            # Add payment and update invoice status
            db.session.add(payment)
            invoice.update_status()

            # Log the payment
            entity_name = invoice.client.name if invoice.client_id else invoice.supplier.name
            log = SystemLog(
                action='payment_add',
                details=f'إضافة دفعة للفاتورة {invoice.invoice_number} ({entity_name}): {payment_amount} ج.م',
                user_id=current_user.id
            )
            db.session.add(log)

            db.session.commit()
            flash(f'تم إضافة الدفعة بمبلغ {payment_amount} ج.م بنجاح', 'success')
            return redirect(url_for('operations.view_invoice', invoice_id=invoice_id))

        except ValueError as e:
            db.session.rollback()
            flash('خطأ في قيمة المبلغ المدخل', 'danger')
            return redirect(url_for('operations.add_payment', invoice_id=invoice_id))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ في معالجة الدفعة: {str(e)}', 'danger')
            return redirect(url_for('operations.add_payment', invoice_id=invoice_id))

    return render_template(
        'operations/add_payment.html',
        form=form,
        invoice=invoice
    )


@operations_bp.route('/get_product_details/<int:product_id>')
@login_required
def get_product_details(product_id):
    product = Product.query.get_or_404(product_id)

    return jsonify({
        'id': product.id,
        'name': product.name,
        'color': product.color,
        'material': product.material,
        'type': product.type,
        'quantity': product.quantity
    })


@operations_bp.route('/delete_invoice/<int:invoice_id>', methods=['POST'])
@login_required
@admin_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Log the deletion
    log = SystemLog(
        action='invoice_delete',
        details=f'حذف الفاتورة: {invoice.invoice_number}',
        user_id=current_user.id
    )
    
    db.session.add(log)
    db.session.delete(invoice)
    db.session.commit()
    
    flash('تم حذف الفاتورة بنجاح', 'success')
    return redirect(url_for('operations.index'))

@operations_bp.route('/export_invoice_pdf/<int:invoice_id>')
@login_required
def export_invoice_pdf(invoice_id):
    """Export invoice as PDF"""
    invoice = Invoice.query.get_or_404(invoice_id)

    # Get related client or supplier
    client = None
    supplier = None

    if invoice.client_id:
        client = Client.query.get(invoice.client_id)

    if invoice.supplier_id:
        supplier = Supplier.query.get(invoice.supplier_id)

    # Get invoice items with product details
    items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    items_with_product = []

    for item in items:
        product = Product.query.get(item.product_id)
        items_with_product.append({
            'product_name': product.name,
            'product_color': product.color,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })

    # Get payments
    payments = Payment.query.filter_by(invoice_id=invoice_id).order_by(Payment.payment_date).all()

    # Calculate total paid and remaining
    total_paid = sum(payment.amount for payment in payments)
    remaining = invoice.total_amount - total_paid

    # Create invoice type label in Arabic
    invoice_type_labels = {
        'sale': 'فاتورة بيع',
        'purchase': 'فاتورة شراء',
        'return': 'مرتجع من عميل',
        'supplier_return': 'مرتجع إلى مورد'
    }
    invoice_type_label = invoice_type_labels.get(invoice.type, 'فاتورة')

    # Create HTML template for the invoice
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{invoice_type_label} #{invoice.invoice_number}</title>
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            @font-face {{
                font-family: 'NotoSansArabic';
                src: url('https://fonts.gstatic.com/s/notosansarabic/v18/nwpxtLGrOAZMl5nJ_wfgRg3DrWFZWsnVBJ_sS6tlqHHFlhQ5l3sQWIHPqzCfyG2vu3CBFQLaig.ttf');
                font-weight: normal;
                font-style: normal;
            }}
            body {{
                font-family: 'NotoSansArabic', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            .invoice-header {{
                text-align: center;
                padding: 20px 0;
                border-bottom: 2px solid #ddd;
            }}
            .invoice-title {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .invoice-number {{
                font-size: 16px;
                color: #666;
            }}
            .invoice-info {{
                display: flex;
                justify-content: space-between;
                margin: 20px 0;
            }}
            .invoice-info-box {{
                width: 45%;
            }}
            .invoice-info-label {{
                font-weight: bold;
            }}
            .invoice-items {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            .invoice-items th, .invoice-items td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: right;
            }}
            .invoice-items th {{
                background-color: #f5f5f5;
            }}
            .invoice-totals {{
                width: 40%;
                margin-left: auto;
                border-collapse: collapse;
            }}
            .invoice-totals td {{
                padding: 8px;
                border: 1px solid #ddd;
            }}
            .invoice-totals .total-row {{
                font-weight: bold;
                background-color: #f5f5f5;
            }}
            .invoice-footer {{
                margin-top: 40px;
                border-top: 1px solid #ddd;
                padding-top: 20px;
                text-align: center;
                font-size: 14px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="invoice-header">
            <div class="invoice-title">{invoice_type_label}</div>
            <div class="invoice-number">رقم الفاتورة: {invoice.invoice_number}</div>
        </div>

        <div class="invoice-info">
            <div class="invoice-info-box">
                <div><span class="invoice-info-label">التاريخ:</span> {invoice.date.strftime('%Y-%m-%d')}</div>
                <div><span class="invoice-info-label">تاريخ الاستحقاق:</span> {invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else 'غير محدد'}</div>
                <div><span class="invoice-info-label">الحالة:</span> {
                    'مدفوعة بالكامل' if invoice.status == 'paid' else 
                    'مدفوعة جزئياً' if invoice.status == 'partial' else 
                    'قيد الانتظار'
                }</div>
            </div>
            <div class="invoice-info-box">
                <div><span class="invoice-info-label">{'العميل' if invoice.client_id else 'المورد'}:</span> {
                    client.name if client else 
                    supplier.name if supplier else 
                    'غير محدد'
                }</div>
                <div><span class="invoice-info-label">رقم الهاتف:</span> {
                    client.phone if client else 
                    supplier.phone if supplier else 
                    'غير محدد'
                }</div>
                <div><span class="invoice-info-label">البريد الإلكتروني:</span> {
                    client.email if client and client.email else 
                    supplier.email if supplier and supplier.email else 
                    'غير محدد'
                }</div>
            </div>
        </div>

        <table class="invoice-items">
            <thead>
                <tr>
                    <th>#</th>
                    <th>المنتج</th>
                    <th>اللون</th>
                    <th>الكمية</th>
                    <th>سعر الوحدة</th>
                    <th>الإجمالي</th>
                </tr>
            </thead>
            <tbody>
                {''.join([
                    f"<tr><td>{i+1}</td><td>{item['product_name']}</td><td>{item['product_color']}</td><td>{item['quantity']}</td><td>{item['unit_price']:.2f} ج.م</td><td>{item['total_price']:.2f} ج.م</td></tr>"
                    for i, item in enumerate(items_with_product)
                ])}
            </tbody>
        </table>

        <table class="invoice-totals">
            <tr>
                <td>إجمالي الفاتورة</td>
                <td>{invoice.total_amount:.2f} ج.م</td>
            </tr>
            <tr>
                <td>إجمالي المدفوع</td>
                <td>{total_paid:.2f} ج.م</td>
            </tr>
            <tr class="total-row">
                <td>المتبقي</td>
                <td>{remaining:.2f} ج.م</td>
            </tr>
        </table>

        <div class="invoice-footer">
            <div>ملاحظات: {invoice.notes if invoice.notes else 'لا توجد'}</div>
            <div>تم إنشاء هذه الفاتورة بواسطة نظام إدارة مخزون وعمليات الملابس بالجملة</div>
        </div>
    </body>
    </html>
    """

    # Configure font
    from weasyprint import HTML, CSS
    from weasyprint.fonts import FontConfiguration
    import io

    font_config = FontConfiguration()

    # Generate PDF
    html = HTML(string=html_content)
    buffer = io.BytesIO()
    html.write_pdf(buffer, font_config=font_config)
    buffer.seek(0)

    # Create response
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={invoice_type_label}_{invoice.invoice_number}.pdf'

    return response