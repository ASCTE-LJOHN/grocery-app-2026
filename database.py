
import sqlite3
from models import Product

# ----------------------------
# Validation + LIKE escaping
# ----------------------------
MAX_NAME = 200
MAX_CATEGORY = 100
MAX_QUERY = 200

def _sanitize_string(value: str, max_length: int) -> str:
    if value is None:
        return ""
    s = value.strip()
    if len(s) > max_length:
        raise ValueError(f"Input too long (max {max_length} chars)")
    return s

def _sanitize_price(value):
    p = float(value)
    if p < 0:
        raise ValueError("Price must be >= 0")
    return p

def _sanitize_query(value: str) -> str:
    return _sanitize_string(value, MAX_QUERY)

def _escape_like(q: str) -> str:
    if q is None:
        return ""
    q = q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return q


class DatabaseManager:
    def __init__(self, db_file='grocery.db'):
        self.db_file = db_file
        self.conn = None
        self.connect()
        self.create_table()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
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

    def insert_product(self, product):
        if self.conn:
            with self.conn:
                name = _sanitize_string(product.name, MAX_NAME)
                price = _sanitize_price(product.price)
                category = _sanitize_string(product.category or "", MAX_CATEGORY) or None

                cursor = self.conn.execute("""
                    INSERT INTO products (name, price, category)
                    VALUES (?, ?, ?)
                """, (name, price, category))
                product.id = cursor.lastrowid
            return product

    def bulk_insert_products(self, products_list):
        if not self.conn:
            return 0, len(products_list), ["No database connection"]

        success = 0
        errors = []
        error_count = 0

        with self.conn:
            for prod in products_list:
                try:
                    name = _sanitize_string(prod.get('name', ''), MAX_NAME)
                    price = _sanitize_price(prod.get('price', 0))
                    category = _sanitize_string(prod.get('category', '') or '', MAX_CATEGORY) or None

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
            q = _sanitize_query(query)
            q_escaped = _escape_like(q)

            cursor = self.conn.execute("""
                SELECT id, name, price, category FROM products
                WHERE name LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\'
            """, (f'%{q_escaped}%', f'%{q_escaped}%'))

            rows = cursor.fetchall()

            return [
                Product(
                    id=row['id'],
                    name=row['name'],
                    price=row['price'],
                    category=row['category']
                )
                for row in rows
            ]

        return []

    def close(self):
        if self.conn:
            self.conn.close()
