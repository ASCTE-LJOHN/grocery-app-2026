import os
import csv
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
    def __init__(self, db_file='grocery.db', csv_file='sample_data.csv'):
        self.db_file = db_file
        self.csv_file = csv_file
        self.conn = None
        self.connect()
        self.create_table()
        self.seed_from_csv_if_needed()

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
                # If you want INSERT OR IGNORE to actually ignore duplicates,
                # you need a UNIQUE constraint/index like this:
                self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_name ON products(name);")

    def _products_count(self) -> int:
        if not self.conn:
            return 0
        cur = self.conn.execute("SELECT COUNT(*) AS c FROM products;")
        row = cur.fetchone()
        return int(row["c"]) if row else 0

    def seed_from_csv_if_needed(self):
        """
        If the DB is empty, import sample_data.csv into products.
        This makes the DB reproducible and avoids committing grocery.db.
        """
        if not self.conn:
            return

        # Only seed if table is empty
        if self._products_count() > 0:
            return

        csv_path = self.csv_file
        # Allow relative path from repo root
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(os.path.dirname(__file__), csv_path)

        if not os.path.exists(csv_path):
            print(f"CSV seed file not found: {csv_path} (skipping seed)")
            return

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            products_list = []
            for r in rows:
                # robust: accept Name/name, Price/price, Category/category
                name = (r.get("name") or r.get("Name") or "").strip()
                price = (r.get("price") or r.get("Price") or "").strip()
                category = (r.get("category") or r.get("Category") or "").strip() or None

                # Skip blank rows
                if not name or not price:
                    continue

                products_list.append({"name": name, "price": price, "category": category})

            success, error_count, errors = self.bulk_insert_products(products_list)
            print(f"Seeded DB from CSV: inserted={success}, errors={error_count}")
            if errors:
                # Print only first few to avoid noise
                for e in errors[:5]:
                    print(e)

        except Exception as e:
            print(f"Error seeding DB from CSV: {e}")

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


def ensure_db_initialized(db_file: str = "grocery.db", csv_file: str = "sample_data.csv") -> None:
    """
    Ensure grocery.db exists, has tables, and is seeded from sample_data.csv if empty.
    Safe to call multiple times.
    """
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row

    # Ensure schema exists
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT
            );
        """)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_name ON products(name);"
        )

    # Check if already seeded
    cur = conn.execute("SELECT COUNT(*) AS c FROM products;")
    count = int(cur.fetchone()["c"])
    if count > 0:
        conn.close()
        return

    # Resolve CSV path
    csv_path = csv_file
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.path.dirname(__file__), csv_path)

    if not os.path.exists(csv_path):
        print(f"CSV seed file not found: {csv_path}")
        conn.close()
        return

    # Seed DB from CSV
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    products = []
    for r in rows:
        name = (r.get("name") or r.get("Name") or "").strip()
        price = (r.get("price") or r.get("Price") or "").strip()
        category = (r.get("category") or r.get("Category") or "").strip() or None

        if not name or not price:
            continue

        products.append((name, float(price), category))

    with conn:
        conn.executemany("""
            INSERT OR IGNORE INTO products (name, price, category)
            VALUES (?, ?, ?)
        """, products)

    conn.close()
