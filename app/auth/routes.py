from datetime import datetime, timezone
from flask import app, render_template, redirect, url_for, flash, request, current_app, session, make_response
from flask_login import login_user, logout_user, current_user, login_required
try:
    # Newer Werkzeug moved url_parse; prefer importing if available
    from werkzeug.urls import url_parse
except Exception:
    # Fallback for environments without that attribute
    from urllib.parse import urlparse as url_parse
from app import db
from app.auth import bp
from app.auth.forms import (LoginForm, RegistrationForm, ResetPasswordRequestForm,
                           ResetPasswordForm, ChangePasswordForm, EditProfileForm,
                           PhoneVerificationForm, VerifyPhoneCodeForm, Setup2FAForm, ProfileImageForm,
                           PasswordResetMethodForm, PhoneResetCodeForm, PhoneResetPasswordForm)
from app.models import User, Order
from app.auth.email import send_password_reset_email
try:
    import pyotp
    import qrcode
    import io
    import base64
    TOTP_AVAILABLE = True
except ImportError:
    TOTP_AVAILABLE = False


from google.oauth2 import id_token
from google.auth.transport import requests
import os


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'warning')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        flash(f'Welcome back, {user.first_name}!', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data
        )
        user.set_password(form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"User registration failed: {str(e)}")
            flash('Registration failed due to a server error. Please try again or contact support.', 'danger')
            return render_template('auth/register.html', title='Register', form=form)

        flash('Congratulations, you are now registered!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))



@bp.route('/google', methods=['GET', 'POST'])
def google_login():
    # Handle GET request - redirect to login page
    if request.method == 'GET':
        return redirect(url_for('auth.login'))
    
    # Handle POST request with Google credential token
    token = request.form.get('credential')
    
    if not token:
        flash('No Google credential received. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Check if Google Client ID is configured
        google_client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        if not google_client_id:
            flash('Google authentication is not properly configured. Please contact support.', 'error')
            return redirect(url_for('auth.login'))
        
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            google_client_id
        )
        
        # Get user info from Google
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', '')
        picture = idinfo.get('picture', '')
        given_name = idinfo.get('given_name', '')
        family_name = idinfo.get('family_name', '')
        
        # Check if user exists
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if user exists with same email
            user = User.query.filter_by(email=email).first()
            if user:
                # Link Google account to existing user
                user.google_id = google_id
                if picture:
                    user.profile_image = picture
            else:
                # Create new user
                username = email.split('@')[0]
                # Ensure username is unique
                counter = 1
                original_username = username
                while User.query.filter_by(username=username).first():
                    username = f"{original_username}{counter}"
                    counter += 1
                
                user = User(
                    username=username,
                    email=email,
                    first_name=given_name,
                    last_name=family_name,
                    google_id=google_id,
                    profile_image=picture,
                    is_active=True
                )
        else:
            # Update user info
            if picture:
                user.profile_image = picture
            if given_name:
                user.first_name = given_name
            if family_name:
                user.last_name = family_name
        
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        next_page = request.args.get('next')
        flash(f'Welcome, {user.first_name or user.username}!', 'success')
        return redirect(next_page) if next_page else redirect(url_for('main.index'))
        
    except ValueError as e:
        current_app.logger.error(f'Google token verification error: {str(e)}')
        flash('Invalid Google token. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error(f'Google authentication error: {str(e)}')
        flash('An error occurred during Google login. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    return redirect(url_for('auth.reset_password_method'))

@bp.route('/reset_password_method', methods=['GET', 'POST'])
def reset_password_method():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = PasswordResetMethodForm()
    if form.validate_on_submit():
        if form.method.data == 'email':
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                token = user.generate_reset_token()
                db.session.commit()
                send_password_reset_email(user, token)
                flash('Check your email for the instructions to reset your password', 'info')
            else:
                flash('Email address not found', 'warning')
            return redirect(url_for('auth.login'))
        
        elif form.method.data == 'phone':
            user = User.query.filter_by(phone=form.phone.data).first()
            if user and user.phone_verified:
                code = user.generate_phone_reset_code()
                db.session.commit()
                
                success, error = user.send_password_reset_sms(code)
                if success:
                    flash('Verification code sent to your phone', 'info')
                    return redirect(url_for('auth.reset_password_phone_code', phone=user.phone))
                else:
                    flash(f'Failed to send SMS: {error}', 'danger')
            else:
                flash('Phone number not found or not verified', 'warning')
            return redirect(url_for('auth.reset_password_method'))
    
    return render_template('auth/reset_password_method.html',
                         title='Reset Password', form=form)

@bp.route('/reset_password_phone_code', methods=['GET', 'POST'])
def reset_password_phone_code():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    phone = request.args.get('phone')
    if not phone:
        flash('Invalid reset request', 'danger')
        return redirect(url_for('auth.reset_password_method'))
    
    form = PhoneResetCodeForm()
    if form.validate_on_submit():
        user = User.query.filter_by(phone=phone).first()
        if user and user.verify_phone_reset_code(form.code.data):
            # Store user ID in session for password reset
            session['reset_user_id'] = user.id
            return redirect(url_for('auth.reset_password_phone_new'))
        else:
            flash('Invalid or expired verification code', 'danger')
    
    return render_template('auth/reset_password_phone_code.html',
                         title='Enter Reset Code', form=form, phone=phone)

@bp.route('/reset_password_phone_new', methods=['GET', 'POST'])
def reset_password_phone_new():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user_id = session.get('reset_user_id')
    if not user_id:
        flash('Invalid reset session', 'danger')
        return redirect(url_for('auth.reset_password_method'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Invalid reset session', 'danger')
        return redirect(url_for('auth.reset_password_method'))
    
    form = PhoneResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.phone_verification_code = None
        user.phone_verification_expires = None
        db.session.commit()
        
        # Clear reset session
        session.pop('reset_user_id', None)
        
        flash('Your password has been reset successfully', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_phone_new.html',
                         title='Set New Password', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset token', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Your password has been reset.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EditProfileForm(current_user.username, current_user.email)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.country = form.country.data
        current_user.postal_code = form.postal_code.data
        current_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Your profile has been updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.country.data = current_user.country
        form.postal_code.data = current_user.postal_code
    
    return render_template('auth/profile.html', title='My Profile', form=form)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username, current_user.email)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.country = form.country.data
        current_user.postal_code = form.postal_code.data
        current_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Your changes have been saved.', 'success')
        return redirect(url_for('auth.profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.country.data = current_user.country
        form.postal_code.data = current_user.postal_code
    
    return render_template('auth/edit_profile.html', title='Edit Profile', form=form)

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Invalid current password', 'danger')
            return redirect(url_for('auth.change_password'))
        
        current_user.set_password(form.password.data)
        current_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Your password has been changed.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html', title='Change Password', form=form)

@bp.route('/my-orders')
@login_required
def my_orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('auth/orders.html', title='My Orders', orders=orders)

@bp.route('/orders')
@login_required
def orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('auth/orders.html', title='My Orders', orders=orders)

# Two-Factor Authentication Routes
@bp.route('/setup_2fa')
@login_required
def setup_2fa():
    if not TOTP_AVAILABLE:
        flash('Two-factor authentication is not available. Please contact support.', 'warning')
        return redirect(url_for('auth.profile'))
    
    if current_user.two_factor_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('auth.profile'))
    
    # Generate secret and QR code
    secret = current_user.generate_2fa_secret()
    if not secret:
        flash('Unable to generate 2FA secret. Please try again.', 'error')
        return redirect(url_for('auth.profile'))
    
    db.session.commit()
    
    # Generate QR code
    qr_code_data = None
    if TOTP_AVAILABLE:
        uri = current_user.get_2fa_uri()
        if uri:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            qr_code_data = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('auth/setup_2fa.html',
                         title='Setup Two-Factor Authentication',
                         secret=secret,
                         qr_code=qr_code_data)

@bp.route('/verify_2fa', methods=['GET', 'POST'])
@login_required
def verify_2fa():
    if not TOTP_AVAILABLE:
        flash('Two-factor authentication is not available.', 'warning')
        return redirect(url_for('auth.profile'))
    
    if current_user.two_factor_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('auth.profile'))
    
    if request.method == 'POST':
        token = request.form.get('token')
        if not token:
            flash('Please enter the verification code.', 'error')
            return render_template('auth/verify_2fa.html', title='Verify 2FA Setup')
        
        if current_user.verify_2fa_token(token):
            current_user.two_factor_enabled = True
            backup_codes = current_user.generate_backup_codes()
            db.session.commit()
            
            flash('Two-factor authentication has been successfully enabled!', 'success')
            return render_template('auth/2fa_backup_codes.html',
                                 title='Backup Codes',
                                 backup_codes=backup_codes)
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    return render_template('auth/verify_2fa.html', title='Verify 2FA Setup')

@bp.route('/disable_2fa', methods=['POST'])
@login_required
def disable_2fa():
    if not current_user.two_factor_enabled:
        flash('Two-factor authentication is not enabled.', 'info')
        return redirect(url_for('auth.profile'))
    
    password = request.form.get('password')
    if not password or not current_user.check_password(password):
        flash('Invalid password. Please try again.', 'error')
        return redirect(url_for('auth.profile'))
    
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = None
    db.session.commit()
    
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('auth.profile'))

@bp.route('/2fa_backup_codes')
@login_required
def view_backup_codes():
    if not current_user.two_factor_enabled:
        flash('Two-factor authentication is not enabled.', 'warning')
        return redirect(url_for('auth.profile'))
    
    remaining_codes = current_user.get_remaining_backup_codes()
    return render_template('auth/backup_codes_info.html',
                         title='Backup Codes',
                         remaining_codes=remaining_codes)

# Phone Verification Routes
@bp.route('/verify_phone', methods=['GET', 'POST'])
@login_required
def verify_phone():
    form = PhoneVerificationForm()
    if form.validate_on_submit():
        current_user.phone = form.phone.data
        code = current_user.generate_phone_verification_code()
        db.session.commit()
        
        # Send SMS code with improved error handling
        sms_sent, error_message = current_user.send_sms_code(code)
        
        if sms_sent:
            flash(f'Verification code sent to {current_user.phone}', 'success')
        else:
            flash(f'Code sent via email to {current_user.email} (SMS service unavailable)', 'warning')
            if error_message:
                current_app.logger.error(f"SMS sending failed: {error_message}")
        
        return redirect(url_for('auth.verify_phone_code'))
    
    elif request.method == 'GET' and current_user.phone:
        form.phone.data = current_user.phone
    
    return render_template('auth/verify_phone.html', title='Verify Phone Number', form=form)

@bp.route('/verify_phone_code', methods=['GET', 'POST'])
@login_required
def verify_phone_code():
    if not current_user.phone or not current_user.phone_verification_code:
        flash('Please request a verification code first.', 'warning')
        return redirect(url_for('auth.verify_phone'))
    
    form = VerifyPhoneCodeForm()
    if form.validate_on_submit():
        if current_user.verify_phone_code(form.code.data):
            db.session.commit()
            flash('Phone number verified successfully!', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Invalid or expired verification code.', 'danger')
    
    return render_template('auth/verify_phone_code.html',
                         title='Enter Verification Code',
                         form=form,
                         phone=current_user.phone)

# Enhanced 2FA Setup
@bp.route('/setup_2fa_method', methods=['GET', 'POST'])
@login_required
def setup_2fa_method():
    if current_user.two_factor_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('auth.profile'))
    
    form = Setup2FAForm()
    if form.validate_on_submit():
        if form.method.data == 'sms':
            if not current_user.phone_verified:
                flash('Please verify your phone number first.', 'warning')
                return redirect(url_for('auth.verify_phone'))
            current_user.two_factor_method = 'sms'
            current_user.two_factor_enabled = True
            db.session.commit()
            flash('SMS-based 2FA has been enabled!', 'success')
            return redirect(url_for('auth.profile'))
        else:
            current_user.two_factor_method = 'totp'
            return redirect(url_for('auth.setup_2fa'))
    
    return render_template('auth/setup_2fa_method.html', title='Choose 2FA Method', form=form)

# Profile Image Upload
@bp.route('/upload_profile_image', methods=['GET', 'POST'])
@login_required
def upload_profile_image():
    form = ProfileImageForm()
    if form.validate_on_submit():
        if form.profile_image.data:
            from werkzeug.utils import secure_filename
            import os
            from datetime import datetime
            
            filename = secure_filename(form.profile_image.data.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            
            # Create profile images directory
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save the file
            file_path = os.path.join(upload_dir, filename)
            form.profile_image.data.save(file_path)
            
            # Update user profile image
            current_user.profile_image = f'profiles/{filename}'
            current_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            flash('Profile image updated successfully!', 'success')
            return redirect(url_for('auth.profile'))
    
    return render_template('auth/upload_profile_image.html', title='Upload Profile Image', form=form)

@bp.route('/remove_profile_image', methods=['POST'])
@login_required
def remove_profile_image():
    if current_user.profile_image and not current_user.profile_image.startswith('http'):
        # Remove local file
        import os
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.profile_image)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    current_user.profile_image = 'default.jpg'
    current_user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    flash('Profile image removed successfully!', 'success')
    return redirect(url_for('auth.profile'))