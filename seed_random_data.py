"""Add random demo data to the blood bank database.

This script uses only the Python standard library so it can run in the local
workspace Python without extra dependencies.
"""

from __future__ import annotations

import random
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"


SUPPLIER_BASES = [
    "Metro Diagnostics",
    "Prime BioLab",
    "Apex Medical Supply",
    "Nova Reagents",
    "Central Lab Traders",
    "MediCore Supplies",
    "BluePeak Laboratory",
    "BrightPath Diagnostics",
]

REAGENT_BLUEPRINTS = [
    ("Anti-A Blood Grouping Reagent", "Blood Grouping Reagent"),
    ("Anti-B Blood Grouping Reagent", "Blood Grouping Reagent"),
    ("Anti-D Blood Grouping Reagent", "Blood Grouping Reagent"),
    ("AHG Reagent", "AHG Reagent"),
    ("Coombs Control Cells", "Control Reagent"),
    ("A1 Cells", "Screening & Identification Cells"),
    ("B Cells", "Screening & Identification Cells"),
    ("LISS Enhancement Solution", "Enhancement Reagent"),
    ("PEG Enhancement Solution", "Enhancement Reagent"),
    ("ABO Control Serum", "Control Reagent"),
]

MANUFACTURERS = [
    "BioTech Labs",
    "Hemacare",
    "Orion Diagnostics",
    "VitaCell",
    "CellSafe",
    "Medigen",
]

STORAGE_LOCATIONS = [
    "Refrigerator A1",
    "Refrigerator A2",
    "Refrigerator B1",
    "QC Shelf 1",
    "QC Shelf 2",
    "Blood Bank Cabinet",
]

QC_TYPES = [
    "Daily QC",
    "New Lot QC",
    "New Vial QC",
    "Periodic QC",
]

UOMS = ["mL", "test", "vial", "kit"]


def connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rand_token(length: int = 4) -> str:
    return secrets.token_hex(length // 2 + 1)[:length].upper()


def rand_past_date(days_back: int = 240) -> str:
    return (datetime.now() - timedelta(days=random.randint(1, days_back))).strftime("%Y-%m-%d")


def rand_future_date(days_ahead: int = 420) -> str:
    return (datetime.now() + timedelta(days=random.randint(30, days_ahead))).strftime("%Y-%m-%d")


def rand_datetime(days_back: int = 90) -> str:
    dt = datetime.now() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return dt.replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def get_role_user_id(conn, role: str):
    row = conn.execute(
        """
        SELECT user_id
        FROM User
        WHERE LOWER(COALESCE(role, '')) = LOWER(?)
        ORDER BY user_id ASC
        LIMIT 1
        """,
        (role,),
    ).fetchone()
    return row["user_id"] if row else None


def seed_suppliers(conn, count: int = 6):
    existing = {row["supplier_name"] for row in conn.execute("SELECT supplier_name FROM Supplier").fetchall()}
    admin_id = get_role_user_id(conn, "ADM")
    inserted = 0
    for base in SUPPLIER_BASES:
        if inserted >= count:
            break
        name = f"{base} {rand_token(3)}"
        if name in existing:
            continue
        conn.execute(
            """
            INSERT INTO Supplier (
                supplier_name, contact_person, phone, email, address, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                name,
                f"Contact {rand_token(3)}",
                f"+66-2-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                f"{name.lower().replace(' ', '.')}@example.com",
                f"{random.randint(10, 99)} Lab Street",
            ),
        )
        inserted += 1
    conn.commit()


def seed_reagent_bundle(conn, supplier_name: str, created_by_user_id: int):
    base_name, reagent_type = random.choice(REAGENT_BLUEPRINTS)
    reagent_name = f"{base_name} {rand_token(3)}"
    lot_number = f"LOT-{datetime.now().strftime('%y%m')}-{rand_token(5)}"
    manufacturer_date = rand_past_date(240)
    expiry_date = rand_future_date(420)
    storage_condition = random.choice(["2-8 C", "Room temperature", "Frozen"])
    manufacturer = random.choice(MANUFACTURERS)
    reagent_code = f"RG-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    supplier_row = conn.execute(
        "SELECT supplier_id FROM Supplier WHERE supplier_name = ?",
        (supplier_name,),
    ).fetchone()
    supplier_id = supplier_row["supplier_id"] if supplier_row else None

    conn.execute(
        """
        INSERT INTO Reagent (
            reagent_code, reagent_name, supplier_id, manufacturer, category, unit_of_measure,
            storage_condition, critical_level, is_active, created_at, updated_at,
            reagent_type, lot_number, manufacturer_date, expiry_date, supplier, minimum_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
        """,
        (
            reagent_code,
            reagent_name,
            supplier_id,
            manufacturer,
            reagent_type,
            "unit",
            storage_condition,
            random.randint(1, 5),
            1,
            reagent_type,
            lot_number,
            manufacturer_date,
            expiry_date,
            supplier_name,
            random.randint(1, 5),
        ),
    )
    reagent_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    return {
        "reagent_id": reagent_id,
        "reagent_name": reagent_name,
        "lot_number": lot_number,
        "expiry_date": expiry_date,
        "created_by_user_id": created_by_user_id,
    }


def seed_receiving_and_qc(conn, reagent_info: dict, received_by_user_id: int, qc_result: str):
    receiving_number = f"RCV-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{rand_token(3)}"
    quantity_received = round(random.uniform(8, 25), 2)
    unit_cost = round(random.uniform(12, 88), 2)
    storage_location = random.choice(STORAGE_LOCATIONS)
    inventory_status = "Available for Use" if qc_result == "Pass" else "QC Failed"
    qc_status = "passed" if qc_result == "Pass" else "failed"
    qc_datetime = rand_datetime(60)

    conn.execute(
        """
        INSERT INTO Inventory (
            reagent_id, lot_number, expiry_date, quantity_on_hand, minimum_level,
            storage_location, status, last_updated, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            reagent_info["reagent_id"],
            reagent_info["lot_number"],
            reagent_info["expiry_date"],
            quantity_received,
            round(random.uniform(2, 6), 2),
            storage_location,
            "Pending QC",
        ),
    )
    inventory_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    conn.execute(
        """
        INSERT INTO Reagent_Receiving (
            receiving_number, request_detail_id, supplier_id, received_by_user_id, inventory_id,
            reagent_id, received_date, lot_number, expiry_date, quantity_received, unit_cost,
            invoice_number, remarks, created_at, updated_at
        ) VALUES (
            ?, NULL,
            (SELECT supplier_id FROM Supplier WHERE supplier_name = (SELECT supplier FROM Reagent WHERE reagent_id = ?)),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """,
        (
            receiving_number,
            reagent_info["reagent_id"],
            received_by_user_id,
            inventory_id,
            reagent_info["reagent_id"],
            qc_datetime,
            reagent_info["lot_number"],
            reagent_info["expiry_date"],
            quantity_received,
            unit_cost,
            f"INV-{rand_token(6)}",
            "Auto-generated sample receiving record",
        ),
    )

    conn.execute(
        """
        INSERT INTO QC_record (
            inventory_id, inspected_by_user_id, qc_date, result, remarks, temperature_c, pH_value,
            status, created_at, updated_at, qc_datetime, qc_type, qc_result, qc_comment, user_id, reagent_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
        """,
        (
            inventory_id,
            received_by_user_id,
            qc_datetime,
            qc_result,
            f"Auto-generated {qc_result.lower()} QC record",
            round(random.uniform(2.0, 8.0), 1),
            round(random.uniform(6.4, 7.4), 2),
            qc_status,
            qc_datetime,
            random.choice(QC_TYPES),
            qc_result,
            f"Auto-generated {qc_result.lower()} QC record",
            received_by_user_id,
            reagent_info["reagent_id"],
        ),
    )

    conn.execute(
        """
        UPDATE Inventory
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE inventory_id = ?
        """,
        (inventory_status, inventory_id),
    )

    return inventory_id, quantity_received


def seed_reagents_and_inventory(conn, count: int = 8):
    admin_id = get_role_user_id(conn, "ADM")
    sup_id = get_role_user_id(conn, "SUP") or admin_id
    suppliers = [row["supplier_name"] for row in conn.execute("SELECT supplier_name FROM Supplier ORDER BY supplier_id ASC").fetchall()]

    reagent_ids = []
    for index in range(count):
        supplier_name = random.choice(suppliers) if suppliers else "Unknown Supplier"
        reagent_info = seed_reagent_bundle(conn, supplier_name, admin_id)
        qc_result = "Pass" if index % 3 != 1 else "Fail"
        seed_receiving_and_qc(conn, reagent_info, sup_id, qc_result)
        reagent_ids.append(reagent_info["reagent_id"])
        conn.commit()

    return reagent_ids


def available_inventory_rows(conn):
    return conn.execute(
        """
        SELECT
            i.inventory_id,
            i.reagent_id,
            i.lot_number,
            i.quantity_on_hand,
            i.expiry_date
        FROM Inventory AS i
        WHERE COALESCE(i.quantity_on_hand, 0) > 0
          AND LOWER(COALESCE(i.status, '')) = 'available for use'
        ORDER BY i.inventory_id ASC
        """
    ).fetchall()


def deduct_inventory_for_requisition(conn, reagent_id: int, quantity: float):
    rows = conn.execute(
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
    remaining = float(quantity)
    for row in rows:
        if remaining <= 0:
            break
        available = float(row["quantity_on_hand"] or 0)
        if available <= 0:
            continue
        deduct = min(available, remaining)
        conn.execute(
            """
            UPDATE Inventory
            SET quantity_on_hand = quantity_on_hand - ?,
                last_updated = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = ?
            """,
            (deduct, row["inventory_id"]),
        )
        remaining -= deduct
    return remaining <= 0


def seed_requisitions(conn, count: int = 5):
    mt_id = get_role_user_id(conn, "MT") or get_role_user_id(conn, "SUP")
    sup_id = get_role_user_id(conn, "SUP") or get_role_user_id(conn, "ADM")
    pool = available_inventory_rows(conn)
    if not pool:
        return

    statuses = ["Pending", "Approved", "Rejected", "Completed", "Pending"]
    for index in range(count):
        chosen = random.sample(pool, k=min(2, len(pool)))
        status = statuses[index % len(statuses)]
        approval_date = rand_datetime(20) if status in {"Approved", "Completed"} else None
        approved_by = sup_id if status in {"Approved", "Completed"} else None
        request_date = rand_datetime(30)
        cursor = conn.execute(
            """
            INSERT INTO Requisition (
                request_date, status, requested_by, approved_by, approval_date, remarks, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                request_date,
                status,
                mt_id,
                approved_by,
                approval_date,
                f"Sample requisition {index + 1}",
            ),
        )
        requisition_id = cursor.lastrowid
        for row in chosen:
            qty = round(min(float(row["quantity_on_hand"]), random.uniform(1, 4)), 2)
            if status in {"Approved", "Completed"}:
                deduct_inventory_for_requisition(conn, row["reagent_id"], qty)
            conn.execute(
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
                    row["lot_number"],
                ),
            )
        conn.commit()


def bump_existing_qc(conn, count: int = 6):
    sup_id = get_role_user_id(conn, "SUP") or get_role_user_id(conn, "ADM")
    inventory_rows = conn.execute(
        """
        SELECT inventory_id
        FROM Inventory
        ORDER BY inventory_id ASC
        LIMIT ?
        """,
        (count,),
    ).fetchall()
    for idx, row in enumerate(inventory_rows):
        qc_result = random.choice(["Pass", "Pass", "Fail"])
        conn.execute(
            """
            INSERT INTO QC_record (
                inventory_id, inspected_by_user_id, qc_date, result, remarks, temperature_c, pH_value,
                status, created_at, updated_at, qc_datetime, qc_type, qc_result, qc_comment, user_id, reagent_id
            )
            SELECT
                i.inventory_id,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                ?,
                ?,
                ?,
                ?,
                ?,
                i.reagent_id
            FROM Inventory AS i
            WHERE i.inventory_id = ?
            """,
            (
                sup_id,
                rand_datetime(20),
                qc_result,
                f"Extra sample {qc_result.lower()} QC record",
                round(random.uniform(2.0, 8.0), 1),
                round(random.uniform(6.4, 7.4), 2),
                "passed" if qc_result == "Pass" else "failed",
                rand_datetime(20),
                random.choice(QC_TYPES),
                qc_result,
                f"Extra sample {qc_result.lower()} QC record",
                sup_id,
                row["inventory_id"],
            ),
        )
        conn.execute(
            """
            UPDATE Inventory
            SET status = CASE WHEN ? = 'Pass' THEN 'Available for Use' ELSE 'QC Failed' END,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = ?
            """,
            (qc_result, row["inventory_id"]),
        )
    conn.commit()


def main():
    random.seed()
    with connect() as conn:
        seed_suppliers(conn, count=6)
        seed_reagents_and_inventory(conn, count=8)
        bump_existing_qc(conn, count=6)
        seed_requisitions(conn, count=5)
    print("Random demo data added successfully.")


if __name__ == "__main__":
    main()
