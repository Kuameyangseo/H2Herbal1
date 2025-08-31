import os
from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Category, Product, ProductImage, Order, OrderItem, Review, Newsletter, CartItem, MessageHistory, ChatSession, ChatMessage, ChatNotification, CannedResponse, ChatAnalytics

# Load environment variables
load_dotenv()

# Create the Flask app
app = create_app()

# Push an application context to make the database available
with app.app_context():
    # Print the database URI to verify it's correct
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Create all tables
    db.create_all()
    print('Database tables created successfully!')
    
    # Add some default canned responses if they don't exist
    if CannedResponse.query.count() == 0:
        default_responses = [
            CannedResponse(
                title="Welcome",
                content="Hello! Welcome to our support chat. How can I help you today?",
                category="greeting"
            ),
            CannedResponse(
                title="Business Hours",
                content="Our business hours are Monday to Friday, 9:00 AM to 5:00 PM EST.",
                category="general"
            ),
            CannedResponse(
                title="Shipping Information",
                content="We offer free shipping on orders over $50. Standard shipping takes 3-5 business days.",
                category="shipping"
            ),
            CannedResponse(
                title="Return Policy",
                content="We offer a 30-day return policy on all products. Items must be in original condition with tags attached.",
                category="returns"
            )
        ]
        
        for response in default_responses:
            db.session.add(response)
        
        db.session.commit()
        print('Default canned responses added!')