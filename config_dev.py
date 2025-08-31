"""
Development Configuration for H2Herbal
This file allows you to easily configure SSL/HTTPS settings for development
"""

# SSL/HTTPS Configuration
# Set to True to enable HTTPS with self-signed certificates (will show browser warnings)
# Set to False to use HTTP only (no warnings, cleaner development experience)
ENABLE_SSL = False

# Force HTTPS redirects (only applies when ENABLE_SSL is True)
FORCE_HTTPS = True

# Development settings
FLASK_ENV = 'development'
DEBUG = True

# Database
SQLALCHEMY_DATABASE_URI = 'sqlite:///h2herbal.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Secret key for sessions (change this in production!)
SECRET_KEY = 'dev-secret-key-change-in-production'

# Chat settings
CHAT_ENABLED = True
SOCKETIO_ASYNC_MODE = 'threading'

print("Development Configuration Loaded")
print(f"   SSL/HTTPS: {'Enabled' if ENABLE_SSL else 'Disabled (HTTP only)'}")
print(f"   Debug Mode: {DEBUG}")
print(f"   Chat System: {'Enabled' if CHAT_ENABLED else 'Disabled'}")