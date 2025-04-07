from flask import Blueprint, render_template, url_for
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, timedelta

from app import db
from models import Product, Client, Supplier, Invoice, Payment, FinancialEntry

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    # Calculate financial summary
    total_cash = calculate_total_cash()
    clients_outstanding = calculate_clients_outstanding()
    suppliers_outstanding = calculate_suppliers_outstanding()
    net_profit = calculate_net_profit()
    profit_margin = calculate_profit_margin()
    
    # Get recent operations
    recent_operations = get_recent_operations()
    
    # Get inventory summary
    inventory_summary = get_inventory_summary()
    
    # Get alerts
    alerts = get_system_alerts()
    
    return render_template(
        'dashboard/index.html',
        total_cash=total_cash,
        clients_outstanding=clients_outstanding,
        suppliers_outstanding=suppliers_outstanding,
        net_profit=net_profit,
        profit_margin=profit_margin,
        recent_operations=recent_operations,
        inventory_summary=inventory_summary,
        alerts=alerts
    )


def calculate_total_cash():
    """Calculate total cash available"""
    # Sum of all sale invoices (paid amount)
    sales_income = db.session.query(func.sum(Payment.amount)) \
        .join(Invoice, Payment.invoice_id == Invoice.id) \
        .filter(Invoice.type == 'sale') \
        .scalar() or 0
    
    # Sum of all purchase invoices (paid amount)
    purchases_expense = db.session.query(func.sum(Payment.amount)) \
        .join(Invoice, Payment.invoice_id == Invoice.id) \
        .filter(Invoice.type == 'purchase') \
        .scalar() or 0
    
    # Sum of all manual income entries
    other_income = db.session.query(func.sum(FinancialEntry.amount)) \
        .filter(FinancialEntry.entry_type == 'income') \
        .scalar() or 0
    
    # Sum of all manual expense entries
    other_expenses = db.session.query(func.sum(FinancialEntry.amount)) \
        .filter(FinancialEntry.entry_type == 'expense') \
        .scalar() or 0
    
    # Calculate total cash
    return sales_income - purchases_expense + other_income - other_expenses


def calculate_clients_outstanding():
    """Calculate total outstanding money from clients"""
    # Sum of all sale invoices
    total_sales = db.session.query(func.sum(Invoice.total_amount)) \
        .filter(Invoice.type == 'sale') \
        .scalar() or 0
    
    # Sum of all returns from clients
    total_returns = db.session.query(func.sum(Invoice.total_amount)) \
        .filter(Invoice.type == 'return') \
        .scalar() or 0
    
    # Sum of all payments from clients
    total_payments = db.session.query(func.sum(Payment.amount)) \
        .join(Invoice, Payment.invoice_id == Invoice.id) \
        .filter(Invoice.type == 'sale') \
        .scalar() or 0
    
    # Calculate outstanding
    return total_sales - total_returns - total_payments


def calculate_suppliers_outstanding():
    """Calculate total money owed to suppliers"""
    # Sum of all purchase invoices
    total_purchases = db.session.query(func.sum(Invoice.total_amount)) \
        .filter(Invoice.type == 'purchase') \
        .scalar() or 0
    
    # Sum of all returns to suppliers
    total_returns = db.session.query(func.sum(Invoice.total_amount)) \
        .filter(Invoice.type == 'supplier_return') \
        .scalar() or 0
    
    # Sum of all payments to suppliers
    total_payments = db.session.query(func.sum(Payment.amount)) \
        .join(Invoice, Payment.invoice_id == Invoice.id) \
        .filter(Invoice.type == 'purchase') \
        .scalar() or 0
    
    # Calculate outstanding
    return total_purchases - total_returns - total_payments


def calculate_net_profit():
    """Calculate net profit after all dues"""
    return calculate_total_cash() + calculate_clients_outstanding() - calculate_suppliers_outstanding()


def calculate_profit_margin():
    """Calculate profit margin percentage"""
    # Sum of all sale invoices
    total_sales = db.session.query(func.sum(Invoice.total_amount)) \
        .filter(Invoice.type == 'sale') \
        .scalar() or 0
    
    # Sum of all costs
    total_costs = db.session.query(func.sum(Invoice.total_amount)) \
        .filter(Invoice.type == 'purchase') \
        .scalar() or 0
    
    # Prevent division by zero
    if total_sales == 0:
        return 0
    
    return ((total_sales - total_costs) / total_sales) * 100


def get_recent_operations():
    """Get the 5 most recent operations"""
    # Get latest invoices (sales and purchases)
    invoices = Invoice.query.order_by(Invoice.date.desc()).limit(5).all()
    
    # Get latest payments
    payments = Payment.query.order_by(Payment.payment_date.desc()).limit(5).all()
    
    # Combine and sort
    operations = invoices + payments
    operations.sort(key=lambda x: x.date if hasattr(x, 'date') else x.payment_date, reverse=True)
    
    # Limit to 5
    return operations[:5]


def get_inventory_summary():
    """Get inventory summary"""
    return Product.query.all()


def get_system_alerts():
    """Generate system alerts"""
    alerts = []
    
    # Low stock alerts (products with quantity < 10)
    low_stock_products = Product.query.filter(Product.quantity < 10).all()
    for product in low_stock_products:
        alerts.append({
            'type': 'warning',
            'message': f'مخزون منخفض: {product.name} ({product.color}) - {product.quantity} فقط متبقية',
            'link': url_for('inventory.view', product_id=product.id)
        })
    
    # Due payments from clients (invoices due within 7 days)
    today = datetime.utcnow().date()
    upcoming_due_dates = Invoice.query.filter(
        Invoice.type == 'sale',
        Invoice.status != 'paid',
        Invoice.due_date <= today + timedelta(days=7),
        Invoice.due_date >= today
    ).all()
    
    for invoice in upcoming_due_dates:
        client = Client.query.get(invoice.client_id)
        alerts.append({
            'type': 'info',
            'message': f'دفعة مستحقة من {client.name} - {invoice.total_amount} ج.م - تاريخ الاستحقاق: {invoice.due_date.strftime("%Y-%m-%d")}',
            'link': url_for('operations.view_invoice', invoice_id=invoice.id)
        })
    
    # Overdue payments from clients
    overdue_invoices = Invoice.query.filter(
        Invoice.type == 'sale',
        Invoice.status != 'paid',
        Invoice.due_date < today
    ).all()
    
    for invoice in overdue_invoices:
        client = Client.query.get(invoice.client_id)
        alerts.append({
            'type': 'danger',
            'message': f'دفعة متأخرة من {client.name} - {invoice.total_amount} ج.م - تاريخ الاستحقاق: {invoice.due_date.strftime("%Y-%m-%d")}',
            'link': url_for('operations.view_invoice', invoice_id=invoice.id)
        })
    
    return alerts
