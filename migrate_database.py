import os
from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Category, Product, ProductImage, Order, OrderItem, Review, Newsletter, CartItem, MessageHistory, ChatSession, ChatMessage, ChatNotification, CannedResponse, ChatAnalytics
import sqlite3

# Load environment variables
load_dotenv()

# Create the Flask app
app = create_app()

# Push an application context to make the database available
with app.app_context():
    # Print the database URI to verify it's correct
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Get the database path
    db_path = os.path.join('instance', 'ecommerce.db')
    print(f"Database path: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Add new columns to chat_session table if they don't exist
    try:
        cursor.execute("ALTER TABLE chat_session ADD COLUMN assigned_at DATETIME")
        print("Added assigned_at column to chat_session")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("assigned_at column already exists in chat_session")
        else:
            print(f"Error adding assigned_at column: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_session ADD COLUMN first_response_at DATETIME")
        print("Added first_response_at column to chat_session")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("first_response_at column already exists in chat_session")
        else:
            print(f"Error adding first_response_at column: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_session ADD COLUMN resolved_at DATETIME")
        print("Added resolved_at column to chat_session")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("resolved_at column already exists in chat_session")
        else:
            print(f"Error adding resolved_at column: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_session ADD COLUMN satisfaction_rating INTEGER")
        print("Added satisfaction_rating column to chat_session")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("satisfaction_rating column already exists in chat_session")
        else:
            print(f"Error adding satisfaction_rating column: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_session ADD COLUMN satisfaction_feedback TEXT")
        print("Added satisfaction_feedback column to chat_session")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("satisfaction_feedback column already exists in chat_session")
        else:
            print(f"Error adding satisfaction_feedback column: {e}")
    
    # Add new columns to chat_message table if they don't exist
    try:
        cursor.execute("ALTER TABLE chat_message ADD COLUMN is_edited BOOLEAN")
        print("Added is_edited column to chat_message")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("is_edited column already exists in chat_message")
        else:
            print(f"Error adding is_edited column: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_message ADD COLUMN edited_at DATETIME")
        print("Added edited_at column to chat_message")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("edited_at column already exists in chat_message")
        else:
            print(f"Error adding edited_at column: {e}")
    
    try:
        cursor.execute("ALTER TABLE chat_message ADD COLUMN reply_to_id INTEGER")
        print("Added reply_to_id column to chat_message")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("reply_to_id column already exists in chat_message")
        else:
            print(f"Error adding reply_to_id column: {e}")
    
    # Update the attachment_url column in chat_message to allow longer URLs
    try:
        cursor.execute("ALTER TABLE chat_message ADD COLUMN attachment_url_temp TEXT")
        cursor.execute("UPDATE chat_message SET attachment_url_temp = attachment_url")
        cursor.execute("ALTER TABLE chat_message DROP COLUMN attachment_url")
        cursor.execute("ALTER TABLE chat_message ADD COLUMN attachment_url TEXT")
        cursor.execute("UPDATE chat_message SET attachment_url = attachment_url_temp")
        cursor.execute("ALTER TABLE chat_message DROP COLUMN attachment_url_temp")
        print("Updated attachment_url column in chat_message")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e) or "no such column" in str(e):
            print("attachment_url column already updated in chat_message")
        else:
            print(f"Error updating attachment_url column: {e}")
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("\nDatabase migration complete!")