from app import create_app, db
from app.models import CannedResponse

# Create the Flask app
app = create_app()

# Push an application context to make the database available
with app.app_context():
    print(f"CannedResponse table: {CannedResponse.query.count()} records")