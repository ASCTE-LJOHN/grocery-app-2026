import sqlite3
from models import Product

class DatabaseManager:
    def __init__(self, db_file='grocery.db'):
        self.db_file = db_file
        self.conn = None
        self.connect()
        self.create_table()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row  # allows dict-like row access
            print(f"Connected to SQLite database: {self.db_file}")
        except Exception as e:
            print(f"Error connecting to SQLite: {e}")

    def create_table(self):
        if self.conn:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        price REAL NOT NULL,
                        category TEXT
                    );
                """)
                # Optional: add unique constraint on name
                # self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name ON products(name);")

    def insert_product(self, product):
        if self.conn:
            with self.conn:
                cursor = self.conn.execute("""
                    INSERT INTO products (name, price, category)
                    VALUES (?, ?, ?)
                """, (product.name, product.price, product.category))
                product.id = cursor.lastrowid
            return product

    def bulk_insert_products(self, products_list):
        """
        products_list: list of dicts [{'name': str, 'price': float/str, 'category': str or None}, ...]
        Returns: (success_count, error_count, errors)
        """
        if not self.conn:
            return 0, len(products_list), ["No database connection"]

        success = 0
        errors = []
        error_count = 0

        with self.conn:
            for prod in products_list:
                try:
                    name = prod['name'].strip()
                    price = float(prod['price'])
                    category = prod.get('category', '').strip() or None

                    if not name:
                        raise ValueError("Missing name")

                    self.conn.execute("""
                        INSERT OR IGNORE INTO products (name, price, category)
                        VALUES (?, ?, ?)
                    """, (name, price, category))
                    success += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row error: {prod} → {str(e)}")

        return success, error_count, errors

    def search_products(self, query):
        if self.conn:
            cursor = self.conn.execute("""
                SELECT id, name, price, category FROM products
                WHERE name LIKE ? OR category LIKE ?
            """, (f'%{query}%', f'%{query}%'))
            rows = cursor.fetchall()
            return [Product(
                id=row['id'],
                name=row['name'],
                price=row['price'],
                category=row['category']
            ) for row in rows]
        return []

    def close(self):
        if self.conn:
            self.conn.close()