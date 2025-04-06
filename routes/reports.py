from flask import Blueprint, render_template, request, send_file, jsonify
from flask_login import login_required
from sqlalchemy import func, desc
import datetime
import io
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from app import db
from models import Invoice, InvoiceItem, Client, Supplier, Product, Payment

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')


@reports_bp.route('/profit_report')
@login_required
def profit_report():
    # Date range filters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base queries
    sales_query = db.session.query(
        func.date_format(Invoice.date, '%Y-%m').label('month'),
        func.sum(Invoice.total_amount).label('amount')
    ).filter(Invoice.type == 'sale')
    
    purchases_query = db.session.query(
        func.date_format(Invoice.date, '%Y-%m').label('month'),
        func.sum(Invoice.total_amount).label('amount')
    ).filter(Invoice.type == 'purchase')
    
    returns_query = db.session.query(
        func.date_format(Invoice.date, '%Y-%m').label('month'),
        func.sum(Invoice.total_amount).label('amount')
    ).filter(Invoice.type == 'return')
    
    supplier_returns_query = db.session.query(
        func.date_format(Invoice.date, '%Y-%m').label('month'),
        func.sum(Invoice.total_amount).label('amount')
    ).filter(Invoice.type == 'supplier_return')
    
    # Apply date filters if provided
    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
            sales_query = sales_query.filter(Invoice.date >= from_date)
            purchases_query = purchases_query.filter(Invoice.date >= from_date)
            returns_query = returns_query.filter(Invoice.date >= from_date)
            supplier_returns_query = supplier_returns_query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            sales_query = sales_query.filter(Invoice.date <= to_date)
            purchases_query = purchases_query.filter(Invoice.date <= to_date)
            returns_query = returns_query.filter(Invoice.date <= to_date)
            supplier_returns_query = supplier_returns_query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Group by month and execute queries
    sales_data = sales_query.group_by('month').order_by('month').all()
    purchases_data = purchases_query.group_by('month').order_by('month').all()
    returns_data = returns_query.group_by('month').order_by('month').all()
    supplier_returns_data = supplier_returns_query.group_by('month').order_by('month').all()
    
    # Convert to dictionaries for easier processing
    sales_by_month = {item.month: item.amount for item in sales_data}
    purchases_by_month = {item.month: item.amount for item in purchases_data}
    returns_by_month = {item.month: item.amount for item in returns_data}
    supplier_returns_by_month = {item.month: item.amount for item in supplier_returns_data}
    
    # Combine all months
    all_months = sorted(set().union(
        sales_by_month.keys(),
        purchases_by_month.keys(),
        returns_by_month.keys(),
        supplier_returns_by_month.keys()
    ))
    
    # Calculate profits
    profit_data = []
    
    for month in all_months:
        sales = sales_by_month.get(month, 0)
        purchases = purchases_by_month.get(month, 0)
        returns = returns_by_month.get(month, 0)
        supplier_returns = supplier_returns_by_month.get(month, 0)
        
        # Profit = (Sales - Returns) - (Purchases - Supplier Returns)
        net_sales = sales - returns
        net_purchases = purchases - supplier_returns
        profit = net_sales - net_purchases
        
        # Calculate profit margin
        profit_margin = 0 if net_sales == 0 else (profit / net_sales) * 100
        
        # Format month for display (YYYY-MM to MM/YYYY)
        year, month_num = month.split('-')
        display_month = f"{month_num}/{year}"
        
        profit_data.append({
            'month': display_month,
            'sales': sales,
            'purchases': purchases,
            'returns': returns,
            'supplier_returns': supplier_returns,
            'net_sales': net_sales,
            'net_purchases': net_purchases,
            'profit': profit,
            'profit_margin': profit_margin
        })
    
    # Chart data
    chart_months = [item['month'] for item in profit_data]
    chart_profits = [item['profit'] for item in profit_data]
    chart_sales = [item['net_sales'] for item in profit_data]
    chart_purchases = [item['net_purchases'] for item in profit_data]
    
    return render_template(
        'reports/profit_report.html',
        profit_data=profit_data,
        chart_months=chart_months,
        chart_profits=chart_profits,
        chart_sales=chart_sales,
        chart_purchases=chart_purchases,
        date_from=date_from,
        date_to=date_to
    )


@reports_bp.route('/top_products')
@login_required
def top_products():
    # Date range filters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base query for top-selling products
    query = db.session.query(
        Product.id,
        Product.name,
        Product.color,
        func.sum(InvoiceItem.quantity).label('quantity'),
        func.sum(InvoiceItem.total_price).label('total_amount')
    ).join(InvoiceItem, Product.id == InvoiceItem.product_id) \
     .join(Invoice, InvoiceItem.invoice_id == Invoice.id) \
     .filter(Invoice.type == 'sale')
    
    # Apply date filters if provided
    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Group and order the results
    products = query.group_by(Product.id).order_by(desc('total_amount')).limit(10).all()
    
    # Chart data
    chart_labels = [f"{p.name} ({p.color})" for p in products]
    chart_values = [float(p.total_amount) for p in products]
    chart_quantities = [int(p.quantity) for p in products]
    
    return render_template(
        'reports/top_products.html',
        products=products,
        chart_labels=chart_labels,
        chart_values=chart_values,
        chart_quantities=chart_quantities,
        date_from=date_from,
        date_to=date_to
    )


@reports_bp.route('/top_clients')
@login_required
def top_clients():
    # Date range filters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base query for top clients
    query = db.session.query(
        Client.id,
        Client.name,
        func.sum(Invoice.total_amount).label('total_amount')
    ).join(Invoice, Client.id == Invoice.client_id) \
     .filter(Invoice.type == 'sale')
    
    # Apply date filters if provided
    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Group and order the results
    clients = query.group_by(Client.id).order_by(desc('total_amount')).limit(10).all()
    
    # Chart data
    chart_labels = [c.name for c in clients]
    chart_values = [float(c.total_amount) for c in clients]
    
    return render_template(
        'reports/top_clients.html',
        clients=clients,
        chart_labels=chart_labels,
        chart_values=chart_values,
        date_from=date_from,
        date_to=date_to
    )


@reports_bp.route('/top_suppliers')
@login_required
def top_suppliers():
    # Date range filters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base query for top suppliers
    query = db.session.query(
        Supplier.id,
        Supplier.name,
        func.sum(Invoice.total_amount).label('total_amount')
    ).join(Invoice, Supplier.id == Invoice.supplier_id) \
     .filter(Invoice.type == 'purchase')
    
    # Apply date filters if provided
    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Group and order the results
    suppliers = query.group_by(Supplier.id).order_by(desc('total_amount')).limit(10).all()
    
    # Chart data
    chart_labels = [s.name for s in suppliers]
    chart_values = [float(s.total_amount) for s in suppliers]
    
    return render_template(
        'reports/top_suppliers.html',
        suppliers=suppliers,
        chart_labels=chart_labels,
        chart_values=chart_values,
        date_from=date_from,
        date_to=date_to
    )


@reports_bp.route('/aging_report')
@login_required
def aging_report():
    today = datetime.datetime.now().date()
    
    # Get all unpaid or partially paid invoices
    invoices = Invoice.query.filter(
        Invoice.type == 'sale',
        Invoice.status != 'paid'
    ).all()
    
    # Categorize invoices by age
    current = []  # 0-7 days
    aging_30 = []  # 8-30 days
    aging_60 = []  # 31-60 days
    aging_90 = []  # 61-90 days
    aging_90_plus = []  # 90+ days
    
    for invoice in invoices:
        # Calculate the age in days
        if invoice.due_date:
            due_date = invoice.due_date.date()
            age = (today - due_date).days
        else:
            # If no due date, use invoice date
            age = (today - invoice.date.date()).days
        
        # Calculate remaining amount
        remaining = invoice.calculate_remaining_amount()
        
        # Only process invoices with remaining balance
        if remaining <= 0:
            continue
        
        # Add client information
        client = Client.query.get(invoice.client_id)
        
        invoice_data = {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'client_name': client.name if client else 'Unknown',
            'date': invoice.date,
            'due_date': invoice.due_date,
            'total_amount': invoice.total_amount,
            'remaining': remaining,
            'age': age
        }
        
        # Categorize by age
        if age <= 7:
            current.append(invoice_data)
        elif age <= 30:
            aging_30.append(invoice_data)
        elif age <= 60:
            aging_60.append(invoice_data)
        elif age <= 90:
            aging_90.append(invoice_data)
        else:
            aging_90_plus.append(invoice_data)
    
    # Calculate totals
    current_total = sum(inv['remaining'] for inv in current)
    aging_30_total = sum(inv['remaining'] for inv in aging_30)
    aging_60_total = sum(inv['remaining'] for inv in aging_60)
    aging_90_total = sum(inv['remaining'] for inv in aging_90)
    aging_90_plus_total = sum(inv['remaining'] for inv in aging_90_plus)
    grand_total = current_total + aging_30_total + aging_60_total + aging_90_total + aging_90_plus_total
    
    # Chart data
    chart_labels = ['1-7 أيام', '8-30 يوم', '31-60 يوم', '61-90 يوم', 'أكثر من 90 يوم']
    chart_values = [current_total, aging_30_total, aging_60_total, aging_90_total, aging_90_plus_total]
    
    return render_template(
        'reports/aging_report.html',
        current=current,
        aging_30=aging_30,
        aging_60=aging_60,
        aging_90=aging_90,
        aging_90_plus=aging_90_plus,
        current_total=current_total,
        aging_30_total=aging_30_total,
        aging_60_total=aging_60_total,
        aging_90_total=aging_90_total,
        aging_90_plus_total=aging_90_plus_total,
        grand_total=grand_total,
        chart_labels=chart_labels,
        chart_values=chart_values
    )


@reports_bp.route('/export_excel/<report_type>')
@login_required
def export_excel(report_type):
    if report_type == 'profit':
        return export_profit_report()
    elif report_type == 'top_products':
        return export_top_products()
    elif report_type == 'top_clients':
        return export_top_clients()
    elif report_type == 'aging':
        return export_aging_report()
    elif report_type == 'inventory':
        return export_inventory()
    
    return "Report type not recognized", 400


def export_profit_report():
    """Export profit report to Excel"""
    # Date range filters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base queries (same as in profit_report view)
    sales_query = db.session.query(
        func.date_format(Invoice.date, '%Y-%m').label('month'),
        func.sum(Invoice.total_amount).label('amount')
    ).filter(Invoice.type == 'sale')
    
    # Apply date filters
    if date_from:
        try:
            from_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
            sales_query = sales_query.filter(Invoice.date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.datetime.strptime(date_to, '%Y-%m-%d')
            sales_query = sales_query.filter(Invoice.date <= to_date)
        except ValueError:
            pass
    
    # Group by month and execute
    sales_data = sales_query.group_by('month').order_by('month').all()
    
    # ... (similar queries for purchases, returns, etc.)
    
    # Create DataFrame
    df = pd.DataFrame([
        {
            'الشهر': item.month,
            'المبيعات': item.amount,
            # ... (other columns)
        }
        for item in sales_data
    ])
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='تقرير الأرباح', index=False)
    
    output.seek(0)
    
    # Send file
    return send_file(
        output,
        download_name='profit_report.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


def export_inventory():
    """Export current inventory to Excel"""
    products = Product.query.all()
    
    # Create DataFrame
    df = pd.DataFrame([
        {
            'اسم المنتج': p.name,
            'اللون': p.color,
            'المادة': p.material,
            'النوع': p.type,
            'الكمية': p.quantity,
            'تكلفة التشطيب': p.finishing_cost,
            'تكلفة الطباعة': p.printing_cost if p.type == 'Printed' else 0
        }
        for p in products
    ])
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='المخزون', index=False)
    
    output.seek(0)
    
    # Send file
    return send_file(
        output,
        download_name='inventory_report.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
