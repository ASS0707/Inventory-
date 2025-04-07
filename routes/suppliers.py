from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import desc
from routes import admin_required

from app import db
from models import Supplier, Invoice, Payment, SystemLog
from forms.suppliers import SupplierForm

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')


@suppliers_bp.route('/')
@login_required
def index():
    # Get all suppliers with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter parameters
    name_filter = request.args.get('name', '')
    
    # Base query
    query = Supplier.query
    
    # Apply filters if provided
    if name_filter:
        query = query.filter(Supplier.name.ilike(f'%{name_filter}%'))
    
    # Execute query with pagination
    suppliers = query.order_by(Supplier.name).paginate(page=page, per_page=per_page)
    
    return render_template('suppliers/index.html', suppliers=suppliers)


@suppliers_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    form = SupplierForm()
    
    if form.validate_on_submit():
        supplier = Supplier(
            name=form.name.data,
            phone=form.phone.data,
            email=form.email.data,
            address=form.address.data
        )
        
        # Log the creation
        log = SystemLog(
            action='supplier_create',
            details=f'إضافة مورد جديد: {supplier.name}',
            user_id=current_user.id
        )
        
        db.session.add(supplier)
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم إضافة المورد {supplier.name} بنجاح', 'success')
        return redirect(url_for('suppliers.index'))
    
    return render_template('suppliers/add.html', form=form)


@suppliers_bp.route('/<int:supplier_id>')
@login_required
def view(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get all invoices for this supplier
    invoices = Invoice.query.filter_by(supplier_id=supplier_id).order_by(desc(Invoice.date)).all()
    
    # Get all payments for this supplier
    payments = Payment.query.filter_by(supplier_id=supplier_id).order_by(desc(Payment.payment_date)).all()
    
    # Calculate total purchased, total paid, and balance
    total_purchased = sum(invoice.total_amount for invoice in invoices if invoice.type == 'purchase')
    total_returns = sum(invoice.total_amount for invoice in invoices if invoice.type == 'supplier_return')
    total_paid = sum(payment.amount for payment in payments)
    balance = total_purchased - total_returns - total_paid
    
    return render_template(
        'suppliers/view.html',
        supplier=supplier,
        invoices=invoices,
        payments=payments,
        total_purchased=total_purchased,
        total_returns=total_returns,
        total_paid=total_paid,
        balance=balance
    )


@suppliers_bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    form = SupplierForm(obj=supplier)
    
    if form.validate_on_submit():
        # Update supplier details
        supplier.name = form.name.data
        supplier.phone = form.phone.data
        supplier.email = form.email.data
        supplier.address = form.address.data
        
        # Log the update
        log = SystemLog(
            action='supplier_edit',
            details=f'تعديل المورد: {supplier.name}',
            user_id=current_user.id
        )
        
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم تحديث بيانات المورد {supplier.name} بنجاح', 'success')
        return redirect(url_for('suppliers.view', supplier_id=supplier.id))
    
    return render_template('suppliers/edit.html', form=form, supplier=supplier)


@suppliers_bp.route('/add_payment/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def add_payment(supplier_id):
    from forms.operations import PaymentForm
    
    supplier = Supplier.query.get_or_404(supplier_id)
    form = PaymentForm()
    
    # For supplier payments, we can safely skip checking for invoice selection
    # and use the default choices that are already set in the form definition
    
    if form.validate_on_submit():
        payment = Payment(
            supplier_id=supplier_id,
            amount=form.amount.data,
            payment_date=form.payment_date.data,
            payment_method=form.payment_method.data,
            reference_number=form.reference_number.data,
            notes=form.notes.data,
            created_by=current_user.id
        )
        
        # If payment is for a specific invoice
        if form.invoice_id.data != 0:
            payment.invoice_id = form.invoice_id.data
            invoice = Invoice.query.get(form.invoice_id.data)
            invoice.update_status()
        
        # Log the payment
        log = SystemLog(
            action='payment_add',
            details=f'إضافة دفعة للمورد {supplier.name}: {payment.amount} ج.م',
            user_id=current_user.id
        )
        
        db.session.add(payment)
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم إضافة الدفعة بمبلغ {payment.amount} ج.م بنجاح', 'success')
        return redirect(url_for('suppliers.view', supplier_id=supplier_id))
    
    return render_template('suppliers/add_payment.html', form=form, supplier=supplier)
