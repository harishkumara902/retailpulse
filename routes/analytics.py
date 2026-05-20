from flask import Blueprint, jsonify
from flask_login import login_required

from database import get_connection, rows_to_dicts
from ml.anomaly import detect_anomalies
from ml.churn_model import predict_churn
from ml.forecasting import revenue_forecast


analytics_bp = Blueprint("analytics", __name__, url_prefix="/api")


def scalar(conn, query, params=()):
    row = conn.execute(query, params).fetchone()
    return list(row)[0] if row else 0


@analytics_bp.get("/kpi")
@login_required
def kpi():
    with get_connection() as conn:
        current_month = scalar(conn, "SELECT MAX(strftime('%Y-%m', order_date)) FROM orders")
        prev_month = scalar(
            conn,
            "SELECT strftime('%Y-%m', date(MAX(order_date), 'start of month', '-1 month')) FROM orders",
        )
        row = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN status='completed' THEN total_amount END), 0) AS total_revenue,
                   COUNT(*) AS total_orders,
                   COUNT(DISTINCT customer_id) AS active_customers,
                   COALESCE(AVG(CASE WHEN status='completed' THEN total_amount END), 0) AS avg_order_value
            FROM orders
            """
        ).fetchone()
        this_month = scalar(conn, "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE status='completed' AND strftime('%Y-%m', order_date)=?", (current_month,))
        last_month = scalar(conn, "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE status='completed' AND strftime('%Y-%m', order_date)=?", (prev_month,))
        return_count = scalar(conn, "SELECT COUNT(*) FROM returns")
        completed_orders = scalar(conn, "SELECT COUNT(*) FROM orders WHERE status='completed'")
        churn = predict_churn(conn, 500)
        high_risk = sum(1 for item in churn if item["risk_level"] == "High")
    mom_growth = ((this_month - last_month) / last_month * 100) if last_month else 0
    return jsonify(
        {
            "total_revenue": round(row["total_revenue"], 2),
            "total_orders": row["total_orders"],
            "active_customers": row["active_customers"],
            "avg_order_value": round(row["avg_order_value"], 2),
            "mom_growth": round(mom_growth, 2),
            "return_rate": round(return_count * 100 / completed_orders, 2) if completed_orders else 0,
            "churn_risk": high_risk,
        }
    )


@analytics_bp.get("/revenue-trend")
@login_required
def revenue_trend():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', order_date) as month,
                   SUM(total_amount) as revenue,
                   COUNT(*) as order_count,
                   AVG(total_amount) as avg_order_value
            FROM orders WHERE status = 'completed'
            GROUP BY month ORDER BY month
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/customer-ltv")
@login_required
def customer_ltv():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.segment, c.region,
                   COUNT(o.id) as total_orders,
                   COALESCE(SUM(o.total_amount), 0) as ltv,
                   COALESCE(AVG(o.total_amount), 0) as avg_order,
                   MIN(o.order_date) as first_order,
                   MAX(o.order_date) as last_order,
                   COALESCE(JULIANDAY((SELECT MAX(order_date) FROM orders)) - JULIANDAY(MAX(o.order_date)), 999) as days_since_last_order
            FROM customers c LEFT JOIN orders o ON c.id = o.customer_id AND o.status='completed'
            GROUP BY c.id
            ORDER BY ltv DESC
            LIMIT 100
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/cohort")
@login_required
def cohort():
    with get_connection() as conn:
        rows = conn.execute(
            """
            WITH cohort_base AS (
                SELECT customer_id,
                       strftime('%Y-%m', MIN(order_date)) as cohort_month
                FROM orders WHERE status='completed' GROUP BY customer_id
            ),
            cohort_activity AS (
                SELECT o.customer_id,
                       cb.cohort_month,
                       strftime('%Y-%m', o.order_date) as order_month,
                       (CAST(strftime('%Y', o.order_date) AS INTEGER) - CAST(strftime('%Y', cb.cohort_month || '-01') AS INTEGER)) * 12 +
                       (CAST(strftime('%m', o.order_date) AS INTEGER) - CAST(strftime('%m', cb.cohort_month || '-01') AS INTEGER)) as period
                FROM orders o JOIN cohort_base cb ON o.customer_id = cb.customer_id
                WHERE o.status='completed'
            ),
            cohort_counts AS (
                SELECT cohort_month, period, COUNT(DISTINCT customer_id) as customers
                FROM cohort_activity GROUP BY cohort_month, period
            )
            SELECT c.cohort_month, c.period, c.customers,
                   FIRST_VALUE(c.customers) OVER (PARTITION BY c.cohort_month ORDER BY c.period) AS cohort_size,
                   ROUND(c.customers * 100.0 / FIRST_VALUE(c.customers) OVER (PARTITION BY c.cohort_month ORDER BY c.period), 2) AS retention
            FROM cohort_counts c
            ORDER BY cohort_month, period
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/return-rate")
@login_required
def return_rate():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.category,
                   COUNT(DISTINCT oi.order_id) as total_orders,
                   COUNT(DISTINCT r.id) as total_returns,
                   ROUND(COUNT(DISTINCT r.id) * 100.0 / COUNT(DISTINCT oi.order_id), 2) as return_rate,
                   COALESCE(SUM(r.refund_amount), 0) as total_refunded
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            LEFT JOIN returns r ON oi.order_id = r.order_id AND oi.product_id = r.product_id
            GROUP BY p.category
            ORDER BY return_rate DESC
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/regional")
@login_required
def regional():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT region,
                   COUNT(*) as orders,
                   SUM(total_amount) as revenue,
                   AVG(total_amount) as avg_order,
                   AVG(shipping_days) as avg_shipping
            FROM orders WHERE status='completed'
            GROUP BY region
            ORDER BY revenue DESC
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/products")
@login_required
def products():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.name, p.category,
                   SUM(oi.quantity) as units_sold,
                   SUM(oi.quantity * oi.unit_price) as revenue,
                   SUM(oi.quantity * (oi.unit_price - p.cost)) as profit,
                   ROUND(SUM(oi.quantity * (oi.unit_price - p.cost)) * 100.0 / SUM(oi.quantity * oi.unit_price), 2) AS margin,
                   COUNT(DISTINCT oi.order_id) as orders
            FROM products p JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status='completed'
            GROUP BY p.id ORDER BY revenue DESC LIMIT 20
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/segment-distribution")
@login_required
def segment_distribution():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT region, segment, COUNT(*) AS customers
            FROM customers
            GROUP BY region, segment
            ORDER BY region, segment
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/category-performance")
@login_required
def category_performance():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.category,
                   SUM(oi.quantity * oi.unit_price) AS revenue,
                   SUM(oi.quantity) AS units_sold,
                   SUM(oi.quantity * (oi.unit_price - p.cost)) AS profit
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status='completed'
            GROUP BY p.category
            ORDER BY revenue DESC
            """
        ).fetchall()
    return jsonify(rows_to_dicts(rows))


@analytics_bp.get("/churn-risk")
@login_required
def churn_risk():
    with get_connection() as conn:
        rows = predict_churn(conn, 100)
    return jsonify(rows)


@analytics_bp.get("/anomalies")
@login_required
def anomalies():
    with get_connection() as conn:
        rows = detect_anomalies(conn)
    return jsonify(rows)


@analytics_bp.get("/forecast")
@login_required
def forecast():
    with get_connection() as conn:
        data = revenue_forecast(conn)
    return jsonify(data)
