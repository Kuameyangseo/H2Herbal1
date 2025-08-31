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
    
    # Check if all tables exist
    print("\nChecking database tables...")
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    
    expected_tables = [
        'user', 'category', 'product', 'product_image', 'order', 'order_item', 
        'review', 'newsletter', 'cart_item', 'message_history', 'chat_session', 
        'chat_message', 'chat_notification', 'canned_response', 'chat_analytics',
        'flask_dance_oauth'
    ]
    
    print("Tables found:")
    for table in sorted(tables):
        print(f"  - {table}")
    
    print("\nExpected tables:")
    for table in sorted(expected_tables):
        status = "OK" if table in tables else "MISSING"
        print(f"  {status} {table}")
    
    # Check if we can query the models
    print("\nTesting model queries...")
    
    # Test Product model
    try:
        product_count = Product.query.count()
        print(f"OK Product model working: {product_count} products found")
    except Exception as e:
        print(f"ERROR Product model error: {e}")
    
    # Test CannedResponse model
    try:
        canned_count = CannedResponse.query.count()
        print(f"OK CannedResponse model working: {canned_count} canned responses found")
    except Exception as e:
        print(f"ERROR CannedResponse model error: {e}")
    
    # Test ChatSession model
    try:
        session_count = ChatSession.query.count()
        print(f"OK ChatSession model working: {session_count} sessions found")
    except Exception as e:
        print(f"ERROR ChatSession model error: {e}")
    
    print("\nSetup verification complete!")