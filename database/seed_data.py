# database/seed_data.py
import sqlite3
import random
from faker import Faker

fake = Faker()

def seed_database():
    conn = sqlite3.connect('sales.db')
    cursor = conn.cursor()

    # 1. Categories & Suppliers
    categories = ['Electronics', 'Office Supplies', 'Furniture', 'Software', 'Hardware']
    for cat in categories:
        cursor.execute("INSERT INTO categories (cat_name) VALUES (?)", (cat,))
    
    for _ in range(10):
        cursor.execute("INSERT INTO suppliers (company_name, country) VALUES (?, ?)", 
                       (fake.company(), fake.country()))

    # 2. Products
    for i in range(1, 31):
        cursor.execute("""INSERT INTO products (prod_name, cat_id, supplier_id, unit_price, stock_level) 
                          VALUES (?, ?, ?, ?, ?)""",
                       (fake.ecommerce_name() if hasattr(fake, 'ecommerce_name') else f"Product {i}", 
                        random.randint(1, 5), random.randint(1, 10), 
                        round(random.uniform(10.0, 500.0), 2), random.randint(5, 100)))

    # 3. Customers & Demographics
    for _ in range(20):
        cursor.execute("INSERT INTO customers (company_name, contact_name, city, country) VALUES (?, ?, ?, ?)",
                       (fake.company(), fake.name(), fake.city(), fake.country()))
        cust_id = cursor.lastrowid
        cursor.execute("INSERT INTO customer_demographics (cust_id, income_bracket, age_group) VALUES (?, ?, ?)",
                       (cust_id, random.choice(['Low', 'Medium', 'High']), random.choice(['18-25', '26-40', '41-60', '60+'])))

    # 4. Employees & Territories
    cursor.execute("INSERT INTO territories (territory_name, region_id) VALUES ('East Coast', 1), ('West Coast', 1), ('London', 2), ('Paris', 2)")
    for _ in range(10):
        cursor.execute("INSERT INTO employees (first_name, last_name, title, territory_id) VALUES (?, ?, ?, ?)",
                       (fake.first_name(), fake.last_name(), 'Sales Rep', random.randint(1, 4)))

    # 5. Orders & Details (The core data)
    for _ in range(100):
        cursor.execute("INSERT INTO orders (cust_id, emp_id, order_date, shipper_id, freight) VALUES (?, ?, ?, ?, ?)",
                       (random.randint(1, 20), random.randint(1, 10), 
                        fake.date_between(start_date='-1y', end_date='today'), 
                        random.randint(1, 3), round(random.uniform(5.0, 50.0), 2)))
        order_id = cursor.lastrowid
        
        # FIX: Use random.sample to pick UNIQUE product IDs for this specific order
        # This prevents the "UNIQUE constraint failed" error
        number_of_items = random.randint(1, 4)
        available_product_ids = list(range(1, 31))
        selected_prods = random.sample(available_product_ids, number_of_items)
        
        for prod_id in selected_prods:
            cursor.execute("INSERT INTO order_details (order_id, prod_id, unit_price, quantity, discount) VALUES (?, ?, ?, ?, ?)",
                           (order_id, prod_id, 200.0, random.randint(1, 5), random.choice([0, 0.05, 0.1])))


    conn.commit()
    conn.close()
    print("✨ Database successfully seeded with 100+ orders and related data!")

if __name__ == "__main__":
    seed_database()
