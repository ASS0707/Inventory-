from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional


class ClientForm(FlaskForm):
    name = StringField('اسم العميل', validators=[DataRequired()])
    phone = StringField('رقم الهاتف', validators=[DataRequired()])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email()])
    address = TextAreaField('العنوان', validators=[Optional()])
    submit = SubmitField('حفظ')
