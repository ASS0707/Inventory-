from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember = BooleanField('تذكرني')
    submit = SubmitField('تسجيل الدخول')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('كلمة المرور الحالية', validators=[DataRequired()])
    new_password = PasswordField('كلمة المرور الجديدة', validators=[
        DataRequired(),
        Length(min=6, message='كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور الجديدة', validators=[
        DataRequired(),
        EqualTo('new_password', message='كلمات المرور غير متطابقة')
    ])
    submit = SubmitField('تغيير كلمة المرور')


class UserForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[
        DataRequired(),
        Length(min=6, message='كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[
        DataRequired(),
        EqualTo('password', message='كلمات المرور غير متطابقة')
    ])
    role = SelectField('الصلاحيات', choices=[
        ('employee', 'موظف'),
        ('admin', 'مدير')
    ], default='employee')
    submit = SubmitField('إضافة مستخدم')


class EditUserForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[
        Length(min=6, message='كلمة المرور يجب أن تكون 6 أحرف على الأقل'),
        EqualTo('confirm_password', message='كلمات المرور غير متطابقة')
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور')
    role = SelectField('الصلاحيات', choices=[
        ('employee', 'موظف'),
        ('admin', 'مدير')
    ])
    submit = SubmitField('تحديث المستخدم')
