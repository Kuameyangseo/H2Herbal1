from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.main.payment import PaystackPayment
import time
import requests
import json

def debug_mobile_money_error():
    """Debug the mobile money payment 401 error"""
    
    app = create_app()
    
    print("=== Mobile Money Payment Debug ===\n")
    
    with app.app_context():
        # Check configuration
        print("1. Configuration Check:")
        secret_key = app.config.get('PAYSTACK_SECRET_KEY')
        public_key = app.config.get('PAYSTACK_PUBLIC_KEY')
        base_url = app.config.get('BASE_URL')
        
        print(f"   Secret Key: {'Found' if secret_key else 'Missing'}")
        print(f"   Public Key: {'Found' if public_key else 'Missing'}")
        print(f"   Base URL: {base_url}")
        
        if not secret_key:
            print("   ERROR: No secret key found!")
            return
        
        # Initialize payment class
        print("\n2. Payment Class Test:")
        try:
            payment = PaystackPayment()
            print(f"   Payment class initialized successfully")
            print(f"   Secret key loaded: {payment.secret_key[:15]}...")
        except Exception as e:
            print(f"   ERROR initializing payment class: {e}")
            return
        
        # Create test order
        class TestOrder:
            def __init__(self):
                self.id = 8888
                self.order_number = f'DEBUG-{int(time.time())}'
                self.total_amount = 25.00
                self.shipping_email = 'debug@example.com'
                self.shipping_first_name = 'Debug'
                self.shipping_last_name = 'User'
                self.shipping_phone = '0202114315'
        
        order = TestOrder()
        
        # Test standard payment first
        print(f"\n3. Standard Payment Test:")
        try:
            result = payment.initialize_payment(order)
            if result['success']:
                print("   SUCCESS: Standard payment works")
            else:
                print(f"   FAILED: {result['message']}")
                if '401' in result['message']:
                    print("   This is the 401 error! Key issue confirmed.")
                    return
        except Exception as e:
            print(f"   EXCEPTION: {e}")
        
        # Test mobile money payment
        print(f"\n4. Mobile Money Payment Test:")
        try:
            result = payment.initialize_mobile_money_payment(order, '0202114315', 'vodafone')
            if result['success']:
                print("   SUCCESS: Mobile money payment works")
                print(f"   URL: {result['authorization_url'][:50]}...")
            else:
                print(f"   FAILED: {result['message']}")
                if '401' in result['message']:
                    print("   Found the 401 error in mobile money!")
                    
                    # Let's test the exact API call
                    print(f"\n5. Direct API Test:")
                    test_direct_call(payment, order)
        except Exception as e:
            print(f"   EXCEPTION: {e}")

def test_direct_call(payment, order):
    """Test the exact API call that's failing"""
    
    # This is the exact payload from the mobile money method
    payload = {
        'email': order.shipping_email,
        'amount': int(float(order.total_amount) * 100),
        'currency': 'GHS',
        'reference': f'momo_{order.id}_{order.order_number}',
        'channels': ['mobile_money'],
        'callback_url': f'http://127.0.0.1:5000/payment_callback',
        'metadata': {
            'order_id': order.id,
            'order_number': order.order_number,
            'customer_name': f'{order.shipping_first_name} {order.shipping_last_name}',
            'payment_method': 'mobile_money',
            'network': 'vodafone',
            'phone_number': '0202114315'
        }
    }
    
    print(f"   Testing exact payload...")
    print(f"   URL: {payment.base_url}/transaction/initialize")
    print(f"   Headers: Authorization: Bearer {payment.secret_key[:15]}...")
    
    try:
        response = requests.post(
            f'{payment.base_url}/transaction/initialize',
            headers=payment.headers,
            data=json.dumps(payload),
            timeout=30
        )
        
        print(f"   HTTP Status: {response.status_code}")
        
        if response.status_code == 401:
            print("   FOUND THE 401 ERROR!")
            print(f"   Response: {response.text}")
            
            # Check the authorization header
            auth_header = payment.headers.get('Authorization')
            print(f"   Auth Header: {auth_header}")
            
            # Test if the key works with a simpler endpoint
            print(f"\n   Testing key with bank endpoint...")
            bank_response = requests.get(
                f'{payment.base_url}/bank',
                headers={'Authorization': f'Bearer {payment.secret_key}'},
                timeout=10
            )
            print(f"   Bank endpoint status: {bank_response.status_code}")
            
        elif response.status_code == 200:
            print("   SUCCESS: Direct API call works")
            result = response.json()
            if result.get('status'):
                print(f"   Auth URL: {result['data']['authorization_url'][:50]}...")
            else:
                print(f"   API Error: {result.get('message')}")
        else:
            print(f"   Unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"   Exception in direct call: {e}")

def provide_fix():
    """Provide the fix for the issue"""
    
    print(f"\n=== SOLUTION ===")
    print("Based on the tests, here's what to do:")
    print()
    print("1. If the API key is invalid:")
    print("   - Log into your Paystack dashboard")
    print("   - Go to Settings > API Keys & Webhooks")
    print("   - Generate new API keys")
    print("   - Update your .env file with the new keys")
    print()
    print("2. If it's a rate limiting issue:")
    print("   - The payment.py already has delays built in")
    print("   - Consider implementing exponential backoff")
    print()
    print("3. If it's intermittent:")
    print("   - Add better error handling and retry logic")
    print("   - Log the exact error responses for debugging")
    print()
    print("4. Immediate fix - Enhanced error handling:")
    print("   - I'll update the payment.py with better error handling")

if __name__ == "__main__":
    debug_mobile_money_error()
    provide_fix()
    print("\n=== Debug Complete ===")