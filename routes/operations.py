from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
import datetime
import random
import string

from app import db
from models import Invoice, InvoiceItem, Product, Client, Supplier, Payment, SystemLog
from forms.operations import InvoiceForm, InvoiceItemForm, PaymentForm

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
def add_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = PaymentForm()
    
    # Clear the existing choices and just use the linked invoice
    form.invoice_id.data = invoice_id
    
    # Set default values
    form.amount.data = invoice.calculate_remaining_amount()
    form.payment_date.data = datetime.datetime.now()
    
    if form.validate_on_submit():
        payment = Payment(
            invoice_id=invoice_id,
            amount=form.amount.data,
            payment_date=form.payment_date.data,
            payment_method=form.payment_method.data,
            reference_number=form.reference_number.data,
            notes=form.notes.data,
            created_by=current_user.id
        )
        
        # Set client or supplier based on invoice type
        if invoice.type in ['sale', 'return']:
            payment.client_id = invoice.client_id
        elif invoice.type in ['purchase', 'supplier_return']:
            payment.supplier_id = invoice.supplier_id
        
        # Log the payment
        entity_name = Client.query.get(invoice.client_id).name if invoice.client_id else Supplier.query.get(invoice.supplier_id).name
        log = SystemLog(
            action='payment_add',
            details=f'إضافة دفعة للفاتورة {invoice.invoice_number} ({entity_name}): {payment.amount} ج.م',
            user_id=current_user.id
        )
        
        db.session.add(payment)
        db.session.add(log)
        
        # Update invoice status
        invoice.update_status()
        db.session.commit()
        
        flash(f'تم إضافة الدفعة بمبلغ {payment.amount} ج.م بنجاح', 'success')
        return redirect(url_for('operations.view_invoice', invoice_id=invoice_id))
    
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
