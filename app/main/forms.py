from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, NumberRange, Length, Optional

class AddToCartForm(FlaskForm):
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1, max=100)], default=1)
    submit = SubmitField('Add to Cart')

class UpdateCartForm(FlaskForm):
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0, max=100)])
    submit = SubmitField('Update')

class CheckoutForm(FlaskForm):
    # Shipping Information
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired(), Length(max=50)])
    country = StringField('Country', validators=[DataRequired(), Length(max=50)])
    postal_code = StringField('Postal Code', validators=[Optional(), Length(max=20)])
    
    # Payment Method
    payment_method = SelectField('Payment Method', 
                               choices=[('card', 'Credit/Debit Card'), 
                                      ('momo', 'Mobile Money'),
                                      ('bank_transfer', 'Bank Transfer')],
                               validators=[DataRequired()])
    
    submit = SubmitField('Place Order')

class ReviewForm(FlaskForm):
    rating = SelectField('Rating', 
                        choices=[(5, '5 Stars - Excellent'), 
                               (4, '4 Stars - Very Good'), 
                               (3, '3 Stars - Good'), 
                               (2, '2 Stars - Fair'), 
                               (1, '1 Star - Poor')],
                        coerce=int, validators=[DataRequired()])
    title = StringField('Review Title', validators=[Optional(), Length(max=200)])
    comment = TextAreaField('Your Review', validators=[Optional()])
    submit = SubmitField('Submit Review')

class NewsletterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Subscribe')

class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired(), Length(max=200)])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')

class SearchForm(FlaskForm):
    q = StringField('Search', validators=[DataRequired()])
    category = SelectField('Category', choices=[('', 'All Categories')], coerce=str)
    min_price = StringField('Min Price', validators=[Optional()])
    max_price = StringField('Max Price', validators=[Optional()])
    sort_by = SelectField('Sort By', 
                         choices=[('name_asc', 'Name A-Z'), 
                                ('name_desc', 'Name Z-A'),
                                ('price_asc', 'Price Low to High'), 
                                ('price_desc', 'Price High to Low'),
                                ('newest', 'Newest First'),
                                ('rating', 'Highest Rated')],
                         default='name_asc')
    submit = SubmitField('Search')

class PaymentForm(FlaskForm):
    payment_method = HiddenField()
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    network = SelectField('Network', 
                         choices=[('mtn', 'MTN'), 
                                ('vodafone', 'Vodafone'), 
                                ('airteltigo', 'AirtelTigo')],
                         validators=[Optional()])
    submit = SubmitField('Pay Now')