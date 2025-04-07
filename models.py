from datetime import datetime
from app import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='employee')  # admin or employee
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    reset_token = db.Column(db.String(32), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    login_logs = db.relationship('LoginLog', backref='user', lazy=True, cascade='all, delete-orphan')


class LoginLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    success = db.Column(db.Boolean, default=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    material = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    type = db.Column(db.String(20), nullable=False)  # 'Plain' or 'Printed'
    finishing_cost = db.Column(db.Float, default=0.0)
    printing_cost = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    invoice_items = db.relationship('InvoiceItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name} ({self.color})>'


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    invoices = db.relationship('Invoice', backref='client', lazy=True, 
                               foreign_keys='Invoice.client_id')
    payments = db.relationship('Payment', backref='client', lazy=True,
                              foreign_keys='Payment.client_id')

    def __repr__(self):
        return f'<Client {self.name}>'
    
    def calculate_balance(self):
        """Calculate total outstanding balance for this client"""
        from sqlalchemy import func
        
        # Sum of all invoice totals
        invoice_total = db.session.query(func.sum(Invoice.total_amount)) \
            .filter(Invoice.client_id == self.id, Invoice.type == 'sale') \
            .scalar() or 0
            
        # Sum of all returns
        returns_total = db.session.query(func.sum(Invoice.total_amount)) \
            .filter(Invoice.client_id == self.id, Invoice.type == 'return') \
            .scalar() or 0
            
        # Sum of all payments
        payments_total = db.session.query(func.sum(Payment.amount)) \
            .filter(Payment.client_id == self.id) \
            .scalar() or 0
            
        # Outstanding balance = invoices - returns - payments
        return invoice_total - returns_total - payments_total


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    invoices = db.relationship('Invoice', backref='supplier', lazy=True,
                              foreign_keys='Invoice.supplier_id')
    payments = db.relationship('Payment', backref='supplier', lazy=True,
                              foreign_keys='Payment.supplier_id')

    def __repr__(self):
        return f'<Supplier {self.name}>'
    
    def calculate_balance(self):
        """Calculate total outstanding balance for this supplier"""
        from sqlalchemy import func
        
        # Sum of all purchase invoice totals
        purchase_total = db.session.query(func.sum(Invoice.total_amount)) \
            .filter(Invoice.supplier_id == self.id, Invoice.type == 'purchase') \
            .scalar() or 0
            
        # Sum of all returns to supplier
        returns_total = db.session.query(func.sum(Invoice.total_amount)) \
            .filter(Invoice.supplier_id == self.id, Invoice.type == 'supplier_return') \
            .scalar() or 0
            
        # Sum of all payments to supplier
        payments_total = db.session.query(func.sum(Payment.amount)) \
            .filter(Payment.supplier_id == self.id) \
            .scalar() or 0
            
        # Outstanding balance = purchases - returns - payments
        return purchase_total - returns_total - payments_total


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'sale', 'purchase', 'return', 'supplier_return'
    date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'paid', 'partial'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'

    def calculate_paid_amount(self):
        """Calculate the total paid amount for this invoice"""
        from sqlalchemy import func
        paid = db.session.query(func.sum(Payment.amount)) \
            .filter(Payment.invoice_id == self.id) \
            .scalar()
        return round(float(paid if paid is not None else 0), 2)

    def calculate_remaining_amount(self):
        """Calculate the remaining amount to be paid"""
        total = round(float(self.total_amount), 2)
        paid = self.calculate_paid_amount()
        remaining = total - paid
        return max(0, round(remaining, 2))  # Ensure we never return negative

    def update_status(self):
        """Update the status based on payments"""
        paid = self.calculate_paid_amount()
        if paid >= self.total_amount:
            self.status = 'paid'
        elif paid > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'


class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<InvoiceItem {self.product_id} x{self.quantity}>'


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))  # 'cash', 'bank_transfer', etc.
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<Payment {self.amount} EGP on {self.payment_date}>'


class FinancialEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_type = db.Column(db.String(50), nullable=False)  # 'expense', 'income', 'loan', etc.
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<FinancialEntry {self.entry_type} {self.amount} EGP>'


class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemLog {self.action}>'
