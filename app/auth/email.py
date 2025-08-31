from flask import render_template, current_app, url_for
from flask_mail import Message
from app import mail
import threading

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            return True, None
        except Exception as e:
            return False, str(e)

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    try:
        # Try to send email synchronously for better error handling
        mail.send(msg)
        return True, None
    except Exception as e:
        return False, str(e)

def send_password_reset_email(user, token):
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    send_email(
        subject='[H2HERBAL] Reset Your Password',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/reset_password.txt',
                                user=user, reset_url=reset_url),
        html_body=render_template('email/reset_password.html',
                                user=user, reset_url=reset_url)
    )

def send_order_confirmation_email(user, order):
    send_email(
        subject=f'[H2HERBAL] Order Confirmation - {order.order_number}',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/order_confirmation.txt',
                                user=user, order=order),
        html_body=render_template('email/order_confirmation.html',
                                user=user, order=order)
    )

def send_admin_message_email(user, message, admin_user):
    return send_email(
        subject='[H2HERBAL] Message from Administrator',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/admin_message.txt',
                                user=user, message=message, admin_user=admin_user),
        html_body=render_template('email/admin_message.html',
                                user=user, message=message, admin_user=admin_user)
    )

def send_order_status_update_email(user, order):
    send_email(
        subject=f'[H2HERBAL] Order Update - {order.order_number}',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/order_status_update.txt',
                                user=user, order=order),
        html_body=render_template('email/order_status_update.html',
                                user=user, order=order)
    )

def send_sms_code_via_email(user, code):
    """Send SMS verification code via email as fallback"""
    return send_email(
        subject='[H2HERBAL] SMS Verification Code',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/sms_code.txt',
                                user=user, code=code),
        html_body=render_template('email/sms_code.html',
                                user=user, code=code)
    )