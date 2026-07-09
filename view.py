"""Presentation helpers for Flask templates."""

from flask import render_template


def render_index(**context):
    return render_template("index.html", **context)


def render_login(**context):
    return render_template("login.html", **context)


def render_register(**context):
    return render_template("register.html", **context)


def render_reagent_list(**context):
    return render_template("reagents/list.html", **context)


def render_reagent_form(**context):
    return render_template("reagents/form.html", **context)


def render_supplier_list(**context):
    return render_template("suppliers/list.html", **context)


def render_supplier_form(**context):
    return render_template("suppliers/form.html", **context)


def render_inventory_list(**context):
    return render_template("inventory/list.html", **context)


def render_inventory_form(**context):
    return render_template("inventory/form.html", **context)


def render_receiving_list(**context):
    return render_template("receiving/list.html", **context)


def render_receiving_form(**context):
    return render_template("receiving/form.html", **context)


def render_qc_list(**context):
    return render_template("qc/list.html", **context)


def render_qc_form(**context):
    return render_template("qc/form.html", **context)


def render_request_list(**context):
    return render_template("requests/list.html", **context)


def render_request_form(**context):
    return render_template("requests/form.html", **context)


def render_dashboard(**context):
    return render_template("dashboard.html", **context)


def render_reports(**context):
    return render_template("reports.html", **context)


def render_audit_log_list(**context):
    return render_template("audit_log/list.html", **context)
