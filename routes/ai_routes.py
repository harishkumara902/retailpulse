import json
import os
from datetime import date

from anthropic import Anthropic
from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from auth import role_required
from database import get_connection, rows_to_dicts
from ml.anomaly import detect_anomalies
from ml.churn_model import predict_churn


ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")
MODEL = "claude-3-5-haiku-latest"


def _session_counter(name, limit):
    today = date.today().isoformat()
    key = f"{name}_{today}"
    used = int(session.get(key, 0))
    if used >= limit:
        return False, 0
    session[key] = used + 1
    session.modified = True
    return True, limit - session[key]


def dashboard_snapshot(conn):
    kpi = conn.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN status='completed' THEN total_amount END), 0) AS total_revenue,
               COUNT(*) AS total_orders,
               COUNT(DISTINCT customer_id) AS customers
        FROM orders
        """
    ).fetchone()
    top_region = conn.execute(
        "SELECT region, SUM(total_amount) revenue FROM orders WHERE status='completed' GROUP BY region ORDER BY revenue DESC LIMIT 1"
    ).fetchone()
    top_category = conn.execute(
        """
        SELECT p.category, SUM(oi.quantity * oi.unit_price) revenue
        FROM products p JOIN order_items oi ON p.id=oi.product_id JOIN orders o ON o.id=oi.order_id
        WHERE o.status='completed'
        GROUP BY p.category ORDER BY revenue DESC LIMIT 1
        """
    ).fetchone()
    current_month = conn.execute("SELECT MAX(strftime('%Y-%m', order_date)) FROM orders").fetchone()[0]
    this_month = conn.execute(
        "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE status='completed' AND strftime('%Y-%m', order_date)=?",
        (current_month,),
    ).fetchone()[0]
    churn_count = sum(1 for row in predict_churn(conn, 500) if row["risk_level"] == "High")
    anomaly_count = len(detect_anomalies(conn))
    return {
        "total_revenue": round(kpi["total_revenue"], 2),
        "total_orders": kpi["total_orders"],
        "customers": kpi["customers"],
        "top_region": top_region["region"] if top_region else "N/A",
        "top_category": top_category["category"] if top_category else "N/A",
        "churn_risk_count": churn_count,
        "anomaly_count": anomaly_count,
        "this_month_revenue": round(this_month, 2),
    }


def call_claude(system_prompt, user_prompt, max_tokens=500):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in message.content if hasattr(block, "text"))


def fallback_insight(snapshot):
    return (
        f"- Revenue is strongest in {snapshot['top_region']}; prioritize inventory and campaigns there.\n"
        f"- {snapshot['top_category']} leads category revenue, so protect stock availability and margins.\n"
        f"- {snapshot['churn_risk_count']} customers are high churn risk; launch win-back offers for recent high-LTV buyers."
    )


@ai_bp.get("/history")
@login_required
def history():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM ai_insights ORDER BY generated_at DESC LIMIT 12").fetchall()
    return jsonify(rows_to_dicts(rows))


@ai_bp.post("/generate-insight")
@login_required
def generate_insight():
    ok, remaining = _session_counter("insight_count", 10)
    if not ok:
        return jsonify({"error": "Daily insight limit reached.", "remaining": 0}), 429
    with get_connection() as conn:
        snapshot = dashboard_snapshot(conn)
        system = "You are a senior data analyst. Analyze this e-commerce data and give 3 specific, actionable insights in bullet points. Be concise. Max 150 words."
        content = call_claude(system, json.dumps(snapshot), 500) or fallback_insight(snapshot)
        conn.execute(
            "INSERT INTO ai_insights (insight_type, content, data_snapshot) VALUES (?, ?, ?)",
            ("daily", content, json.dumps(snapshot)),
        )
        conn.commit()
    return jsonify({"content": content, "remaining": remaining})


@ai_bp.post("/chat")
@login_required
def chat():
    ok, remaining = _session_counter("chat_count", 20)
    if not ok:
        return jsonify({"error": "Daily chat limit reached.", "remaining": 0}), 429
    question = request.json.get("message", "").strip() if request.is_json else ""
    if not question:
        return jsonify({"error": "Message is required.", "remaining": remaining}), 400
    with get_connection() as conn:
        summary = dashboard_snapshot(conn)
    system = (
        "You are RetailPulse AI, a data analyst assistant. You have access to this "
        f"e-commerce dataset summary: {json.dumps(summary)}. Answer questions about sales, "
        "customers, products, and trends. Be concise (max 100 words). If asked something outside this data, "
        "say you can only answer about RetailPulse data."
    )
    fallback = f"Based on RetailPulse data, revenue is led by {summary['top_region']} and {summary['top_category']} is the top category. High churn risk count is {summary['churn_risk_count']}."
    content = call_claude(system, question, 300) or fallback
    return jsonify({"reply": content, "remaining": remaining})


@ai_bp.post("/weekly-summary")
@role_required("admin")
def weekly_summary():
    with get_connection() as conn:
        snapshot = dashboard_snapshot(conn)
        system = "Write a 2-sentence executive summary of this week's e-commerce performance."
        content = call_claude(system, json.dumps(snapshot), 250) or (
            f"RetailPulse shows total revenue of Rs {snapshot['total_revenue']:,.0f}, with {snapshot['top_region']} as the leading region. "
            f"Focus next on {snapshot['churn_risk_count']} high-risk customers and active anomaly review."
        )
        conn.execute(
            "INSERT INTO ai_insights (insight_type, content, data_snapshot) VALUES (?, ?, ?)",
            ("weekly", content, json.dumps(snapshot)),
        )
        conn.commit()
    return jsonify({"content": content})
