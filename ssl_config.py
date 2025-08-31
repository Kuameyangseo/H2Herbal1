"""
SSL/HTTPS Configuration for Flask Application
This module provides SSL certificate generation and HTTPS configuration
"""

import os
import ssl
import subprocess
import ipaddress
from pathlib import Path
from flask import Flask

class SSLConfig:
    """SSL Configuration Manager"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.ssl_dir = Path('ssl_certificates')
        self.cert_file = self.ssl_dir / 'cert.pem'
        self.key_file = self.ssl_dir / 'key.pem'
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize SSL configuration with Flask app"""
        self.app = app
        
        # Create SSL directory if it doesn't exist
        self.ssl_dir.mkdir(exist_ok=True)
        
        # Generate SSL certificates if they don't exist
        if not self.certificates_exist():
            self.generate_self_signed_certificate()
        
        # Configure Flask for HTTPS
        self.configure_flask_ssl()
    
    def certificates_exist(self) -> bool:
        """Check if SSL certificates exist"""
        return self.cert_file.exists() and self.key_file.exists()
    
    def generate_self_signed_certificate(self):
        """Generate self-signed SSL certificate for development"""
        try:
            # Use OpenSSL to generate certificate
            cmd = [
                'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
                '-keyout', str(self.key_file),
                '-out', str(self.cert_file),
                '-days', '365', '-nodes',
                '-subj', '/C=GH/ST=Greater Accra/L=Accra/O=H2Herbal/OU=IT/CN=localhost'
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"SSL certificates generated successfully!")
            print(f"   Certificate: {self.cert_file}")
            print(f"   Private Key: {self.key_file}")
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate SSL certificate using OpenSSL: {e}")
            self._generate_python_certificate()
        except FileNotFoundError:
            print("OpenSSL not found. Generating certificate using Python...")
            self._generate_python_certificate()
    
    def _generate_python_certificate(self):
        """Generate SSL certificate using Python cryptography library"""
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Create certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "GH"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Greater Accra"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Accra"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "H2Herbal"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # Write private key
            with open(self.key_file, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            # Write certificate
            with open(self.cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            print(f"SSL certificates generated using Python cryptography!")
            print(f"   Certificate: {self.cert_file}")
            print(f"   Private Key: {self.key_file}")
            
        except ImportError:
            print("cryptography library not installed. Installing...")
            subprocess.run(['pip', 'install', 'cryptography'], check=True)
            self._generate_python_certificate()
        except Exception as e:
            print(f"Failed to generate SSL certificate: {e}")
            raise
    
    def configure_flask_ssl(self):
        """Configure Flask app for SSL"""
        if self.app:
            # Set secure cookie settings
            self.app.config.update(
                SESSION_COOKIE_SECURE=True,
                SESSION_COOKIE_HTTPONLY=True,
                SESSION_COOKIE_SAMESITE='Lax',
                PERMANENT_SESSION_LIFETIME=1800,  # 30 minutes
            )
    
    def get_ssl_context(self):
        """Get SSL context for Flask app"""
        if self.certificates_exist():
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.load_cert_chain(str(self.cert_file), str(self.key_file))
            return context
        return None
    
    def force_https_redirect(self):
        """Decorator to force HTTPS redirects"""
        def decorator(f):
            def wrapper(*args, **kwargs):
                from flask import request, redirect, url_for
                
                if not request.is_secure and self.app.config.get('FORCE_HTTPS', False):
                    return redirect(request.url.replace('http://', 'https://'))
                return f(*args, **kwargs)
            return wrapper
        return decorator

def setup_https_redirect(app: Flask):
    """Setup automatic HTTP to HTTPS redirect"""
    @app.before_request
    def force_https():
        from flask import request, redirect, url_for
        
        # Skip redirect for local development if not explicitly forced
        if request.endpoint == 'static':
            return
            
        if not request.is_secure and app.config.get('FORCE_HTTPS', False):
            # Redirect HTTP to HTTPS
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

def create_ssl_app(app: Flask, force_https: bool = True, enable_ssl: bool = None) -> tuple:
    """
    Configure Flask app for SSL/HTTPS
    Returns: (app, ssl_context)
    
    Args:
        app: Flask application instance
        force_https: Whether to force HTTPS redirects
        enable_ssl: Whether to enable SSL (None = auto-detect based on environment)
    """
    # Auto-detect SSL preference based on environment
    if enable_ssl is None:
        # Disable SSL in development by default to avoid certificate warnings
        enable_ssl = app.config.get('FLASK_ENV') != 'development'
    
    ssl_context = None
    
    if enable_ssl:
        ssl_config = SSLConfig(app)
        
        # Configure HTTPS redirect
        if force_https:
            app.config['FORCE_HTTPS'] = True
            setup_https_redirect(app)
        
        # Get SSL context
        ssl_context = ssl_config.get_ssl_context()
        
        print("HTTPS enabled with SSL certificates")
        print("You may see a security warning for self-signed certificate")
        print("   Click 'Advanced' and 'Proceed to localhost' to continue")
    else:
        print("Running in HTTP mode (development)")
        print("To enable HTTPS, set FLASK_ENV=production or enable_ssl=True")
    
    return app, ssl_context

if __name__ == '__main__':
    # Test SSL certificate generation
    ssl_config = SSLConfig()
    if not ssl_config.certificates_exist():
        ssl_config.generate_self_signed_certificate()
    else:
        print("SSL certificates already exist!")