from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.main.payment import PaystackPayment
import time
import requests
import json

def test_payment_scenarios():
    """Test various payment scenarios to identify the 401 error"""
    
    app = create_app()
    
    print("=== Debugging Mobile Money Payment Error ===\n")
    
    with app.app_context():
        # Test 1: Check configuration
        print("1. Configuration Check:")
        print(f"   PAYSTACK_SECRET_KEY: {'✓ Found' if app.config.get('PAYSTACK_SECRET_KEY') else '✗ Missing'}")
        print(f"   PAYSTACK_PUBLIC_KEY: {'✓ Found' if app.config.get('PAYSTACK_PUBLIC_KEY') else '✗ Missing'}")
        print(f"   BASE_URL: {app.config.get('BASE_URL', 'Not set')}")
        
        # Test 2: Initialize payment class
        print("\n2. Payment Class Initialization:")
        try:
            payment = PaystackPayment()
            print(f"   Secret Key: {'✓ Loaded' if payment.secret_key else '✗ Not loaded'}")
            print(f"   Public Key: {'✓ Loaded' if payment.public_key else '✗ Not loaded'}")
            print(f"   Headers: {'✓ Set' if payment.headers.get('Authorization') else '✗ Not set'}")
        except Exception as e:
            print(f"   ✗ Error initializing PaystackPayment: {e}")
            return
        
        # Test 3: Create dummy order
        class TestOrder:
            def __init__(self):
                self.id = 9999
                self.order_number = f'DEBUG-{int(time.time())}'
                self.total_amount = 50.00
                self.shipping_email = 'debug@test.com'
                self.shipping_first_name = 'Debug'
                self.shipping_last_name = 'Test'
                self.shipping_phone = '0202114315'
        
        order = TestOrder()
        
        # Test 4: Standard payment (should work)
        print(f"\n3. Standard Payment Test:")
        try:
            result = payment.initialize_payment(order)
            if result['success']:
                print("   ✓ Standard payment initialization successful")
            else:
                print(f"   ✗ Standard payment failed: {result['message']}")
        except Exception as e:
            print(f"   ✗ Exception in standard payment: {e}")
        
        # Test 5: Mobile money payment (the problematic one)
        print(f"\n4. Mobile Money Payment Test:")
        try:
            result = payment.initialize_mobile_money_payment(order, '0202114315', 'vodafone')
            if result['success']:
                print("   ✓ Mobile money payment initialization successful")
                print(f"   Authorization URL: {result['authorization_url'][:50]}...")
            else:
                print(f"   ✗ Mobile money payment failed: {result['message']}")
                
                # If it fails, let's try direct API call to see the exact error
                print(f"\n5. Direct API Call Test:")
                test_direct_api_call(payment, order)
                
        except Exception as e:
            print(f"   ✗ Exception in mobile money payment: {e}")
        
        # Test 6: Multiple rapid calls (rate limiting test)
        print(f"\n6. Rate Limiting Test:")
        test_rate_limiting(payment, order)

def test_direct_api_call(payment, order):
    """Test direct API call to see exact error response"""
    
    payload = {
        'email': order.shipping_email,
        'amount': int(float(order.total_amount) * 100),
        'currency': 'GHS',
        'reference': f'direct_test_{int(time.time())}',
        'channels': ['mobile_money'],
        'callback_url': 'http://127.0.0.1:5000/payment_callback',
        'metadata': {
            'order_id': order.id,
            'payment_method': 'mobile_money',
            'network': 'vodafone',
            'phone_number': '0202114315'
        }
    }
    
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers=payment.headers,
            data=json.dumps(payload),
            timeout=30
        )
        
        print(f"   HTTP Status: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        
        if response.status_code == 401:
            print("   ✗ 401 Unauthorized - This is the error!")
            print(f"   Full Response: {response.text}")
            
            # Check if it's a key format issue
            auth_header = payment.headers.get('Authorization', '')
            print(f"   Auth Header: {auth_header[:30]}...")
            
        elif response.status_code == 200:
            print("   ✓ Direct API call successful")
            result = response.json()
            if result.get('status'):
                print(f"   Success: {result['data']['authorization_url'][:50]}...")
            else:
                print(f"   API Error: {result.get('message')}")
        else:
            print(f"   Unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"   ✗ Direct API call exception: {e}")

def test_rate_limiting(payment, order):
    """Test if rate limiting is causing issues"""
    
    print("   Testing rapid successive calls...")
    
    for i in range(3):
        try:
            start_time = time.time()
            result = payment.initialize_mobile_money_payment(
                order, '0202114315', 'vodafone'
            )
            end_time = time.time()
            
            status = "✓ Success" if result['success'] else f"✗ Failed: {result['message']}"
            print(f"   Call {i+1}: {status} (took {end_time - start_time:.2f}s)")
            
            if not result['success'] and '401' in result['message']:
                print("   Found the 401 error in rapid calls!")
                break
                
        except Exception as e:
            print(f"   Call {i+1}: ✗ Exception: {e}")
        
        # Small delay between calls
        time.sleep(0.1)

def provide_solutions():
    """Provide solutions based on findings"""
    
    print(f"\n=== SOLUTIONS ===")
    print("Based on the analysis, here are potential solutions:")
    print()
    print("1. API Key Issues:")
    print("   - Ensure the API key hasn't expired or been revoked")
    print("   - Check Paystack dashboard for key status")
    print("   - Regenerate keys if necessary")
    print()
    print("2. Rate Limiting:")
    print("   - Add delays between API calls")
    print("   - Implement retry logic with exponential backoff")
    print("   - Use session pooling for better connection management")
    print()
    print("3. Header Issues:")
    print("   - Verify Authorization header format")
    print("   - Check for extra spaces or characters")
    print("   - Ensure proper Bearer token format")
    print()
    print("4. Environment Issues:")
    print("   - Verify .env file is loaded correctly")
    print("   - Check for environment variable conflicts")
    print("   - Ensure proper Flask app context")

if __name__ == "__main__":
    test_payment_scenarios()
    provide_solutions()
    print("\n=== Debug Complete ===")