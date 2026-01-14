from flask import (
    Flask, 
    render_template, 
    request, 
    jsonify, 
    flash, 
    redirect, 
    url_for, 
    session)
import csv
from io import StringIO
import xml.etree.ElementTree as ET
from database import DatabaseManager
from contextlib import contextmanager
from models import Product
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'super-secret-key-for-flash-messages'  # required for flash


# ────────────────────────────────────────────────
# Load config from XML (theme + admin credentials)
# ────────────────────────────────────────────────
def load_config():
    defaults = {
        'theme': {
            'bg': '#f8f9fa', 'text': '#212529', 'accent': '#0d6efd',
            'btn_bg': '#0d6efd', 'btn_text': '#ffffff',
            'container': '#ffffff', 'border': '#dee2e6', 'font': 'system-ui, sans-serif'
        },
        'admin': {'username': 'admin', 'password': 'TXJXb2JiaW5z'}
    }

    try:
        tree = ET.parse('config.xml')
        root = tree.getroot()

        # Theme
        theme_node = root.find('theme')
        if theme_node is not None:
            for child in theme_node:
                if child.tag in defaults['theme']:
                    defaults['theme'][child.tag] = child.text

        # Admin credentials
        security = root.find('security')
        if security is not None:
            username = security.find('admin_username')
            password = security.find('admin_password')
            if username is not None and password is not None:
                defaults['admin']['username'] = username.text.strip()
                defaults['admin']['password'] = password.text.strip()

        return defaults['theme'], defaults['admin']

    except Exception as e:
        print(f"Error loading config.xml: {e} → using defaults")
        return defaults['theme'], defaults['admin']

theme, ADMIN_CREDENTIALS = load_config()

# # Load theme from XML (unchanged)
# def load_theme():
#     try:
#         tree = ET.parse('config.xml')
#         root = tree.getroot()
#         theme = root.find('theme')
#         return {
#             'bg': theme.find('background_color').text,
#             'text': theme.find('text_color').text,
#             'accent': theme.find('accent_color').text,
#             'btn_bg': theme.find('button_bg').text,
#             'btn_text': theme.find('button_text').text,
#             'container': theme.find('container_bg').text,
#             'border': theme.find('border_color').text,
#             'font': theme.find('font_family').text,
#         }
#     except:
#         return {
#             'bg': '#f8f9fa',
#             'text': '#212529',
#             'accent': '#0d6efd',
#             'btn_bg': '#0d6efd',
#             'btn_text': '#ffffff',
#             'container': '#ffffff',
#             'border': '#dee2e6',
#             'font': 'system-ui, sans-serif',
#         }
# theme = load_theme()

# Use SQLite — no config.ini needed anymore
# db_manager = DatabaseManager(db_file='grocery.db')
# Instead, create a context manager for per-request connections
@contextmanager
def get_db(db_file='grocery.db'):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Helper to get a cursor with context
def get_cursor():
    return get_db().__enter__().cursor()  # but we'll use conn directly in most cases

# ────────────────────────────────────────────────
# Simple login required decorator
# ────────────────────────────────────────────────
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin to access this page.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ────────────────────────────────────────────────
# Login / Logout routes
# ────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if (username == ADMIN_CREDENTIALS['username'] and
            password == ADMIN_CREDENTIALS['password']):
            session['admin_logged_in'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html', theme=theme)

@app.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# ────────────────────────────────────────────────
# Protected import routes
# ────────────────────────────────────────────────
@app.route('/import', methods=['GET', 'POST'])
@admin_required
def import_data():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        category = request.form.get('category', '')
        product = Product(name=name, price=price, category=category)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (name, price, category)
                VALUES (?, ?, ?)
            """, (product.name, product.price, product.category))
            product.id = cursor.lastrowid
            conn.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('import.html', theme=theme)

@app.route('/import-file', methods=['GET', 'POST'])
@admin_required
def import_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if file:
            try:
                stream = StringIO(file.stream.read().decode('utf-8'), newline=None)
                csv_reader = csv.DictReader(stream)
                products = [dict(row) for row in csv_reader]

                success = 0
                errors = []

                with get_db() as conn:
                    for prod in products:
                        try:
                            name = prod.get('name', '').strip()
                            price = float(prod.get('price', 0))
                            category = prod.get('category', '').strip() or None
                            if not name:
                                raise ValueError("Missing name")
                            conn.execute("""
                                INSERT OR IGNORE INTO products (name, price, category)
                                VALUES (?, ?, ?)
                            """, (name, price, category))
                            success += 1
                        except Exception as e:
                            errors.append(f"Row error: {prod} → {str(e)}")
                    conn.commit()

                msg = f"Import complete: {success} products added."
                if errors:
                    msg += f" {len(errors)} failed.<br><br>Errors:<br>" + "<br>".join(errors[:8])
                    if len(errors) > 8:
                        msg += f"<br>... and {len(errors)-8} more."
                flash(msg, 'success' if success > 0 else 'error')
                return redirect(url_for('index'))

            except Exception as e:
                flash(f'Import failed: {str(e)}', 'error')
                return redirect(request.url)

        flash('Please upload a .csv file', 'error')
        return redirect(request.url)

    return render_template('import_file.html', theme=theme)

# ────────────────────────────────────────────────
# Unprotected routes
# ────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html', theme=theme)

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form['query']
        products = []

        with get_db() as conn:
            cursor = conn.execute("""
                SELECT id, name, price, category FROM products
                WHERE name LIKE ? OR category LIKE ?
            """, (f'%{query}%', f'%{query}%'))
            rows = cursor.fetchall()
            products = [Product(
                id=row['id'],
                name=row['name'],
                price=row['price'],
                category=row['category']
            ) for row in rows]

        return jsonify({'products': [p.to_dict() for p in products]})

    return render_template('search.html', theme=theme)

@app.route('/change-theme', methods=['GET', 'POST'])
def change_theme():
    global theme  # we'll update the global theme variable

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if file:
            try:
                # Save the uploaded file as config.xml (overwrite)
                filename = 'config.xml'
                file.save(filename)

                # Immediately reload the theme from the new file
                new_theme, _ = load_config()  # we only care about theme part
                theme.clear()
                theme.update(new_theme)

                flash('Theme updated successfully! Refresh any page to see changes.', 'success')
                return redirect(url_for('index'))

            except ET.ParseError:
                flash('Invalid XML format in the uploaded file.', 'error')
            except Exception as e:
                flash(f'Error applying new theme: {str(e)}', 'error')

            # If failed, don't keep the bad file – but for simplicity we keep it
            # You could add os.remove(filename) here on failure if desired
        else:
            flash('Please upload a valid .xml file', 'error')

        return redirect(request.url)

    return render_template('change_theme.html', theme=theme)

if __name__ == '__main__':
    print("Theme loaded:", theme)
    print("Using SQLite database: grocery.db")
    app.run(debug=True)