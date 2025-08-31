#!/usr/bin/env python3
"""
Script to fix product images that are not properly set as main images.
This will set the first image of each product as the main image if no main image exists.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Product, ProductImage

def fix_product_images():
    """Fix product images by setting the first image as main if no main image exists."""
    app = create_app()
    
    with app.app_context():
        print("Fixing product images...")
        
        # Get all products
        products = Product.query.all()
        fixed_count = 0
        
        for product in products:
            # Check if product has any main image
            main_image = ProductImage.query.filter_by(product_id=product.id, is_main=True).first()
            
            if not main_image:
                # Get the first image for this product
                first_image = ProductImage.query.filter_by(product_id=product.id).first()
                
                if first_image:
                    print(f"Setting main image for product '{product.name}': {first_image.image_url}")
                    first_image.is_main = True
                    fixed_count += 1
                else:
                    print(f"No images found for product '{product.name}'")
            else:
                print(f"Product '{product.name}' already has a main image: {main_image.image_url}")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\nFixed {fixed_count} products with missing main images.")
        else:
            print("\nNo products needed fixing.")
        
        # Show summary of all product images
        print("\n=== Product Images Summary ===")
        for product in products:
            images = ProductImage.query.filter_by(product_id=product.id).all()
            main_images = [img for img in images if img.is_main]
            
            print(f"\nProduct: {product.name}")
            print(f"  Total images: {len(images)}")
            print(f"  Main images: {len(main_images)}")
            
            for img in images:
                status = " (MAIN)" if img.is_main else ""
                print(f"    - {img.image_url}{status}")

if __name__ == '__main__':
    fix_product_images()