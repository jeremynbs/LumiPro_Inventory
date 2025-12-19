# LumiPro Inventory Management System

**LumiPro** is a robust, technical asset-tracking platform designed for lighting production houses and rental firms. It bridges the gap between technical specifications and logistics, allowing you to manage everything from a light's IP rating to its current deployment on a client site.



---

## 🚀 Core Modules

### 1. Inventory Intelligence
The main dashboard provides a bird's-eye view of your business:
* **Asset Distribution**: Real-time stats on Available, Sold, and Maintenance units.
* **Logistics Tracking**: Monitor units currently "In Transit" or in "Repair."
* **Sales Breakdown**: See exactly which fixtures are deployed at which client sites.

### 2. Fixture Registry (Technical Datasheets)
Go beyond simple naming. Each fixture entry acts as a technical specification sheet:
* **Specs**: Track Wattage, IP Ratings, Color/Finish, and Beam Angles.
* **Commercials**: Manage Unit Cost (USD) vs. Selling Price (SGD/USD).
* **Relationships**: Link fixtures to specific Suppliers and Categories.

### 3. Stock Tracking & Serial Management
Track individual physical units with precision:
* **Unique Serials**: Every unit is tracked by its unique serial number.
* **Lifecycle Status**: Manage units through stages: `Warehouse` → `Sold` → `Maintenance`.
* **Bulk Operations**: Rapidly ingest hundreds of units via CSV upload.

### 4. Client & Warehouse Management
* **Client Sites**: View "On-Site" inventory for every client.
* **Warehouses**: Monitor stock volumes across different physical storage hubs.

---

## 🛠️ Technical Stack

* **Backend:** Python 3.x / Flask
* **Database:** SQLite3 (Relational mapping for Suppliers, Types, Fixtures, Stock, Warehouses, and Clients)
* **Frontend:** HTML5, Jinja2, Bootstrap 5, Bootstrap Icons
* **Data Science:** Pandas (for high-speed CSV processing and exports)

---

## 📦 Quick Start

### 1. Installation
Clone the repository and install the required dependencies:
```bash
git clone [https://github.com/your-username/lumipro-inventory.git](https://github.com/your-username/lumipro-inventory.git)
cd lumipro-inventory
pip install flask pandas
```

### 2. Database Setup

The application uses a local SQLite database (`database.db`).

* Ensure your schema is initialized.
* Place `database.db` in the root directory.

### 3. Run the App

```bash
python app.py
```

Access the dashboard at: `http://127.0.0.1:5000`

---

## 📁 Project Architecture

```text
├── app.py              # Application logic, SQL queries, and Routing
├── database.db         # SQLite Database
├── templates/          # Jinja2 UI Components
│   ├── layout.html     # Base Navigation & Styling
│   ├── inventory.html  # Dashboard
│   ├── view_fixtures.html # Technical Datasheet View
│   ├── manage_stock.html # Inventory Registry
│   └── ...             # Management pages for Clients, Warehouses, etc.
└── README.md           # Documentation

```

---

## 🛡️ Business Rules & Integrity

* **Smart Status**: Assigning a unit to a **Client** automatically updates its status to `SOLD` and clears its **Warehouse** location.
* **Deletion Safety**: The system prevents the deletion of Clients or Warehouses if they still have active equipment assigned to them.
* **Unique Serials**: Database constraints prevent duplicate serial numbers across the entire system.

---

## 📝 License

Proprietary software for **LumiPro**. All rights reserved.