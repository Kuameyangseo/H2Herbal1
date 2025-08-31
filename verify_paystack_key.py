from dotenv import load_dotenv
import os
import requests
import json

# Load environment variables
load_dotenv()

def verify_paystack_key():
    """Verify if the Paystack API key is valid"""
    
    secret_key = os.getenv('PAYSTACK_SECRET_KEY')
    public_key = os.getenv('PAYSTACK_PUBLIC_KEY')
    
    print("=== Paystack API Key Verification ===\n")
    
    # Check if keys are loaded
    print(f"Secret Key Found: {'Yes' if secret_key else 'No'}")
    if secret_key:
        print(f"Secret Key Format: {secret_key[:15]}...")
        print(f"Key Type: {'Live' if secret_key.startswith('sk_live_') else 'Test' if secret_key.startswith('sk_test_') else 'Unknown'}")
    
    print(f"Public Key Found: {'Yes' if public_key else 'No'}")
    if public_key:
        print(f"Public Key Format: {public_key[:15]}...")
        print(f"Key Type: {'Live' if public_key.startswith('pk_live_') else 'Test' if public_key.startswith('pk_test_') else 'Unknown'}")
    
    if not secret_key:
        print("\n❌ ERROR: No secret key found in environment variables")
        return False
    
    # Test the key with a simple API call
    print(f"\n=== Testing API Key Validity ===")
    
    headers = {
        'Authorization': f'Bearer {secret_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Test with a simple endpoint that doesn't require much data
        response = requests.get(
            'https://api.paystack.co/bank',
            headers=headers,
            timeout=10
        )
        
        print(f"HTTP Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("INVALID KEY: The API key is not valid or has been revoked")
            print("Response:", response.text[:200])
            return False
        elif response.status_code == 200:
            print("VALID KEY: API key is working correctly")
            result = response.json()
            if result.get('status'):
                print(f"API Response: Successfully retrieved {len(result.get('data', []))} banks")
            return True
        else:
            print(f"UNEXPECTED RESPONSE: HTTP {response.status_code}")
            print("Response:", response.text[:200])
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"NETWORK ERROR: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_payment_initialization():
    """Test payment initialization with current key"""
    
    secret_key = os.getenv('PAYSTACK_SECRET_KEY')
    if not secret_key:
        print("No secret key available for testing")
        return
    
    print(f"\n=== Testing Payment Initialization ===")
    
    headers = {
        'Authorization': f'Bearer {secret_key}',
        'Content-Type': 'application/json'
    }
    
    # Test payload for payment initialization
    payload = {
        'email': 'test@example.com',
        'amount': 10000,  # 100 GHS in kobo
        'currency': 'GHS',
        'reference': f'test_ref_{int(__import__("time").time())}',
        'callback_url': 'http://127.0.0.1:5000/payment_callback'
    }
    
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers=headers,
            data=json.dumps(payload),
            timeout=10
        )
        
        print(f"Payment Init HTTP Status: {response.status_code}")
        
        if response.status_code == 401:
            print("PAYMENT INIT FAILED: Invalid API key")
            print("Response:", response.text[:200])
        elif response.status_code == 200:
            result = response.json()
            if result.get('status'):
                print("PAYMENT INIT SUCCESS: Payment can be initialized")
                print(f"Authorization URL: {result['data']['authorization_url'][:50]}...")
            else:
                print(f"PAYMENT INIT FAILED: {result.get('message')}")
        else:
            print(f"UNEXPECTED RESPONSE: HTTP {response.status_code}")
            print("Response:", response.text[:200])
            
    except Exception as e:
        print(f"ERROR: {e}")

def test_mobile_money_initialization():
    """Test mobile money payment initialization"""
    
    secret_key = os.getenv('PAYSTACK_SECRET_KEY')
    if not secret_key:
        print("No secret key available for testing")
        return
    
    print(f"\n=== Testing Mobile Money Initialization ===")
    
    headers = {
        'Authorization': f'Bearer {secret_key}',
        'Content-Type': 'application/json'
    }
    
    # Test payload for mobile money
    payload = {
        'email': 'test@example.com',
        'amount': 10000,  # 100 GHS in kobo
        'currency': 'GHS',
        'reference': f'momo_test_{int(__import__("time").time())}',
        'channels': ['mobile_money'],
        'callback_url': 'http://127.0.0.1:5000/payment_callback',
        'metadata': {
            'payment_method': 'mobile_money',
            'network': 'vodafone',
            'phone_number': '0202114315'
        }
    }
    
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers=headers,
            data=json.dumps(payload),
            timeout=10
        )
        
        print(f"Mobile Money HTTP Status: {response.status_code}")
        
        if response.status_code == 401:
            print("MOBILE MONEY FAILED: Invalid API key")
            print("Response:", response.text[:200])
        elif response.status_code == 200:
            result = response.json()
            if result.get('status'):
                print("MOBILE MONEY SUCCESS: Mobile money payment can be initialized")
                print(f"Authorization URL: {result['data']['authorization_url'][:50]}...")
            else:
                print(f"MOBILE MONEY FAILED: {result.get('message')}")
        else:
            print(f"UNEXPECTED RESPONSE: HTTP {response.status_code}")
            print("Response:", response.text[:200])
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    key_valid = verify_paystack_key()
    
    if key_valid:
        test_payment_initialization()
        test_mobile_money_initialization()
    else:
        print("\nRECOMMENDATIONS:")
        print("1. Check your Paystack dashboard for the correct API keys")
        print("2. Ensure you're using the right environment (test vs live)")
        print("3. Verify that your Paystack account is active and in good standing")
        print("4. Consider regenerating your API keys if they've been compromised")
        print("5. For testing, use test keys (sk_test_... and pk_test_...)")
    
    print("\n=== Verification Complete ===")