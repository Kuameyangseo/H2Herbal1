import os
from dotenv import load_dotenv
from app import create_app, db, socketio
from app.models import User, Category, Product, ProductImage, Order, OrderItem, Review, Newsletter, CartItem, MessageHistory, ChatSession, ChatMessage, ChatNotification
from ssl_config import create_ssl_app

# Load environment variables
load_dotenv()

# Load development configuration
try:
    from config_dev import ENABLE_SSL, FORCE_HTTPS
    print("Using config_dev.py settings")
except ImportError:
    # Fallback to default settings
    ENABLE_SSL = False
    FORCE_HTTPS = True
    print("Using default settings (config_dev.py not found)")

app = create_app()

# Configure SSL/HTTPS based on configuration
app, ssl_context = create_ssl_app(app, force_https=FORCE_HTTPS, enable_ssl=ENABLE_SSL)

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Category': Category,
        'Product': Product,
        'ProductImage': ProductImage,
        'Order': Order,
        'OrderItem': OrderItem,
        'Review': Review,
        'Newsletter': Newsletter,
        'CartItem': CartItem,
        'MessageHistory': MessageHistory,
        'ChatSession': ChatSession,
        'ChatMessage': ChatMessage,
        'ChatNotification': ChatNotification
    }

@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print('Database initialized.')

@app.cli.command()
def create_admin():
    """Create an admin user."""
    from werkzeug.security import generate_password_hash
    
    admin = User(
        username='admin',
        email='admin@h2herbal.com',
        first_name='Admin',
        last_name='User',
        is_admin=True,
        is_active=True
    )
    admin.set_password('admin123')
    
    db.session.add(admin)
    db.session.commit()
    print('Admin user created: admin@h2herbal.com / admin123')

@app.cli.command()
def seed_data():
    """Seed the database with sample data."""
    # Create categories
    categories = [
        Category(name='Herbal Supplements', description='Natural herbal supplements for health and wellness', is_active=True),
        Category(name='Essential Oils', description='Pure essential oils for aromatherapy and wellness', is_active=True),
        Category(name='Organic Teas', description='Premium organic herbal teas', is_active=True),
        Category(name='Natural Skincare', description='Natural and organic skincare products', is_active=True),
        Category(name='Vitamins & Minerals', description='Essential vitamins and mineral supplements', is_active=True),
    ]
    
    for category in categories:
        db.session.add(category)
    
    db.session.commit()
    
    # Create sample products
    products = [
        Product(
            name='Turmeric Curcumin Capsules',
            description='High-potency turmeric curcumin supplement with black pepper extract for enhanced absorption. Supports joint health and reduces inflammation.',
            price=1.99,
            compare_price=2.99,
            cost_price=1.00,
            sku='TUR-001',
            stock_quantity=100,
            min_stock_level=10,
            weight=0.2,
            dimensions='10x5x5 cm',
            category_id=1,
            is_active=True,
            is_featured=True,
            meta_title='Turmeric Curcumin Capsules - Natural Anti-inflammatory',
            meta_description='Premium turmeric curcumin supplement for joint health and inflammation support.'
        ),
        Product(
            name='Lavender Essential Oil',
            description='Pure lavender essential oil perfect for relaxation, aromatherapy, and promoting better sleep. 100% natural and therapeutic grade.',
            price=1.99,
            compare_price=2.99,
            cost_price=1.00,
            sku='LAV-001',
            stock_quantity=75,
            min_stock_level=5,
            weight=0.1,
            dimensions='8x3x3 cm',
            category_id=2,
            is_active=True,
            is_featured=True,
            meta_title='Pure Lavender Essential Oil - Therapeutic Grade',
            meta_description='Premium lavender essential oil for relaxation and aromatherapy.'
        ),
        Product(
            name='Chamomile Sleep Tea',
            description='Organic chamomile tea blend designed to promote relaxation and better sleep. Caffeine-free and naturally soothing.',
            price=18.99,
            compare_price=24.99,
            cost_price=8.00,
            sku='CHA-001',
            stock_quantity=150,
            min_stock_level=15,
            weight=0.15,
            dimensions='12x8x4 cm',
            category_id=3,
            is_active=True,
            is_featured=True,
            meta_title='Organic Chamomile Sleep Tea - Natural Relaxation',
            meta_description='Premium organic chamomile tea for better sleep and relaxation.'
        ),
        Product(
            name='Aloe Vera Face Cream',
            description='Natural aloe vera face cream with organic ingredients. Moisturizes and soothes sensitive skin while providing anti-aging benefits.',
            price=34.99,
            compare_price=44.99,
            cost_price=18.00,
            sku='ALO-001',
            stock_quantity=80,
            min_stock_level=8,
            weight=0.25,
            dimensions='8x8x6 cm',
            category_id=4,
            is_active=True,
            is_featured=False,
            meta_title='Natural Aloe Vera Face Cream - Organic Skincare',
            meta_description='Premium aloe vera face cream for sensitive skin care.'
        ),
        Product(
            name='Vitamin D3 + K2 Capsules',
            description='High-potency Vitamin D3 with K2 for optimal calcium absorption and bone health. Supports immune system and overall wellness.',
            price=39.99,
            compare_price=49.99,
            cost_price=20.00,
            sku='VIT-001',
            stock_quantity=120,
            min_stock_level=12,
            weight=0.18,
            dimensions='9x4x4 cm',
            category_id=5,
            is_active=True,
            is_featured=True,
            meta_title='Vitamin D3 + K2 Capsules - Bone Health Support',
            meta_description='Premium Vitamin D3 and K2 supplement for bone and immune health.'
        ),
    ]
    
    for product in products:
        db.session.add(product)
    
    db.session.commit()
    print('Sample data seeded successfully!')

if __name__ == '__main__':
    # Run the application with SocketIO
    if ssl_context:
        print("Starting H2Herbal with HTTPS/SSL security and real-time chat...")
        print("Access your application at: https://localhost:5000")
        print("Real-time chat system enabled")
        print("You may see a security warning for self-signed certificate - click 'Advanced' and 'Proceed to localhost'")
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, ssl_context=ssl_context)
    else:
        print("Starting H2Herbal with HTTP and real-time chat...")
        print("Access your application at: http://localhost:5000")
        print("Real-time chat system enabled")
        print("No certificate warnings - clean development experience!")
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)