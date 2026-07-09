"""Application data and business logic."""

from datetime import date, datetime
import random
import json
import os
from pathlib import Path
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = BASE_DIR / "database.db"
# Keep the project database as the default so deployed apps show the same seed/data
# that is committed in the repository unless an explicit DATABASE_PATH is provided.
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))
AUTO_SEED_DEMO_DATA = os.environ.get("AUTO_SEED_DEMO_DATA", "1") == "1"
SCHEMA_PATH = BASE_DIR / "schema.sql"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin@123"
DEFAULT_ADMIN_FULL_NAME = "System Administrator"
ROLE_USERNAME_PREFIXES = {
    "MT": "MT",
    "SUP": "SUP",
    "ADM": "ADM",
}


def get_db_connection():
    """Return a SQLite connection with dictionary-style rows."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create the database file, load schema, and seed the default admin."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.touch(exist_ok=True)

    with get_db_connection() as connection:
        with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
            connection.executescript(schema_file.read())

        _migrate_reagent_compatibility(connection)
        _migrate_qc_record(connection)
        _migrate_request_compatibility(connection)
        _migrate_user_compatibility(connection)
        _migrate_requisition_compatibility(connection)
        _migrate_audit_log(connection)
        connection.execute("DROP TABLE IF EXISTS Usage_record")
        connection.commit()

        user_count = connection.execute("SELECT COUNT(*) AS count FROM User").fetchone()["count"]
        if user_count == 0:
            connection.execute(
                """
                INSERT INTO User (username, password_hash, full_name, email, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "ADM000001",
                    generate_password_hash(DEFAULT_ADMIN_PASSWORD),
                    DEFAULT_ADMIN_FULL_NAME,
                    None,
                    "ADM",
                    1,
                ),
            )
            connection.commit()

        _seed_demo_data_if_needed(connection)


def _seed_demo_data_if_needed(connection):
    """Populate the database with a lightweight demo dataset when it is empty."""
    if not AUTO_SEED_DEMO_DATA:
        return

    reagent_count = connection.execute("SELECT COUNT(*) AS count FROM Reagent").fetchone()["count"]
    inventory_count = connection.execute("SELECT COUNT(*) AS count FROM Inventory").fetchone()["count"]
    if reagent_count > 0 or inventory_count > 0:
        return

    admin_id = connection.execute(
        "SELECT user_id FROM User WHERE LOWER(COALESCE(role, '')) = 'adm' ORDER BY user_id ASC LIMIT 1"
    ).fetchone()
    admin_user_id = admin_id["user_id"] if admin_id else None

    supplier_names = [
        "Metro Diagnostics",
        "Prime BioLab",
        "Apex Medical Supply",
        "Nova Reagents",
        "Central Lab Traders",
    ]
    reagent_rows = [
        ("Anti-A Blood Grouping Reagent", "Blood Grouping Reagent"),
        ("Anti-B Blood Grouping Reagent", "Blood Grouping Reagent"),
        ("Anti-D Blood Grouping Reagent", "Blood Grouping Reagent"),
        ("AHG Reagent", "AHG Reagent"),
        ("Coombs Control Cells", "Control Reagent"),
        ("A1 Cells", "Screening & Identification Cells"),
        ("B Cells", "Screening & Identification Cells"),
        ("LISS Enhancement Solution", "Enhancement Reagent"),
    ]

    supplier_ids = {}
    for supplier_name in supplier_names:
        connection.execute(
            """
            INSERT OR IGNORE INTO Supplier (
                supplier_name, contact_person, phone, email, address, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                supplier_name,
                "Demo Contact",
                "+66-2-555-0101",
                f"{supplier_name.lower().replace(' ', '.')}@example.com",
                "Demo Lab Road",
            ),
        )
        row = connection.execute(
            "SELECT supplier_id FROM Supplier WHERE supplier_name = ?",
            (supplier_name,),
        ).fetchone()
        if row:
            supplier_ids[supplier_name] = row["supplier_id"]

    for index, (reagent_name, reagent_type) in enumerate(reagent_rows, start=1):
        supplier_name = supplier_names[(index - 1) % len(supplier_names)]
        supplier_id = supplier_ids.get(supplier_name)
        reagent_code = f"RG-DEMO-{index:03d}"
        lot_number = f"DEMO-LOT-{index:03d}"
        expiry_date = (datetime.now().date().replace(day=1) if index == 1 else None)
        if index % 2 == 0:
            expiry_date = (datetime.now().date()).isoformat()
        else:
            expiry_date = (datetime.now().date()).replace(day=min(28, datetime.now().day)).isoformat()
        manufacturer_date = (datetime.now().date()).isoformat()
        storage_condition = "2-8 C"
        critical_level = random.randint(1, 5)
        minimum_level = random.randint(1, 5)

        reagent_table = connection.execute("PRAGMA table_info(Reagent)").fetchall()
        reagent_value_map = {
            "reagent_code": reagent_code,
            "reagent_name": reagent_name,
            "supplier_id": supplier_id,
            "manufacturer": "Demo Manufacturer",
            "category": reagent_type,
            "unit_of_measure": "unit",
            "storage_condition": storage_condition,
            "critical_level": critical_level,
            "is_active": 1,
            "reagent_type": reagent_type,
            "lot_number": lot_number,
            "manufacturer_date": manufacturer_date,
            "expiry_date": expiry_date,
            "supplier": supplier_name,
            "minimum_level": minimum_level,
        }
        insert_columns = []
        insert_values = []
        for column in reagent_table:
            column_name = column["name"]
            if column_name in {"reagent_id", "created_at", "updated_at"}:
                continue
            insert_columns.append(column_name)
            value = reagent_value_map.get(column_name)
            if value is None and column["notnull"]:
                column_type = (column["type"] or "").upper()
                if any(token in column_type for token in ("INT", "REAL", "NUM", "DEC")):
                    value = 0
                else:
                    value = ""
            insert_values.append(value)

        connection.execute(
            f"""
            INSERT INTO Reagent (
                {", ".join(insert_columns)}, updated_at
            ) VALUES ({", ".join(["?"] * len(insert_columns))}, CURRENT_TIMESTAMP)
            """,
            tuple(insert_values),
        )

        reagent_row = connection.execute(
            "SELECT * FROM Reagent ORDER BY reagent_id DESC LIMIT 1"
        ).fetchone()
        if reagent_row is None:
            continue

        quantity_on_hand = random.randint(8, 24)
        inventory_status = "Available for Use" if index % 3 != 0 else "Pending QC"
        connection.execute(
            """
            INSERT INTO Inventory (
                reagent_id, lot_number, expiry_date, quantity_on_hand, minimum_level,
                storage_location, status, last_updated, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                reagent_row["reagent_id"],
                lot_number,
                expiry_date,
                quantity_on_hand,
                minimum_level,
                "Refrigerator A1" if index % 2 else "Refrigerator A2",
                inventory_status,
            ),
        )

    inventory_rows = connection.execute(
        "SELECT inventory_id, reagent_id, quantity_on_hand FROM Inventory ORDER BY inventory_id ASC"
    ).fetchall()
    qc_types = ["Daily QC", "New Lot QC", "Periodic QC"]
    for idx, row in enumerate(inventory_rows, start=1):
        qc_result = "Pass" if idx % 3 != 0 else "Fail"
        qc_status = "passed" if qc_result == "Pass" else "failed"
        qc_time = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        connection.execute(
            """
            INSERT INTO QC_record (
                inventory_id, inspected_by_user_id, qc_date, result, remarks, temperature_c, pH_value,
                status, created_at, updated_at, qc_datetime, qc_type, qc_result, qc_comment, user_id, reagent_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["inventory_id"],
                admin_user_id,
                qc_time,
                qc_result,
                f"Demo {qc_result.lower()} QC record",
                4.0 + (idx % 2),
                7.0,
                qc_status,
                qc_time,
                qc_types[idx % len(qc_types)],
                qc_result,
                f"Demo {qc_result.lower()} QC record",
                admin_user_id,
                row["reagent_id"],
            ),
        )

    requests_to_create = min(5, len(inventory_rows))
    for index in range(requests_to_create):
        status = ["Pending", "Approved", "Rejected", "Completed", "Pending"][index]
        request_date = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        approved_by = admin_user_id if status in {"Approved", "Completed"} else None
        approval_date = request_date if approved_by else None
        cursor = connection.execute(
            """
            INSERT INTO Requisition (
                request_date, status, requested_by, approved_by, approval_date, remarks, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                request_date,
                status,
                admin_user_id,
                approved_by,
                approval_date,
                f"Demo requisition {index + 1}",
            ),
        )
        requisition_id = cursor.lastrowid
        row = inventory_rows[index % len(inventory_rows)]
        qty = min(float(row["quantity_on_hand"] or 0), random.randint(1, 3))
        connection.execute(
            """
            INSERT INTO Requisition_Item (
                requisition_id, reagent_id, quantity_requested, quantity_received, created_at, updated_at, lot_number
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            """,
            (
                requisition_id,
                row["reagent_id"],
                qty,
                qty if status in {"Approved", "Completed"} else 0,
                lot_number_for_reagent(connection, row["reagent_id"]),
            ),
        )

    connection.commit()


def lot_number_for_reagent(connection, reagent_id):
    row = connection.execute(
        "SELECT lot_number FROM Inventory WHERE reagent_id = ? ORDER BY inventory_id ASC LIMIT 1",
        (reagent_id,),
    ).fetchone()
    return row["lot_number"] if row else None


def _migrate_reagent_compatibility(connection):
    """Add reagent columns required by the current app to older databases."""
    reagent_columns = {row["name"] for row in connection.execute("PRAGMA table_info(Reagent)").fetchall()}
    reagent_migrations = [
        ("reagent_type", "TEXT"),
        ("lot_number", "TEXT"),
        ("manufacturer_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("supplier", "TEXT"),
    ]
    for column_name, column_type in reagent_migrations:
        if column_name not in reagent_columns:
            connection.execute(f"ALTER TABLE Reagent ADD COLUMN {column_name} {column_type}")


def _migrate_qc_record(connection):
    """Add QC columns when an older database is opened."""
    qc_columns = {row["name"] for row in connection.execute("PRAGMA table_info(QC_record)").fetchall()}
    qc_migrations = [
        ("qc_datetime", "TEXT"),
        ("qc_type", "TEXT"),
        ("qc_result", "TEXT"),
        ("qc_comment", "TEXT"),
        ("user_id", "INTEGER"),
        ("reagent_id", "INTEGER"),
        ("inventory_id", "INTEGER"),
    ]
    for column_name, column_type in qc_migrations:
        if column_name not in qc_columns:
            connection.execute(f"ALTER TABLE QC_record ADD COLUMN {column_name} {column_type}")

    connection.execute(
        """
        UPDATE QC_record
        SET inventory_id = (
            SELECT inventory_id
            FROM Inventory
            WHERE Inventory.reagent_id = QC_record.reagent_id
            ORDER BY inventory_id ASC
            LIMIT 1
        )
        WHERE inventory_id IS NULL
        """
    )


def _migrate_request_compatibility(connection):
    """Add request columns required for completion tracking."""
    request_columns = {row["name"] for row in connection.execute("PRAGMA table_info(Reagent_Request)").fetchall()}
    request_migrations = [
        ("inventory_deducted", "INTEGER NOT NULL DEFAULT 0"),
        ("completed_at", "TEXT"),
    ]
    for column_name, column_type in request_migrations:
        if column_name not in request_columns:
            connection.execute(f"ALTER TABLE Reagent_Request ADD COLUMN {column_name} {column_type}")


def _migrate_user_compatibility(connection):
    """Normalize older role values to the new role codes."""
    user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(User)").fetchall()}
    if "role" not in user_columns:
        connection.execute("ALTER TABLE User ADD COLUMN role TEXT NOT NULL DEFAULT 'MT'")
    connection.execute(
        """
        UPDATE User
        SET role = CASE
            WHEN LOWER(COALESCE(role, '')) IN ('admin', 'adm') THEN 'ADM'
            WHEN LOWER(COALESCE(role, '')) IN ('supervisor', 'sup') THEN 'SUP'
            ELSE 'MT'
        END
        """
    )


def _migrate_requisition_compatibility(connection):
    """Create requisition tables and backfill them from legacy request tables when needed."""
    connection.execute(
        """
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
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Requisition_Item (
            requisition_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requisition_id INTEGER NOT NULL,
            reagent_id INTEGER NOT NULL,
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
        )
        """
    )

    requisition_count = connection.execute("SELECT COUNT(*) AS count FROM Requisition").fetchone()["count"]
    legacy_count = connection.execute("SELECT COUNT(*) AS count FROM Reagent_Request").fetchone()["count"]
    if requisition_count == 0 and legacy_count > 0:
        legacy_rows = connection.execute(
            """
            SELECT request_id, request_date, needed_by_date, status, requested_by_user_id, notes, completed_at, updated_at
            FROM Reagent_Request
            ORDER BY request_date ASC, request_id ASC
            """
        ).fetchall()
        for row in legacy_rows:
            status = (row["status"] or "Pending").strip()
            normalized_status = {
                "draft": "Pending",
                "submitted": "Pending",
                "pending": "Pending",
                "approved": "Approved",
                "rejected": "Rejected",
                "completed": "Completed",
                "fulfilled": "Completed",
            }.get(status.lower(), "Pending")
            cursor = connection.execute(
                """
                INSERT INTO Requisition (
                    request_date, status, requested_by, approved_by, approval_date, remarks, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, NULL, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    row["request_date"],
                    normalized_status,
                    row["requested_by_user_id"],
                    row["notes"],
                    row["updated_at"] or row["completed_at"] or row["request_date"],
                ),
            )
            requisition_id = cursor.lastrowid
            items = connection.execute(
                """
                SELECT reagent_id, requested_quantity
                FROM Reagent_Request_Detail
                WHERE request_id = ?
                ORDER BY request_detail_id ASC
                """,
                (row["request_id"],),
            ).fetchall()
            for item in items:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO Requisition_Item (
                        requisition_id, reagent_id, quantity_requested, quantity_received, created_at, updated_at
                    ) VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        requisition_id,
                        item["reagent_id"],
                        item["requested_quantity"],
                    ),
                )


def authenticate_user(username, password):
    """Return a user row when username/password are valid."""
    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT user_id, username, full_name, role, password_hash, is_active FROM User WHERE username = ?",
            (username,),
        ).fetchone()

    if user is None or not user["is_active"]:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def get_logged_in_user(user_id):
    """Fetch the current logged-in user."""
    with get_db_connection() as connection:
        return connection.execute(
            "SELECT user_id, username, full_name, role FROM User WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def normalize_role(role):
    value = (role or "MT").strip().upper()
    if value in {"MT", "SUP", "ADM"}:
        return value
    if value in {"STAFF", "ADMIN"}:
        return "ADM" if value == "ADMIN" else "MT"
    return "MT"


def _username_prefix(role):
    return ROLE_USERNAME_PREFIXES.get(normalize_role(role), "MT")


def generate_username_for_role(role, connection=None):
    prefix = _username_prefix(role)
    owns_connection = connection is None
    if owns_connection:
        connection = get_db_connection()
    try:
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(username, 4, 6) AS INTEGER)), 0) AS max_seq
            FROM User
            WHERE username GLOB ?
            """,
            (f"{prefix}[0-9][0-9][0-9][0-9][0-9][0-9]",),
        ).fetchone()
        next_seq = int(row["max_seq"] or 0) + 1
        while True:
            username = f"{prefix}{next_seq:06d}"
            exists = connection.execute(
                "SELECT 1 FROM User WHERE LOWER(username) = LOWER(?)",
                (username,),
            ).fetchone()
            if not exists:
                return username
            next_seq += 1
    finally:
        if owns_connection:
            connection.close()


def create_user(username, password, full_name, email=None, role="MT", actor_user_id=None):
    """Create a user with a hashed password."""
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    email = (email or "").strip() or None
    role = normalize_role(role)

    if not full_name or not password:
        return False, None, "Full name and password are required."

    with get_db_connection() as connection:
        if not username:
            username = generate_username_for_role(role, connection)
        existing_username = connection.execute(
            "SELECT 1 FROM User WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        if existing_username:
            return False, None, "That username is already in use."

        if email:
            existing_email = connection.execute(
                "SELECT 1 FROM User WHERE LOWER(email) = LOWER(?)",
                (email,),
            ).fetchone()
            if existing_email:
                return False, None, "That email address is already in use."

        connection.execute(
            """
            INSERT INTO User (username, password_hash, full_name, email, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                username,
                generate_password_hash(password),
                full_name,
                email,
                role,
            ),
        )
        created_user = connection.execute(
            "SELECT user_id, username, full_name, email, role FROM User WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Create User",
            entity_type="User",
            entity_id=created_user["user_id"] if created_user else username,
            details=f"Created role {role}",
            after_data=created_user,
        )
        connection.commit()

    return True, username, None


def preview_username(role):
    with get_db_connection() as connection:
        return generate_username_for_role(role, connection)


def get_dashboard_summary():
    with get_db_connection() as connection:
        reagent_total = connection.execute("SELECT COUNT(*) AS count FROM Reagent").fetchone()["count"]
        inventory_total = connection.execute("SELECT COUNT(*) AS count FROM Inventory").fetchone()["count"]
        low_stock_total = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM Inventory
            WHERE quantity_on_hand <= minimum_level
            """
        ).fetchone()["count"]
        expired_total = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM Inventory
            WHERE expiry_date IS NOT NULL
              AND expiry_date <> ''
              AND date(expiry_date) < date('now')
            """
        ).fetchone()["count"]
        qc_failed_total = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM QC_record
            WHERE LOWER(COALESCE(qc_result, result, '')) = 'failed'
               OR LOWER(COALESCE(status, '')) = 'failed'
            """
        ).fetchone()["count"]
        qc_pending_total = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM QC_record
            WHERE LOWER(COALESCE(status, '')) = 'pending'
            """
        ).fetchone()["count"]

    return {
        "total_reagents": reagent_total,
        "total_inventory_items": inventory_total,
        "low_stock_count": low_stock_total,
        "expired_reagent_count": expired_total,
        "qc_pending_count": qc_pending_total,
        "qc_failed_count": qc_failed_total,
    }


def get_dashboard_alerts():
    with get_db_connection() as connection:
        expired_reagents = connection.execute(
            """
            SELECT
                i.inventory_id,
                r.reagent_id,
                r.reagent_name,
                i.lot_number,
                i.expiry_date
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.expiry_date IS NOT NULL
              AND i.expiry_date <> ''
              AND date(i.expiry_date) < date('now')
            ORDER BY date(i.expiry_date) ASC, r.reagent_name ASC
            """
        ).fetchall()

        expiring_soon_reagents = connection.execute(
            """
            SELECT
                i.inventory_id,
                r.reagent_id,
                r.reagent_name,
                i.lot_number,
                i.expiry_date
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.expiry_date IS NOT NULL
              AND i.expiry_date <> ''
              AND date(i.expiry_date) BETWEEN date('now') AND date('now', '+30 day')
            ORDER BY date(i.expiry_date) ASC, r.reagent_name ASC
            """
        ).fetchall()

        low_stock_reagents = connection.execute(
            """
            SELECT
                i.inventory_id,
                r.reagent_name,
                i.lot_number,
                i.quantity_on_hand,
                i.minimum_level,
                i.status
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.quantity_on_hand <= i.minimum_level
            ORDER BY (i.minimum_level - i.quantity_on_hand) DESC, r.reagent_name ASC
            """
        ).fetchall()

        qc_failed_records = connection.execute(
            """
            SELECT
                qc.qc_record_id,
                qc.qc_datetime,
                qc.qc_type,
                qc.qc_result,
                qc.qc_comment,
                r.reagent_name,
                COALESCE(i.lot_number, r.lot_number) AS lot_number
            FROM QC_record AS qc
            LEFT JOIN Inventory AS i ON i.inventory_id = qc.inventory_id
            LEFT JOIN Reagent AS r ON r.reagent_id = COALESCE(qc.reagent_id, i.reagent_id)
            WHERE LOWER(COALESCE(qc.qc_result, result, '')) = 'failed'
               OR LOWER(COALESCE(qc.status, '')) = 'failed'
            ORDER BY qc.qc_datetime DESC, qc.qc_record_id DESC
            """
        ).fetchall()

    return {
        "expired_reagents": expired_reagents,
        "expiring_soon_reagents": expiring_soon_reagents,
        "low_stock_reagents": low_stock_reagents,
        "qc_failed_records": qc_failed_records,
    }


def get_dashboard_activity_feed(limit=20):
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM (
                SELECT
                    rr.received_date AS occurred_at,
                    'Receiving' AS activity_type,
                    'success' AS tone,
                    rr.receiving_number AS headline,
                    COALESCE(r.reagent_name, 'Unknown reagent') || ' received (' || rr.quantity_received || ')' AS detail
                FROM Reagent_Receiving AS rr
                LEFT JOIN Reagent AS r ON r.reagent_id = rr.reagent_id

                UNION ALL

                SELECT
                    COALESCE(qc.qc_datetime, qc.qc_date) AS occurred_at,
                    'QC' AS activity_type,
                    CASE
                        WHEN LOWER(COALESCE(qc.qc_result, qc.result, '')) = 'failed' OR LOWER(COALESCE(qc.status, '')) = 'failed' THEN 'danger'
                        WHEN LOWER(COALESCE(qc.qc_result, qc.result, '')) = 'pending' OR LOWER(COALESCE(qc.status, '')) = 'pending' THEN 'warning'
                        ELSE 'success'
                    END AS tone,
                    COALESCE(qc.qc_type, 'QC Record') AS headline,
                    COALESCE(r.reagent_name, 'Unknown reagent') || ' - ' || COALESCE(qc.qc_result, qc.result, 'Recorded') AS detail
                FROM QC_record AS qc
                LEFT JOIN Reagent AS r ON r.reagent_id = COALESCE(qc.reagent_id, (SELECT reagent_id FROM Inventory WHERE inventory_id = qc.inventory_id))

                UNION ALL

                SELECT
                    rq.request_date AS occurred_at,
                    'Request' AS activity_type,
                    CASE
                        WHEN LOWER(COALESCE(rq.status, '')) IN ('approved', 'completed') THEN 'success'
                        WHEN LOWER(COALESCE(rq.status, '')) = 'rejected' THEN 'danger'
                        ELSE 'warning'
                    END AS tone,
                    'REQ-' || printf('%06d', rq.requisition_id) AS headline,
                    LOWER(COALESCE(rq.status, 'pending')) || ' requisition' AS detail
                FROM Requisition AS rq

            )
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_inventory_report():
    return list_inventory()


def get_low_stock_report():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                i.inventory_id,
                r.reagent_name,
                r.reagent_type,
                i.lot_number,
                i.expiry_date,
                i.quantity_on_hand,
                i.minimum_level,
                i.storage_location,
                i.status
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.quantity_on_hand <= i.minimum_level
            ORDER BY
                (i.minimum_level - i.quantity_on_hand) DESC,
                date(i.expiry_date) ASC,
                r.reagent_name ASC,
                i.lot_number ASC
            """
        ).fetchall()


def get_pending_qc_report():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                qc.qc_record_id,
                qc.qc_datetime,
                qc.qc_type,
                qc.qc_result,
                qc.qc_comment,
                qc.status,
                i.lot_number,
                i.expiry_date,
                r.reagent_name,
                u.full_name AS user_name
            FROM QC_record AS qc
            LEFT JOIN Inventory AS i ON i.inventory_id = qc.inventory_id
            LEFT JOIN Reagent AS r ON r.reagent_id = COALESCE(qc.reagent_id, i.reagent_id)
            LEFT JOIN User AS u ON u.user_id = qc.user_id
            WHERE LOWER(COALESCE(qc.status, '')) = 'pending'
            ORDER BY qc.qc_datetime DESC, qc.qc_record_id DESC
            """
        ).fetchall()


def get_failed_qc_report():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                qc.qc_record_id,
                qc.qc_datetime,
                qc.qc_type,
                qc.qc_result,
                qc.qc_comment,
                qc.status,
                i.lot_number,
                i.expiry_date,
                r.reagent_name,
                u.full_name AS user_name
            FROM QC_record AS qc
            LEFT JOIN Inventory AS i ON i.inventory_id = qc.inventory_id
            LEFT JOIN Reagent AS r ON r.reagent_id = COALESCE(qc.reagent_id, i.reagent_id)
            LEFT JOIN User AS u ON u.user_id = qc.user_id
            WHERE LOWER(COALESCE(qc.qc_result, qc.result, qc.status, '')) = 'failed'
               OR LOWER(COALESCE(qc.status, '')) = 'failed'
            ORDER BY qc.qc_datetime DESC, qc.qc_record_id DESC
            """
        ).fetchall()


def get_qc_history_report():
    return list_qc()


def get_receiving_history_report():
    return list_receiving()


def get_fefo_report():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                i.inventory_id,
                r.reagent_name,
                r.reagent_type,
                i.lot_number,
                i.expiry_date,
                i.quantity_on_hand,
                i.minimum_level,
                i.storage_location,
                i.status,
                CASE
                    WHEN i.expiry_date IS NULL OR i.expiry_date = '' THEN NULL
                    ELSE CAST(julianday(i.expiry_date) - julianday(date('now')) AS INTEGER)
                END AS days_to_expiry
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE COALESCE(i.quantity_on_hand, 0) > 0
            ORDER BY
                CASE WHEN i.expiry_date IS NULL OR i.expiry_date = '' THEN 1 ELSE 0 END ASC,
                date(i.expiry_date) ASC,
                CASE
                    WHEN i.quantity_on_hand <= i.minimum_level THEN 0
                    ELSE 1
                END ASC,
                r.reagent_name ASC,
                i.lot_number ASC
            """
        ).fetchall()


def get_expiring_soon_report():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                r.reagent_id,
                r.reagent_name,
                r.reagent_type,
                r.manufacturer,
                i.lot_number,
                i.expiry_date,
                r.supplier
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.expiry_date IS NOT NULL
              AND i.expiry_date <> ''
              AND date(i.expiry_date) BETWEEN date('now') AND date('now', '+30 day')
            ORDER BY date(i.expiry_date) ASC, r.reagent_name ASC
            """
        ).fetchall()


def get_expired_reagent_report():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                r.reagent_id,
                r.reagent_name,
                r.reagent_type,
                r.manufacturer,
                i.lot_number,
                i.expiry_date,
                r.supplier
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.expiry_date IS NOT NULL
              AND i.expiry_date <> ''
              AND date(i.expiry_date) < date('now')
            ORDER BY date(i.expiry_date) ASC, r.reagent_name ASC
            """
        ).fetchall()


def list_reagents(search_term="", reagent_type=""):
    query = "SELECT r.* FROM Reagent AS r"
    params = []
    conditions = []
    if search_term:
        conditions.append(
            """
            (
                r.reagent_name LIKE ?
                OR r.reagent_type LIKE ?
                OR r.manufacturer LIKE ?
                OR r.lot_number LIKE ?
                OR r.supplier LIKE ?
            )
            """
        )
        like_term = f"%{search_term}%"
        params.extend([like_term] * 5)
    if reagent_type:
        conditions.append("r.reagent_type = ?")
        params.append(reagent_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.reagent_name ASC"
    with get_db_connection() as connection:
        return connection.execute(query, params).fetchall()


def get_reagent(reagent_id):
    with get_db_connection() as connection:
        return connection.execute("SELECT * FROM Reagent WHERE reagent_id = ?", (reagent_id,)).fetchone()


def create_reagent(data, actor_user_id=None):
    with get_db_connection() as connection:
        table_info = connection.execute("PRAGMA table_info(Reagent)").fetchall()
        column_values = {
            "reagent_name": data["reagent_name"],
            "reagent_type": data["reagent_type"],
            "manufacturer": data["manufacturer"],
            "lot_number": data["lot_number"],
            "manufacturer_date": data["manufacturer_date"],
            "expiry_date": data["expiry_date"],
            "storage_condition": data["storage_condition"],
            "supplier": data["supplier"],
            "reagent_code": data.get("reagent_code") or f"RG-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "unit_of_measure": data.get("unit_of_measure") or "unit",
        }
        insert_columns = []
        values = []
        for column in table_info:
            column_name = column["name"]
            if column_name in {"reagent_id", "created_at", "updated_at"}:
                continue
            insert_columns.append(column_name)
            value = column_values.get(column_name)
            if value is None:
                if column["notnull"]:
                    column_type = (column["type"] or "").upper()
                    if any(token in column_type for token in ("INT", "REAL", "NUM", "DEC")):
                        value = 0
                    else:
                        value = ""
            values.append(value)
        placeholders = ", ".join(["?"] * len(insert_columns))
        connection.execute(
            f"""
            INSERT INTO Reagent (
                {", ".join(insert_columns)}, updated_at
            ) VALUES ({placeholders}, CURRENT_TIMESTAMP)
            """,
            tuple(values),
        )
        reagent_row = connection.execute(
            "SELECT * FROM Reagent WHERE reagent_id = last_insert_rowid()"
        ).fetchone()
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Create Reagent",
            entity_type="Reagent",
            entity_id=reagent_row["reagent_id"] if reagent_row else None,
            details=data.get("reagent_name"),
            after_data=reagent_row,
        )
        connection.commit()


def update_reagent(reagent_id, data, actor_user_id=None):
    with get_db_connection() as connection:
        before_row = connection.execute("SELECT * FROM Reagent WHERE reagent_id = ?", (reagent_id,)).fetchone()
        connection.execute(
            """
            UPDATE Reagent
            SET reagent_name = ?,
                reagent_type = ?,
                manufacturer = ?,
                lot_number = ?,
                manufacturer_date = ?,
                expiry_date = ?,
                storage_condition = ?,
                supplier = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE reagent_id = ?
            """,
            (
                data["reagent_name"],
                data["reagent_type"],
                data["manufacturer"],
                data["lot_number"],
                data["manufacturer_date"],
                data["expiry_date"],
                data["storage_condition"],
                data["supplier"],
                reagent_id,
            ),
        )
        after_row = connection.execute("SELECT * FROM Reagent WHERE reagent_id = ?", (reagent_id,)).fetchone()
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Update Reagent",
            entity_type="Reagent",
            entity_id=reagent_id,
            details=data.get("reagent_name"),
            before_data=before_row,
            after_data=after_row,
        )
        connection.commit()


def delete_reagent(reagent_id, actor_user_id=None):
    with get_db_connection() as connection:
        before_row = connection.execute("SELECT * FROM Reagent WHERE reagent_id = ?", (reagent_id,)).fetchone()
        connection.execute("DELETE FROM Reagent_Receiving WHERE reagent_id = ?", (reagent_id,))
        connection.execute("DELETE FROM Reagent_Request_Detail WHERE reagent_id = ?", (reagent_id,))
        connection.execute("DELETE FROM Inventory WHERE reagent_id = ?", (reagent_id,))
        connection.execute("DELETE FROM Reagent WHERE reagent_id = ?", (reagent_id,))
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Delete Reagent",
            entity_type="Reagent",
            entity_id=reagent_id,
            before_data=before_row,
        )
        connection.commit()


def list_suppliers():
    with get_db_connection() as connection:
        return connection.execute(
            "SELECT supplier_id, supplier_name, contact_person FROM Supplier ORDER BY supplier_name ASC"
        ).fetchall()


def get_supplier(supplier_id):
    with get_db_connection() as connection:
        return connection.execute(
            "SELECT supplier_id, supplier_name, contact_person FROM Supplier WHERE supplier_id = ?",
            (supplier_id,),
        ).fetchone()


def create_supplier(supplier_name, contact, actor_user_id=None):
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO Supplier (supplier_name, contact_person, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (supplier_name, contact),
        )
        supplier_row = connection.execute(
            "SELECT * FROM Supplier WHERE supplier_id = last_insert_rowid()"
        ).fetchone()
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Create Supplier",
            entity_type="Supplier",
            entity_id=supplier_row["supplier_id"] if supplier_row else None,
            details=supplier_name,
            after_data=supplier_row,
        )
        connection.commit()


def update_supplier(supplier_id, supplier_name, contact, actor_user_id=None):
    with get_db_connection() as connection:
        before_row = connection.execute("SELECT * FROM Supplier WHERE supplier_id = ?", (supplier_id,)).fetchone()
        connection.execute(
            """
            UPDATE Supplier
            SET supplier_name = ?, contact_person = ?, updated_at = CURRENT_TIMESTAMP
            WHERE supplier_id = ?
            """,
            (supplier_name, contact, supplier_id),
        )
        after_row = connection.execute("SELECT * FROM Supplier WHERE supplier_id = ?", (supplier_id,)).fetchone()
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Update Supplier",
            entity_type="Supplier",
            entity_id=supplier_id,
            details=supplier_name,
            before_data=before_row,
            after_data=after_row,
        )
        connection.commit()


def delete_supplier(supplier_id, actor_user_id=None):
    with get_db_connection() as connection:
        before_row = connection.execute("SELECT * FROM Supplier WHERE supplier_id = ?", (supplier_id,)).fetchone()
        connection.execute("DELETE FROM Supplier WHERE supplier_id = ?", (supplier_id,))
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Delete Supplier",
            entity_type="Supplier",
            entity_id=supplier_id,
            before_data=before_row,
        )
        connection.commit()


def list_inventory(search_term=""):
    query = """
        SELECT
            i.inventory_id, i.reagent_id, i.lot_number, i.expiry_date, i.quantity_on_hand,
            i.minimum_level, i.storage_location, i.status, i.last_updated,
            r.reagent_name, r.reagent_type, r.manufacturer, r.supplier
        FROM Inventory AS i
        LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
    """
    params = []
    if search_term:
        query += """
            WHERE r.reagent_name LIKE ?
               OR r.reagent_type LIKE ?
               OR i.lot_number LIKE ?
               OR i.storage_location LIKE ?
               OR i.status LIKE ?
               OR r.supplier LIKE ?
        """
        like_term = f"%{search_term}%"
        params = [like_term] * 6
    query += """
        ORDER BY
            CASE
                WHEN i.expiry_date IS NULL OR i.expiry_date = '' THEN 1
                ELSE 0
            END ASC,
            date(i.expiry_date) ASC,
            r.reagent_name ASC,
            i.lot_number ASC
    """
    with get_db_connection() as connection:
        return connection.execute(query, params).fetchall()


def get_inventory_item(inventory_id):
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                i.inventory_id, i.reagent_id, i.lot_number, i.expiry_date, i.quantity_on_hand,
                i.minimum_level, i.storage_location, i.status, i.last_updated,
                r.reagent_name, r.reagent_type, r.manufacturer, r.supplier
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.inventory_id = ?
            """,
            (inventory_id,),
        ).fetchone()


def update_inventory(inventory_id, quantity, minimum_stock, storage_location, status, actor_user_id=None):
    with get_db_connection() as connection:
        before_row = connection.execute("SELECT * FROM Inventory WHERE inventory_id = ?", (inventory_id,)).fetchone()
        connection.execute(
            """
            UPDATE Inventory
            SET quantity_on_hand = ?,
                minimum_level = ?,
                storage_location = ?,
                status = ?,
                last_updated = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = ?
            """,
            (quantity, minimum_stock, storage_location, status, inventory_id),
        )
        after_row = connection.execute("SELECT * FROM Inventory WHERE inventory_id = ?", (inventory_id,)).fetchone()
        log_audit_event(
            connection,
            user_id=actor_user_id,
            action="Update Inventory",
            entity_type="Inventory",
            entity_id=inventory_id,
            details=f"quantity={quantity}, minimum_stock={minimum_stock}, status={status}",
            before_data=before_row,
            after_data=after_row,
        )
        connection.commit()


def reagent_choices():
    with get_db_connection() as connection:
        reagents = connection.execute(
            "SELECT reagent_id, reagent_name, lot_number FROM Reagent ORDER BY reagent_name ASC"
        ).fetchall()
    return [(r["reagent_id"], f"{r['reagent_name']} ({r['lot_number'] or 'No lot'})") for r in reagents]


def qc_lot_choices():
    with get_db_connection() as connection:
        lots = connection.execute(
            """
            SELECT
                i.inventory_id,
                r.reagent_name,
                i.lot_number,
                i.expiry_date,
                i.status
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE COALESCE(i.quantity_on_hand, 0) > 0
            ORDER BY
                CASE WHEN LOWER(COALESCE(i.status, '')) = 'pending qc' THEN 0 ELSE 1 END ASC,
                date(i.expiry_date) ASC,
                r.reagent_name ASC,
                i.lot_number ASC
            """
        ).fetchall()
    return [
        (
            lot["inventory_id"],
            f"{lot['reagent_name']} | Lot {lot['lot_number']} | Exp {lot['expiry_date'] or 'N/A'}",
        )
        for lot in lots
    ]


def user_choices():
    with get_db_connection() as connection:
        users = connection.execute(
            "SELECT user_id, full_name, username FROM User WHERE is_active = 1 ORDER BY full_name ASC"
        ).fetchall()
    return [(u["user_id"], f"{u['full_name']} ({u['username']})") for u in users]


def ensure_inventory_row(connection, reagent_id, lot_number, expiry_date, received_quantity):
    item = connection.execute(
        """
        SELECT inventory_id
        FROM Inventory
        WHERE reagent_id = ? AND LOWER(COALESCE(lot_number, '')) = LOWER(?)
        LIMIT 1
        """,
        (reagent_id, lot_number),
    ).fetchone()
    if item is None:
        connection.execute(
            """
            INSERT INTO Inventory (
                reagent_id, lot_number, expiry_date, quantity_on_hand, minimum_level,
                storage_location, status, last_updated, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (reagent_id, lot_number, expiry_date, received_quantity, 0, None, "Pending QC"),
        )
        item = connection.execute(
            """
            SELECT inventory_id
            FROM Inventory
            WHERE reagent_id = ? AND LOWER(COALESCE(lot_number, '')) = LOWER(?)
            LIMIT 1
            """,
            (reagent_id, lot_number),
        ).fetchone()
    else:
        connection.execute(
            """
            UPDATE Inventory
            SET quantity_on_hand = quantity_on_hand + ?,
                expiry_date = COALESCE(NULLIF(?, ''), expiry_date),
                status = 'Pending QC',
                last_updated = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = ?
            """,
            (received_quantity, expiry_date, item["inventory_id"]),
        )
    return item["inventory_id"]


def _update_inventory_status(connection, inventory_id, status):
    connection.execute(
        """
        UPDATE Inventory
        SET status = ?,
            last_updated = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE inventory_id = ?
        """,
        (status, inventory_id),
    )


def _qc_inventory_status(qc_result):
    value = (qc_result or "").strip().lower()
    if not value or "pending" in value:
        return "Pending QC"
    if any(token in value for token in ("pass", "approved", "success", "complete", "completed", "fulfilled")):
        return "Available for Use"
    if any(token in value for token in ("fail", "failed", "reject", "rejected")):
        return "QC Failed"
    return None


def _qc_record_status(qc_result):
    value = (qc_result or "").strip().lower()
    if not value or "pending" in value:
        return "pending"
    if any(token in value for token in ("pass", "approved", "success", "complete", "completed", "fulfilled")):
        return "passed"
    if any(token in value for token in ("fail", "failed", "reject", "rejected")):
        return "failed"
    return value or "pending"


def inventory_id_for_reagent(connection, reagent_id):
    row = connection.execute(
        """
        SELECT inventory_id
        FROM Inventory
        WHERE reagent_id = ?
        ORDER BY
            CASE WHEN LOWER(COALESCE(status, '')) = 'pending qc' THEN 0 ELSE 1 END ASC,
            inventory_id DESC
        LIMIT 1
        """,
        (reagent_id,),
    ).fetchone()
    return row["inventory_id"] if row else None


def supplier_id_by_name(connection, supplier_name):
    row = connection.execute(
        """
        SELECT supplier_id
        FROM Supplier
        WHERE LOWER(TRIM(supplier_name)) = LOWER(TRIM(?))
        LIMIT 1
        """,
        (supplier_name,),
    ).fetchone()
    return row["supplier_id"] if row else None


def list_receiving():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                rr.receiving_id, rr.receiving_number, rr.received_date, rr.quantity_received,
                rr.lot_number, rr.expiry_date, rr.invoice_number, rr.remarks,
                r.reagent_name, u.full_name AS received_by_name
            FROM Reagent_Receiving AS rr
            LEFT JOIN Reagent AS r ON r.reagent_id = rr.reagent_id
            LEFT JOIN User AS u ON u.user_id = rr.received_by_user_id
            ORDER BY rr.received_date DESC, rr.receiving_id DESC
            """
        ).fetchall()


def create_receiving(received_date, reagent_id, lot_number, expiry_date, quantity_received, received_by_user_id):
    receiving_number = f"RCV-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    with get_db_connection() as connection:
        reagent_row = connection.execute(
            """
            SELECT
                reagent_id,
                reagent_name,
                supplier,
                expiry_date
            FROM Reagent
            WHERE reagent_id = ?
            """,
            (reagent_id,),
        ).fetchone()
        if reagent_row is None:
            return None, "The selected reagent was not found."

        supplier_name = reagent_row["supplier"].strip() if reagent_row["supplier"] else ""
        if not supplier_name:
            supplier_name = "Unknown"

        supplier_id = supplier_id_by_name(connection, supplier_name)
        if supplier_id is None:
            connection.execute(
                """
                INSERT INTO Supplier (supplier_name, updated_at)
                VALUES (?, CURRENT_TIMESTAMP)
                """,
                (supplier_name,),
            )
            supplier_id = supplier_id_by_name(connection, supplier_name)

        inventory_id = ensure_inventory_row(connection, reagent_id, lot_number, expiry_date, quantity_received)
        _update_inventory_status(connection, inventory_id, "Pending QC")
        qc_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        connection.execute(
            """
            INSERT INTO Reagent_Receiving (
                receiving_number, supplier_id, received_by_user_id, inventory_id, reagent_id,
                received_date, lot_number, expiry_date, quantity_received, unit_cost,
                invoice_number, remarks, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                receiving_number,
                supplier_id,
                received_by_user_id,
                inventory_id,
                reagent_id,
                received_date,
                lot_number,
                expiry_date,
                quantity_received,
            ),
        )
        receiving_row = connection.execute(
            "SELECT * FROM Reagent_Receiving WHERE receiving_id = last_insert_rowid()"
        ).fetchone()
        connection.execute(
            """
            INSERT INTO QC_record (
                qc_datetime, qc_type, qc_result, qc_comment, user_id, reagent_id, inventory_id,
                inspected_by_user_id, result, remarks, status, qc_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                qc_timestamp,
                "New Lot QC",
                "Pending",
                "Auto-created after receiving.",
                received_by_user_id,
                reagent_id,
                inventory_id,
                received_by_user_id,
                "Pending",
                "Auto-created after receiving.",
                "pending",
                qc_timestamp,
            ),
        )
        qc_row = connection.execute(
            "SELECT * FROM QC_record WHERE qc_record_id = last_insert_rowid()"
        ).fetchone()
        log_audit_event(
            connection,
            user_id=received_by_user_id,
            action="Create Receiving",
            entity_type="Reagent_Receiving",
            entity_id=receiving_row["receiving_id"] if receiving_row else None,
            details=f"Lot {lot_number}",
            after_data=receiving_row,
        )
        log_audit_event(
            connection,
            user_id=received_by_user_id,
            action="Create Pending QC",
            entity_type="QC_record",
            entity_id=qc_row["qc_record_id"] if qc_row else None,
            details=f"Auto-created new lot QC for lot {lot_number}",
            after_data=qc_row,
        )
        connection.commit()
    return receiving_number, None


def list_qc(search_term="", qc_type=""):
    query = """
        SELECT
            qc.qc_record_id, qc.qc_datetime, qc.qc_type, qc.qc_result, qc.qc_comment, qc.user_id,
            u.username AS user_username, u.full_name AS user_name,
            r.reagent_name, COALESCE(i.lot_number, r.lot_number) AS lot_number
        FROM QC_record AS qc
        LEFT JOIN User AS u ON u.user_id = qc.user_id
        LEFT JOIN Inventory AS i ON i.inventory_id = qc.inventory_id
        LEFT JOIN Reagent AS r ON r.reagent_id = COALESCE(qc.reagent_id, i.reagent_id)
    """
    conditions = []
    params = []
    if search_term:
        conditions.append("""
            (
                qc.qc_result LIKE ?
                OR qc.qc_comment LIKE ?
                OR u.full_name LIKE ?
                OR r.reagent_name LIKE ?
                OR COALESCE(i.lot_number, r.lot_number) LIKE ?
            )
        """)
        like_term = f"%{search_term}%"
        params.extend([like_term] * 5)
    if qc_type:
        conditions.append("qc.qc_type = ?")
        params.append(qc_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY qc.qc_datetime DESC, qc.qc_record_id DESC"
    with get_db_connection() as connection:
        return connection.execute(query, params).fetchall()


def create_qc_record(qc_datetime, qc_type, qc_result, qc_comment, user_id, inventory_id):
    with get_db_connection() as connection:
        before_row = connection.execute(
            """
            SELECT *
            FROM QC_record
            WHERE inventory_id = ?
            ORDER BY qc_datetime DESC, qc_record_id DESC
            LIMIT 1
            """,
            (inventory_id,),
        ).fetchone()
        inventory_row = connection.execute(
            """
            SELECT i.inventory_id, i.reagent_id, r.reagent_name
            FROM Inventory AS i
            LEFT JOIN Reagent AS r ON r.reagent_id = i.reagent_id
            WHERE i.inventory_id = ?
            """,
            (inventory_id,),
        ).fetchone()
        if inventory_row is None:
            raise ValueError("The selected lot was not found.")
        inventory_status = _qc_inventory_status(qc_result)
        record_status = _qc_record_status(qc_result)
        pending_record = connection.execute(
            """
            SELECT qc_record_id
            FROM QC_record
            WHERE inventory_id = ?
              AND LOWER(COALESCE(status, '')) = 'pending'
            ORDER BY qc_datetime DESC, qc_record_id DESC
            LIMIT 1
            """,
            (inventory_id,),
        ).fetchone()

        if pending_record is not None:
            connection.execute(
                """
                UPDATE QC_record
                SET qc_datetime = ?,
                    qc_type = ?,
                    qc_result = ?,
                    qc_comment = ?,
                    user_id = ?,
                    reagent_id = ?,
                    inventory_id = ?,
                    inspected_by_user_id = ?,
                    result = ?,
                    remarks = ?,
                    status = ?,
                    qc_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE qc_record_id = ?
                """,
                (
                    qc_datetime,
                    qc_type,
                    qc_result,
                    qc_comment,
                    user_id,
                    inventory_row["reagent_id"],
                    inventory_id,
                    user_id,
                    qc_result,
                    qc_comment,
                    record_status,
                    qc_datetime,
                    pending_record["qc_record_id"],
                ),
            )
            after_row = connection.execute(
                "SELECT * FROM QC_record WHERE qc_record_id = ?",
                (pending_record["qc_record_id"],),
            ).fetchone()
            log_audit_event(
                connection,
                user_id=user_id,
                action="Update QC Record",
                entity_type="QC_record",
                entity_id=pending_record["qc_record_id"],
                details=f"QC {qc_result} for lot {inventory_id}",
                before_data=before_row,
                after_data=after_row,
            )
        else:
            connection.execute(
                """
                INSERT INTO QC_record (
                    qc_datetime, qc_type, qc_result, qc_comment, user_id, reagent_id, inventory_id,
                    inspected_by_user_id, result, remarks, status, qc_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    qc_datetime,
                    qc_type,
                    qc_result,
                    qc_comment,
                    user_id,
                    inventory_row["reagent_id"],
                    inventory_id,
                    user_id,
                    qc_result,
                    qc_comment,
                    record_status,
                ),
            )
            after_row = connection.execute(
                "SELECT * FROM QC_record WHERE qc_record_id = last_insert_rowid()"
            ).fetchone()
            log_audit_event(
                connection,
                user_id=user_id,
                action="Create QC Record",
                entity_type="QC_record",
                entity_id=after_row["qc_record_id"] if after_row else None,
                details=f"QC {qc_result} for lot {inventory_id}",
                after_data=after_row,
            )
        if inventory_status is not None:
            _update_inventory_status(connection, inventory_id, inventory_status)
        connection.commit()


def get_qc_record(qc_record_id):
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                qc.qc_record_id,
                qc.qc_datetime,
                qc.qc_type,
                qc.qc_result,
                qc.qc_comment,
                qc.user_id,
                qc.inventory_id,
                qc.reagent_id,
                u.username AS user_username,
                r.reagent_name,
                i.lot_number,
                i.expiry_date
            FROM QC_record AS qc
            LEFT JOIN User AS u ON u.user_id = qc.user_id
            LEFT JOIN Inventory AS i ON i.inventory_id = qc.inventory_id
            LEFT JOIN Reagent AS r ON r.reagent_id = COALESCE(qc.reagent_id, i.reagent_id)
            WHERE qc.qc_record_id = ?
            """,
            (qc_record_id,),
        ).fetchone()


def _sync_inventory_status_from_latest_qc(connection, inventory_id):
    row = connection.execute(
        """
        SELECT qc_result, status, result
        FROM QC_record
        WHERE inventory_id = ?
        ORDER BY
            CASE WHEN qc_datetime IS NULL OR qc_datetime = '' THEN 1 ELSE 0 END ASC,
            qc_datetime DESC,
            qc_record_id DESC
        LIMIT 1
        """,
        (inventory_id,),
    ).fetchone()
    if row is None:
        return
    status = _qc_inventory_status(row["qc_result"] or row["result"] or row["status"])
    if status is not None:
        _update_inventory_status(connection, inventory_id, status)


def update_qc_record(qc_record_id, qc_datetime, qc_type, qc_result, qc_comment, user_id, inventory_id, editor_user_id):
    with get_db_connection() as connection:
        record = connection.execute(
            """
            SELECT qc_record_id, user_id, inventory_id
            FROM QC_record
            WHERE qc_record_id = ?
            """,
            (qc_record_id,),
        ).fetchone()
        if record is None:
            return False, "QC record not found."
        if int(record["user_id"]) != int(editor_user_id):
            return False, "You can only edit QC records that you created."

        before_row = connection.execute("SELECT * FROM QC_record WHERE qc_record_id = ?", (qc_record_id,)).fetchone()
        inventory_row = connection.execute(
            """
            SELECT i.inventory_id, i.reagent_id
            FROM Inventory AS i
            WHERE i.inventory_id = ?
            """,
            (inventory_id,),
        ).fetchone()
        if inventory_row is None:
            return False, "The selected lot was not found."

        old_inventory_id = record["inventory_id"]
        connection.execute(
            """
            UPDATE QC_record
            SET qc_datetime = ?,
                qc_type = ?,
                qc_result = ?,
                qc_comment = ?,
                user_id = ?,
                reagent_id = ?,
                inventory_id = ?,
                inspected_by_user_id = ?,
                result = ?,
                remarks = ?,
                status = ?,
                qc_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE qc_record_id = ?
            """,
            (
                qc_datetime,
                qc_type,
                qc_result,
                qc_comment,
                user_id,
                inventory_row["reagent_id"],
                inventory_id,
                user_id,
                qc_result,
                qc_comment,
                _qc_record_status(qc_result),
                qc_datetime,
                qc_record_id,
            ),
        )
        after_row = connection.execute("SELECT * FROM QC_record WHERE qc_record_id = ?", (qc_record_id,)).fetchone()
        log_audit_event(
            connection,
            user_id=editor_user_id,
            action="Update QC Record",
            entity_type="QC_record",
            entity_id=qc_record_id,
            details=f"Edited QC record for lot {inventory_id}",
            before_data=before_row,
            after_data=after_row,
        )
        _sync_inventory_status_from_latest_qc(connection, inventory_id)
        if old_inventory_id != inventory_id:
            _sync_inventory_status_from_latest_qc(connection, old_inventory_id)
        connection.commit()
    return True, None


def requisition_reagent_choices():
    with get_db_connection() as connection:
        recommended_rows = _requestable_reagent_lots(connection)

    return [
        (
            row["reagent_id"],
            f"{row['reagent_name']} | Lot {row['lot_number']} | Expires {row['expiry_date'] or 'N/A'}",
        )
        for row in sorted(
            recommended_rows.values(),
            key=lambda row: (
                row["expiry_date"] is None or row["expiry_date"] == "",
                row["expiry_date"] or "",
                row["reagent_name"] or "",
                row["lot_number"] or "",
            ),
        )
    ]


def _requestable_reagent_ids(connection):
    rows = _requestable_reagent_lots(connection)
    return set(rows.keys())


def _requestable_reagent_lots(connection):
    rows = connection.execute(
        """
        SELECT
            r.reagent_id,
            r.reagent_name,
            i.lot_number,
            i.expiry_date,
            i.inventory_id
        FROM Reagent AS r
        INNER JOIN Inventory AS i ON i.reagent_id = r.reagent_id
        WHERE COALESCE(i.quantity_on_hand, 0) > 0
          AND LOWER(COALESCE(i.status, '')) = 'available for use'
        ORDER BY
            r.reagent_id ASC,
            CASE
                WHEN i.expiry_date IS NULL OR i.expiry_date = '' THEN 1
                ELSE 0
            END ASC,
            date(i.expiry_date) ASC,
            i.inventory_id ASC
        """
    ).fetchall()

    recommended_rows = {}
    for row in rows:
        reagent_id = int(row["reagent_id"])
        if reagent_id not in recommended_rows:
            recommended_rows[reagent_id] = row
    return recommended_rows


def request_history():
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                rq.requisition_id AS request_id,
                'REQ-' || printf('%06d', rq.requisition_id) AS request_number,
                rq.request_date,
                rq.approval_date,
                rq.status,
                rq.remarks AS notes,
                requested.full_name AS requested_by_name,
                approved.full_name AS approved_by_name,
                COUNT(ri.requisition_item_id) AS line_count,
                COALESCE(SUM(ri.quantity_requested), 0) AS total_requested,
                GROUP_CONCAT(
                    COALESCE(r.reagent_name, 'Unknown reagent')
                    || CASE
                        WHEN ri.lot_number IS NULL OR ri.lot_number = '' THEN ''
                        ELSE ' | Lot ' || ri.lot_number
                    END
                    || ' x'
                    || COALESCE(ri.quantity_requested, 0),
                    ' | '
                ) AS line_summary
            FROM Requisition AS rq
            LEFT JOIN User AS requested ON requested.user_id = rq.requested_by
            LEFT JOIN User AS approved ON approved.user_id = rq.approved_by
            LEFT JOIN Requisition_Item AS ri ON ri.requisition_id = rq.requisition_id
            LEFT JOIN Reagent AS r ON r.reagent_id = ri.reagent_id
            GROUP BY rq.requisition_id
            ORDER BY rq.request_date DESC, rq.requisition_id DESC
            """
        ).fetchall()


def request_details(request_id):
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT
                ri.requisition_item_id AS request_detail_id,
                ri.requisition_id AS request_id,
                ri.reagent_id,
                ri.lot_number,
                ri.quantity_requested AS requested_quantity,
                ri.quantity_received AS approved_quantity,
                NULL AS unit_of_measure,
                NULL AS remarks,
                r.reagent_name
            FROM Requisition_Item AS ri
            LEFT JOIN Reagent AS r ON r.reagent_id = ri.reagent_id
            WHERE ri.requisition_id = ?
            ORDER BY r.reagent_name ASC, ri.requisition_item_id ASC
            """,
            (request_id,),
        ).fetchall()


def _available_inventory_quantity(connection, reagent_id):
    row = connection.execute(
        "SELECT COALESCE(SUM(quantity_on_hand), 0) AS total FROM Inventory WHERE reagent_id = ?",
        (reagent_id,),
    ).fetchone()
    return float(row["total"] if row else 0)


def _deduct_inventory_for_reagent(connection, reagent_id, quantity_needed):
    inventory_rows = connection.execute(
        """
        SELECT inventory_id, quantity_on_hand
        FROM Inventory
        WHERE reagent_id = ?
        ORDER BY
            CASE WHEN expiry_date IS NULL OR expiry_date = '' THEN 1 ELSE 0 END,
            expiry_date ASC,
            inventory_id ASC
        """,
        (reagent_id,),
    ).fetchall()

    remaining = float(quantity_needed)
    for row in inventory_rows:
        if remaining <= 0:
            break
        available = float(row["quantity_on_hand"] or 0)
        if available <= 0:
            continue
        deduct_amount = min(available, remaining)
        new_quantity = available - deduct_amount
        if new_quantity < 0:
            return False, "Inventory cannot go below zero."
        connection.execute(
            """
            UPDATE Inventory
            SET quantity_on_hand = ?,
                last_updated = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = ?
            """,
            (new_quantity, row["inventory_id"]),
        )
        remaining -= deduct_amount

    if remaining > 0:
        return False, "Not enough inventory to complete the request."
    return True, None


def create_request(requested_by_user_id, needed_by_date, notes, line_items):
    request_number = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    with get_db_connection() as connection:
        requestable_ids = _requestable_reagent_ids(connection)
        requestable_lots = _requestable_reagent_lots(connection)
        for line in line_items:
            reagent_id = int(line["reagent_id"])
            if reagent_id not in requestable_ids:
                reagent_row = connection.execute(
                    "SELECT reagent_name, lot_number FROM Reagent WHERE reagent_id = ?",
                    (reagent_id,),
                ).fetchone()
                reagent_label = (
                    f"{reagent_row['reagent_name']} ({reagent_row['lot_number'] or 'No lot'})"
                    if reagent_row
                    else f"Reagent {reagent_id}"
                )
                return None, f"{reagent_label} is not available for request until it passes New Lot QC."

        cursor = connection.execute(
            """
            INSERT INTO Requisition (
                request_date, status, requested_by, approved_by, approval_date, remarks, created_at, updated_at
            ) VALUES (CURRENT_TIMESTAMP, 'Pending', ?, NULL, NULL, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                requested_by_user_id,
                notes,
            ),
        )
        request_id = cursor.lastrowid
        for line in line_items:
            recommended_lot = requestable_lots.get(int(line["reagent_id"]))
            connection.execute(
                """
                INSERT INTO Requisition_Item (
                    requisition_id, reagent_id, lot_number, quantity_requested, quantity_received, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    request_id,
                    line["reagent_id"],
                    recommended_lot["lot_number"] if recommended_lot else None,
                    line["requested_quantity"],
                ),
            )
        request_row = connection.execute(
            "SELECT * FROM Requisition WHERE requisition_id = ?",
            (request_id,),
        ).fetchone()
        detail_rows = connection.execute(
            "SELECT * FROM Requisition_Item WHERE requisition_id = ? ORDER BY requisition_item_id ASC",
            (request_id,),
        ).fetchall()
        log_audit_event(
            connection,
            user_id=requested_by_user_id,
            action="Create Requisition",
            entity_type="Requisition",
            entity_id=request_id,
            details=f"{len(line_items)} item(s)",
            after_data={
                "requisition": request_row,
                "items": detail_rows,
            },
        )
        connection.commit()
    return request_number, None


def update_request_status(request_id, status, approved_by_user_id):
    with get_db_connection() as connection:
        current = connection.execute(
            "SELECT status, approved_by, approval_date FROM Requisition WHERE requisition_id = ?",
            (request_id,),
        ).fetchone()
        if current is None:
            return False, "Request not found."

        normalized_status = (status or "Pending").strip().title()
        if normalized_status not in {"Pending", "Approved", "Rejected", "Completed"}:
            return False, "Invalid requisition status."

        current_status = (current["status"] or "").strip().title()
        should_deduct_inventory = normalized_status in {"Approved", "Completed"} and current_status not in {"Approved", "Completed"}

        try:
            connection.execute("BEGIN")
            if should_deduct_inventory:
                items = connection.execute(
                    """
                    SELECT reagent_id, quantity_requested
                    FROM Requisition_Item
                    WHERE requisition_id = ?
                    ORDER BY requisition_item_id ASC
                    """,
                    (request_id,),
                ).fetchall()
                for item in items:
                    ok, message = _deduct_inventory_for_reagent(connection, item["reagent_id"], item["quantity_requested"])
                    if not ok:
                        connection.rollback()
                        return False, message
                    connection.execute(
                        """
                        UPDATE Requisition_Item
                        SET quantity_received = quantity_requested,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE requisition_id = ? AND reagent_id = ?
                        """,
                        (request_id, item["reagent_id"]),
                    )

            if normalized_status in {"Approved", "Rejected", "Completed"}:
                connection.execute(
                    """
                    UPDATE Requisition
                    SET status = ?,
                        approved_by = ?,
                        approval_date = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE requisition_id = ?
                    """,
                    (normalized_status, approved_by_user_id, request_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE Requisition
                    SET status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE requisition_id = ?
                    """,
                    (normalized_status, request_id),
                )
            after_row = connection.execute(
                "SELECT * FROM Requisition WHERE requisition_id = ?",
                (request_id,),
            ).fetchone()
            item_rows = connection.execute(
                "SELECT * FROM Requisition_Item WHERE requisition_id = ? ORDER BY requisition_item_id ASC",
                (request_id,),
            ).fetchall()
            log_audit_event(
                connection,
                user_id=approved_by_user_id,
                action="Update Requisition Status",
                entity_type="Requisition",
                entity_id=request_id,
                details=f"Status changed to {normalized_status}",
                before_data=current,
                after_data={"requisition": after_row, "items": item_rows},
            )
            connection.commit()
            return True, None
        except Exception as exc:
            connection.rollback()
            return False, str(exc)


def _migrate_audit_log(connection):
    """Create the audit log table for older databases."""
    connection.execute(
        """
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
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_event_time ON Audit_Log (event_time DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON Audit_Log (user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_entity_type ON Audit_Log (entity_type)")


def _jsonify_audit_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, sqlite3.Row):
        return {key: _jsonify_audit_value(value[key]) for key in value.keys()}
    if isinstance(value, dict):
        return {key: _jsonify_audit_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify_audit_value(item) for item in value]
    return str(value)


def _dump_audit_payload(value):
    if value is None:
        return None
    return json.dumps(_jsonify_audit_value(value), ensure_ascii=False, default=str)


def log_audit_event(connection=None, user_id=None, action="", entity_type="", entity_id=None, details=None, before_data=None, after_data=None, ip_address=None):
    owns_connection = connection is None
    if owns_connection:
        connection = get_db_connection()
    try:
        connection.execute(
            """
            INSERT INTO Audit_Log (
                event_time, user_id, action, entity_type, entity_id, details, before_data, after_data, ip_address, created_at
            ) VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                action,
                entity_type,
                None if entity_id is None else str(entity_id),
                details,
                _dump_audit_payload(before_data),
                _dump_audit_payload(after_data),
                ip_address,
            ),
        )
        if owns_connection:
            connection.commit()
    finally:
        if owns_connection:
            connection.close()


def audit_log_action_choices():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT action
            FROM Audit_Log
            WHERE action IS NOT NULL AND TRIM(action) <> ''
            ORDER BY action ASC
            """
        ).fetchall()
    return [(row["action"], row["action"]) for row in rows]


def list_audit_logs(search_term="", action_filter="", user_filter="", date_from="", date_to=""):
    query = """
        SELECT
            a.audit_log_id, a.event_time, a.action, a.entity_type, a.entity_id, a.details,
            a.before_data, a.after_data, a.ip_address,
            a.user_id,
            u.username AS user_username, u.full_name AS user_name, u.role AS user_role
        FROM Audit_Log AS a
        LEFT JOIN User AS u ON u.user_id = a.user_id
    """
    conditions = []
    params = []
    if search_term:
        conditions.append("""
            (
                a.action LIKE ? OR a.entity_type LIKE ? OR a.entity_id LIKE ? OR a.details LIKE ?
                OR u.username LIKE ? OR u.full_name LIKE ?
            )
        """)
        like_term = f"%{search_term}%"
        params.extend([like_term] * 6)
    if action_filter:
        conditions.append("a.action = ?")
        params.append(action_filter)
    if user_filter:
        conditions.append("CAST(a.user_id AS TEXT) = ?")
        params.append(str(user_filter))
    if date_from:
        conditions.append("date(a.event_time) >= date(?)")
        params.append(date_from)
    if date_to:
        conditions.append("date(a.event_time) <= date(?)")
        params.append(date_to)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY a.event_time DESC, a.audit_log_id DESC"
    with get_db_connection() as connection:
        return connection.execute(query, params).fetchall()


def audit_log_user_choices():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT u.user_id, COALESCE(u.full_name, u.username) AS display_name, u.username
            FROM Audit_Log AS a
            LEFT JOIN User AS u ON u.user_id = a.user_id
            WHERE a.user_id IS NOT NULL
            ORDER BY display_name ASC, u.username ASC
            """
        ).fetchall()
    return [(row["user_id"], f"{row['display_name']} ({row['username']})") for row in rows]


def requisition_receiving_choices():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                ri.requisition_item_id,
                ri.reagent_id,
                'REQ-' || printf('%06d', rq.requisition_id) AS request_number,
                r.reagent_name,
                ri.quantity_requested,
                ri.quantity_received
            FROM Requisition_Item AS ri
            LEFT JOIN Requisition AS rq ON rq.requisition_id = ri.requisition_id
            LEFT JOIN Reagent AS r ON r.reagent_id = ri.reagent_id
            WHERE LOWER(COALESCE(rq.status, '')) IN ('approved', 'completed')
            ORDER BY rq.request_date DESC, rq.requisition_id DESC, r.reagent_name ASC
            """
        ).fetchall()
    return [
        (
            row["requisition_item_id"],
            f"Reagent {row['reagent_id']} - {row['reagent_name']} | {row['request_number']} ({row['quantity_requested']})",
        )
        for row in rows
    ]


def requisition_item_choices():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                ri.requisition_item_id,
                'REQ-' || printf('%06d', rq.requisition_id) AS request_number,
                r.reagent_name,
                ri.quantity_requested,
                ri.quantity_received
            FROM Requisition_Item AS ri
            LEFT JOIN Requisition AS rq ON rq.requisition_id = ri.requisition_id
            LEFT JOIN Reagent AS r ON r.reagent_id = ri.reagent_id
            WHERE LOWER(COALESCE(rq.status, '')) IN ('approved', 'completed')
              AND COALESCE(ri.quantity_received, 0) > 0
            ORDER BY rq.request_date DESC, rq.requisition_id DESC, r.reagent_name ASC
            """
        ).fetchall()
    return [
        (
            row["requisition_item_id"],
            f"{row['request_number']} - {row['reagent_name']} ({row['quantity_requested']})",
        )
        for row in rows
    ]
