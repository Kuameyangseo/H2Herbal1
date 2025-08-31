from dotenv import load_dotenv
from app import create_app, db
from app.models import Product, CannedResponse, ChatSession

# Load environment variables
load_dotenv()

# Create the Flask app
app = create_app()

# Push an application context to make the database available
with app.app_context():
    print(f"Product table: {Product.query.count()} records")
    print(f"CannedResponse table: {CannedResponse.query.count()} records")
    print(f"ChatSession table: {ChatSession.query.count()} records")
    print("All models are working correctly!")