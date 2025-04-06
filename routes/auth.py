from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import ipaddress

from app import db
from models import User, LoginLog
from forms.auth import LoginForm, ChangePasswordForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            
            # Update last login time
            user.last_login = datetime.utcnow()
            
            # Log successful login
            ip = request.remote_addr
            log_entry = LoginLog(
                user_id=user.id,
                ip_address=ip,
                success=True
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            # Redirect to the page user tried to access or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            # Log failed login attempt
            if user:
                log_entry = LoginLog(
                    user_id=user.id,
                    ip_address=request.remote_addr,
                    success=False
                )
                db.session.add(log_entry)
                db.session.commit()
            
            flash('فشل تسجيل الدخول. يرجى التحقق من اسم المستخدم وكلمة المرور', 'danger')
    
    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash('تم تغيير كلمة المرور بنجاح', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('كلمة المرور الحالية غير صحيحة', 'danger')
    
    return render_template('change_password.html', form=form)
