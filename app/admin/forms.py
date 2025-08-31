from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from app.models import Category, Product

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    image = FileField('Category Image', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Category')

    def __init__(self, original_name=None, *args, **kwargs):
        super(CategoryForm, self).__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        if name.data != self.original_name:
            category = Category.query.filter_by(name=name.data).first()
            if category is not None:
                raise ValidationError('Please use a different category name.')

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    price = DecimalField('Price', validators=[DataRequired(), NumberRange(min=0)], places=2)
    compare_price = DecimalField('Compare Price', validators=[Optional(), NumberRange(min=0)], places=2)
    cost_price = DecimalField('Cost Price', validators=[Optional(), NumberRange(min=0)], places=2)
    sku = StringField('SKU', validators=[Optional(), Length(max=100)])
    stock_quantity = IntegerField('Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    min_stock_level = IntegerField('Minimum Stock Level', validators=[Optional(), NumberRange(min=0)], default=5)
    weight = DecimalField('Weight (kg)', validators=[Optional(), NumberRange(min=0)], places=2)
    dimensions = StringField('Dimensions', validators=[Optional(), Length(max=100)])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    is_featured = BooleanField('Featured', default=False)
    meta_title = StringField('Meta Title', validators=[Optional(), Length(max=200)])
    meta_description = TextAreaField('Meta Description')
    submit = SubmitField('Save Product')

    def __init__(self, original_sku=None, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.original_sku = original_sku
        self.category_id.choices = [(c.id, c.name) for c in Category.query.filter_by(is_active=True).all()]

    def validate_sku(self, sku):
        if sku.data and sku.data != self.original_sku:
            product = Product.query.filter_by(sku=sku.data).first()
            if product is not None:
                raise ValidationError('Please use a different SKU.')

class ProductImageForm(FlaskForm):
    image = FileField('Product Image', validators=[DataRequired(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')])
    alt_text = StringField('Alt Text', validators=[Optional(), Length(max=200)])
    is_main = BooleanField('Main Image', default=False)
    sort_order = IntegerField('Sort Order', validators=[Optional(), NumberRange(min=0)], default=0)
    submit = SubmitField('Upload Image')

class OrderStatusForm(FlaskForm):
    status = SelectField('Order Status', 
                        choices=[('pending', 'Pending'), 
                               ('confirmed', 'Confirmed'), 
                               ('processing', 'Processing'), 
                               ('shipped', 'Shipped'), 
                               ('delivered', 'Delivered'), 
                               ('cancelled', 'Cancelled')],
                        validators=[DataRequired()])
    payment_status = SelectField('Payment Status',
                                choices=[('pending', 'Pending'),
                                       ('paid', 'Paid'),
                                       ('failed', 'Failed'),
                                       ('refunded', 'Refunded')],
                                validators=[DataRequired()])
    submit = SubmitField('Update Order')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address')
    city = StringField('City', validators=[Optional(), Length(max=50)])
    country = StringField('Country', validators=[Optional(), Length(max=50)])
    postal_code = StringField('Postal Code', validators=[Optional(), Length(max=20)])
    is_admin = BooleanField('Admin User', default=False)
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save User')

class ReviewModerationForm(FlaskForm):
    is_approved = BooleanField('Approved', default=True)
    submit = SubmitField('Update Review')

class BulkActionForm(FlaskForm):
    action = SelectField('Action', 
                        choices=[('', 'Select Action'),
                               ('activate', 'Activate'),
                               ('deactivate', 'Deactivate'),
                               ('delete', 'Delete')],
                        validators=[DataRequired()])
    submit = SubmitField('Apply')

class SearchForm(FlaskForm):
    search = StringField('Search')
    submit = SubmitField('Search')

class DateRangeForm(FlaskForm):
    start_date = StringField('Start Date')
    end_date = StringField('End Date')
    submit = SubmitField('Filter')