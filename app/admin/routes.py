import os
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_, or_
from app import db
from app.admin import bp
from app.admin.forms import (CategoryForm, ProductForm, ProductImageForm, OrderStatusForm, 
                            UserForm, ReviewModerationForm, BulkActionForm, SearchForm, DateRangeForm)
from app.models import (Category, Product, ProductImage, Order, OrderItem, User, Review,
                       Newsletter, CartItem, MessageHistory)
from app.auth.email import send_order_status_update_email
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
@admin_required
def dashboard():
    # Get dashboard statistics
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Sales statistics
    total_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.payment_status == 'paid'
    ).scalar() or 0
    
    today_sales = db.session.query(func.sum(Order.total_amount)).filter(
        and_(Order.payment_status == 'paid',
             func.date(Order.created_at) == today)
    ).scalar() or 0
    
    week_sales = db.session.query(func.sum(Order.total_amount)).filter(
        and_(Order.payment_status == 'paid',
             func.date(Order.created_at) >= week_ago)
    ).scalar() or 0
    
    month_sales = db.session.query(func.sum(Order.total_amount)).filter(
        and_(Order.payment_status == 'paid',
             func.date(Order.created_at) >= month_ago)
    ).scalar() or 0
    
    # Order statistics
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    processing_orders = Order.query.filter_by(status='processing').count()
    shipped_orders = Order.query.filter_by(status='shipped').count()
    
    # Product statistics
    total_products = Product.query.filter_by(is_active=True).count()
    low_stock_products = Product.query.filter(
        and_(Product.is_active == True,
             Product.stock_quantity <= Product.min_stock_level)
    ).count()
    out_of_stock_products = Product.query.filter(
        and_(Product.is_active == True,
             Product.stock_quantity == 0)
    ).count()
    
    # User statistics
    total_users = User.query.filter_by(is_active=True).count()
    new_users_today = User.query.filter(
        func.date(User.created_at) == today
    ).count()
    
    # Recent orders
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    # Low stock products
    low_stock_list = Product.query.filter(
        and_(Product.is_active == True,
             Product.stock_quantity <= Product.min_stock_level)
    ).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_sales=float(total_sales),
                         today_sales=float(today_sales),
                         week_sales=float(week_sales),
                         month_sales=float(month_sales),
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         processing_orders=processing_orders,
                         shipped_orders=shipped_orders,
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         out_of_stock_products=out_of_stock_products,
                         total_users=total_users,
                         new_users_today=new_users_today,
                         recent_orders=recent_orders,
                         low_stock_list=low_stock_list)

# Category Management
@bp.route('/categories')
@login_required
@admin_required
def categories():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Category.query
    if search:
        query = query.filter(Category.name.contains(search))
    
    categories = query.order_by(Category.name).paginate(
        page=page, per_page=20, error_out=False)
    
    search_form = SearchForm()
    search_form.search.data = search
    
    return render_template('admin/categories.html', 
                         categories=categories, 
                         search_form=search_form)

@bp.route('/category/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category():
    form = CategoryForm()
    
    if form.validate_on_submit():
        category = Category(
            name=form.name.data,
            description=form.description.data,
            is_active=form.is_active.data
        )
        
        # Handle image upload
        if form.image.data:
            filename = secure_filename(form.image.data.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories', filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            form.image.data.save(image_path)
            category.image = f'categories/{filename}'
        
        db.session.add(category)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('admin.categories'))
    
    return render_template('admin/category_form.html', form=form, title='Add Category')

@bp.route('/category/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    form = CategoryForm(original_name=category.name)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        category.is_active = form.is_active.data
        
        # Handle image upload
        if form.image.data:
            filename = secure_filename(form.image.data.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories', filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            form.image.data.save(image_path)
            category.image = f'categories/{filename}'
        
        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('admin.categories'))
    
    elif request.method == 'GET':
        form.name.data = category.name
        form.description.data = category.description
        form.is_active.data = category.is_active
    
    return render_template('admin/category_form.html', form=form, title='Edit Category')

@bp.route('/category/delete/<int:id>')
@login_required
@admin_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    
    # Check if category has products
    if category.products:
        flash('Cannot delete category with products. Please move or delete products first.', 'danger')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully!', 'success')
    
    return redirect(url_for('admin.categories'))

# Product Management
@bp.route('/products')
@login_required
@admin_required
def products():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category_id = request.args.get('category', type=int)
    status = request.args.get('status', '')
    
    query = Product.query
    
    if search:
        query = query.filter(or_(
            Product.name.contains(search),
            Product.sku.contains(search)
        ))
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'low_stock':
        query = query.filter(Product.stock_quantity <= Product.min_stock_level)
    elif status == 'out_of_stock':
        query = query.filter_by(stock_quantity=0)
    
    products = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    categories = Category.query.filter_by(is_active=True).all()
    search_form = SearchForm()
    search_form.search.data = search
    
    return render_template('admin/products.html', 
                         products=products, 
                         categories=categories,
                         search_form=search_form,
                         current_category=category_id,
                         current_status=status)

@bp.route('/product/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    form = ProductForm()
    
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            compare_price=form.compare_price.data,
            cost_price=form.cost_price.data,
            sku=form.sku.data,
            stock_quantity=form.stock_quantity.data,
            min_stock_level=form.min_stock_level.data,
            weight=form.weight.data,
            dimensions=form.dimensions.data,
            category_id=form.category_id.data,
            is_active=form.is_active.data,
            is_featured=form.is_featured.data,
            meta_title=form.meta_title.data,
            meta_description=form.meta_description.data
        )
        
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin.edit_product', id=product.id))
    
    return render_template('admin/product_form.html', form=form, title='Add Product')

@bp.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    form = ProductForm(original_sku=product.sku)
    
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.compare_price = form.compare_price.data
        product.cost_price = form.cost_price.data
        product.sku = form.sku.data
        product.stock_quantity = form.stock_quantity.data
        product.min_stock_level = form.min_stock_level.data
        product.weight = form.weight.data
        product.dimensions = form.dimensions.data
        product.category_id = form.category_id.data
        product.is_active = form.is_active.data
        product.is_featured = form.is_featured.data
        product.meta_title = form.meta_title.data
        product.meta_description = form.meta_description.data
        product.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin.products'))
    
    elif request.method == 'GET':
        form.name.data = product.name
        form.description.data = product.description
        form.price.data = product.price
        form.compare_price.data = product.compare_price
        form.cost_price.data = product.cost_price
        form.sku.data = product.sku
        form.stock_quantity.data = product.stock_quantity
        form.min_stock_level.data = product.min_stock_level
        form.weight.data = product.weight
        form.dimensions.data = product.dimensions
        form.category_id.data = product.category_id
        form.is_active.data = product.is_active
        form.is_featured.data = product.is_featured
        form.meta_title.data = product.meta_title
        form.meta_description.data = product.meta_description
    
    # Get product images
    images = ProductImage.query.filter_by(product_id=id).order_by(ProductImage.sort_order).all()
    image_form = ProductImageForm()
    
    return render_template('admin/product_form.html', 
                         form=form, 
                         product=product,
                         images=images,
                         image_form=image_form,
                         title='Edit Product')

@bp.route('/product/<int:product_id>/add_image', methods=['POST'])
@login_required
@admin_required
def add_product_image(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductImageForm()
    
    if form.validate_on_submit():
        filename = secure_filename(form.image.data.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products', filename)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        form.image.data.save(image_path)
        
        # Check if this is the first image for the product
        existing_images = ProductImage.query.filter_by(product_id=product_id).count()
        is_first_image = existing_images == 0
        
        # If this is set as main image, unset other main images
        if form.is_main.data or is_first_image:
            ProductImage.query.filter_by(product_id=product_id, is_main=True).update({'is_main': False})
        
        product_image = ProductImage(
            product_id=product_id,
            image_url=f'products/{filename}',
            alt_text=form.alt_text.data,
            is_main=form.is_main.data or is_first_image,  # Set as main if explicitly requested or if it's the first image
            sort_order=form.sort_order.data
        )
        
        db.session.add(product_image)
        db.session.commit()
        flash('Image added successfully!', 'success')
    
    return redirect(url_for('admin.edit_product', id=product_id))

@bp.route('/product/image/delete/<int:image_id>')
@login_required
@admin_required
def delete_product_image(image_id):
    image = ProductImage.query.get_or_404(image_id)
    product_id = image.product_id
    
    # Delete file from filesystem
    image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image.image_url)
    if os.path.exists(image_path):
        os.remove(image_path)
    
    db.session.delete(image)
    db.session.commit()
    flash('Image deleted successfully!', 'success')
    
    return redirect(url_for('admin.edit_product', id=product_id))

# Order Management
@bp.route('/orders')
@login_required
@admin_required
def orders():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    payment_status = request.args.get('payment_status', '')
    search = request.args.get('search', '')
    
    query = Order.query
    
    if status:
        query = query.filter_by(status=status)
    
    if payment_status:
        query = query.filter_by(payment_status=payment_status)
    
    if search:
        query = query.filter(or_(
            Order.order_number.contains(search),
            Order.shipping_email.contains(search),
            Order.shipping_first_name.contains(search),
            Order.shipping_last_name.contains(search)
        ))
    
    orders = query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    search_form = SearchForm()
    search_form.search.data = search
    
    return render_template('admin/orders.html', 
                         orders=orders, 
                         search_form=search_form,
                         current_status=status,
                         current_payment_status=payment_status)

@bp.route('/order/<int:id>')
@login_required
@admin_required
def order_detail(id):
    order = Order.query.get_or_404(id)
    form = OrderStatusForm()
    
    return render_template('admin/order_detail.html', order=order, form=form)

@bp.route('/order/<int:id>/update_status', methods=['POST'])
@login_required
@admin_required
def update_order_status(id):
    order = Order.query.get_or_404(id)
    form = OrderStatusForm()
    
    if form.validate_on_submit():
        old_status = order.status
        order.status = form.status.data
        order.payment_status = form.payment_status.data
        order.updated_at = datetime.utcnow()
        
        # Set timestamps for status changes
        if form.status.data == 'shipped' and old_status != 'shipped':
            order.shipped_at = datetime.utcnow()
        elif form.status.data == 'delivered' and old_status != 'delivered':
            order.delivered_at = datetime.utcnow()
        
        db.session.commit()
        
        # Send status update email
        if old_status != form.status.data:
            send_order_status_update_email(order.customer, order)
        
        flash('Order status updated successfully!', 'success')
    
    return redirect(url_for('admin.order_detail', id=id))

# User Management
@bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    role = request.args.get('role', '')
    
    query = User.query
    
    if search:
        query = query.filter(or_(
            User.username.contains(search),
            User.email.contains(search),
            User.first_name.contains(search),
            User.last_name.contains(search)
        ))
    
    if role == 'admin':
        query = query.filter_by(is_admin=True)
    elif role == 'customer':
        query = query.filter_by(is_admin=False)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    search_form = SearchForm()
    search_form.search.data = search
    
    return render_template('admin/users.html', 
                         users=users, 
                         search_form=search_form,
                         current_role=role)

@bp.route('/user/<int:id>')
@login_required
@admin_required
def user_detail(id):
    user = User.query.get_or_404(id)
    
    # Get user's orders
    orders = Order.query.filter_by(user_id=id).order_by(Order.created_at.desc()).limit(10).all()
    
    # Get user's reviews
    reviews = Review.query.filter_by(user_id=id).order_by(Review.created_at.desc()).limit(10).all()
    
    # Get message history for this user
    message_history = MessageHistory.query.filter_by(recipient_id=id).order_by(MessageHistory.created_at.desc()).limit(10).all()
    
    return render_template('admin/user_detail.html',
                         user=user,
                         orders=orders,
                         reviews=reviews,
                         message_history=message_history)

# Review Management
@bp.route('/reviews')
@login_required
@admin_required
def reviews():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = Review.query
    
    if status == 'approved':
        query = query.filter_by(is_approved=True)
    elif status == 'pending':
        query = query.filter_by(is_approved=False)
    
    reviews = query.order_by(Review.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('admin/reviews.html',
                         reviews=reviews,
                         current_status=status)

@bp.route('/review/<int:id>/moderate', methods=['POST'])
@login_required
@admin_required
def moderate_review(id):
    review = Review.query.get_or_404(id)
    form = ReviewModerationForm()
    
    if form.validate_on_submit():
        review.is_approved = form.is_approved.data
        db.session.commit()
        
        status = 'approved' if form.is_approved.data else 'rejected'
        flash(f'Review {status} successfully!', 'success')
    
    return redirect(url_for('admin.reviews'))

# User Management Actions
@bp.route('/user/<int:id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_user(id):
    user = User.query.get_or_404(id)
    user.is_active = True
    db.session.commit()
    flash(f'User {user.username} has been activated.', 'success')
    return redirect(url_for('admin.user_detail', id=user.id))

@bp.route('/user/<int:id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_user(id):
    user = User.query.get_or_404(id)
    user.is_active = False
    db.session.commit()
    flash(f'User {user.username} has been deactivated.', 'success')
    return redirect(url_for('admin.user_detail', id=user.id))

@bp.route('/user/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('admin.users'))

@bp.route('/user/<int:id>/send_message', methods=['POST'])
@login_required
@admin_required
def send_message_to_user(id):
    user = User.query.get_or_404(id)
    message = request.form.get('message')
    
    if message:
        # Create message history record
        message_history = MessageHistory(
            sender_id=current_user.id,
            recipient_id=user.id,
            subject='Message from Administrator',
            message=message,
            email_sent=False
        )
        
        try:
            # Try to send email
            from app.auth.email import send_admin_message_email
            success, error = send_admin_message_email(user, message, current_user)
            
            if success:
                message_history.email_sent = True
                flash(f'Message sent to {user.username} via email successfully.', 'success')
            else:
                message_history.email_sent = False
                message_history.email_error = error
                flash(f'Message saved but email failed to send to {user.username}. Error: {error}', 'warning')
                
        except Exception as e:
            message_history.email_sent = False
            message_history.email_error = str(e)
            flash(f'Message saved but email failed to send to {user.username}. Error: {str(e)}', 'warning')
        
        # Save message history regardless of email success
        db.session.add(message_history)
        db.session.commit()
        
    else:
        flash(f'Please enter a message to send to {user.username}.', 'warning')
    
    return redirect(url_for('admin.user_detail', id=user.id))

@bp.route('/message/<int:id>/resend', methods=['POST'])
@login_required
@admin_required
def resend_message(id):
    message_history = MessageHistory.query.get_or_404(id)
    
    try:
        # Try to resend email
        from app.auth.email import send_admin_message_email
        success, error = send_admin_message_email(
            message_history.recipient,
            message_history.message,
            message_history.sender
        )
        
        if success:
            message_history.email_sent = True
            message_history.email_error = None
            db.session.commit()
            flash(f'Message successfully resent to {message_history.recipient.username}.', 'success')
        else:
            message_history.email_error = error
            db.session.commit()
            flash(f'Failed to resend message to {message_history.recipient.username}. Error: {error}', 'danger')
            
    except Exception as e:
        message_history.email_error = str(e)
        db.session.commit()
        flash(f'Failed to resend message to {message_history.recipient.username}. Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin.user_detail', id=message_history.recipient_id))

# Analytics and Reports
@bp.route('/analytics')
@login_required
@admin_required
def analytics():
    # Sales analytics
    sales_data = db.session.query(
        func.date(Order.created_at).label('date'),
        func.sum(Order.total_amount).label('total_sales'),
        func.count(Order.id).label('order_count')
    ).filter(Order.payment_status == 'paid').group_by(
        func.date(Order.created_at)
    ).order_by(func.date(Order.created_at).desc()).limit(30).all()
    
    # Top selling products
    top_products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.total_price).label('total_revenue')
    ).join(OrderItem).join(Order).filter(
        Order.payment_status == 'paid'
    ).group_by(Product.id, Product.name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(10).all()
    
    return render_template('admin/analytics.html',
                         sales_data=sales_data,
                         top_products=top_products)

# Newsletter Management
@bp.route('/newsletter')
@login_required
@admin_required
def newsletter():
    page = request.args.get('page', 1, type=int)
    subscribers = Newsletter.query.filter_by(is_active=True).order_by(
        Newsletter.created_at.desc()
    ).paginate(page=page, per_page=50, error_out=False)
    
    return render_template('admin/newsletter.html', subscribers=subscribers)

# API endpoints for AJAX requests
@bp.route('/api/dashboard_stats')
@login_required
@admin_required
def api_dashboard_stats():
    today = datetime.utcnow().date()
    
    stats = {
        'today_sales': float(db.session.query(func.sum(Order.total_amount)).filter(
            and_(Order.payment_status == 'paid',
                 func.date(Order.created_at) == today)
        ).scalar() or 0),
        'today_orders': Order.query.filter(
            func.date(Order.created_at) == today
        ).count(),
        'pending_orders': Order.query.filter_by(status='pending').count(),
        'low_stock_count': Product.query.filter(
            and_(Product.is_active == True,
                 Product.stock_quantity <= Product.min_stock_level)
        ).count()
    }
    
    return jsonify(stats)