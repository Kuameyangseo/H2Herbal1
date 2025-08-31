from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Change Password')

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    phone = StringField('Phone', validators=[Length(max=20)])
    address = TextAreaField('Address')
    city = StringField('City', validators=[Length(max=50)])
    country = StringField('Country', validators=[Length(max=50)])
    postal_code = StringField('Postal Code', validators=[Length(max=20)])
    submit = SubmitField('Update Profile')

    def __init__(self, original_username, original_email, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=self.email.data).first()
            if user is not None:
                raise ValidationError('Please use a different email address.')

class PhoneVerificationForm(FlaskForm):
    phone = StringField('Phone Number', validators=[
        DataRequired(),
        Length(min=10, max=20),
        Regexp(r'^\+?[1-9]\d{1,14}$', message="Please enter a valid phone number")
    ])
    submit = SubmitField('Send Verification Code')

class VerifyPhoneCodeForm(FlaskForm):
    code = StringField('Verification Code', validators=[
        DataRequired(),
        Length(min=6, max=6),
        Regexp(r'^\d{6}$', message="Please enter a 6-digit code")
    ])
    submit = SubmitField('Verify Code')

class Setup2FAForm(FlaskForm):
    method = SelectField('2FA Method', choices=[
        ('totp', 'Authenticator App (Google Authenticator, Authy)'),
        ('sms', 'SMS to Phone Number')
    ], validators=[DataRequired()])
    submit = SubmitField('Continue')

class ProfileImageForm(FlaskForm):
    profile_image = FileField('Profile Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    submit = SubmitField('Upload Image')

class PasswordResetMethodForm(FlaskForm):
    method = SelectField('Reset Method', choices=[
        ('email', 'Send reset link to email'),
        ('phone', 'Send verification code to phone')
    ], validators=[DataRequired()])
    email = StringField('Email', validators=[Email()])
    phone = StringField('Phone Number', validators=[
        Regexp(r'^\+?[1-9]\d{1,14}$', message="Please enter a valid phone number")
    ])
    submit = SubmitField('Send Reset Code')

class PhoneResetCodeForm(FlaskForm):
    code = StringField('Reset Code', validators=[
        DataRequired(),
        Length(min=6, max=6),
        Regexp(r'^\d{6}$', message="Please enter a 6-digit code")
    ])
    submit = SubmitField('Verify Code')

class PhoneResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')