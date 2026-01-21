
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    session
)
import csv
from io import StringIO
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from models import Product
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'super-secret-key-for-flash-messages'

# ----------------------------------------
# Validation + LIKE escaping
# ----------------------------------------
MAX_NAME = 200
MAX_CATEGORY = 100
MAX_QUERY = 200


def _sanitize_string(value: str, max_length: int) -> str:
    if value is None:
        return ""
    s = value.strip()
    if len(s) > max_length:
        raise ValueError(f"Input too long (max {max_length} characters)")
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
    return q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


# ----------------------------------------
# Load config.xml
# ----------------------------------------
def load_config():
    defaults = {
        'theme': {
            'bg': '#f8f9fa',
            'text': '#212529',
            'accent': '#0d6efd',
            'btn_bg': '#0d6efd',
            'btn_text': '#ffffff',
            'container': '#ffffff',
            'border': '#dee2e6',
            'font': 'system-ui, sans-serif'
        },
        'admin': {"username": "admin", "password": "TXJXb2JiaW5z"}
    }

    try:
        tree = ET.parse("config.xml")
        root = tree.getroot()

        # theme
        theme_node = root.find("theme")
        if theme_node:
            for child in theme_node:
                if child.tag in defaults["theme"]:
                    defaults["theme"][child.tag] = child.text

        # admin settings
        sec = root.find("security")
        if sec:
            u = sec.find("admin_username")
            p = sec.find("admin_password")
            if u is not None and p is not None:
                defaults["admin"]["username"] = u.text.strip()
                defaults["admin"]["password"] = p.text.strip()

        return defaults["theme"], defaults["admin"]

    except Exception as e:
        print("Error loading XML:", e)
        return defaults["theme"], defaults["admin"]


theme, ADMIN_CREDENTIALS = load_config()


# ----------------------------------------
# DB helper
# ----------------------------------------
@contextmanager
def get_db(db_file="grocery.db"):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ----------------------------------------
# Admin login required wrapper
# ----------------------------------------
from functools import wraps


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in as admin.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return wrapper


# ----------------------------------------
# Login / Logout
# ----------------------------------------
@app.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if u == ADMIN_CREDENTIALS["username"] and p == ADMIN_CREDENTIALS["password"]:
            session["admin_logged_in"] = True
            flash("Logged in!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials", "error")

    return render_template("login.html", theme=theme)


@app.route("/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out.", "success")
    return redirect(url_for("index"))


# ----------------------------------------
# Manual product import
# ----------------------------------------
@app.route("/import", methods=["GET", "POST"])
@admin_required
def import_data():
    if request.method == "POST":
        try:
            name = _sanitize_string(request.form["name"], MAX_NAME)
            price = _sanitize_price(request.form["price"])
            category = _sanitize_string(request.form.get("category", ""), MAX_CATEGORY) or None
        except Exception as e:
            flash(str(e), "error")
            return redirect(request.url)

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO products (name, price, category)
                VALUES (?, ?, ?)
                """,
                (name, price, category),
            )
            conn.commit()

        flash("Product added!", "success")
        return redirect(url_for("index"))

    return render_template("import.html", theme=theme)


# ----------------------------------------
# CSV Import
# ----------------------------------------
@app.route("/import-file", methods=["GET", "POST"])
@admin_required
def import_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)

        try:
            stream = StringIO(file.stream.read().decode("utf-8"), newline=None)
            reader = csv.DictReader(stream)
            rows = list(reader)

            success = 0
            errors = []

            with get_db() as conn:
                for row in rows:
                    try:
                        name = _sanitize_string(row.get("name", ""), MAX_NAME)
                        price = _sanitize_price(row.get("price", 0))
                        category = _sanitize_string(row.get("category", ""), MAX_CATEGORY) or None

                        if not name:
                            raise ValueError("Missing name")

                        conn.execute(
                            """
                            INSERT OR IGNORE INTO products (name, price, category)
                            VALUES (?, ?, ?)
                            """,
                            (name, price, category),
                        )
                        success += 1

                    except Exception as e:
                        errors.append(f"{row} → {e}")

                conn.commit()

            msg = f"Imported: {success} successful."
            if errors:
                msg += f" {len(errors)} failed.<br>" + "<br>".join(errors[:10])
            flash(msg, "success" if success > 0 else "error")
            return redirect(url_for("index"))

        except Exception as e:
            flash(f"Import failed: {e}", "error")
            return redirect(request.url)

    return render_template("import_file.html", theme=theme)


# ----------------------------------------
# SEARCH
# ----------------------------------------
@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        query = _sanitize_query(request.form["query"])
        escaped = _escape_like(query)

        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT id, name, price, category FROM products
                WHERE name LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\'
                """,
                (f"%{escaped}%", f"%{escaped}%"),
            )
            rows = cursor.fetchall()

        products = [
            Product(
                id=row["id"],
                name=row["name"],
                price=row["price"],
                category=row["category"],
            ).to_dict()
            for row in rows
        ]

        return jsonify({"products": products})

    return render_template("search.html", theme=theme)


# ----------------------------------------
# Change Theme
# ----------------------------------------
@app.route("/change-theme", methods=["GET", "POST"])
@admin_required
def change_theme():
    global theme

    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)

        file = request.files["file"]

        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)

        try:
            file.save("config.xml")
            new_theme, _ = load_config()
            theme.clear()
            theme.update(new_theme)
            flash("Theme updated!", "success")
            return redirect(url_for("index"))

        except Exception as e:
            flash(f"Theme update error: {e}", "error")
            return redirect(request.url)

    return render_template("change_theme.html", theme=theme)


# ----------------------------------------
# Home
# ----------------------------------------
@app.route("/")
def index():
    return render_template("index.html", theme=theme)


# ----------------------------------------
# Run
# ----------------------------------------
if __name__ == "__main__":
    print("Theme loaded:", theme)
    print("Using SQLite")
    app.run(debug=True)
