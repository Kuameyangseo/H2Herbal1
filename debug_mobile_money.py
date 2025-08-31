from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.main.payment import PaystackPayment
import time

app = create_app()
with app.app_context():
    p = PaystackPayment()
    
    class DummyOrder:
        def __init__(self, order_id):
            self.id = order_id
            self.order_number = f'TEST-{order_id}-{int(time.time())}'
            self.total_amount = 100.00
            self.shipping_email = 'test@example.com'
            self.shipping_first_name = 'Test'
            self.shipping_last_name = 'User'
            self.shipping_phone = '0241234567'
    
    print("=== Debugging Mobile Money Payment ===\n")
    
    # Test 1: Standard payment (should work)
    print("1. Testing standard payment...")
    order1 = DummyOrder(2001)
    result1 = p.initialize_payment(order1)
    print(f"Standard payment: {'SUCCESS' if result1['success'] else 'FAILED'}")
    if not result1['success']:
        print(f"Error: {result1['message']}")
    
    # Test 2: Mobile money with different payload structure
    print("\n2. Testing mobile money with standard payload...")
    order2 = DummyOrder(2002)
    
    # Try mobile money as a channel instead of separate mobile_money object
    import requests
    import json
    
    payload = {
        'email': order2.shipping_email,
        'amount': int(float(order2.total_amount) * 100),
        'currency': 'GHS',
        'reference': f'momo_test_{order2.id}_{int(time.time())}',
        'channels': ['mobile_money'],
        'callback_url': 'http://127.0.0.1:5000/payment_callback',
        'metadata': {
            'order_id': order2.id,
            'order_number': order2.order_number,
            'payment_method': 'mobile_money'
        }
    }
    
    try:
        response = requests.post(
            f'{p.base_url}/transaction/initialize',
            headers=p.headers,
            data=json.dumps(payload),
            timeout=30
        )
        
        print(f"HTTP Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            if result.get('status'):
                print("SUCCESS: Mobile money with channels approach works!")
                print(f"Authorization URL: {result['data']['authorization_url']}")
            else:
                print(f"FAILED: {result.get('message')}")
        else:
            print(f"FAILED: HTTP {response.status_code}: {response.text[:200]}")
            
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("\n=== Debug Complete ===")