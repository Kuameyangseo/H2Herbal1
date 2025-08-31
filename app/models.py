from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
import secrets

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    google_id = db.Column(db.String(100), unique=True)
    profile_image = db.Column(db.String(255), default='default.jpg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Password reset token
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    
    # Two-Factor Authentication
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32))
    backup_codes = db.Column(db.Text)  # JSON string of backup codes
    
    # Phone verification for 2FA
    phone_verified = db.Column(db.Boolean, default=False)
    phone_verification_code = db.Column(db.String(6))
    phone_verification_expires = db.Column(db.DateTime)
    two_factor_method = db.Column(db.String(10), default='totp')  # 'totp' or 'sms'
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token
    
    def verify_reset_token(self, token):
        return (self.reset_token == token and
                self.reset_token_expiry and
                self.reset_token_expiry > datetime.utcnow())
    
    def generate_phone_reset_code(self):
        """Generate a 6-digit phone reset code"""
        import random
        from datetime import datetime, timedelta
        
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.phone_verification_code = code
        self.phone_verification_expires = datetime.utcnow() + timedelta(minutes=10)
        return code
    
    def verify_phone_reset_code(self, code):
        """Verify phone reset code"""
        from datetime import datetime
        
        if not self.phone_verification_code or not self.phone_verification_expires:
            return False
        
        if datetime.utcnow() > self.phone_verification_expires:
            return False
        
        if self.phone_verification_code == code:
            # Don't clear the code yet - will be cleared after password reset
            return True
        
        return False
    
    def send_password_reset_sms(self, code):
        """Send password reset code via SMS"""
        from flask import current_app
        import requests
        
        # Method 1: Twilio SMS
        if current_app.config.get('TWILIO_ACCOUNT_SID') and current_app.config.get('TWILIO_AUTH_TOKEN'):
            try:
                from twilio.rest import Client
                client = Client(
                    current_app.config['TWILIO_ACCOUNT_SID'],
                    current_app.config['TWILIO_AUTH_TOKEN']
                )
                message = client.messages.create(
                    body=f"Your H2HERBAL password reset code is: {code}. Valid for 10 minutes.",
                    from_=current_app.config.get('TWILIO_PHONE_NUMBER'),
                    to=self.phone
                )
                current_app.logger.info(f"Password reset SMS sent via Twilio: {message.sid}")
                return True, None
            except Exception as e:
                current_app.logger.error(f"Twilio SMS failed: {str(e)}")
        
        # Method 2: TextBelt SMS (Free alternative)
        try:
            response = requests.post('https://textbelt.com/text', {
                'phone': self.phone,
                'message': f"Your H2HERBAL password reset code is: {code}. Valid for 10 minutes.",
                'key': current_app.config.get('TEXTBELT_API_KEY', 'textbelt')
            }, timeout=10)
            
            result = response.json()
            if result.get('success'):
                current_app.logger.info(f"Password reset SMS sent via TextBelt to {self.phone}")
                return True, None
            else:
                error_message = f"TextBelt SMS failed: {result.get('error', 'Unknown error')}"
                current_app.logger.error(error_message)
                return False, error_message
        except Exception as e:
            error_message = f"TextBelt SMS failed: {str(e)}"
            current_app.logger.error(error_message)
        
        # Development mode fallback
        if current_app.config.get('FLASK_ENV') == 'development':
            current_app.logger.info(f"Development Mode - Password Reset Code for {self.phone}: {code}")
            print(f"Password Reset Code for {self.phone}: {code}")
            
            from flask import session
            session['dev_reset_code'] = code
            session['dev_reset_phone'] = self.phone
            return True, "Development mode - code displayed in UI"
        
        return False, "SMS service unavailable"
    
    def get_cart_total(self):
        total = Decimal('0.00')
        for item in self.cart_items:
            item_total = Decimal(str(item.product.price)) * Decimal(str(item.quantity))
            total += item_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return float(total)
    
    def get_cart_count(self):
        return sum(item.quantity for item in self.cart_items)
    
    def generate_2fa_secret(self):
        """Generate a new 2FA secret key"""
        try:
            import pyotp
            self.two_factor_secret = pyotp.random_base32()
            return self.two_factor_secret
        except ImportError:
            return None
    
    def get_2fa_uri(self):
        """Get the 2FA URI for QR code generation"""
        try:
            import pyotp
            if self.two_factor_secret:
                totp = pyotp.TOTP(self.two_factor_secret)
                return totp.provisioning_uri(
                    name=self.email,
                    issuer_name="H2HERBAL"
                )
        except ImportError:
            pass
        return None
    
    def verify_2fa_token(self, token):
        """Verify a 2FA token"""
        try:
            import pyotp
            if self.two_factor_secret:
                totp = pyotp.TOTP(self.two_factor_secret)
                return totp.verify(token, valid_window=1)
        except ImportError:
            pass
        return False
    
    def generate_backup_codes(self):
        """Generate backup codes for 2FA"""
        import secrets
        import json
        codes = [secrets.token_hex(4).upper() for _ in range(10)]
        self.backup_codes = json.dumps(codes)
        return codes
    
    def verify_backup_code(self, code):
        """Verify and consume a backup code"""
        import json
        if self.backup_codes:
            codes = json.loads(self.backup_codes)
            if code.upper() in codes:
                codes.remove(code.upper())
                self.backup_codes = json.dumps(codes)
                return True
        return False
    
    def get_remaining_backup_codes(self):
        """Get count of remaining backup codes"""
        import json
        if self.backup_codes:
            codes = json.loads(self.backup_codes)
            return len(codes)
        return 0
    
    def generate_phone_verification_code(self):
        """Generate a 6-digit phone verification code"""
        import random
        from datetime import datetime, timedelta
        
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.phone_verification_code = code
        self.phone_verification_expires = datetime.utcnow() + timedelta(minutes=10)
        return code
    
    def verify_phone_code(self, code):
        """Verify phone verification code"""
        from datetime import datetime
        
        if not self.phone_verification_code or not self.phone_verification_expires:
            return False
        
        if datetime.utcnow() > self.phone_verification_expires:
            return False
        
        if self.phone_verification_code == code:
            self.phone_verified = True
            self.phone_verification_code = None
            self.phone_verification_expires = None
            return True
        
        return False
    
    def send_sms_code(self, code):
        """Send SMS verification code to phone number"""
        from flask import current_app
        import requests
        import json
        
        sms_sent = False
        error_message = None
        
        # Method 1: Twilio SMS (Primary)
        if current_app.config.get('TWILIO_ACCOUNT_SID') and current_app.config.get('TWILIO_AUTH_TOKEN'):
            try:
                from twilio.rest import Client
                client = Client(
                    current_app.config['TWILIO_ACCOUNT_SID'],
                    current_app.config['TWILIO_AUTH_TOKEN']
                )
                message = client.messages.create(
                    body=f"Your H2HERBAL verification code is: {code}. Valid for 10 minutes.",
                    from_=current_app.config.get('TWILIO_PHONE_NUMBER'),
                    to=self.phone
                )
                current_app.logger.info(f"SMS sent via Twilio: {message.sid}")
                return True, None
            except Exception as e:
                error_message = f"Twilio SMS failed: {str(e)}"
                current_app.logger.error(error_message)
        
        # Method 2: TextBelt SMS (Free alternative)
        try:
            response = requests.post('https://textbelt.com/text', {
                'phone': self.phone,
                'message': f"Your H2HERBAL verification code is: {code}. Valid for 10 minutes.",
                'key': current_app.config.get('TEXTBELT_API_KEY', 'textbelt')  # 'textbelt' for free quota
            }, timeout=10)
            
            result = response.json()
            if result.get('success'):
                current_app.logger.info(f"SMS sent via TextBelt to {self.phone}")
                return True, None
            else:
                error_message = f"TextBelt SMS failed: {result.get('error', 'Unknown error')}"
                current_app.logger.error(error_message)
        except Exception as e:
            error_message = f"TextBelt SMS failed: {str(e)}"
            current_app.logger.error(error_message)
        
        # Method 3: SMS API (Alternative free service)
        try:
            # Using SMS API service (you can replace with your preferred SMS service)
            api_key = current_app.config.get('SMS_API_KEY')
            if api_key:
                response = requests.post('https://api.smsapi.com/sms.do', {
                    'username': current_app.config.get('SMS_API_USERNAME'),
                    'password': current_app.config.get('SMS_API_PASSWORD'),
                    'to': self.phone,
                    'message': f"Your H2HERBAL verification code is: {code}. Valid for 10 minutes.",
                    'format': 'json'
                }, timeout=10)
                
                if response.status_code == 200:
                    current_app.logger.info(f"SMS sent via SMS API to {self.phone}")
                    return True, None
        except Exception as e:
            current_app.logger.error(f"SMS API failed: {str(e)}")
        
        # Development mode fallback - show code in UI
        if current_app.config.get('FLASK_ENV') == 'development':
            current_app.logger.info(f"Development Mode - SMS Code for {self.phone}: {code}")
            print(f"SMS Code for {self.phone}: {code}")
            
            # Store code in session for development mode display
            from flask import session
            session['dev_sms_code'] = code
            session['dev_sms_phone'] = self.phone
            return True, "Development mode - code displayed in UI"
        
        return False, error_message or "All SMS services failed"
    
    def to_dict(self):
        """Convert user to dictionary for JSON responses"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'profile_image': self.profile_image,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    compare_price = db.Column(db.Numeric(10, 2))  # Original price for discounts
    cost_price = db.Column(db.Numeric(10, 2))  # Cost price for profit calculation
    sku = db.Column(db.String(100), unique=True)
    stock_quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=5)
    weight = db.Column(db.Float)
    dimensions = db.Column(db.String(100))  # e.g., "10x5x3 cm"
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    
    # Relationships
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    reviews = db.relationship('Review', backref='product', lazy=True)
    
    def get_main_image(self):
        # First try to get the main image
        main_image = ProductImage.query.filter_by(product_id=self.id, is_main=True).first()
        if main_image:
            return main_image.image_url
        
        # If no main image, get the first available image
        first_image = ProductImage.query.filter_by(product_id=self.id).first()
        if first_image:
            return first_image.image_url
        
        # If no images at all, return a default placeholder URL
        return 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?ixlib=rb-4.0.3&w=300&h=250&fit=crop'
    
    def get_discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            discount = ((self.compare_price - self.price) / self.compare_price) * 100
            return round(float(discount))
        return 0
    
    def is_in_stock(self):
        return self.stock_quantity > 0
    
    def is_low_stock(self):
        return self.stock_quantity <= self.min_stock_level
    
    def get_average_rating(self):
        if self.reviews:
            total_rating = sum(review.rating for review in self.reviews)
            return round(total_rating / len(self.reviews), 1)
        return 0
    
    def get_price_float(self):
        return float(self.price)

    def __repr__(self):
        return f'<Product {self.name}>'

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(200))
    is_main = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ProductImage {self.image_url}>'

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_total_price(self):
        total = Decimal(str(self.product.price)) * Decimal(str(self.quantity))
        return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def __repr__(self):
        return f'<CartItem {self.product.name} x {self.quantity}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Order totals
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    shipping_cost = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Order status
    status = db.Column(db.String(50), default='pending')  # pending, confirmed, processing, shipped, delivered, cancelled
    payment_status = db.Column(db.String(50), default='pending')  # pending, paid, failed, refunded
    payment_method = db.Column(db.String(50))  # card, momo, bank_transfer
    payment_reference = db.Column(db.String(100))
    
    # Shipping information
    shipping_first_name = db.Column(db.String(50), nullable=False)
    shipping_last_name = db.Column(db.String(50), nullable=False)
    shipping_email = db.Column(db.String(120), nullable=False)
    shipping_phone = db.Column(db.String(20))
    shipping_address = db.Column(db.Text, nullable=False)
    shipping_city = db.Column(db.String(50), nullable=False)
    shipping_country = db.Column(db.String(50), nullable=False)
    shipping_postal_code = db.Column(db.String(20))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def generate_order_number(self):
        import random
        import string
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        random_part = ''.join(random.choices(string.digits, k=4))
        return f'ORD-{timestamp}-{random_part}'
    
    def get_total_items(self):
        return sum(item.quantity for item in self.items)
    
    def get_status_color(self):
        status_colors = {
            'pending': 'warning',
            'confirmed': 'info',
            'processing': 'primary',
            'shipped': 'secondary',
            'delivered': 'success',
            'cancelled': 'danger'
        }
        return status_colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Product details at time of order (in case product changes later)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(100))

    def __repr__(self):
        return f'<OrderItem {self.product_name} x {self.quantity}>'

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    title = db.Column(db.String(200))
    comment = db.Column(db.Text)
    is_verified_purchase = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Review {self.rating} stars for {self.product.name}>'

class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Newsletter {self.email}>'

class MessageHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Admin who sent the message
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # User who received the message
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    email_sent = db.Column(db.Boolean, default=False)
    email_error = db.Column(db.Text)  # Store any email sending errors
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

    def __repr__(self):
        return f'<MessageHistory from {self.sender.username} to {self.recipient.username}>'

class ChatSession(db.Model):
    """Chat session between customer and support agent"""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Null if unassigned
    status = db.Column(db.String(20), default='active')  # active, closed, waiting
    subject = db.Column(db.String(200))
    priority = db.Column(db.String(10), default='normal')  # low, normal, high, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    
    # New fields for enhanced functionality
    assigned_at = db.Column(db.DateTime)  # When agent was assigned
    first_response_at = db.Column(db.DateTime)  # Time of first agent response
    resolved_at = db.Column(db.DateTime)  # When chat was resolved/closed
    satisfaction_rating = db.Column(db.Integer)  # 1-5 rating from customer
    satisfaction_feedback = db.Column(db.Text)  # Customer feedback
    
    # Relationships
    customer = db.relationship('User', foreign_keys=[customer_id], backref='customer_chat_sessions')
    agent = db.relationship('User', foreign_keys=[agent_id], backref='agent_chat_sessions')
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def get_last_message(self):
        """Get the last message in this session"""
        return ChatMessage.query.filter_by(session_id=self.id).order_by(ChatMessage.created_at.desc()).first()
    
    def get_unread_count_for_user(self, user_id):
        """Get count of unread messages for a specific user"""
        return ChatMessage.query.filter_by(
            session_id=self.id,
            is_read=False
        ).filter(ChatMessage.sender_id != user_id).count()
    
    def mark_messages_as_read(self, user_id):
        """Mark all messages as read for a specific user (except their own messages)"""
        ChatMessage.query.filter_by(session_id=self.id).filter(
            ChatMessage.sender_id != user_id
        ).update({'is_read': True})
        db.session.commit()
    
    def get_status_color(self):
        """Get Bootstrap color class for status"""
        status_colors = {
            'active': 'success',
            'waiting': 'warning',
            'closed': 'secondary'
        }
        return status_colors.get(self.status, 'secondary')
    
    def get_priority_color(self):
        """Get Bootstrap color class for priority"""
        priority_colors = {
            'low': 'info',
            'normal': 'secondary',
            'high': 'warning',
            'urgent': 'danger'
        }
        return priority_colors.get(self.priority, 'secondary')
    
    def get_customer_messages(self):
        """Get all messages from the customer (non-admin users) in this session"""
        return ChatMessage.query.filter_by(session_id=self.id).join(User).filter(
            User.is_admin == False
        ).all()

    def __repr__(self):
        return f'<ChatSession {self.id} - {self.customer.username}>'

class ChatMessage(db.Model):
    """Individual chat message within a session"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, file, system
    attachment_url = db.Column(db.String(500))  # For file/image attachments
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Enhanced fields for better functionality
    is_edited = db.Column(db.Boolean, default=False)  # Whether message was edited
    edited_at = db.Column(db.DateTime)  # When message was last edited
    reply_to_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'))  # For message threading
    
    # Relationships
    sender = db.relationship('User', backref='chat_messages')
    replies = db.relationship('ChatMessage', backref=db.backref('parent', remote_side=[id]))
    
    def is_from_customer(self):
        """Check if message is from customer (not admin)"""
        return not self.sender.is_admin
    
    def is_from_agent(self):
        """Check if message is from agent (admin)"""
        return self.sender.is_admin
    
    def get_time_ago(self):
        """Get human-readable time ago"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    def __repr__(self):
        return f'<ChatMessage {self.id} from {self.sender.username}>'

class ChatNotification(db.Model):
    """Notifications for chat events"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # new_message, session_assigned, session_closed
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='chat_notifications')
    session = db.relationship('ChatSession', backref='notifications')
    
    def get_time_ago(self):
        """Get human-readable time ago"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        if diff.days > 0:
            return f"{diff.days}d"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m"
        else:
            return "now"

    def __repr__(self):
        return f'<ChatNotification {self.title} for {self.user.username}>'

class OAuth(OAuthConsumerMixin, db.Model):
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship("User")


class CannedResponse(db.Model):
    """Predefined responses for common inquiries"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # e.g., 'shipping', 'returns', 'general'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category': self.category
        }

class ChatAnalytics(db.Model):
    """Business metrics tracking for chat support"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    total_chats = db.Column(db.Integer, default=0)
    chats_resolved = db.Column(db.Integer, default=0)
    chats_transferred = db.Column(db.Integer, default=0)
    total_messages = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Integer)  # in seconds
    avg_resolution_time = db.Column(db.Integer)  # in seconds
    customer_satisfaction = db.Column(db.Float)  # 0-5 rating
    conversion_chats_to_sales = db.Column(db.Integer, default=0)
    total_sales_from_chat = db.Column(db.Numeric(10, 2), default=0)
    
    def get_conversion_rate(self):
        """Calculate conversion rate from chats to sales"""
        if self.total_chats > 0:
            return round((self.conversion_chats_to_sales / self.total_chats) * 100, 2)
        return 0