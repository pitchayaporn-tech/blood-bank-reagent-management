"""Create a coherent blood bank demo dataset.

This adds related suppliers, reagents, inventory, QC, receiving, and requisition
records so the website looks like a real working lab instead of unrelated rows.
The script appends data to the existing database.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"

SUPPLIERS = [
    {
        "supplier_name": "Metro Diagnostics",
        "contact_person": "Anong S.",
        "phone": "+66-2-555-0101",
        "email": "orders@metrodiagnostics.example",
        "address": "12 Laboratory Road",
    },
    {
        "supplier_name": "Prime BioLab",
        "contact_person": "Kanya P.",
        "phone": "+66-2-555-0102",
        "email": "sales@primebiolab.example",
        "address": "44 Science Avenue",
    },
    {
        "supplier_name": "Apex Medical Supply",
        "contact_person": "Somchai T.",
        "phone": "+66-2-555-0103",
        "email": "support@apexmed.example",
        "address": "88 Hospital Link",
    },
    {
        "supplier_name": "Nova Reagents",
        "contact_person": "Ratchanee W.",
        "phone": "+66-2-555-0104",
        "email": "care@novareagents.example",
        "address": "9 Diagnostic Circle",
    },
    {
        "supplier_name": "Central Lab Traders",
        "contact_person": "Niran C.",
        "phone": "+66-2-555-0105",
        "email": "hello@centrallab.example",
        "address": "101 Central Plaza",
    },
]

DEMO_BATCH = [
    {
        "reagent_name": "Anti-A Blood Grouping Reagent",
        "reagent_type": "Blood Grouping Reagent",
        "manufacturer": "BioTech Labs",
        "storage_condition": "2-8 C",
        "supplier_name": "Metro Diagnostics",
        "lot_number": "AA-2407-001",
        "quantity_on_hand": 18,
        "minimum_level": 4,
        "qc_result": "Pass",
        "qc_type": "New Lot QC",
        "storage_location": "Refrigerator A1",
        "expiry_days": 240,
    },
    {
        "reagent_name": "Anti-B Blood Grouping Reagent",
        "reagent_type": "Blood Grouping Reagent",
        "manufacturer": "Hemacare",
        "storage_condition": "2-8 C",
        "supplier_name": "Prime BioLab",
        "lot_number": "AB-2407-001",
        "quantity_on_hand": 16,
        "minimum_level": 4,
        "qc_result": "Pass",
        "qc_type": "New Lot QC",
        "storage_location": "Refrigerator A1",
        "expiry_days": 210,
    },
    {
        "reagent_name": "Anti-D Blood Grouping Reagent",
        "reagent_type": "Blood Grouping Reagent",
        "manufacturer": "Orion Diagnostics",
        "storage_condition": "2-8 C",
        "supplier_name": "Apex Medical Supply",
        "lot_number": "AD-2407-001",
        "quantity_on_hand": 14,
        "minimum_level": 3,
        "qc_result": "Fail",
        "qc_type": "New Lot QC",
        "storage_location": "Refrigerator A2",
        "expiry_days": 180,
    },
    {
        "reagent_name": "AHG Reagent",
        "reagent_type": "AHG Reagent",
        "manufacturer": "VitaCell",
        "storage_condition": "2-8 C",
        "supplier_name": "Nova Reagents",
        "lot_number": "AHG-2407-001",
        "quantity_on_hand": 12,
        "minimum_level": 3,
        "qc_result": "Pass",
        "qc_type": "Periodic QC",
        "storage_location": "QC Shelf 1",
        "expiry_days": 300,
    },
    {
        "reagent_name": "A1 Cells",
        "reagent_type": "Screening & Identification Cells",
        "manufacturer": "CellSafe",
        "storage_condition": "Frozen",
        "supplier_name": "Central Lab Traders",
        "lot_number": "A1-2407-001",
        "quantity_on_hand": 10,
        "minimum_level": 2,
        "qc_result": "Pass",
        "qc_type": "Daily QC",
        "storage_location": "QC Shelf 2",
        "expiry_days": 150,
    },
    {
        "reagent_name": "B Cells",
        "reagent_type": "Screening & Identification Cells",
        "manufacturer": "Medigen",
        "storage_condition": "Frozen",
        "supplier_name": "Metro Diagnostics",
        "lot_number": "B-2407-001",
        "quantity_on_hand": 11,
        "minimum_level": 2,
        "qc_result": "Pass",
        "qc_type": "New Vial QC",
        "storage_location": "Refrigerator B1",
        "expiry_days": 160,
    },
    {
        "reagent_name": "LISS Enhancement Solution",
        "reagent_type": "Enhancement Reagent",
        "manufacturer": "BioTech Labs",
        "storage_condition": "Room temperature",
        "supplier_name": "Prime BioLab",
        "lot_number": "LISS-2407-001",
        "quantity_on_hand": 20,
        "minimum_level": 5,
        "qc_result": "Pass",
        "qc_type": "Daily QC",
        "storage_location": "Blood Bank Cabinet",
        "expiry_days": 365,
    },
]

REQUESTS = [
    {"status": "Pending", "lines": 2},
    {"status": "Approved", "lines": 2},
    {"status": "Rejected", "lines": 1},
    {"status": "Completed", "lines": 2},
]


def connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_ts():
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def date_days_ahead(days: int) -> str:
    return (datetime.now().date() + timedelta(days=days)).isoformat()


def date_days_ago(days: int) -> str:
    return (datetime.now().date() - timedelta(days=days)).isoformat()


def get_user_id(conn, role: str):
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


def ensure_supplier(conn, supplier):
    conn.execute(
        """
        INSERT OR IGNORE INTO Supplier (
            supplier_name, contact_person, phone, email, address, is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            supplier["supplier_name"],
            supplier["contact_person"],
            supplier["phone"],
            supplier["email"],
            supplier["address"],
        ),
    )
    row = conn.execute(
        "SELECT supplier_id FROM Supplier WHERE supplier_name = ?",
        (supplier["supplier_name"],),
    ).fetchone()
    return row["supplier_id"] if row else None


def insert_reagent(conn, batch):
    supplier_row = conn.execute(
        "SELECT supplier_id FROM Supplier WHERE supplier_name = ?",
        (batch["supplier_name"],),
    ).fetchone()
    supplier_id = supplier_row["supplier_id"] if supplier_row else None

    reagent_values = {
        "reagent_code": f"CORR-{batch['lot_number']}",
        "reagent_name": batch["reagent_name"],
        "supplier_id": supplier_id,
        "manufacturer": batch["manufacturer"],
        "category": batch["reagent_type"],
        "unit_of_measure": "unit",
        "storage_condition": batch["storage_condition"],
        "critical_level": batch["minimum_level"],
        "is_active": 1,
        "reagent_type": batch["reagent_type"],
        "lot_number": batch["lot_number"],
        "manufacturer_date": date_days_ago(45),
        "expiry_date": date_days_ahead(batch["expiry_days"]),
        "supplier": batch["supplier_name"],
        "minimum_level": batch["minimum_level"],
    }
    columns = conn.execute("PRAGMA table_info(Reagent)").fetchall()
    insert_columns = []
    insert_values = []
    for column in columns:
        name = column["name"]
        if name in {"reagent_id", "created_at", "updated_at"}:
            continue
        insert_columns.append(name)
        value = reagent_values.get(name)
        if value is None and column["notnull"]:
            col_type = (column["type"] or "").upper()
            value = 0 if any(token in col_type for token in ("INT", "REAL", "NUM", "DEC")) else ""
        insert_values.append(value)

    conn.execute(
        f"""
        INSERT INTO Reagent (
            {", ".join(insert_columns)}, updated_at
        ) VALUES ({", ".join(["?"] * len(insert_columns))}, CURRENT_TIMESTAMP)
        """,
        tuple(insert_values),
    )
    row = conn.execute(
        "SELECT * FROM Reagent WHERE reagent_code = ?",
        (reagent_values["reagent_code"],),
    ).fetchone()
    return row


def insert_inventory_qc_receiving(conn, reagent_row, batch, received_by_user_id):
    quantity = batch["quantity_on_hand"]
    inventory_status = "Available for Use" if batch["qc_result"] == "Pass" else "QC Failed"
    qc_status = "passed" if batch["qc_result"] == "Pass" else "failed"
    receiving_number = f"RCV-{batch['lot_number']}"
    qc_time = now_ts()

    conn.execute(
        """
        INSERT INTO Inventory (
            reagent_id, lot_number, expiry_date, quantity_on_hand, minimum_level, storage_location,
            status, last_updated, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            reagent_row["reagent_id"],
            batch["lot_number"],
            date_days_ahead(batch["expiry_days"]),
            quantity,
            batch["minimum_level"],
            batch["storage_location"],
            inventory_status,
        ),
    )
    inventory_row = conn.execute(
        "SELECT * FROM Inventory WHERE reagent_id = ? AND lot_number = ? ORDER BY inventory_id DESC LIMIT 1",
        (reagent_row["reagent_id"], batch["lot_number"]),
    ).fetchone()

    supplier_row = conn.execute(
        "SELECT supplier_id FROM Supplier WHERE supplier_name = ?",
        (batch["supplier_name"],),
    ).fetchone()
    supplier_id = supplier_row["supplier_id"] if supplier_row else None

    conn.execute(
        """
        INSERT INTO Reagent_Receiving (
            receiving_number, request_detail_id, supplier_id, received_by_user_id, inventory_id, reagent_id,
            received_date, lot_number, expiry_date, quantity_received, unit_cost, invoice_number, remarks,
            created_at, updated_at
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            receiving_number,
            supplier_id,
            received_by_user_id,
            inventory_row["inventory_id"],
            reagent_row["reagent_id"],
            qc_time,
            batch["lot_number"],
            date_days_ahead(batch["expiry_days"]),
            quantity,
            round(random.uniform(12, 88), 2),
            f"INV-{batch['lot_number']}",
            "Correlated demo receiving record",
        ),
    )

    conn.execute(
        """
        INSERT INTO QC_record (
            inventory_id, inspected_by_user_id, qc_date, result, remarks, temperature_c, pH_value, status,
            created_at, updated_at, qc_datetime, qc_type, qc_result, qc_comment, user_id, reagent_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
        """,
        (
            inventory_row["inventory_id"],
            received_by_user_id,
            qc_time,
            batch["qc_result"],
            f"Correlated demo {batch['qc_result'].lower()} QC record",
            4.0,
            7.0,
            qc_status,
            qc_time,
            batch["qc_type"],
            batch["qc_result"],
            f"Correlated demo {batch['qc_result'].lower()} QC record",
            received_by_user_id,
            reagent_row["reagent_id"],
        ),
    )

    conn.execute(
        """
        UPDATE Inventory
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE inventory_id = ?
        """,
        (inventory_status, inventory_row["inventory_id"]),
    )
    return inventory_row


def available_inventory(conn):
    return conn.execute(
        """
        SELECT i.inventory_id, i.reagent_id, i.lot_number, i.quantity_on_hand, r.reagent_name
        FROM Inventory AS i
        JOIN Reagent AS r ON r.reagent_id = i.reagent_id
        WHERE LOWER(COALESCE(i.status, '')) = 'available for use'
          AND COALESCE(i.quantity_on_hand, 0) > 0
        ORDER BY i.inventory_id ASC
        """
    ).fetchall()


def requisition_item_lot(conn, reagent_id):
    row = conn.execute(
        "SELECT lot_number FROM Inventory WHERE reagent_id = ? ORDER BY inventory_id ASC LIMIT 1",
        (reagent_id,),
    ).fetchone()
    return row["lot_number"] if row else None


def deduct_inventory(conn, reagent_id, quantity):
    rows = conn.execute(
        """
        SELECT inventory_id, quantity_on_hand
        FROM Inventory
        WHERE reagent_id = ?
        ORDER BY inventory_id ASC
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
        deduction = min(available, remaining)
        conn.execute(
            """
            UPDATE Inventory
            SET quantity_on_hand = quantity_on_hand - ?,
                last_updated = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE inventory_id = ?
            """,
            (deduction, row["inventory_id"]),
        )
        remaining -= deduction


def create_requisition(conn, requested_by_user_id, approved_by_user_id, status, rows, note):
    cursor = conn.execute(
        """
        INSERT INTO Requisition (
            request_date, status, requested_by, approved_by, approval_date, remarks, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            now_ts(),
            status,
            requested_by_user_id,
            approved_by_user_id if status in {"Approved", "Completed"} else None,
            now_ts() if status in {"Approved", "Completed"} else None,
            note,
        ),
    )
    requisition_id = cursor.lastrowid
    for line in rows:
        qty = line["quantity"]
        if status in {"Approved", "Completed"}:
            deduct_inventory(conn, line["reagent_id"], qty)
        conn.execute(
            """
            INSERT INTO Requisition_Item (
                requisition_id, reagent_id, quantity_requested, quantity_received, created_at, updated_at, lot_number
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            """,
            (
                requisition_id,
                line["reagent_id"],
                qty,
                qty if status in {"Approved", "Completed"} else 0,
                line["lot_number"],
            ),
        )


def main():
    with connect() as conn:
        admin_id = get_user_id(conn, "ADM")
        sup_id = get_user_id(conn, "SUP") or admin_id
        mt_id = get_user_id(conn, "MT") or sup_id

        for supplier in SUPPLIERS:
            ensure_supplier(conn, supplier)

        reagent_rows = []
        for batch in DEMO_BATCH:
            reagent_row = insert_reagent(conn, batch)
            reagent_rows.append((reagent_row, batch))
        conn.commit()

        inventory_rows = []
        for reagent_row, batch in reagent_rows:
            inventory_row = insert_inventory_qc_receiving(conn, reagent_row, batch, sup_id)
            inventory_rows.append((inventory_row, batch))
        conn.commit()

        usable = [row for row in available_inventory(conn)]
        if usable:
            request_sets = [
                ("Pending", 2, "Pending restock request for routine workflow"),
                ("Approved", 2, "Approved request for urgent issue"),
                ("Rejected", 1, "Rejected due to stock review"),
                ("Completed", 2, "Completed issue request"),
            ]
            for index, (status, line_count, note) in enumerate(request_sets):
                chosen_rows = usable[index : index + line_count]
                if len(chosen_rows) < line_count:
                    chosen_rows = usable[:line_count]
                lines = []
                for row in chosen_rows:
                    lines.append(
                        {
                            "reagent_id": row["reagent_id"],
                            "lot_number": row["lot_number"],
                            "quantity": round(min(float(row["quantity_on_hand"]), random.uniform(1, 3)), 2),
                        }
                    )
                create_requisition(conn, mt_id, sup_id, status, lines, note)
            conn.commit()

    print("Correlated demo data added successfully.")


if __name__ == "__main__":
    main()
