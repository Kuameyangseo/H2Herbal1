from app import create_app, db
from app.models import CannedResponse
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Create the Flask app
app = create_app()

print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

# Push an application context to make the database available
with app.app_context():
    # Check if we can execute a simple query
    try:
        result = db.session.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='canned_response';"))
        table_exists = result.fetchone()
        print(f"canned_response table exists in database: {table_exists is not None}")
    except Exception as e:
        print(f"Error checking table existence: {e}")
    
    # Check if we can query the model
    try:
        count = CannedResponse.query.count()
        print(f"CannedResponse model working: {count} records found")
    except Exception as e:
        print(f"Error querying CannedResponse model: {e}")
        import traceback
        traceback.print_exc()