-- Table: Suppliers (Factories)
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT,
    phone TEXT
);

-- Table: Fixture Types (e.g., Moving Head, Par, Bar)
CREATE TABLE IF NOT EXISTS fixture_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

-- Table: Fixtures (The Master Product List)

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    model_name TEXT,
    factory_model_name TEXT,
    sku TEXT UNIQUE,
    type_id INTEGER,
    supplier_id INTEGER,
    power_watts INTEGER,
    color TEXT,
    beam_angle TEXT,
    ip_rating TEXT,
    remarks TEXT,
    weight_kg REAL,
    cost REAL,
    price_sgd REAL,
    price_usd REAL,
    FOREIGN KEY (type_id) REFERENCES fixture_types (id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
);

-- Table: Warehouses
CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT
);

-- Updated Stock Table for Individual Unit Tracking
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    serial_number TEXT UNIQUE, 
    status TEXT NOT NULL DEFAULT 'FOR SALE', -- e.g., Available, Installed, Maintenance
    client_id INTEGER,                           -- Links to Clients table
    warehouse_id INTEGER,                        -- Current or Home warehouse
    install_date DATE,
    mfg_date DATE,                               -- Manufacturing Date
    FOREIGN KEY (fixture_id) REFERENCES fixtures (id),
    FOREIGN KEY (client_id) REFERENCES clients (id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

-- Ensure you have a Clients table
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_info TEXT
);