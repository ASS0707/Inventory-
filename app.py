import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager


# Configure logging
logging.basicConfig(level=logging.DEBUG)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "devkey-changeme-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the extension
db.init_app(app)

# Setup Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'الرجاء تسجيل الدخول للوصول إلى هذه الصفحة'
login_manager.login_message_category = 'warning'

# Import and register blueprints
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.inventory import inventory_bp
from routes.clients import clients_bp
from routes.suppliers import suppliers_bp
from routes.operations import operations_bp
from routes.reports import reports_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(suppliers_bp)
app.register_blueprint(operations_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(admin_bp)

# Initialize database
with app.app_context():
    # Import models
    import models
    
    # Create database tables
    db.create_all()
    
    # Create admin user if it doesn't exist
    from models import User
    from werkzeug.security import generate_password_hash
    
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        app.logger.info('Created admin user')


@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))


# Format EGP currency
@app.template_filter('egp')
def format_egp(value):
    """Format a value as EGP currency"""
    if value is None:
        return "0.00 ج.م"
    return f"{float(value):,.2f} ج.م"


# Date formatting for Arabic
@app.template_filter('aradate')
def format_arabic_date(date):
    """Format date for Arabic display"""
    if not date:
        return ""
    # Could be enhanced with Arabic month names
    return date.strftime("%Y/%m/%d")


# Root route for the website
@app.route('/')
def index():
    """Redirect to dashboard or login page"""
    from flask import redirect, url_for
    from flask_login import current_user
    
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    else:
        return redirect(url_for('auth.login'))


# Serve robots.txt
@app.route('/robots.txt')
def robots():
    """Serve robots.txt file"""
    from flask import send_from_directory
    return send_from_directory(app.static_folder, 'robots.txt')


# Serve sitemap.xml
@app.route('/sitemap.xml')
def sitemap():
    """Serve sitemap.xml file"""
    from flask import send_from_directory
    return send_from_directory(app.static_folder, 'sitemap.xml')


# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    from flask import render_template
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    from flask import render_template
    return render_template('errors/500.html'), 500
