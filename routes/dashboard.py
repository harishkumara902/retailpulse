from flask import Blueprint, render_template
from flask_login import login_required


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@login_required
def dashboard():
    return render_template("dashboard.html", title="Dashboard")


@dashboard_bp.get("/customers")
@login_required
def customers():
    return render_template("customers.html", title="Customers")


@dashboard_bp.get("/products")
@login_required
def products():
    return render_template("products.html", title="Products")


@dashboard_bp.get("/regions")
@login_required
def regions():
    return render_template("regions.html", title="Regions")


@dashboard_bp.get("/cohorts")
@login_required
def cohorts():
    return render_template("cohorts.html", title="Cohorts")


@dashboard_bp.get("/anomalies")
@login_required
def anomalies():
    return render_template("anomalies.html", title="Anomalies")


@dashboard_bp.get("/ai-insights")
@login_required
def ai_insights():
    return render_template("ai_insights.html", title="AI Insights")


@dashboard_bp.get("/exports")
@login_required
def exports():
    return render_template("exports.html", title="Export")
