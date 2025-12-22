import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, g, Response
from datetime import datetime
import csv
import pandas as pd
import io
import os

# Define the absolute path to your database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'database.db')

app = Flask(__name__)
DATABASE = 'database.db'

application = app  # For passenger_wsgi compatibility

app.secret_key = 'lamdashirtproductions' # Replace with a random string


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        with open('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        print("Database Initialized!")

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('inventory'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< CLIENT <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

@app.route('/clients')
def manage_clients():
    """List all clients and their contact information."""
    db = get_db()
    # Fetch clients along with a count of how many units they currently have
    clients = db.execute("""
        SELECT 
            c.*, 
            COUNT(s.id) as unit_count
        FROM clients c
        LEFT JOIN stock s ON c.id = s.client_id
        GROUP BY c.id
    """).fetchall()
    
    return render_template('manage_clients.html', 
                           data=clients, 
                           title="Clients")

# --- CLIENT CRUD OPERATIONS ---

# 1. ADD CLIENT

@app.route('/clients/add', methods=['POST'])
def add_client():
    """Create a new client record."""
    name = request.form.get('name')
    contact_info = request.form.get('contact_info')
    
    if not name:
        flash("Client name is required.", "danger")
        return redirect(url_for('manage_clients'))
        
    db = get_db()
    db.execute("INSERT INTO clients (name, contact_info) VALUES (?, ?)", 
               (name, contact_info))
    db.commit()
    flash(f"Client '{name}' added successfully.", "success")
    return redirect(url_for('manage_clients'))

# 2. VIEW CLIENT DETAILS

@app.route('/clients/view/<int:id>')
def view_client(id):
    """View details of a specific client and the equipment installed at their site."""
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id = ?", (id,)).fetchone()
    
    if not client:
        flash("Client not found.", "danger")
        return redirect(url_for('manage_clients'))
    
    # Fetch all stock units assigned to this client
    # We join with fixtures to get the readable names of the equipment
    stocks = db.execute("""
        SELECT s.*, f.name as fixture_name 
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        WHERE s.client_id = ?
    """, (id,)).fetchall()
    
    return render_template('view_client.html', 
                           client=client, 
                           stocks=stocks)

# 3. EDIT CLIENT

@app.route('/clients/edit/<int:id>', methods=['POST'])
def edit_client(id):
    """Update existing client information."""
    name = request.form.get('name')
    contact_info = request.form.get('contact_info')
    
    db = get_db()
    db.execute("UPDATE clients SET name = ?, contact_info = ? WHERE id = ?", 
               (name, contact_info, id))
    db.commit()
    flash("Client information updated.", "success")
    return redirect(url_for('manage_clients'))

# 4. DELETE CLIENT

@app.route('/clients/delete/<int:id>', methods=['POST'])
def delete_client(id):
    """Delete a client record after checking for assigned equipment."""
    db = get_db()
    
    # Prevent deletion if client has equipment assigned to them
    check = db.execute("SELECT COUNT(*) as count FROM stock WHERE client_id = ?", (id,)).fetchone()
    if check['count'] > 0:
        flash("Cannot delete client. Please reassign or remove their equipment first.", "warning")
        return redirect(url_for('manage_clients'))
        
    db.execute("DELETE FROM clients WHERE id = ?", (id,))
    db.commit()
    flash("Client deleted successfully.", "success")
    return redirect(url_for('manage_clients'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< FIXTURE TYPES <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

@app.route('/fixture-types')
def manage_fixture_types():
    """List all fixture categories and count how many models belong to each."""
    db = get_db()
    # Fetch types with a count of linked fixture models
    types = db.execute("""
        SELECT 
            t.id, t.name, 
            COUNT(f.id) as model_count
        FROM fixture_types t
        LEFT JOIN fixtures f ON t.id = f.type_id
        GROUP BY t.id
    """).fetchall()
    
    return render_template('manage_fixture_types.html', types=types)

# --- FIXTURE TYPE CRUD OPERATIONS ---

# 1. ADD FIXTURE TYPE

@app.route('/fixture-types/add', methods=['POST'])
def add_fixture_type():
    """Add a new category for equipment."""
    name = request.form.get('name')
    
    if not name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for('manage_fixture_types'))
        
    db = get_db()
    try:
        db.execute("INSERT INTO fixture_types (name) VALUES (?)", (name,))
        db.commit()
        flash(f"Category '{name}' created.", "success")
    except sqlite3.IntegrityError:
        flash("This category already exists.", "warning")
        
    return redirect(url_for('manage_fixture_types'))

# 2. EDIT FIXTURE TYPE

@app.route('/fixture-types/edit/<int:id>', methods=['POST'])
def edit_fixture_type(id):
    """Rename an existing category."""
    new_name = request.form.get('name')
    db = get_db()
    db.execute("UPDATE fixture_types SET name = ? WHERE id = ?", (new_name, id))
    db.commit()
    flash("Category updated successfully.", "success")
    return redirect(url_for('manage_fixture_types'))

# 3. DELETE FIXTURE TYPE

@app.route('/fixture-types/delete/<int:id>', methods=['POST'])
def delete_fixture_type(id):
    """Delete a category only if no fixture models are assigned to it."""
    db = get_db()
    
    # Check if any fixture models are using this type
    usage_check = db.execute("SELECT COUNT(*) as count FROM fixtures WHERE type_id = ?", (id,)).fetchone()
    
    if usage_check['count'] > 0:
        flash("Cannot delete: This category is still assigned to active fixture models.", "danger")
    else:
        db.execute("DELETE FROM fixture_types WHERE id = ?", (id,))
        db.commit()
        flash("Category removed.", "success")
        
    return redirect(url_for('manage_fixture_types'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< FIXTURES <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

@app.route('/fixtures')
def manage_fixtures():
    db = get_db()
    # 1. Fetch Master Fixture List
    fixtures = db.execute("""
        SELECT f.*, t.name as category_name, s.name as supplier_name,
        (SELECT COUNT(*) FROM stock WHERE fixture_id = f.id) as inventory_count
        FROM fixtures f
        LEFT JOIN fixture_types t ON f.type_id = t.id
        LEFT JOIN suppliers s ON f.supplier_id = s.id
        ORDER BY f.name ASC
    """).fetchall()

    # 2. Fetch Stock Counts grouped by Fixture and Warehouse
    # This creates a mapping of where everything is
    stock_distribution = db.execute("""
        SELECT s.fixture_id, w.name as warehouse_name, COUNT(s.id) as quantity
        FROM stock s
        JOIN warehouses w ON s.warehouse_id = w.id
        WHERE s.status IN ('In Warehouse', 'FOR SALE')
        GROUP BY s.fixture_id, w.id
    """).fetchall()

    # Convert distribution to a dictionary for easy template access
    # Format: {fixture_id: [ {'warehouse_name': 'Main', 'quantity': 5}, ... ]}
    dist_map = {}
    for row in stock_distribution:
        fid = row['fixture_id']
        if fid not in dist_map:
            dist_map[fid] = []
        dist_map[fid].append({'warehouse_name': row['warehouse_name'], 'quantity': row['quantity']})

    types = db.execute("SELECT * FROM fixture_types").fetchall()
    suppliers = db.execute("SELECT * FROM suppliers").fetchall()
    
    return render_template('manage_fixtures.html', 
                           fixtures=fixtures, 
                           types=types, 
                           suppliers=suppliers, 
                           dist_map=dist_map)

# --- FIXTURE CRUD OPERATIONS ---

# 1. ADD FIXTURE

@app.route('/fixtures/add', methods=['GET', 'POST'])
def add_fixture():
    """Form to add a new fixture model to the master database."""
    db = get_db()
    if request.method == 'POST':
        # Collect form data
        data = (
            request.form.get('name'),
            request.form.get('model_name'),
            request.form.get('factory_model_name'),
            request.form.get('sku'),
            request.form.get('type_id'),
            request.form.get('supplier_id'),
            request.form.get('power_watts'),
            request.form.get('color'),
            request.form.get('beam_angle'),
            request.form.get('ip_rating'),
            request.form.get('weight_kg'),
            request.form.get('cost'),
            request.form.get('price_sgd'),
            request.form.get('price_usd'),
            request.form.get('remarks')
        )
        
        try:
            db.execute("""
                INSERT INTO fixtures (
                    name, model_name, factory_model_name, sku, type_id, 
                    supplier_id, power_watts, color, beam_angle, ip_rating, weight_kg, 
                    cost, price_sgd, price_usd, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            db.commit()
            flash(f"Fixture model '{request.form.get('name')}' added.", "success")
            return redirect(url_for('manage_fixtures'))
        except sqlite3.IntegrityError:
            flash("SKU must be unique.", "danger")
            
    # Need dropdown data for the form
    types = db.execute("SELECT * FROM fixture_types").fetchall()
    suppliers = db.execute("SELECT * FROM suppliers").fetchall()
    return render_template('edit_fixture.html', types=types, suppliers=suppliers, action="Add")

# 2. VIEW FIXTURE DETAILS

@app.route('/fixtures/view/<int:id>')
def view_fixture(id):
    """Detailed view of a specific fixture model's specifications."""
    db = get_db()
    fixture = db.execute("""
        SELECT f.*, t.name as category_name, s.name as supplier_name
        FROM fixtures f
        LEFT JOIN fixture_types t ON f.type_id = t.id
        LEFT JOIN suppliers s ON f.supplier_id = s.id
        WHERE f.id = ?
    """, (id,)).fetchone()
    
    if not fixture:
        flash("Fixture model not found.", "danger")
        return redirect(url_for('manage_fixtures'))
        
    return render_template('view_fixtures.html', fixture=fixture)

# 3. EDIT FIXTURE

@app.route('/fixtures/edit/<int:id>', methods=['GET', 'POST'])
def edit_fixture(id):
    """Edit an existing fixture model's specifications."""
    db = get_db()
    if request.method == 'POST':
        data = (
            request.form.get('name'),
            request.form.get('model_name'),
            request.form.get('factory_model_name'),
            request.form.get('sku'),
            request.form.get('type_id'),
            request.form.get('supplier_id'),
            request.form.get('power_watts'),
            request.form.get('color'),
            request.form.get('beam_angle'),
            request.form.get('ip_rating'),
            request.form.get('weight_kg'),
            request.form.get('cost'),
            request.form.get('price_sgd'),
            request.form.get('price_usd'),
            request.form.get('remarks'),
            id
        )
        db.execute("""
            UPDATE fixtures SET 
                name=?, model_name=?, factory_model_name=?, sku=?, type_id=?, 
                supplier_id=?, power_watts=?, color=?, beam_angle=?, ip_rating=?, weight_kg=?,
                cost=?, price_sgd=?, price_usd=?, remarks=?
            WHERE id=?
        """, data)
        db.commit()
        flash("Fixture model updated.", "success")
        return redirect(url_for('manage_fixtures'))

    fixture = db.execute("SELECT * FROM fixtures WHERE id = ?", (id,)).fetchone()
    types = db.execute("SELECT * FROM fixture_types").fetchall()
    suppliers = db.execute("SELECT * FROM suppliers").fetchall()
    return render_template('edit_fixture.html', fixture=fixture, types=types, suppliers=suppliers, action="Edit")

# 4. DELETE FIXTURE

@app.route('/fixtures/delete/<int:id>', methods=['POST'])
def delete_fixture(id):
    """Delete a fixture model if no inventory exists for it."""
    db = get_db()
    check = db.execute("SELECT COUNT(*) as count FROM stock WHERE fixture_id = ?", (id,)).fetchone()
    if check['count'] > 0:
        flash("Cannot delete: Inventory units exist for this model. Remove stock first.", "danger")
    else:
        db.execute("DELETE FROM fixtures WHERE id = ?", (id,))
        db.commit()
        flash("Fixture model removed from database.", "success")
    return redirect(url_for('manage_fixtures'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< SUPPLIER <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

@app.route('/suppliers')
def manage_suppliers():
    """List all suppliers/factories and their contact details."""
    db = get_db()
    # Fetch suppliers and count how many unique fixture profiles are linked to them
    suppliers = db.execute("""
        SELECT 
            s.*, 
            COUNT(f.id) as fixture_count
        FROM suppliers s
        LEFT JOIN fixtures f ON s.id = f.supplier_id
        GROUP BY s.id
    """).fetchall()
    
    return render_template('manage_suppliers.html', suppliers=suppliers)

# --- SUPPLIER CRUD OPERATIONS ---

# 1. ADD SUPPLIER

@app.route('/suppliers/add', methods=['POST'])
def add_supplier():
    """Add a new supplier/factory record."""
    name = request.form.get('name')
    contact_person = request.form.get('contact_person')
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    if not name:
        flash("Supplier name is required.", "danger")
        return redirect(url_for('manage_suppliers'))
        
    db = get_db()
    db.execute("""
        INSERT INTO suppliers (name, contact_person, email, phone) 
        VALUES (?, ?, ?, ?)
    """, (name, contact_person, email, phone))
    db.commit()
    flash(f"Supplier '{name}' added successfully.", "success")
    return redirect(url_for('manage_suppliers'))

# 2. EDIT SUPPLIER

@app.route('/suppliers/edit/<int:id>', methods=['POST'])
def edit_supplier(id):
    """Update supplier contact details."""
    name = request.form.get('name')
    contact_person = request.form.get('contact_person')
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    db = get_db()
    db.execute("""
        UPDATE suppliers 
        SET name = ?, contact_person = ?, email = ?, phone = ? 
        WHERE id = ?
    """, (name, contact_person, email, phone, id))
    db.commit()
    flash("Supplier information updated.", "success")
    return redirect(url_for('manage_suppliers'))

# 3. DELETE SUPPLIER

@app.route('/suppliers/delete/<int:id>', methods=['POST'])
def delete_supplier(id):
    """Delete a supplier only if no fixture profiles are linked to them."""
    db = get_db()
    
    # Check for linked fixtures
    check = db.execute("SELECT COUNT(*) as count FROM fixtures WHERE supplier_id = ?", (id,)).fetchone()
    if check['count'] > 0:
        flash("Cannot delete: This supplier has linked fixture profiles.", "warning")
        return redirect(url_for('manage_suppliers'))
        
    db.execute("DELETE FROM suppliers WHERE id = ?", (id,))
    db.commit()
    flash("Supplier deleted.", "success")
    return redirect(url_for('manage_suppliers'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< WAREHOUSE <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

@app.route('/warehouses')
def manage_warehouses():
    """List all warehouses and the count of units currently in stock there."""
    db = get_db()
    # Fetch warehouses with a count of active stock units
    warehouses = db.execute("""
        SELECT 
            w.id, w.name, w.location, 
            COUNT(s.id) as unit_count
        FROM warehouses w
        LEFT JOIN stock s ON w.id = s.warehouse_id
        GROUP BY w.id
    """).fetchall()
    
    return render_template('manage_warehouses.html', warehouses=warehouses)

# --- WAREHOUSE CRUD OPERATIONS ---

# 1. ADD WAREHOUSE

@app.route('/warehouses/add', methods=['POST'])
def add_warehouse():
    """Create a new storage location."""
    name = request.form.get('name')
    location = request.form.get('location')
    
    if not name:
        flash("Warehouse name is required.", "danger")
        return redirect(url_for('manage_warehouses'))
        
    db = get_db()
    db.execute("INSERT INTO warehouses (name, location) VALUES (?, ?)", (name, location))
    db.commit()
    flash(f"Warehouse '{name}' added successfully.", "success")
    return redirect(url_for('manage_warehouses'))

# 2. VIEW WAREHOUSE DETAILS

@app.route('/warehouses/view/<int:id>')
def view_warehouse(id):
    """View detailed inventory list for a specific warehouse."""
    db = get_db()
    warehouse = db.execute("SELECT * FROM warehouses WHERE id = ?", (id,)).fetchone()
    
    if not warehouse:
        flash("Warehouse not found.", "danger")
        return redirect(url_for('manage_warehouses'))
    
    # Fetch all stock units in this warehouse with fixture names
    stocks = db.execute("""
        SELECT s.*, f.name as fixture_name 
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        WHERE s.warehouse_id = ?
    """, (id,)).fetchall()
    
    return render_template('view_warehouse.html', warehouse=warehouse, stocks=stocks)

# 3. EDIT WAREHOUSE

@app.route('/warehouses/edit/<int:id>', methods=['POST'])
def edit_warehouse(id):
    """Update warehouse name or address."""
    name = request.form.get('name')
    location = request.form.get('location')
    
    db = get_db()
    db.execute("UPDATE warehouses SET name = ?, location = ? WHERE id = ?", (name, location, id))
    db.commit()
    flash("Warehouse updated.", "success")
    return redirect(url_for('manage_warehouses'))

# 4. DELETE WAREHOUSE

@app.route('/warehouses/delete/<int:id>', methods=['POST'])
def delete_warehouse(id):
    """Delete a warehouse only if it is completely empty."""
    db = get_db()
    
    # Integrity check: is there stock in this warehouse?
    check = db.execute("SELECT COUNT(*) as count FROM stock WHERE warehouse_id = ?", (id,)).fetchone()
    if check['count'] > 0:
        flash("Cannot delete: This warehouse still contains stock units.", "warning")
        return redirect(url_for('manage_warehouses'))
        
    db.execute("DELETE FROM warehouses WHERE id = ?", (id,))
    db.commit()
    flash("Warehouse removed.", "success")
    return redirect(url_for('manage_warehouses'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< STOCK <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\

@app.route('/stock')
def manage_stock():
    """List all individual stock units with their status and location."""
    db = get_db()
    # Fetch all stock units with fixture names, warehouse names, and client names
    stocks = db.execute("""
        SELECT 
            s.*, 
            f.name as fixture_name,
            w.name as warehouse_name,
            c.name as client_name
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        LEFT JOIN warehouses w ON s.warehouse_id = w.id
        LEFT JOIN clients c ON s.client_id = c.id
        ORDER BY s.id DESC
    """).fetchall()
    
    return render_template('manage_stocks.html', stocks=stocks)

# --- STOCK CRUD OPERATIONS ---

# 1. ADD STOCK

@app.route('/stock/add', methods=['GET', 'POST'])
def add_stock():
    """Add a new individual unit to the inventory."""
    db = get_db()
    if request.method == 'POST':
        fixture_id = request.form.get('fixture_id')
        serial_number = request.form.get('serial_number')
        warehouse_id = request.form.get('warehouse_id')
        mfg_date = request.form.get('mfg_date')
        
        try:
            db.execute("""
                INSERT INTO stock (fixture_id, serial_number, warehouse_id, mfg_date, status)
                VALUES (?, ?, ?, ?, 'FOR SALE')
            """, (fixture_id, serial_number, warehouse_id, mfg_date))
            db.commit()
            flash(f"Unit {serial_number} added to inventory.", "success")
            return redirect(url_for('manage_stock'))
        except sqlite3.IntegrityError:
            flash("Serial Number must be unique.", "danger")

    fixtures = db.execute("SELECT id, name FROM fixtures").fetchall()
    warehouses = db.execute("SELECT id, name FROM warehouses").fetchall()
    return render_template('edit_stock.html', fixtures=fixtures, warehouses=warehouses, action="Add")

# 1.2 ADD BULK STOCK

@app.route('/stock/bulk-upload', methods=['POST'])
def bulk_upload_stock():
    """
    Handles bulk insertion of stock units via CSV.
    Transforms manufacturing dates into database-friendly format.
    """
    if 'file' not in request.files:
        flash("No file part in the request.", "danger")
        return redirect(url_for('add_stock'))
        
    file = request.files['file']
    selected_fixture_id = request.form.get('fixture_id')
    selected_warehouse_id = request.form.get('warehouse_id')

    if not selected_fixture_id or not selected_warehouse_id:
        flash("Please select both a Fixture Model and a Target Warehouse.", "danger")
        return redirect(url_for('add_stock'))

    if file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('add_stock'))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        
        required_headers = {'serial_number'}
        if not required_headers.issubset(set(reader.fieldnames)):
            flash(f"Invalid CSV format. Required headers: {', '.join(required_headers)}", "danger")
            return redirect(url_for('add_stock'))

        db = get_db()
        import_count = 0
        errors = []

        try:
            for row_idx, row in enumerate(reader, start=2):
                try:
                    sn = row['serial_number'].strip()
                    raw_mfg = row.get('mfg_date', '').strip()
                    
                    # Transform the date format automatically
                    standardized_mfg = parse_date(raw_mfg)

                    if not sn:
                        errors.append(f"Row {row_idx}: Serial number is empty.")
                        continue

                    db.execute("""
                        INSERT INTO stock (fixture_id, serial_number, warehouse_id, mfg_date, status)
                        VALUES (?, ?, ?, ?, 'FOR SALE')
                    """, (selected_fixture_id, sn, selected_warehouse_id, standardized_mfg))
                    import_count += 1
                    
                except sqlite3.IntegrityError:
                    errors.append(f"Row {row_idx}: Serial Number '{sn}' already exists.")
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")

            db.commit()
            
            if errors:
                flash(f"Imported {import_count} units. {len(errors)} rows had errors.", "warning")
                for err in errors[:3]:
                    flash(err, "danger")
            else:
                flash(f"Successfully imported {import_count} units.", "success")

        except Exception as e:
            db.rollback()
            flash(f"Database error: {str(e)}", "danger")

    except Exception as e:
        flash(f"File processing error: {str(e)}", "danger")

    return redirect(url_for('manage_stock'))

# 2. EDIT STOCK

@app.route('/stock/edit/<int:id>', methods=['GET', 'POST'])
def edit_stock(id):
    """Update status, location, or assignment of a specific unit."""
    db = get_db()
    if request.method == 'POST':
        # Update logic including movement between warehouse and client
        status = request.form.get('status')
        warehouse_id = request.form.get('warehouse_id') or None
        client_id = request.form.get('client_id') or None
        install_date = request.form.get('install_date') or None
        
        db.execute("""
            UPDATE stock SET 
                status = ?, 
                warehouse_id = ?, 
                client_id = ?, 
                install_date = ?
            WHERE id = ?
        """, (status, warehouse_id, client_id, install_date, id))
        db.commit()
        flash("Unit status updated.", "success")
        return redirect(url_for('manage_stock'))

    stock = db.execute("SELECT * FROM stock WHERE id = ?", (id,)).fetchone()
    fixtures = db.execute("SELECT id, name FROM fixtures").fetchall()
    warehouses = db.execute("SELECT id, name FROM warehouses").fetchall()
    clients = db.execute("SELECT id, name FROM clients").fetchall()
    
    return render_template('edit_stock.html', 
                           stock=stock, 
                           fixtures=fixtures, 
                           warehouses=warehouses, 
                           clients=clients, 
                           action="Edit")

def parse_date(date_str):
    """Utility to normalize date strings to YYYY-MM-DD."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str

@app.route('/stock/export-csv')
def export_stock_csv():
    """Generates a CSV of all current stock for bulk editing."""
    db = get_db()
    stocks = db.execute("""
        SELECT 
            s.serial_number, 
            f.name as fixture_name, 
            s.status, 
            s.mfg_date,
            w.name as warehouse_name,
            c.name as client_name,
            s.install_date
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        LEFT JOIN warehouses w ON s.warehouse_id = w.id
        LEFT JOIN clients c ON s.client_id = c.id
    """).fetchall()

    def generate():
        data = io.StringIO()
        writer = csv.writer(data)
        # Headers
        writer.writerow(['serial_number', 'fixture_name', 'status', 'mfg_date', 'warehouse_name', 'client_name', 'install_date'])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        for s in stocks:
            writer.writerow([
                s['serial_number'], 
                s['fixture_name'], 
                s['status'], 
                s['mfg_date'],
                s['warehouse_name'] or '',
                s['client_name'] or '',
                s['install_date'] or ''
            ])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-disposition": "attachment; filename=lumi_stock_export.csv"}
    )

@app.route('/stock/bulk-update-csv', methods=['POST'])
def bulk_update_stock_csv():
    """Processes a CSV to update stock. Automatically creates missing Clients/Warehouses."""
    if 'file' not in request.files:
        flash("No file provided.", "danger")
        return redirect(url_for('manage_stock'))
        
    file = request.files['file']
    if file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('manage_stock'))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        
        db = get_db()
        update_count = 0
        new_clients = 0
        new_warehouses = 0
        errors = []

        # Required headers for matching and updating
        required = {'serial_number', 'status'}
        if not required.issubset(set(reader.fieldnames)):
            flash(f"CSV missing required columns: {required}", "danger")
            return redirect(url_for('manage_stock'))

        for row_idx, row in enumerate(reader, start=2):
            sn = row['serial_number'].strip()
            new_status = row['status'].strip().upper()
            raw_mfg = row.get('mfg_date', '').strip()
            raw_install = row.get('install_date', '').strip()
            w_name = row.get('warehouse_name', '').strip()
            c_name = row.get('client_name', '').strip()
            f_name = row.get('fixture_name', '').strip()
            
            if not sn:
                continue

            # Check if stock unit exists
            unit = db.execute("SELECT id FROM stock WHERE serial_number = ?", (sn,)).fetchone()
            if not unit:
                errors.append(f"Row {row_idx}: Serial '{sn}' not found.")
                continue

            # 1. Handle Warehouse (Get or Create)
            warehouse_id = None
            if w_name:
                w_row = db.execute("SELECT id FROM warehouses WHERE name = ?", (w_name,)).fetchone()
                if w_row:
                    warehouse_id = w_row['id']
                else:
                    # Create new warehouse
                    cursor = db.execute("INSERT INTO warehouses (name) VALUES (?)", (w_name,))
                    warehouse_id = cursor.lastrowid
                    new_warehouses += 1

            # 2. Handle Client (Get or Create)
            client_id = None
            if c_name:
                c_row = db.execute("SELECT id FROM clients WHERE name = ?", (c_name,)).fetchone()
                if c_row:
                    client_id = c_row['id']
                else:
                    # Create new client
                    cursor = db.execute("INSERT INTO clients (name) VALUES (?)", (c_name,))
                    client_id = cursor.lastrowid
                    new_clients += 1

            # 2.5. Hanndle Fixture Name Verification (Optional)
            if f_name:
                f_row = db.execute("SELECT id FROM fixtures WHERE name = ?", (f_name,)).fetchone()
                if not f_row:
                    errors.append(f"Row {row_idx}: Fixture '{f_name}' not found.")
                    continue

            # 3. Normalize dates
            mfg_date = parse_date(raw_mfg)
            install_date = parse_date(raw_install)

            # 4. Perform update
            db.execute("""
                UPDATE stock SET 
                    status = ?, 
                    mfg_date = COALESCE(?, mfg_date), 
                    install_date = ?, 
                    warehouse_id = ?, 
                    client_id = ?, 
                    fixture_id = ?
                WHERE serial_number = ?
            """, (new_status, mfg_date, install_date, warehouse_id, client_id, f_row['id'], sn))
            
            update_count += 1

        db.commit()
        
        msg = f"Updated {update_count} units."
        if new_clients > 0 or new_warehouses > 0:
            msg += f" Created {new_clients} new clients and {new_warehouses} new warehouses."
        
        if errors:
            flash(f"{msg} Some errors occurred.", "warning")
            for err in errors[:3]: flash(err, "danger") 
        else:
            flash(msg, "success")

    except Exception as e:
        flash(f"Error processing CSV: {str(e)}", "danger")

    return redirect(url_for('manage_stock'))

# 3. DELETE STOCK

@app.route('/stock/delete/<int:id>', methods=['POST'])
def delete_stock(id):
    """Remove a unit from the database."""
    db = get_db()
    db.execute("DELETE FROM stock WHERE id = ?", (id,))
    db.commit()
    flash("Unit removed from inventory.", "success")
    return redirect(url_for('manage_stock'))

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< OTHERS <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

def parse_date(date_str):
    """
    Attempts to parse a date string from various common formats
    and return a standardized YYYY-MM-DD string.
    """
    if not date_str or not date_str.strip():
        return None
        
    date_str = date_str.strip()
    # List of common formats found in CSVs
    formats = [
        '%Y-%m-%d',   # 2023-12-31
        '%d/%m/%Y',   # 31/12/2023
        '%m/%d/%Y',   # 12/31/2023
        '%d-%m-%Y',   # 31-12-2023
        '%Y/%m/%d',   # 2023/12/31
        '%d %b %Y',   # 31 Dec 2023
        '%b %d, %Y'   # Dec 31, 2023
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If no formats match, return original (or handle as error)
    return date_str

# --------------------------------------------------------------------------------------------------# -------------------------------- INVENTORY MANAGEMENT ROUTES --------------------------------
# 1. VIEW: All Inventory (Combined)
@app.route('/inventory')
def inventory():
    db = get_db()
    
    # Capture current timestamp
    now = datetime.now()
    
    # 1. Global Stats
    # Note: Added 'FOR SALE' to the logic so it counts in Global Stats
    stats = db.execute("""
        SELECT 
            COUNT(*) as total_units,
            COALESCE(SUM(CASE WHEN status IN ('In Warehouse', 'FOR SALE') THEN 1 ELSE 0 END), 0) as in_stock,
            COALESCE(SUM(CASE WHEN status IN ('Sold', 'sold', 'SOLD') THEN 1 ELSE 0 END), 0) as total_sold,
            COALESCE(SUM(CASE WHEN status IN ('Maintenance', 'Repair', 'MAINTENANCE', 'REPAIR') THEN 1 ELSE 0 END), 0) as in_repair
        FROM stock
    """).fetchone()

    # 2. Get Warehouses
    warehouses = db.execute("SELECT * FROM warehouses ORDER BY name ASC").fetchall()
    
    # Updated to include 'FOR SALE' status
    inventory_split = db.execute("""
        SELECT 
            w.id as warehouse_id, 
            f.name as fixture_name, 
            f.model_name, 
            COUNT(s.id) as qty
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        JOIN warehouses w ON s.warehouse_id = w.id
        WHERE s.status IN ('In Warehouse', 'FOR SALE')
        GROUP BY w.id, f.id
    """).fetchall()

    # 3. Logistics & Maintenance Data
    logistics_data = db.execute("""
        SELECT 
            s.status,
            f.name as fixture_name,
            s.serial_number,
            COALESCE(w.name, 'Transit') as last_warehouse,
            s.mfg_date
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        LEFT JOIN warehouses w ON s.warehouse_id = w.id
        WHERE UPPER(s.status) IN ('MAINTENANCE', 'IN TRANSIT', 'REPAIR')
        ORDER BY s.status ASC
    """).fetchall()

    # 4. Sales Breakdown by Client
    sales_split = db.execute("""
        SELECT 
            c.id as client_id,
            c.name as client_name,
            f.name as fixture_name,
            COUNT(s.id) as qty
        FROM stock s
        JOIN fixtures f ON s.fixture_id = f.id
        JOIN clients c ON s.client_id = c.id
        WHERE UPPER(s.status) = 'SOLD'
        GROUP BY c.id, f.id
    """).fetchall()

    sold_to_clients = db.execute("""
        SELECT DISTINCT c.id, c.name 
        FROM clients c
        JOIN stock s ON c.id = s.client_id
        WHERE UPPER(s.status) = 'SOLD'
        ORDER BY c.name ASC
    """).fetchall()

    db.close()
    return render_template('inventory.html', 
                           stats=stats, 
                           warehouses=warehouses, 
                           inventory_split=inventory_split,
                           logistics_data=logistics_data,
                           sales_split=sales_split,
                           sold_to_clients=sold_to_clients,
                           now=now,
                           title="Inventory")

# -------------------------------- RUN THE APP --------------------------------

if __name__ == "__main__":
    init_db()  # Ensure DB is initialized on startup
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)