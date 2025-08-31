from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import current_user, login_required
from sqlalchemy import or_, and_
from app import db
from app.main import bp
from app.main.forms import (AddToCartForm, UpdateCartForm, CheckoutForm, ReviewForm, 
                           NewsletterForm, ContactForm, SearchForm, PaymentForm)
from app.models import (Product, Category, CartItem, Order, OrderItem, Review, 
                       Newsletter, User)
from app.main.payment import PaystackPayment
from app.auth.email import send_order_confirmation_email
import json

@bp.route('/')
@bp.route('/index')
def index():
    # Get featured products
    featured_products = Product.query.filter_by(is_featured=True, is_active=True).limit(8).all()
    
    # Get categories
    categories = Category.query.filter_by(is_active=True).all()
    
    # Get latest products
    latest_products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    
    # Newsletter form
    newsletter_form = NewsletterForm()
    
    return render_template('main/index.html', 
                         featured_products=featured_products,
                         categories=categories,
                         latest_products=latest_products,
                         newsletter_form=newsletter_form)

@bp.route('/products')
def products():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    search_query = request.args.get('q', '')
    sort_by = request.args.get('sort', 'name_asc')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    # Base query
    query = Product.query.filter_by(is_active=True)
    
    # Apply filters
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if search_query:
        query = query.filter(or_(
            Product.name.contains(search_query),
            Product.description.contains(search_query)
        ))
    
    if min_price:
        query = query.filter(Product.price >= min_price)
    
    if max_price:
        query = query.filter(Product.price <= max_price)
    
    # Apply sorting
    if sort_by == 'name_asc':
        query = query.order_by(Product.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Product.name.desc())
    elif sort_by == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'newest':
        query = query.order_by(Product.created_at.desc())
    elif sort_by == 'rating':
        # This would need a more complex query with joins
        query = query.order_by(Product.created_at.desc())
    
    products = query.paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()
    
    # Search form
    search_form = SearchForm()
    search_form.category.choices = [('', 'All Categories')] + [(str(c.id), c.name) for c in categories]
    
    return render_template('main/products.html', 
                         products=products, 
                         categories=categories,
                         search_form=search_form,
                         current_category=category_id,
                         current_search=search_query,
                         current_sort=sort_by)

@bp.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    
    if not product.is_active:
        flash('Product not available', 'warning')
        return redirect(url_for('main.products'))
    
    # Get related products from same category
    related_products = Product.query.filter(
        and_(Product.category_id == product.category_id,
             Product.id != product.id,
             Product.is_active == True)
    ).limit(4).all()
    
    # Get reviews
    reviews = Review.query.filter_by(product_id=id, is_approved=True).order_by(Review.created_at.desc()).all()
    
    # Forms
    add_to_cart_form = AddToCartForm()
    review_form = ReviewForm()
    
    return render_template('main/product_detail.html', 
                         product=product,
                         related_products=related_products,
                         reviews=reviews,
                         add_to_cart_form=add_to_cart_form,
                         review_form=review_form)

@bp.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    form = AddToCartForm()
    product = Product.query.get_or_404(product_id)
    
    if not product.is_active or not product.is_in_stock():
        flash('Product is not available', 'warning')
        return redirect(url_for('main.product_detail', id=product_id))
    
    if form.validate_on_submit():
        quantity = form.quantity.data
        
        # Check if item already in cart
        cart_item = CartItem.query.filter_by(
            user_id=current_user.id, 
            product_id=product_id
        ).first()
        
        if cart_item:
            # Update quantity
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.stock_quantity:
                flash(f'Only {product.stock_quantity} items available in stock', 'warning')
                return redirect(url_for('main.product_detail', id=product_id))
            cart_item.quantity = new_quantity
            cart_item.updated_at = datetime.utcnow()
        else:
            # Add new item
            if quantity > product.stock_quantity:
                flash(f'Only {product.stock_quantity} items available in stock', 'warning')
                return redirect(url_for('main.product_detail', id=product_id))
            cart_item = CartItem(
                user_id=current_user.id,
                product_id=product_id,
                quantity=quantity
            )
            db.session.add(cart_item)
        
        db.session.commit()
        flash(f'{product.name} added to cart!', 'success')
    
    return redirect(url_for('main.product_detail', id=product_id))

@bp.route('/cart')
@login_required
def cart():
    cart_items = current_user.cart_items
    total = current_user.get_cart_total()
    
    return render_template('main/cart.html', 
                         cart_items=cart_items, 
                         total=total)

@bp.route('/update_cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('main.cart'))
    
    form = UpdateCartForm()
    if form.validate_on_submit():
        quantity = form.quantity.data
        
        if quantity == 0:
            db.session.delete(cart_item)
            flash('Item removed from cart', 'info')
        else:
            if quantity > cart_item.product.stock_quantity:
                flash(f'Only {cart_item.product.stock_quantity} items available', 'warning')
                return redirect(url_for('main.cart'))
            
            cart_item.quantity = quantity
            cart_item.updated_at = datetime.utcnow()
            flash('Cart updated', 'success')
        
        db.session.commit()
    
    return redirect(url_for('main.cart'))

@bp.route('/remove_from_cart/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('main.cart'))
    
    db.session.delete(cart_item)
    db.session.commit()
    flash('Item removed from cart', 'info')
    
    return redirect(url_for('main.cart'))

@bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = current_user.cart_items
    
    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('main.cart'))
    
    # Check stock availability
    for item in cart_items:
        if not item.product.is_in_stock() or item.quantity > item.product.stock_quantity:
            flash(f'{item.product.name} is not available in requested quantity', 'warning')
            return redirect(url_for('main.cart'))
    
    form = CheckoutForm()
    
    if form.validate_on_submit():
        # Calculate totals
        subtotal = Decimal(str(current_user.get_cart_total()))
        tax_amount = Decimal('0.00')  # Add tax calculation if needed
        shipping_cost = Decimal('2.00')  # Fixed shipping cost (2 GHS)
        total_amount = subtotal + tax_amount + shipping_cost
        
        # Create order
        order = Order(
            order_number=Order().generate_order_number(),
            user_id=current_user.id,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_cost=shipping_cost,
            total_amount=total_amount,
            payment_method=form.payment_method.data,
            shipping_first_name=form.first_name.data,
            shipping_last_name=form.last_name.data,
            shipping_email=form.email.data,
            shipping_phone=form.phone.data,
            shipping_address=form.address.data,
            shipping_city=form.city.data,
            shipping_country=form.country.data,
            shipping_postal_code=form.postal_code.data
        )
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Create order items
        for cart_item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.price,
                total_price=Decimal(str(cart_item.product.price)) * Decimal(str(cart_item.quantity)),
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku
            )
            db.session.add(order_item)
            
            # Update product stock
            cart_item.product.stock_quantity -= cart_item.quantity
        
        # Clear cart
        for cart_item in cart_items:
            db.session.delete(cart_item)
        
        db.session.commit()
        
        # Process payment
        if form.payment_method.data in ['card', 'momo']:
            return redirect(url_for('main.payment', order_id=order.id))
        else:
            # For bank transfer, mark as pending
            flash('Order placed successfully! Please check your email for payment instructions.', 'success')
            send_order_confirmation_email(current_user, order)
            return redirect(url_for('main.order_success', order_id=order.id))
    
    # Pre-fill form with user data
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.country.data = current_user.country
        form.postal_code.data = current_user.postal_code
    
    subtotal = current_user.get_cart_total()
    shipping_cost = 2.00
    total = subtotal + shipping_cost
    
    return render_template('main/checkout.html', 
                         form=form, 
                         cart_items=cart_items,
                         subtotal=subtotal,
                         shipping_cost=shipping_cost,
                         total=total)

@bp.route('/payment/<int:order_id>')
@login_required
def payment(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    if order.payment_status == 'paid':
        flash('Order already paid', 'info')
        return redirect(url_for('main.order_success', order_id=order.id))
    
    payment_form = PaymentForm()
    
    return render_template('main/payment.html', 
                         order=order, 
                         payment_form=payment_form)

@bp.route('/process_payment/<int:order_id>', methods=['POST'])
@login_required
def process_payment(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    try:
        payment_processor = PaystackPayment()
        
        # Get payment method from form data
        payment_method = request.form.get('payment_method')
        
        if payment_method == 'card':
            result = payment_processor.initialize_payment(order)
        elif payment_method == 'momo':
            phone_number = request.form.get('phone_number')
            network = request.form.get('network')
            
            if not phone_number or not network:
                return jsonify({'success': False, 'message': 'Phone number and network are required for mobile money'})
            
            result = payment_processor.initialize_mobile_money_payment(order, phone_number, network)
        else:
            return jsonify({'success': False, 'message': 'Invalid payment method'})
        
        if result['success']:
            order.payment_reference = result['reference']
            db.session.commit()
            return jsonify({
                'success': True,
                'authorization_url': result['authorization_url'],
                'reference': result['reference']
            })
        else:
            current_app.logger.error(f'Payment initialization failed: {result["message"]}')
            return jsonify({'success': False, 'message': result['message']})
            
    except Exception as e:
        current_app.logger.error(f'Payment processing error: {str(e)}')
        return jsonify({'success': False, 'message': f'Payment processing error: {str(e)}'})

@bp.route('/payment_callback')
def payment_callback():
    reference = request.args.get('reference')
    
    # Log the callback attempt
    current_app.logger.info(f"Payment callback received for reference: {reference}")
    
    if not reference:
        current_app.logger.error("Payment callback received without reference")
        flash('Invalid payment reference', 'danger')
        return redirect(url_for('main.index'))
    
    order = Order.query.filter_by(payment_reference=reference).first()
    
    if not order:
        current_app.logger.error(f"Order not found for payment reference: {reference}")
        flash('Order not found', 'danger')
        return redirect(url_for('main.index'))
    
    # Check if payment is already processed
    if order.payment_status == 'paid':
        current_app.logger.info(f"Payment already processed for order {order.id}")
        flash('Payment already processed successfully!', 'info')
        return redirect(url_for('main.order_success', order_id=order.id))
    
    try:
        payment_processor = PaystackPayment()
        result = payment_processor.verify_payment(reference)
        
        current_app.logger.info(f"Payment verification result for order {order.id}: {result}")
        
        if result['success']:
            # Verify the amount matches
            expected_amount = float(order.total_amount)
            paid_amount = result.get('amount', 0)
            
            if abs(expected_amount - paid_amount) > 0.01:  # Allow for small rounding differences
                current_app.logger.error(f"Amount mismatch for order {order.id}: expected {expected_amount}, got {paid_amount}")
                order.payment_status = 'failed'
                order.status = 'pending'
                db.session.commit()
                flash('Payment amount mismatch. Please contact support.', 'danger')
                return redirect(url_for('main.payment', order_id=order.id))
            
            # Payment successful
            order.payment_status = 'paid'
            order.status = 'confirmed'
            order.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Payment successful for order {order.id}")
            flash('Payment successful! Your order has been confirmed.', 'success')
            
            try:
                send_order_confirmation_email(order.customer, order)
            except Exception as e:
                current_app.logger.error(f"Failed to send confirmation email for order {order.id}: {str(e)}")
                # Don't fail the payment process if email fails
            
            return redirect(url_for('main.order_success', order_id=order.id))
        else:
            # Payment failed or pending
            payment_status = result.get('payment_status', 'failed')
            error_message = result.get('message', 'Payment verification failed')
            
            current_app.logger.warning(f"Payment verification failed for order {order.id}: {error_message}")
            
            # Only mark as failed if it's actually failed, not if it's still pending
            if payment_status in ['failed', 'cancelled', 'abandoned']:
                order.payment_status = 'failed'
                order.updated_at = datetime.utcnow()
                db.session.commit()
                flash(f'Payment failed: {error_message}', 'danger')
                return redirect(url_for('main.payment', order_id=order.id))
            else:
                # Payment might still be pending
                current_app.logger.info(f"Payment still pending for order {order.id}")
                flash('Payment is still being processed. Please wait a moment and check again.', 'info')
                return redirect(url_for('main.payment', order_id=order.id))
                
    except Exception as e:
        current_app.logger.error(f"Payment callback error for order {order.id}: {str(e)}")
        flash('An error occurred while processing your payment. Please contact support.', 'danger')
        return redirect(url_for('main.payment', order_id=order.id))

@bp.route('/order_success/<int:order_id>')
@bp.route('/order-success/<int:order_id>')
@login_required
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('main/order_success.html', order=order)

@bp.route('/add_review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    form = ReviewForm()
    
    if form.validate_on_submit():
        # Check if user has already reviewed this product
        existing_review = Review.query.filter_by(
            user_id=current_user.id, 
            product_id=product_id
        ).first()
        
        if existing_review:
            flash('You have already reviewed this product', 'warning')
        else:
            # Check if user has purchased this product
            has_purchased = db.session.query(OrderItem).join(Order).filter(
                Order.user_id == current_user.id,
                OrderItem.product_id == product_id,
                Order.payment_status == 'paid'
            ).first()
            
            review = Review(
                user_id=current_user.id,
                product_id=product_id,
                rating=form.rating.data,
                title=form.title.data,
                comment=form.comment.data,
                is_verified_purchase=bool(has_purchased)
            )
            
            db.session.add(review)
            db.session.commit()
            flash('Thank you for your review!', 'success')
    
    return redirect(url_for('main.product_detail', id=product_id))

@bp.route('/subscribe_newsletter', methods=['POST'])
def subscribe_newsletter():
    form = NewsletterForm()
    
    if form.validate_on_submit():
        existing_subscriber = Newsletter.query.filter_by(email=form.email.data).first()
        
        if existing_subscriber:
            if existing_subscriber.is_active:
                flash('You are already subscribed to our newsletter', 'info')
            else:
                existing_subscriber.is_active = True
                db.session.commit()
                flash('Welcome back! You have been resubscribed to our newsletter', 'success')
        else:
            subscriber = Newsletter(email=form.email.data)
            db.session.add(subscriber)
            db.session.commit()
            flash('Thank you for subscribing to our newsletter!', 'success')
    
    return redirect(url_for('main.index'))

@bp.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    
    if form.validate_on_submit():
        # Here you would typically send an email to the admin
        flash('Thank you for your message! We will get back to you soon.', 'success')
        return redirect(url_for('main.contact'))
    
    return render_template('main/contact.html', form=form)

@bp.route('/about')
def about():
    return render_template('main/about.html')

@bp.route('/search')
def search():
    return redirect(url_for('main.products', **request.args))