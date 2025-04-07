from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import ipaddress

from app import db, mail
from models import User, LoginLog
from forms.auth import LoginForm, ChangePasswordForm
from flask_mail import Message

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

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate password reset token
            reset_token = generate_password_hash(str(datetime.utcnow()))[:32]
            user.reset_token = reset_token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
            
            # Send reset email
            reset_url = url_for('auth.reset_password_confirm', token=reset_token, _external=True)
            msg = Message('إعادة تعيين كلمة المرور',
                        recipients=[email])
            msg.body = f'''لإعادة تعيين كلمة المرور الخاصة بك، يرجى النقر على الرابط التالي:
{reset_url}

إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذا البريد الإلكتروني.
'''
            mail.send(msg)
            flash('تم إرسال تعليمات إعادة تعيين كلمة المرور إلى بريدك الإلكتروني', 'info')
            
        flash('إذا كان البريد الإلكتروني موجود، سيتم إرسال تعليمات إعادة تعيين كلمة المرور', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('رابط إعادة تعيين كلمة المرور غير صالح أو منتهي الصلاحية', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('تم تغيير كلمة المرور بنجاح', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password_confirm.html')
