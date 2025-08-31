#!/usr/bin/env python3
"""
Script to create an admin user for the H2Herbal application
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

def create_admin_user():
    """Create an admin user"""
    app = create_app()
    
    with app.app_context():
        # Check if admin user already exists
        existing_admin = User.query.filter_by(email='iamyangseo@gmail.com').first()
        if existing_admin:
            print("Admin user already exists!")
            print(f"Email: iamyangseo@gmail.com")
            print("Updating password to: Login@12")
            existing_admin.set_password('Login@12')
            existing_admin.is_admin = True
            existing_admin.is_active = True
            db.session.commit()
            print("Admin user updated successfully!")
            return
        
        # Create new admin user
        admin = User(
            username='Kuame',
            email='adminherbal@gmail.com',
            first_name='Admin',
            last_name='herbal',
            is_admin=True,
            is_active=True
        )
        admin.set_password('Login@12')
        
        try:
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Login credentials:")
            print("Email: admin@h2herbal.com")
            print("Password: admin123")
            print("\nYou can now log in to access admin features.")
        except Exception as e:
            print(f"Error creating admin user: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_admin_user()