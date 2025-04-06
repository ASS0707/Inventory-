from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import subprocess
import datetime
import os

from app import db
from models import User, LoginLog, SystemLog

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/users')
@login_required
def users():
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Get all users
    users_list = User.query.all()
    
    return render_template('admin/users.html', users=users_list)


@admin_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    from forms.auth import UserForm
    form = UserForm()
    
    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('اسم المستخدم موجود بالفعل', 'danger')
            return render_template('admin/add_user.html', form=form)
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('البريد الإلكتروني موجود بالفعل', 'danger')
            return render_template('admin/add_user.html', form=form)
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            role=form.role.data
        )
        
        # Log the creation
        log = SystemLog(
            action='user_create',
            details=f'إنشاء مستخدم جديد: {user.username}',
            user_id=current_user.id
        )
        
        db.session.add(user)
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم إنشاء المستخدم {user.username} بنجاح', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/add_user.html', form=form)


@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    user = User.query.get_or_404(user_id)
    
    from forms.auth import EditUserForm
    form = EditUserForm(obj=user)
    
    if form.validate_on_submit():
        # Check if username already exists (excluding this user)
        existing_user = User.query.filter(User.username == form.username.data, User.id != user_id).first()
        if existing_user:
            flash('اسم المستخدم موجود بالفعل', 'danger')
            return render_template('admin/edit_user.html', form=form, user=user)
        
        # Check if email already exists (excluding this user)
        existing_email = User.query.filter(User.email == form.email.data, User.id != user_id).first()
        if existing_email:
            flash('البريد الإلكتروني موجود بالفعل', 'danger')
            return render_template('admin/edit_user.html', form=form, user=user)
        
        # Update user details
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        
        # Update password if provided
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data)
        
        # Log the update
        log = SystemLog(
            action='user_edit',
            details=f'تعديل المستخدم: {user.username}',
            user_id=current_user.id
        )
        
        db.session.add(log)
        db.session.commit()
        
        flash(f'تم تحديث المستخدم {user.username} بنجاح', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', form=form, user=user)


@admin_bp.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Prevent deleting self
    if user_id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    
    # Log the deletion
    log = SystemLog(
        action='user_delete',
        details=f'حذف المستخدم: {user.username}',
        user_id=current_user.id
    )
    
    db.session.add(log)
    db.session.delete(user)
    db.session.commit()
    
    flash(f'تم حذف المستخدم {user.username} بنجاح', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/login_logs')
@login_required
def login_logs():
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Get login logs with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs = LoginLog.query.order_by(LoginLog.login_time.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin/login_logs.html', logs=logs)


@admin_bp.route('/system_logs')
@login_required
def system_logs():
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Get system logs with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin/system_logs.html', logs=logs)


@admin_bp.route('/backup')
@login_required
def backup():
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    return render_template('admin/backups.html')


@admin_bp.route('/create_backup')
@login_required
def create_backup():
    # Check if user is admin
    if current_user.role != 'admin':
        flash('ليس لديك صلاحيات كافية للوصول إلى هذه الصفحة', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Create backup using SQLAlchemy
    from sqlalchemy import create_engine, MetaData
    from app import app
    
    try:
        # Get database URI
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Create dump
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backup_{now}.sql"
        
        # For SQLite, we can just create a memory output
        if db_uri.startswith('sqlite'):
            # Create a simple backup with data inserts
            metadata = MetaData()
            metadata.reflect(bind=db.engine)
            
            output = []
            
            # For each table
            for table in metadata.sorted_tables:
                output.append(f"-- Table: {table.name}")
                
                # Get column names
                columns = [c.name for c in table.columns]
                
                # Get all rows
                result = db.session.execute(table.select())
                for row in result:
                    values = ", ".join([f"'{str(v)}'" if v is not None else "NULL" for v in row])
                    output.append(f"INSERT INTO {table.name} ({', '.join(columns)}) VALUES ({values});")
                
                output.append("\n")
            
            # Create response
            response = Response(
                "\n".join(output),
                mimetype="application/sql",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
            
            # Log the backup
            log = SystemLog(
                action='backup_create',
                details=f'إنشاء نسخة احتياطية: {filename}',
                user_id=current_user.id
            )
            db.session.add(log)
            db.session.commit()
            
            return response
        else:
            flash('الخاصية غير متاحة للقواعد البيانات الغير SQLite في الوقت الحالي', 'warning')
            return redirect(url_for('admin.backup'))
    
    except Exception as e:
        flash(f'حدث خطأ أثناء إنشاء النسخة الاحتياطية: {str(e)}', 'danger')
        return redirect(url_for('admin.backup'))
