import csv
import io

from flask import Blueprint, Response, send_file
from flask_login import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from auth import role_required
from database import get_connection


exports_bp = Blueprint("exports_api", __name__, url_prefix="/api/export")


def csv_response(filename, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([row[key] for key in row.keys()])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@exports_bp.get("/revenue.csv")
@role_required("admin")
def revenue_csv():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', order_date) month, SUM(total_amount) revenue, COUNT(*) orders
            FROM orders WHERE status='completed'
            GROUP BY month ORDER BY month
            """
        ).fetchall()
    return csv_response("retailpulse_revenue.csv", rows)


@exports_bp.get("/customer-ltv.csv")
@role_required("admin")
def ltv_csv():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.name, c.email, c.segment, c.region, COUNT(o.id) orders, COALESCE(SUM(o.total_amount),0) ltv
            FROM customers c LEFT JOIN orders o ON c.id=o.customer_id AND o.status='completed'
            GROUP BY c.id ORDER BY ltv DESC
            """
        ).fetchall()
    return csv_response("retailpulse_customer_ltv.csv", rows)


@exports_bp.get("/report.pdf")
@role_required("admin")
def report_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="RetailPulse Report")
    styles = getSampleStyleSheet()
    with get_connection() as conn:
        kpi = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN status='completed' THEN total_amount END), 0) revenue,
                   COUNT(*) orders,
                   COUNT(DISTINCT customer_id) customers,
                   COALESCE(AVG(CASE WHEN status='completed' THEN total_amount END), 0) aov
            FROM orders
            """
        ).fetchone()
        top_products = conn.execute(
            """
            SELECT p.name, p.category, SUM(oi.quantity * oi.unit_price) revenue
            FROM products p JOIN order_items oi ON p.id=oi.product_id JOIN orders o ON o.id=oi.order_id
            WHERE o.status='completed'
            GROUP BY p.id ORDER BY revenue DESC LIMIT 8
            """
        ).fetchall()
        insight = conn.execute("SELECT content FROM ai_insights ORDER BY generated_at DESC LIMIT 1").fetchone()

    story = [
        Paragraph("RetailPulse Executive Report", styles["Title"]),
        Spacer(1, 14),
        Paragraph(f"Revenue: Rs {kpi['revenue']:,.2f} | Orders: {kpi['orders']} | Customers: {kpi['customers']} | AOV: Rs {kpi['aov']:,.2f}", styles["BodyText"]),
        Spacer(1, 18),
        Paragraph("Top Products", styles["Heading2"]),
    ]
    table_data = [["Product", "Category", "Revenue"]] + [[r["name"], r["category"], f"Rs {r['revenue']:,.0f}"] for r in top_products]
    table = Table(table_data, colWidths=[230, 110, 110])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8447FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B388EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F2FF")]),
            ]
        )
    )
    story.extend([table, Spacer(1, 18), Paragraph("Latest AI Insight", styles["Heading2"])])
    story.append(Paragraph(insight["content"] if insight else "No AI insight generated yet.", styles["BodyText"]))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="retailpulse_report.pdf", mimetype="application/pdf")
