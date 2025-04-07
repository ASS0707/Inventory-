from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, FloatField, HiddenField, SubmitField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Optional
import datetime


class InvoiceForm(FlaskForm):
    invoice_number = StringField('رقم الفاتورة', validators=[DataRequired()])
    type = SelectField('نوع الفاتورة', choices=[
        ('sale', 'مبيعات'),
        ('purchase', 'مشتريات'),
        ('return', 'مرتجع من عميل'),
        ('supplier_return', 'مرتجع إلى مورد')
    ], validators=[DataRequired()])
    date = DateField('تاريخ الفاتورة', validators=[DataRequired()], default=datetime.datetime.now)
    due_date = DateField('تاريخ الاستحقاق', validators=[Optional()])
    client_id = SelectField('العميل', coerce=int, validators=[Optional()])
    supplier_id = SelectField('المورد', coerce=int, validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    submit = SubmitField('إنشاء الفاتورة')


class InvoiceItemForm(FlaskForm):
    product_id = SelectField('المنتج', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('الكمية', validators=[DataRequired(), NumberRange(min=1)])
    unit_price = FloatField('سعر الوحدة', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('إضافة')


class PaymentForm(FlaskForm):
    invoice_id = SelectField('الفاتورة', coerce=int, validators=[Optional()], 
                           choices=[(0, 'دفعة عامة (غير مرتبطة بفاتورة)')], default=0)
    amount = FloatField('المبلغ', validators=[DataRequired(), NumberRange(min=0.01)])
    payment_date = DateField('تاريخ الدفع', validators=[DataRequired()], default=datetime.datetime.now)
    payment_method = SelectField('طريقة الدفع', choices=[
        ('cash', 'نقدي'),
        ('bank_transfer', 'تحويل بنكي'),
        ('check', 'شيك'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    reference_number = StringField('رقم مرجعي', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    submit = SubmitField('إضافة الدفعة')
