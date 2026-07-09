PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS User (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE,
    role TEXT NOT NULL DEFAULT 'MT' CHECK (role IN ('MT', 'SUP', 'ADM')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS Requisition (
    requisition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'Pending',
    requested_by INTEGER NOT NULL,
    approved_by INTEGER,
    approval_date TEXT,
    remarks TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (requested_by) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    FOREIGN KEY (approved_by) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Requisition_Item (
    requisition_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requisition_id INTEGER NOT NULL,
    reagent_id INTEGER NOT NULL,
    lot_number TEXT,
    quantity_requested REAL NOT NULL,
    quantity_received REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (requisition_id, reagent_id),
    FOREIGN KEY (requisition_id) REFERENCES Requisition(requisition_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (reagent_id) REFERENCES Reagent(reagent_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Supplier (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL UNIQUE,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS Reagent (
    reagent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reagent_name TEXT NOT NULL,
    reagent_type TEXT,
    manufacturer TEXT,
    lot_number TEXT,
    manufacturer_date TEXT,
    expiry_date TEXT,
    storage_condition TEXT,
    supplier TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS Inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reagent_id INTEGER NOT NULL,
    lot_number TEXT NOT NULL,
    expiry_date TEXT,
    quantity_on_hand REAL NOT NULL DEFAULT 0,
    minimum_level REAL NOT NULL DEFAULT 0,
    storage_location TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (reagent_id, lot_number),
    FOREIGN KEY (reagent_id) REFERENCES Reagent(reagent_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS QC_record (
    qc_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER NOT NULL,
    inspected_by_user_id INTEGER NOT NULL,
    qc_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result TEXT NOT NULL,
    remarks TEXT,
    temperature_c REAL,
    pH_value REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (inventory_id) REFERENCES Inventory(inventory_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (inspected_by_user_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Reagent_Request (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_number TEXT NOT NULL UNIQUE,
    requested_by_user_id INTEGER NOT NULL,
    request_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    needed_by_date TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    notes TEXT,
    inventory_deducted INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (requested_by_user_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Reagent_Request_Detail (
    request_detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    reagent_id INTEGER NOT NULL,
    requested_quantity REAL NOT NULL,
    approved_quantity REAL NOT NULL DEFAULT 0,
    unit_of_measure TEXT NOT NULL,
    remarks TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (request_id, reagent_id),
    FOREIGN KEY (request_id) REFERENCES Reagent_Request(request_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (reagent_id) REFERENCES Reagent(reagent_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Reagent_Receiving (
    receiving_id INTEGER PRIMARY KEY AUTOINCREMENT,
    receiving_number TEXT NOT NULL UNIQUE,
    request_detail_id INTEGER,
    supplier_id INTEGER NOT NULL,
    received_by_user_id INTEGER NOT NULL,
    inventory_id INTEGER,
    reagent_id INTEGER NOT NULL,
    received_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lot_number TEXT NOT NULL,
    expiry_date TEXT,
    quantity_received REAL NOT NULL,
    unit_cost REAL,
    invoice_number TEXT,
    remarks TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (request_detail_id) REFERENCES Reagent_Request_Detail(request_detail_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES Supplier(supplier_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    FOREIGN KEY (received_by_user_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    FOREIGN KEY (inventory_id) REFERENCES Inventory(inventory_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    FOREIGN KEY (reagent_id) REFERENCES Reagent(reagent_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Audit_Log (
    audit_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details TEXT,
    before_data TEXT,
    after_data TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_reagent_supplier
    ON Reagent (supplier);

CREATE INDEX IF NOT EXISTS idx_reagent_name
    ON Reagent (reagent_name);

CREATE INDEX IF NOT EXISTS idx_reagent_lot_number
    ON Reagent (lot_number);

CREATE INDEX IF NOT EXISTS idx_reagent_expiry_date
    ON Reagent (expiry_date);

CREATE INDEX IF NOT EXISTS idx_inventory_reagent_id
    ON Inventory (reagent_id);

CREATE INDEX IF NOT EXISTS idx_inventory_expiry_date
    ON Inventory (expiry_date);

CREATE INDEX IF NOT EXISTS idx_requisition_requested_by
    ON Requisition (requested_by);

CREATE INDEX IF NOT EXISTS idx_requisition_approved_by
    ON Requisition (approved_by);

CREATE INDEX IF NOT EXISTS idx_requisition_item_requisition_id
    ON Requisition_Item (requisition_id);

CREATE INDEX IF NOT EXISTS idx_requisition_item_reagent_id
    ON Requisition_Item (reagent_id);

CREATE INDEX IF NOT EXISTS idx_qc_record_inventory_id
    ON QC_record (inventory_id);

CREATE INDEX IF NOT EXISTS idx_qc_record_inspected_by_user_id
    ON QC_record (inspected_by_user_id);

CREATE INDEX IF NOT EXISTS idx_reagent_request_requested_by_user_id
    ON Reagent_Request (requested_by_user_id);

CREATE INDEX IF NOT EXISTS idx_request_detail_request_id
    ON Reagent_Request_Detail (request_id);

CREATE INDEX IF NOT EXISTS idx_request_detail_reagent_id
    ON Reagent_Request_Detail (reagent_id);

CREATE INDEX IF NOT EXISTS idx_receiving_request_detail_id
    ON Reagent_Receiving (request_detail_id);

CREATE INDEX IF NOT EXISTS idx_receiving_supplier_id
    ON Reagent_Receiving (supplier_id);

CREATE INDEX IF NOT EXISTS idx_receiving_received_by_user_id
    ON Reagent_Receiving (received_by_user_id);

CREATE INDEX IF NOT EXISTS idx_receiving_inventory_id
    ON Reagent_Receiving (inventory_id);

CREATE INDEX IF NOT EXISTS idx_receiving_reagent_id
    ON Reagent_Receiving (reagent_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_event_time
    ON Audit_Log (event_time DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
    ON Audit_Log (user_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity_type
    ON Audit_Log (entity_type);
