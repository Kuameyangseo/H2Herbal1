import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from decimal import ROUND_HALF_UP
import decimal

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()
socketio = SocketIO()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    # Ensure DEBUG is off by default in production unless explicitly enabled
    app.config['DEBUG'] = str(os.environ.get('FLASK_DEBUG', '0')).lower() in ['1', 'true', 'on']
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///h2herbal.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Google OAuth Configuration
    app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Mail Configuration
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT') or 587)
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Paystack Configuration
    app.config['PAYSTACK_SECRET_KEY'] = os.environ.get('PAYSTACK_SECRET_KEY')
    app.config['PAYSTACK_PUBLIC_KEY'] = os.environ.get('PAYSTACK_PUBLIC_KEY')
    app.config['BASE_URL'] = os.environ.get('BASE_URL') or 'https://localhost:5000'
    
    # Upload Configuration
    app.config['UPLOAD_FOLDER'] = 'app/static/uploads'
    # Allow overriding the maximum upload size via environment (value in MB)
    try:
        max_mb = int(os.environ.get('MAX_CONTENT_LENGTH_MB', '16'))
    except Exception:
        max_mb = 16
    app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024  # default 16MB max file size
    
    # SMS Configuration (Twilio)
    app.config['TWILIO_ACCOUNT_SID'] = os.environ.get('TWILIO_ACCOUNT_SID')
    app.config['TWILIO_AUTH_TOKEN'] = os.environ.get('TWILIO_AUTH_TOKEN')
    app.config['TWILIO_PHONE_NUMBER'] = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # Set decimal context for proper rounding
    decimal.getcontext().rounding = ROUND_HALF_UP
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    # Configure SocketIO async mode and optional message queue for production scaling.
    # Prefer eventlet -> gevent -> threading. If REDIS_URL is set, use it as message_queue.
    message_queue = os.environ.get('REDIS_URL')
    async_mode = None
    try:
        # Prefer eventlet when installed (best for SocketIO)
        import eventlet  # type: ignore
        async_mode = 'eventlet'
    except Exception:
        try:
            import gevent  # type: ignore
            async_mode = 'gevent'
        except Exception:
            async_mode = 'threading'

    # Initialize SocketIO with detected async mode and optional message queue.
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode=async_mode,
        message_queue=message_queue,
        transports=['polling', 'websocket'],
        engineio_logger=False,
        socketio_logger=False,
    )

    app.logger.info(f"SocketIO async_mode={async_mode} message_queue={'set' if message_queue else 'none'}")
    csrf.init_app(app)
    
    # Make CSRF token available in templates
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    
    # Login manager configuration
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import models to ensure they are registered with SQLAlchemy
    from app import models
    from app.chat import models as chat_models
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.chat import bp as messenger_bp
    app.register_blueprint(messenger_bp, url_prefix='/messenger')
    
    # Google OAuth is now handled directly in auth routes
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(app.instance_path, '..', app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_dir, exist_ok=True)

    # Error handler for requests that exceed MAX_CONTENT_LENGTH
    try:
        from werkzeug.exceptions import RequestEntityTooLarge

        @app.errorhandler(RequestEntityTooLarge)
        def handle_request_entity_too_large(error):
            # Return a concise, non-crashing response for oversized requests
            return ("Request body too large. Max allowed size is %d MB." % max_mb, 413)
    except Exception:
        # If werkzeug API differs, skip registering the handler; it's non-fatal
        pass

    # Handle oversized request bodies gracefully
    try:
        from werkzeug.exceptions import RequestEntityTooLarge

        @app.errorhandler(RequestEntityTooLarge)
        def handle_request_entity_too_large(error):
            app.logger.warning('RequestEntityTooLarge: client tried to send too large a payload')
            return ("Request payload too large. Maximum allowed is %d bytes." % app.config.get('MAX_CONTENT_LENGTH', 0)), 413
    except Exception:
        # If werkzeug doesn't expose RequestEntityTooLarge (very old Werkzeug), skip handler
        pass

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))
