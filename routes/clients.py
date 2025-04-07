from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import desc
from routes import admin_required

from app import db
from models import Client, Invoice, Payment, SystemLog
from forms.clients import ClientForm

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')


@clients_bp.route('/')
@login_required
def index():
    # Get all clients with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter parameters
    name_filter = request.args.get('name', '')
    
    # Base query
    query = Client.query
    
    # Apply filters if provided
    if name_filter:
        query = query.filter(Client.name.ilike(f'%{name_filter}%'))
    
    # Execute query with pagination
    clients = query.order_by(Client.name).paginate(page=page, per_page=per_page)
    
    return render_template('clients/index.html', clients=clients)


@clients_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    form = ClientForm()
    
    if form.validate_on_submit():
        client = Client(
            name=form.name.data,
            phone=form.phone.data,
            email=form.email.data,
            address=form.address.data
        )
        
        # Log the creation
        log = SystemLog(
            action='client_create',
            details=f'إضافة عميل جديد: {client.name}',
            user_id=current_user.id
        )
        
        db.session.add(client)
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم إضافة العميل {client.name} بنجاح', 'success')
        return redirect(url_for('clients.index'))
    
    return render_template('clients/add.html', form=form)


@clients_bp.route('/<int:client_id>')
@login_required
def view(client_id):
    client = Client.query.get_or_404(client_id)
    
    # Get all invoices for this client
    invoices = Invoice.query.filter_by(client_id=client_id).order_by(desc(Invoice.date)).all()
    
    # Get all payments for this client
    payments = Payment.query.filter_by(client_id=client_id).order_by(desc(Payment.payment_date)).all()
    
    # Calculate total purchased, total paid, and balance
    total_purchased = sum(invoice.total_amount for invoice in invoices if invoice.type == 'sale')
    total_returns = sum(invoice.total_amount for invoice in invoices if invoice.type == 'return')
    total_paid = sum(payment.amount for payment in payments)
    balance = total_purchased - total_returns - total_paid
    
    return render_template(
        'clients/view.html',
        client=client,
        invoices=invoices,
        payments=payments,
        total_purchased=total_purchased,
        total_returns=total_returns,
        total_paid=total_paid,
        balance=balance
    )


@clients_bp.route('/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit(client_id):
    client = Client.query.get_or_404(client_id)
    form = ClientForm(obj=client)
    
    if form.validate_on_submit():
        # Update client details
        client.name = form.name.data
        client.phone = form.phone.data
        client.email = form.email.data
        client.address = form.address.data
        
        # Log the update
        log = SystemLog(
            action='client_edit',
            details=f'تعديل العميل: {client.name}',
            user_id=current_user.id
        )
        
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم تحديث بيانات العميل {client.name} بنجاح', 'success')
        return redirect(url_for('clients.view', client_id=client.id))
    
    return render_template('clients/edit.html', form=form, client=client)


@clients_bp.route('/delete/<int:client_id>', methods=['POST'])
@login_required
@admin_required
def delete(client_id):
    client = Client.query.get_or_404(client_id)
    
    # Log the deletion
    log = SystemLog(
        action='client_delete',
        details=f'حذف العميل: {client.name}',
        user_id=current_user.id
    )
    
    db.session.add(log)
    db.session.delete(client)
    db.session.commit()
    
    flash('تم حذف العميل بنجاح', 'success')
    return redirect(url_for('clients.index'))

@clients_bp.route('/add_payment/<int:client_id>', methods=['GET', 'POST'])
@login_required
def add_payment(client_id):
    from forms.operations import PaymentForm
    
    client = Client.query.get_or_404(client_id)
    form = PaymentForm()
    
    # For client payments, we can safely skip checking for invoice selection
    # and use the default choices that are already set in the form definition
    
    if form.validate_on_submit():
        payment = Payment(
            client_id=client_id,
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
            details=f'إضافة دفعة من العميل {client.name}: {payment.amount} ج.م',
            user_id=current_user.id
        )
        
        db.session.add(payment)
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم إضافة الدفعة بمبلغ {payment.amount} ج.م بنجاح', 'success')
        return redirect(url_for('clients.view', client_id=client_id))
    
    return render_template('clients/add_payment.html', form=form, client=client)
