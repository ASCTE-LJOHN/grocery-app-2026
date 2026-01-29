import os
import csv
import sqlite3
from models import Product

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
                    category = prod.get('category', '')
                    category = category.strip() if isinstance(category, str) else category
                    category = category or None

                    if not name:
                        raise ValueError("Missing name")

                    cursor = self.conn.execute("""
                        INSERT OR IGNORE INTO products (name, price, category)
                        VALUES (?, ?, ?)
                    """, (name, price, category))

                    if cursor.rowcount == 1:
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


import os
import csv

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