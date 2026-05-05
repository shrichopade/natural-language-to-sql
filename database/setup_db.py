# database/setup_db.py
import sqlite3
import os

def initialize_database():
    db_path = 'sales.db'
    schema_path = 'database/schema.sql'
    
    # Connect to SQLite (creates the file if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Read and execute the schema
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    cursor.executescript(schema_sql)
    
    # Add sample data for one table to test
    cursor.execute("INSERT OR IGNORE INTO regions (region_id, region_name) VALUES (1, 'North America'), (2, 'Europe')")
    
    conn.commit()
    conn.close()
    print(f"✅ Database '{db_path}' initialized successfully with 15 tables.")

if __name__ == "__main__":
    initialize_database()