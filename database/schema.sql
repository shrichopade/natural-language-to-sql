-- database/schema.sql
CREATE TABLE IF NOT EXISTS regions (region_id INTEGER PRIMARY KEY, region_name TEXT);
CREATE TABLE IF NOT EXISTS territories (territory_id INTEGER PRIMARY KEY, territory_name TEXT, region_id INTEGER, FOREIGN KEY(region_id) REFERENCES regions(region_id));
CREATE TABLE IF NOT EXISTS employees (emp_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, title TEXT, reports_to INTEGER, territory_id INTEGER, FOREIGN KEY(territory_id) REFERENCES territories(territory_id));
CREATE TABLE IF NOT EXISTS categories (cat_id INTEGER PRIMARY KEY, cat_name TEXT);
CREATE TABLE IF NOT EXISTS suppliers (supplier_id INTEGER PRIMARY KEY, company_name TEXT, country TEXT);
CREATE TABLE IF NOT EXISTS products (prod_id INTEGER PRIMARY KEY, prod_name TEXT, cat_id INTEGER, supplier_id INTEGER, unit_price REAL, stock_level INTEGER, FOREIGN KEY(cat_id) REFERENCES categories(cat_id), FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id));
CREATE TABLE IF NOT EXISTS customers (cust_id INTEGER PRIMARY KEY, company_name TEXT, contact_name TEXT, city TEXT, country TEXT);
CREATE TABLE IF NOT EXISTS shippers (shipper_id INTEGER PRIMARY KEY, shipper_name TEXT);
CREATE TABLE IF NOT EXISTS orders (order_id INTEGER PRIMARY KEY, cust_id INTEGER, emp_id INTEGER, order_date DATE, shipper_id INTEGER, freight REAL, FOREIGN KEY(cust_id) REFERENCES customers(cust_id), FOREIGN KEY(emp_id) REFERENCES employees(emp_id), FOREIGN KEY(shipper_id) REFERENCES shippers(shipper_id));
CREATE TABLE IF NOT EXISTS order_details (order_id INTEGER, prod_id INTEGER, unit_price REAL, quantity INTEGER, discount REAL, PRIMARY KEY(order_id, prod_id), FOREIGN KEY(order_id) REFERENCES orders(order_id), FOREIGN KEY(prod_id) REFERENCES products(prod_id));
CREATE TABLE IF NOT EXISTS inventory_logs (log_id INTEGER PRIMARY KEY, prod_id INTEGER, change_amount INTEGER, log_date TIMESTAMP, FOREIGN KEY(prod_id) REFERENCES products(prod_id));
CREATE TABLE IF NOT EXISTS customer_demographics (demo_id INTEGER PRIMARY KEY, cust_id INTEGER, income_bracket TEXT, age_group TEXT, FOREIGN KEY(cust_id) REFERENCES customers(cust_id));
CREATE TABLE IF NOT EXISTS product_reviews (review_id INTEGER PRIMARY KEY, prod_id INTEGER, rating INTEGER, comment TEXT, FOREIGN KEY(prod_id) REFERENCES products(prod_id));
CREATE TABLE IF NOT EXISTS marketing_campaigns (camp_id INTEGER PRIMARY KEY, camp_name TEXT, budget REAL, start_date DATE);
CREATE TABLE IF NOT EXISTS sales_targets (target_id INTEGER PRIMARY KEY, emp_id INTEGER, target_amount REAL, year INTEGER, FOREIGN KEY(emp_id) REFERENCES employees(emp_id));