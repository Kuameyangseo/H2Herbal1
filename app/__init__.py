import os
# Note: eventlet/gevent monkey-patching must be applied inside worker processes
# (see `gunicorn_config.post_worker_init`) to avoid patching the Gunicorn
# master/arbiter. Do NOT monkey-patch here at module import time.

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from decimal import ROUND_HALF_UP
import decimal
try:
    from flask_compress import Compress
    _have_compress = True
except Exception:
    _have_compress = False

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
    # Production-ready engine options for non-SQLite databases (tweak via env vars)
    if app.config['SQLALCHEMY_DATABASE_URI'] and not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:'):
        app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {})
        engine_opts = app.config['SQLALCHEMY_ENGINE_OPTIONS']
        engine_opts.setdefault('pool_pre_ping', True)
        engine_opts.setdefault('pool_size', int(os.environ.get('DB_POOL_SIZE', '5')))
        engine_opts.setdefault('max_overflow', int(os.environ.get('DB_MAX_OVERFLOW', '10')))
    
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
    # Optional response compression to reduce response sizes and improve client latency
    if _have_compress:
        Compress().init_app(app)
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
    # Slightly larger ping values reduce false-positive "Invalid session" events
    # when reverse proxies or mobile clients introduce latency.
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode=async_mode,
        message_queue=message_queue,
        transports=['polling', 'websocket'],
        # Enable engineio logging (INFO) to capture invalid session traces when debugging.
        engineio_logger=True,
        socketio_logger=False,
        # These settings help keep the Engine.IO session alive during longer page loads or
        # when reverse proxies introduce latency. Values are in seconds.
        ping_interval=int(os.environ.get('SOCKETIO_PING_INTERVAL', '25')),
        ping_timeout=int(os.environ.get('SOCKETIO_PING_TIMEOUT', '90')),
    )

    app.logger.info(f"SocketIO async_mode={async_mode} message_queue={'set' if message_queue else 'none'}")
    # Warn if multiple workers are configured without a message queue.
    try:
        workers = int(os.environ.get('GUNICORN_WORKERS', os.environ.get('WEB_CONCURRENCY', '1')))
    except Exception:
        workers = 1
    if workers > 1 and not message_queue:
        app.logger.warning(
            'Multiple Gunicorn workers configured (workers=%d) but REDIS_URL is not set. '
            'Socket.IO sessions will not be shared between workers and you will see "Invalid session" errors. '
            'Set REDIS_URL to a Redis instance and restart, or run with a single worker.' % workers
        )
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

    # Import chat socket event handlers so they are registered with SocketIO
    try:
        from app.chat import events  # noqa: F401
    except Exception:
        app.logger.exception('Failed to import chat socket event handlers')
    
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
