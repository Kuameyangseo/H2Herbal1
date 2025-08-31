import sqlite3
import os

# Connect to the database
db_path = os.path.join('instance', 'ecommerce.db')
print(f"Database path: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tables in the database:")
for table in tables:
    print(f"  - {table[0]}")

# Check if canned_response table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='canned_response';")
canned_response_table = cursor.fetchone()

if canned_response_table:
    print("\ncanned_response table exists!")
    
    # Get column information for canned_response table
    cursor.execute("PRAGMA table_info(canned_response);")
    columns = cursor.fetchall()
    
    print("\ncanned_response table columns:")
    for column in columns:
        print(f"  - {column[1]} ({column[2]})")
else:
    print("\ncanned_response table does not exist!")

# Close the connection
conn.close()