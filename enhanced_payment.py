import requests
import json
import time
import logging
from flask import current_app
from decimal import Decimal, ROUND_HALF_UP
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator to retry API calls on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    result = func(*args, **kwargs)
                    # If it's a dict with success=False and contains 401 error, retry
                    if isinstance(result, dict) and not result.get('success'):
                        if '401' in str(result.get('message', '')):
                            retries += 1
                            if retries < max_retries:
                                wait_time = delay * (backoff ** (retries - 1))
                                logger.warning(f"API call failed with 401, retrying in {wait_time}s (attempt {retries}/{max_retries})")
                                time.sleep(wait_time)
                                continue
                    return result
                except Exception as e:
                    retries += 1
                    if retries < max_retries:
                        wait_time = delay * (backoff ** (retries - 1))
                        logger.warning(f"API call exception: {e}, retrying in {wait_time}s (attempt {retries}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"API call failed after {max_retries} attempts: {e}")
                        raise
            return result
        return wrapper
    return decorator

class EnhancedPaystackPayment:
    def __init__(self):
        self.secret_key = current_app.config.get('PAYSTACK_SECRET_KEY')
        self.public_key = current_app.config.get('PAYSTACK_PUBLIC_KEY')
        self.base_url = 'https://api.paystack.co'
        
        # Validate configuration on initialization
        self._validate_configuration()
        
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'H2Herbal-ECommerce/1.0',
            'Accept': 'application/json',
            'Cache-Control': 'no-cache'
        }
        
        # Create session with enhanced retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[401, 403, 429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
        
        # Test the API key on initialization
        self._test_api_key()
    
    def _validate_configuration(self):
        """Validate Paystack configuration"""
        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is not configured")
        
        if not self.public_key:
            raise ValueError("PAYSTACK_PUBLIC_KEY is not configured")
        
        # Validate key format
        if not self.secret_key.startswith(('sk_test_', 'sk_live_')):
            raise ValueError("Invalid Paystack secret key format")
        
        if not self.public_key.startswith(('pk_test_', 'pk_live_')):
            raise ValueError("Invalid Paystack public key format")
        
        # Ensure both keys are from the same environment
        secret_env = 'live' if self.secret_key.startswith('sk_live_') else 'test'
        public_env = 'live' if self.public_key.startswith('pk_live_') else 'test'
        
        if secret_env != public_env:
            raise ValueError("Secret and public keys are from different environments")
        
        logger.info(f"Paystack configuration validated ({secret_env} environment)")
    
    def _test_api_key(self):
        """Test API key validity on initialization"""
        try:
            response = requests.get(
                f'{self.base_url}/bank',
                headers={'Authorization': f'Bearer {self.secret_key}'},
                timeout=10
            )
            
            if response.status_code == 401:
                raise ValueError("Invalid Paystack API key - authentication failed")
            elif response.status_code != 200:
                logger.warning(f"API key test returned status {response.status_code}")
            else:
                logger.info("Paystack API key validated successfully")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not validate API key due to network error: {e}")
    
    def _make_request(self, method, url, **kwargs):
        """Make HTTP request with enhanced error handling"""
        # Add delay to avoid rate limiting
        time.sleep(0.5)
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            # Log the request for debugging
            logger.debug(f"{method} {url} - Status: {response.status_code}")
            
            return response
            
        except requests.exceptions.Timeout:
            logger.error("Request timeout - Paystack API may be slow")
            raise
        except requests.exceptions.ConnectionError:
            logger.error("Connection error - Check internet connection")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    @retry_on_failure(max_retries=3, delay=1, backoff=2)
    def initialize_payment(self, order):
        """Initialize a standard card payment with enhanced error handling"""
        try:
            # Convert amount to kobo (multiply by 100)
            amount_kobo = int(float(order.total_amount) * 100)
            
            payload = {
                'email': order.shipping_email,
                'amount': amount_kobo,
                'currency': 'GHS',
                'reference': f'order_{order.id}_{order.order_number}',
                'callback_url': f'{current_app.config.get("BASE_URL", "http://127.0.0.1:5000")}/payment_callback',
                'metadata': {
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'customer_name': f'{order.shipping_first_name} {order.shipping_last_name}',
                    'customer_phone': order.shipping_phone,
                    'payment_type': 'standard'
                }
            }
            
            logger.info(f"Initializing payment for order {order.id} - Amount: GHS {order.total_amount}")
            
            response = self._make_request(
                'POST',
                f'{self.base_url}/transaction/initialize',
                data=json.dumps(payload)
            )
            
            # Enhanced error handling
            if response.status_code == 401:
                error_msg = "Invalid API key - please check your Paystack configuration"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            if response.status_code == 429:
                error_msg = "Rate limit exceeded - please try again later"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            if response.status_code != 200:
                error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                logger.error(f"Payment initialization failed: {error_msg}")
                return {'success': False, 'message': error_msg}
            
            # Check if response has content
            if not response.text.strip():
                error_msg = 'Empty response from Paystack API'
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                error_msg = f'Invalid JSON response: {str(e)}'
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            if result.get('status'):
                logger.info(f"Payment initialized successfully for order {order.id}")
                return {
                    'success': True,
                    'authorization_url': result['data']['authorization_url'],
                    'access_code': result['data']['access_code'],
                    'reference': result['data']['reference']
                }
            else:
                error_msg = result.get('message', 'Payment initialization failed')
                logger.error(f"Paystack API error: {error_msg}")
                return {'success': False, 'message': error_msg}
                
        except Exception as e:
            error_msg = f'Payment initialization error: {str(e)}'
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}
    
    @retry_on_failure(max_retries=3, delay=1, backoff=2)
    def initialize_mobile_money_payment(self, order, phone_number, network):
        """Initialize mobile money payment with enhanced error handling"""
        try:
            # Validate phone number
            validated_phone = self._validate_phone_number(phone_number, network)
            if not validated_phone:
                return {
                    'success': False,
                    'message': f'Invalid phone number format for {network} network'
                }
            
            # Convert amount to kobo (multiply by 100)
            amount_kobo = int(float(order.total_amount) * 100)
            
            payload = {
                'email': order.shipping_email,
                'amount': amount_kobo,
                'currency': 'GHS',
                'reference': f'momo_{order.id}_{order.order_number}',
                'channels': ['mobile_money'],
                'callback_url': f'{current_app.config.get("BASE_URL", "http://127.0.0.1:5000")}/payment_callback',
                'metadata': {
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'customer_name': f'{order.shipping_first_name} {order.shipping_last_name}',
                    'payment_method': 'mobile_money',
                    'network': network,
                    'phone_number': validated_phone,
                    'payment_type': 'mobile_money'
                }
            }
            
            logger.info(f"Initializing mobile money payment for order {order.id} - Network: {network}, Amount: GHS {order.total_amount}")
            
            response = self._make_request(
                'POST',
                f'{self.base_url}/transaction/initialize',
                data=json.dumps(payload)
            )
            
            # Enhanced error handling
            if response.status_code == 401:
                error_msg = "Invalid API key - please check your Paystack configuration"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            if response.status_code == 429:
                error_msg = "Rate limit exceeded - please try again later"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            if response.status_code != 200:
                error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                logger.error(f"Mobile money initialization failed: {error_msg}")
                return {'success': False, 'message': error_msg}
            
            # Check if response has content
            if not response.text.strip():
                error_msg = 'Empty response from Paystack API'
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                error_msg = f'Invalid JSON response: {str(e)}'
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            if result.get('status'):
                logger.info(f"Mobile money payment initialized successfully for order {order.id}")
                return {
                    'success': True,
                    'authorization_url': result['data']['authorization_url'],
                    'access_code': result['data']['access_code'],
                    'reference': result['data']['reference']
                }
            else:
                error_msg = result.get('message', 'Mobile money payment initialization failed')
                logger.error(f"Paystack API error: {error_msg}")
                return {'success': False, 'message': error_msg}
                
        except Exception as e:
            error_msg = f'Mobile money payment error: {str(e)}'
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}
    
    def _validate_phone_number(self, phone_number, network):
        """Validate phone number format for Ghana networks"""
        # Remove any spaces or special characters
        phone = ''.join(filter(str.isdigit, phone_number))
        
        # Ghana phone number validation
        if len(phone) == 10 and phone.startswith(('02', '05', '024', '054', '055', '059')):
            return f'233{phone[1:]}'  # Convert to international format
        elif len(phone) == 12 and phone.startswith('233'):
            return phone
        else:
            return None
    
    def verify_payment(self, reference):
        """Verify payment status with enhanced error handling"""
        try:
            logger.info(f"Verifying payment: {reference}")
            
            response = self._make_request(
                'GET',
                f'{self.base_url}/transaction/verify/{reference}'
            )
            
            if response.status_code == 401:
                return {'success': False, 'message': 'Invalid API key'}
            
            if response.status_code != 200:
                return {'success': False, 'message': f'HTTP {response.status_code}: {response.text[:200]}'}
            
            result = response.json()
            
            if result.get('status') and result.get('data'):
                data = result['data']
                if data.get('status') == 'success':
                    logger.info(f"Payment verified successfully: {reference}")
                    return {
                        'success': True,
                        'amount': data.get('amount', 0) / 100,  # Convert from kobo
                        'currency': data.get('currency'),
                        'reference': data.get('reference'),
                        'gateway_response': data.get('gateway_response'),
                        'paid_at': data.get('paid_at'),
                        'channel': data.get('channel'),
                        'fees': data.get('fees', 0) / 100 if data.get('fees') else 0
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Payment failed: {data.get("gateway_response", "Unknown error")}'
                    }
            else:
                return {
                    'success': False,
                    'message': result.get('message', 'Payment verification failed')
                }
                
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return {
                'success': False,
                'message': f'Payment verification error: {str(e)}'
            }

# Alias for backward compatibility
PaystackPayment = EnhancedPaystackPayment