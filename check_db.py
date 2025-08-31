import sqlite3
import os

# Check h2herbal.db
print("Checking h2herbal.db:")
db_path = os.path.join('instance', 'h2herbal.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Database tables:")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Check if product table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='product';")
    product_table = cursor.fetchone()
    
    if product_table:
        print("\nProduct table exists!")
        
        # Get column information for product table
        cursor.execute("PRAGMA table_info(product);")
        columns = cursor.fetchall()
        
        print("\nProduct table columns:")
        for column in columns:
            print(f"  - {column[1]} ({column[2]})")
    else:
        print("\nProduct table does not exist!")
    
    # Close the connection
    conn.close()
else:
    print("h2herbal.db does not exist")

print("\n" + "="*50 + "\n")

# Check ecommerce.db
print("Checking ecommerce.db:")
db_path = os.path.join('instance', 'ecommerce.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Database tables:")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Check if product table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='product';")
    product_table = cursor.fetchone()
    
    if product_table:
        print("\nProduct table exists!")
        
        # Get column information for product table
        cursor.execute("PRAGMA table_info(product);")
        columns = cursor.fetchall()
        
        print("\nProduct table columns:")
        for column in columns:
            print(f"  - {column[1]} ({column[2]})")
    else:
        print("\nProduct table does not exist!")
    
    # Close the connection
    conn.close()
else:
    print("ecommerce.db does not exist")