"""Application controller."""

from datetime import date, datetime
from functools import wraps

from flask import Flask, flash, g, redirect, request, session, url_for

import model
import view
from forms import (
    DeleteForm,
    InventoryForm,
    QCRecordForm,
    ReceivingForm,
    ReagentForm,
    ReagentRequestForm,
    ReagentRequestStatusForm,
    RegistrationForm,
    reagent_type_choices,
    role_choices,
    SupplierForm,
)


def create_app():
    app = Flask(__name__)
    app.secret_key = "change-this-secret-key"

    model.initialize_database()

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = model.get_logged_in_user(user_id) if user_id else None

    @app.context_processor
    def inject_ui_helpers():
        def badge_class(value):
            text = (value or "").strip().lower()
            if not text:
                return "status-neutral"
            if any(token in text for token in ("pass", "active", "available", "approved", "completed", "fulfilled", "success")):
                return "status-success"
            if any(token in text for token in ("pending", "near expiry", "draft", "submitted", "warning")):
                return "status-warning"
            if any(token in text for token in ("low stock", "low", "near", "expiring")):
                return "status-low"
            if any(token in text for token in ("fail", "expired", "rejected", "inactive")):
                return "status-danger"
            return "status-neutral"

        def activity_icon(activity_type):
            mapping = {
                "Receiving": "bi-truck",
                "QC": "bi-clipboard2-pulse",
                "Request": "bi-file-earmark-text",
                "Usage": "bi-droplet",
            }
            return mapping.get(activity_type, "bi-circle")

        return {
            "badge_class": badge_class,
            "activity_icon": activity_icon,
        }

    def login_required(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if g.get("user") is None:
                next_url = request.full_path if request.query_string else request.path
                next_url = next_url.rstrip("?")
                return redirect(url_for("login", next=next_url))
            return view_func(*args, **kwargs)

        return wrapped_view

    def role_required(*allowed_roles):
        allowed = {model.normalize_role(role) for role in allowed_roles}

        def decorator(view_func):
            @wraps(view_func)
            def wrapped_view(*args, **kwargs):
                if g.get("user") is None:
                    next_url = request.full_path if request.query_string else request.path
                    next_url = next_url.rstrip("?")
                    return redirect(url_for("login", next=next_url))
                if model.normalize_role(g.user["role"]) not in allowed:
                    flash("You do not have permission to access that page.", "warning")
                    return redirect(url_for("dashboard"))
                return view_func(*args, **kwargs)

            return wrapped_view

        return decorator

    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/login", methods=("GET", "POST"))
    def login():
        next_url = request.args.get("next", "") if request.method == "GET" else request.form.get("next", "")
        if request.method == "POST":
            user = model.authenticate_user(
                request.form.get("username", "").strip(),
                request.form.get("password", ""),
            )
            if user is None:
                flash("Invalid username or password.", "danger")
                return view.render_login(next_url=next_url)

            session.clear()
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = model.normalize_role(user["role"])
            model.log_audit_event(
                user_id=user["user_id"],
                action="Login",
                entity_type="User",
                entity_id=user["user_id"],
                details=f"User {user['username']} logged in",
            )
            flash("You are now logged in.", "success")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        return view.render_login(next_url=next_url)

    @app.route("/register", methods=("GET", "POST"))
    @login_required
    @role_required("ADM")
    def register():
        form = RegistrationForm()
        form.role.choices = role_choices()
        selected_role = model.normalize_role(form.role.data or "MT")
        if request.method == "GET":
            form.role.data = selected_role
        generated_usernames = {role_value: model.preview_username(role_value) for role_value, _ in role_choices()}
        generated_username = generated_usernames.get(selected_role, model.preview_username("MT"))
        if request.method == "POST" and form.validate_on_submit():
            selected_role = model.normalize_role(request.form.get("role", form.role.data or "MT"))
            ok, generated_username, message = model.create_user(
                None,
                form.password.data,
                form.full_name.data,
                form.email.data,
                selected_role,
                actor_user_id=session["user_id"],
            )
            if ok:
                flash(f"User created successfully. Generated username: {generated_username}", "success")
                return redirect(url_for("register"))
            flash(message or "Unable to create account.", "danger")
        selected_role = model.normalize_role(form.role.data or request.form.get("role", "MT"))
        generated_username = generated_usernames.get(selected_role, model.preview_username("MT"))
        return view.render_register(
            form=form,
            generated_username=generated_username,
            generated_usernames=generated_usernames,
        )

    @app.route("/logout")
    @login_required
    def logout():
        if g.get("user") is not None:
            model.log_audit_event(
                user_id=session.get("user_id"),
                action="Logout",
                entity_type="User",
                entity_id=session.get("user_id"),
                details=f"User {session.get('username')} logged out",
            )
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    def dashboard():
        return view.render_dashboard(
            summary=model.get_dashboard_summary(),
            alerts=model.get_dashboard_alerts(),
            activity_feed=model.get_dashboard_activity_feed(),
        )

    @app.route("/reagents")
    @login_required
    def reagent_list():
        return view.render_reagent_list(
            reagents=model.list_reagents(request.args.get("q", "").strip(), request.args.get("type", "").strip()),
            search_term=request.args.get("q", "").strip(),
            reagent_type_filter=request.args.get("type", "").strip(),
            reagent_type_choices=reagent_type_choices(),
            delete_form=DeleteForm(),
        )

    @app.route("/reagents/add", methods=("GET", "POST"))
    @login_required
    @role_required("SUP", "ADM")
    def reagent_add():
        form = ReagentForm()
        form.reagent_type.choices = reagent_type_choices()
        if request.method == "POST" and form.validate_on_submit():
            model.create_reagent(
                {
                    "reagent_name": form.reagent_name.data,
                    "reagent_type": form.reagent_type.data,
                    "manufacturer": form.manufacturer.data,
                    "lot_number": form.lot_number.data,
                    "manufacturer_date": form.manufacturer_date.data.isoformat() if form.manufacturer_date.data else None,
                    "expiry_date": form.expiry_date.data.isoformat() if form.expiry_date.data else None,
                    "storage_condition": form.storage_condition.data,
                    "supplier": form.supplier.data,
                },
                actor_user_id=session["user_id"],
            )
            flash("Reagent added successfully.", "success")
            return redirect(url_for("reagent_list"))
        return view.render_reagent_form(form=form, form_title="Add Reagent")

    @app.route("/reagents/edit/<int:reagent_id>", methods=("GET", "POST"))
    @login_required
    @role_required("ADM")
    def reagent_edit(reagent_id):
        reagent = model.get_reagent(reagent_id)
        if reagent is None:
            flash("Reagent not found.", "warning")
            return redirect(url_for("reagent_list"))
        form = ReagentForm()
        form.reagent_type.choices = reagent_type_choices(reagent["reagent_type"])
        if request.method == "GET":
            form.reagent_name.data = reagent["reagent_name"]
            form.reagent_type.data = reagent["reagent_type"]
            form.manufacturer.data = reagent["manufacturer"]
            form.lot_number.data = reagent["lot_number"]
            form.manufacturer_date.data = date.fromisoformat(reagent["manufacturer_date"]) if reagent["manufacturer_date"] else None
            form.expiry_date.data = date.fromisoformat(reagent["expiry_date"]) if reagent["expiry_date"] else None
            form.storage_condition.data = reagent["storage_condition"]
            form.supplier.data = reagent["supplier"]
        if request.method == "POST" and form.validate_on_submit():
            model.update_reagent(
                reagent_id,
                {
                    "reagent_name": form.reagent_name.data,
                    "reagent_type": form.reagent_type.data,
                    "manufacturer": form.manufacturer.data,
                    "lot_number": form.lot_number.data,
                    "manufacturer_date": form.manufacturer_date.data.isoformat() if form.manufacturer_date.data else None,
                    "expiry_date": form.expiry_date.data.isoformat() if form.expiry_date.data else None,
                    "storage_condition": form.storage_condition.data,
                    "supplier": form.supplier.data,
                },
                actor_user_id=session["user_id"],
            )
            flash("Reagent updated successfully.", "success")
            return redirect(url_for("reagent_list"))
        return view.render_reagent_form(form=form, form_title="Edit Reagent")

    @app.route("/reagents/delete/<int:reagent_id>", methods=("POST",))
    @login_required
    @role_required("ADM")
    def reagent_delete(reagent_id):
        if DeleteForm().validate_on_submit():
            model.delete_reagent(reagent_id, actor_user_id=session["user_id"])
            flash("Reagent deleted successfully.", "success")
        else:
            flash("Unable to delete reagent.", "danger")
        return redirect(url_for("reagent_list"))

    @app.route("/suppliers")
    @login_required
    @role_required("ADM")
    def supplier_list():
        return view.render_supplier_list(suppliers=model.list_suppliers(), delete_form=DeleteForm())

    @app.route("/suppliers/add", methods=("GET", "POST"))
    @login_required
    @role_required("ADM")
    def supplier_add():
        form = SupplierForm()
        if request.method == "POST" and form.validate_on_submit():
            model.create_supplier(form.supplier_name.data, form.contact.data, actor_user_id=session["user_id"])
            flash("Supplier added successfully.", "success")
            return redirect(url_for("supplier_list"))
        return view.render_supplier_form(form=form, form_title="Add Supplier")

    @app.route("/suppliers/edit/<int:supplier_id>", methods=("GET", "POST"))
    @login_required
    @role_required("ADM")
    def supplier_edit(supplier_id):
        supplier = model.get_supplier(supplier_id)
        if supplier is None:
            flash("Supplier not found.", "warning")
            return redirect(url_for("supplier_list"))
        form = SupplierForm()
        if request.method == "GET":
            form.supplier_name.data = supplier["supplier_name"]
            form.contact.data = supplier["contact_person"]
        if request.method == "POST" and form.validate_on_submit():
            model.update_supplier(supplier_id, form.supplier_name.data, form.contact.data, actor_user_id=session["user_id"])
            flash("Supplier updated successfully.", "success")
            return redirect(url_for("supplier_list"))
        return view.render_supplier_form(form=form, form_title="Edit Supplier")

    @app.route("/suppliers/delete/<int:supplier_id>", methods=("POST",))
    @login_required
    @role_required("ADM")
    def supplier_delete(supplier_id):
        if DeleteForm().validate_on_submit():
            model.delete_supplier(supplier_id, actor_user_id=session["user_id"])
            flash("Supplier deleted successfully.", "success")
        else:
            flash("Unable to delete supplier.", "danger")
        return redirect(url_for("supplier_list"))

    @app.route("/inventory")
    @login_required
    def inventory_list():
        return view.render_inventory_list(
            inventory_items=model.list_inventory(request.args.get("q", "").strip()),
            search_term=request.args.get("q", "").strip(),
        )

    @app.route("/inventory/update/<int:inventory_id>", methods=("GET", "POST"))
    @login_required
    @role_required("SUP", "ADM")
    def inventory_update(inventory_id):
        item = model.get_inventory_item(inventory_id)
        if item is None:
            flash("Inventory item not found.", "warning")
            return redirect(url_for("inventory_list"))
        form = InventoryForm()
        if request.method == "GET":
            form.quantity.data = item["quantity_on_hand"]
            form.minimum_stock.data = item["minimum_level"]
            form.storage_location.data = item["storage_location"]
            form.status.data = item["status"]
        else:
            form.status.data = item["status"]
        if request.method == "POST" and form.validate_on_submit():
            model.update_inventory(
                inventory_id,
                float(form.quantity.data),
                float(form.minimum_stock.data),
                form.storage_location.data,
                item["status"],
                actor_user_id=session["user_id"],
            )
            flash("Inventory updated successfully.", "success")
            return redirect(url_for("inventory_list"))
        return view.render_inventory_form(form=form, form_title="Update Inventory", inventory_item=item)

    @app.route("/receiving")
    @login_required
    def receiving_list():
        return view.render_receiving_list(receiving_records=model.list_receiving())

    @app.route("/receiving/add", methods=("GET", "POST"))
    @login_required
    @role_required("SUP", "MT", "ADM")
    def receiving_add():
        form = ReceivingForm()
        form.reagent_id.choices = model.reagent_choices()
        if request.method == "GET":
            form.receiving_date.data = date.today()
        if request.method == "POST" and form.validate_on_submit():
            receiving_number, error = model.create_receiving(
                form.receiving_date.data.isoformat(),
                form.reagent_id.data,
                form.lot_number.data.strip(),
                form.expiry_date.data.isoformat(),
                float(form.quantity_received.data),
                int(session["user_id"]),
            )
            if error:
                flash(error, "danger")
                return view.render_receiving_form(form=form, form_title="Record Receiving")
            flash("Receiving recorded, inventory updated, and QC pending record created.", "success")
            return redirect(url_for("receiving_list"))
        return view.render_receiving_form(form=form, form_title="Record Receiving")

    @app.route("/qc")
    @login_required
    def qc_list():
        return view.render_qc_list(
            qc_records=model.list_qc(request.args.get("q", "").strip(), request.args.get("type", "").strip()),
            search_term=request.args.get("q", "").strip(),
            selected_type=request.args.get("type", "").strip(),
        )

    @app.route("/qc/add", methods=("GET", "POST"))
    @login_required
    @role_required("SUP", "MT", "ADM")
    def qc_add():
        form = QCRecordForm()
        form.inventory_id.choices = model.qc_lot_choices()
        if request.method == "GET":
            form.qc_datetime.data = datetime.now().replace(second=0, microsecond=0)
        if request.method == "POST" and form.validate_on_submit():
            try:
                model.create_qc_record(
                    form.qc_datetime.data.isoformat(sep=" "),
                    form.qc_type.data,
                    form.qc_result.data,
                    form.qc_comment.data,
                    int(session["user_id"]),
                    form.inventory_id.data,
                )
            except ValueError as exc:
                flash(str(exc), "danger")
            else:
                flash("QC record added successfully.", "success")
                return redirect(url_for("qc_list"))
        return view.render_qc_form(form=form, form_title="Add QC Record")

    @app.route("/qc/edit/<int:qc_record_id>", methods=("GET", "POST"))
    @login_required
    @role_required("SUP", "MT", "ADM")
    def qc_edit(qc_record_id):
        record = model.get_qc_record(qc_record_id)
        if record is None:
            flash("QC record not found.", "warning")
            return redirect(url_for("qc_list"))
        if int(record["user_id"]) != int(session["user_id"]):
            flash("You can only edit QC records that you created.", "warning")
            return redirect(url_for("qc_list"))

        form = QCRecordForm()
        form.inventory_id.choices = model.qc_lot_choices()
        if request.method == "GET":
            form.qc_datetime.data = datetime.fromisoformat(record["qc_datetime"])
            form.qc_type.data = record["qc_type"]
            form.qc_result.data = record["qc_result"] if record["qc_result"] in {"Pass", "Fail"} else ""
            form.qc_comment.data = record["qc_comment"]
            form.inventory_id.data = int(record["inventory_id"])
        if request.method == "POST" and form.validate_on_submit():
            ok, message = model.update_qc_record(
                qc_record_id,
                form.qc_datetime.data.isoformat(sep=" "),
                form.qc_type.data,
                form.qc_result.data,
                form.qc_comment.data,
                int(session["user_id"]),
                form.inventory_id.data,
                session["user_id"],
            )
            if ok:
                flash("QC record updated successfully.", "success")
                return redirect(url_for("qc_list"))
            flash(message or "Unable to update QC record.", "danger")
        return view.render_qc_form(form=form, form_title="Edit QC Record")

    @app.route("/requests")
    @login_required
    def request_history():
        return view.render_request_list(
            requests=model.request_history(),
            status_form=ReagentRequestStatusForm(),
        )

    @app.route("/requests/create", methods=("GET", "POST"))
    @login_required
    @role_required("MT", "SUP", "ADM")
    def request_create():
        form = ReagentRequestForm()
        reagent_choices = model.requisition_reagent_choices()
        if request.method == "POST":
            line_reagent_ids = request.form.getlist("reagent_id[]")
            line_quantities = request.form.getlist("requested_quantity[]")
            valid_lines = []
            for idx, reagent_id_value in enumerate(line_reagent_ids):
                reagent_id_value = (reagent_id_value or "").strip()
                quantity_value = (line_quantities[idx] if idx < len(line_quantities) else "").strip()
                if not reagent_id_value and not quantity_value:
                    continue
                if not reagent_id_value or not quantity_value:
                    flash("Please complete reagent and quantity for each requisition line.", "danger")
                    return view.render_request_form(form=form, reagent_choices=reagent_choices, line_count=max(len(line_reagent_ids), 1))
                valid_lines.append(
                    {
                        "reagent_id": int(reagent_id_value),
                        "requested_quantity": float(quantity_value),
                    }
                )
            if not valid_lines:
                flash("Add at least one reagent line.", "danger")
                return view.render_request_form(form=form, reagent_choices=reagent_choices, line_count=max(len(line_reagent_ids), 1))
            if form.validate_on_submit():
                request_number, error = model.create_request(
                    session["user_id"],
                    None,
                    form.notes.data,
                    valid_lines,
                )
                if error:
                    flash(error, "danger")
                    return view.render_request_form(form=form, reagent_choices=reagent_choices, line_count=max(len(line_reagent_ids), 1))
                flash("Requisition created successfully.", "success")
                return redirect(url_for("request_history"))
        return view.render_request_form(form=form, reagent_choices=reagent_choices, line_count=1)

    @app.route("/requests/status/<int:request_id>", methods=("POST",))
    @login_required
    @role_required("SUP", "ADM")
    def request_status_update(request_id):
        if ReagentRequestStatusForm().validate_on_submit():
            ok, message = model.update_request_status(request_id, request.form.get("status", "Pending"), session["user_id"])
            if ok:
                flash("Requisition status updated.", "success")
            else:
                flash(message or "Unable to update requisition status.", "danger")
        else:
            flash("Unable to update requisition status.", "danger")
        return redirect(url_for("request_history"))

    @app.route("/reports")
    @login_required
    def reports():
        return view.render_reports(
            inventory_report=model.get_inventory_report(),
            low_stock_report=model.get_low_stock_report(),
            fefo_report=model.get_fefo_report(),
            pending_qc_report=model.get_pending_qc_report(),
            failed_qc_report=model.get_failed_qc_report(),
            expiring_soon_report=model.get_expiring_soon_report(),
            qc_history_report=model.get_qc_history_report(),
            receiving_history_report=model.get_receiving_history_report(),
            expired_reagent_report=model.get_expired_reagent_report(),
        )

    @app.route("/audit-log")
    @login_required
    @role_required("SUP", "ADM")
    def audit_log():
        return view.render_audit_log_list(
            audit_logs=model.list_audit_logs(
                search_term=request.args.get("q", "").strip(),
                action_filter=request.args.get("action", "").strip(),
                user_filter=request.args.get("user", "").strip(),
                date_from=request.args.get("from", "").strip(),
                date_to=request.args.get("to", "").strip(),
            ),
            search_term=request.args.get("q", "").strip(),
            selected_action=request.args.get("action", "").strip(),
            selected_user=request.args.get("user", "").strip(),
            selected_from=request.args.get("from", "").strip(),
            selected_to=request.args.get("to", "").strip(),
            action_choices=model.audit_log_action_choices(),
            user_choices=model.audit_log_user_choices(),
        )

    return app
