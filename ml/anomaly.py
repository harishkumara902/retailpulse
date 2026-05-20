import pandas as pd


def _iqr_anomalies(df, value_col, date_col, metric_name):
    if df.empty:
        return []
    q1 = df[value_col].quantile(0.25)
    q3 = df[value_col].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    baseline = max(df[value_col].median(), 1)
    anomalies = []
    for _, row in df.iterrows():
        value = float(row[value_col])
        if value < lower or value > upper:
            deviation = abs(value - baseline) / baseline
            anomalies.append(
                {
                    "date": str(row[date_col]),
                    "metric": metric_name,
                    "value": round(value, 2),
                    "type": "dip" if value < lower else "spike",
                    "severity": "High" if deviation > 0.75 else "Medium",
                    "deviation": round(deviation * 100, 1),
                }
            )
    return anomalies


def detect_anomalies(conn):
    daily_revenue = pd.read_sql_query(
        """
        SELECT order_date AS date, SUM(total_amount) AS revenue
        FROM orders
        WHERE status='completed'
        GROUP BY order_date
        ORDER BY order_date
        """,
        conn,
    )
    daily_cancel = pd.read_sql_query(
        """
        SELECT order_date AS date,
               SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS cancellation_rate
        FROM orders
        GROUP BY order_date
        ORDER BY order_date
        """,
        conn,
    )
    weekly_returns = pd.read_sql_query(
        """
        SELECT strftime('%Y-%W', o.order_date) AS week,
               COUNT(DISTINCT r.id) * 100.0 / COUNT(DISTINCT o.id) AS return_rate
        FROM orders o
        LEFT JOIN returns r ON o.id = r.order_id
        GROUP BY week
        ORDER BY week
        """,
        conn,
    )
    anomalies = []
    anomalies.extend(_iqr_anomalies(daily_revenue, "revenue", "date", "Daily revenue"))
    anomalies.extend(_iqr_anomalies(daily_cancel, "cancellation_rate", "date", "Cancellation rate"))
    anomalies.extend(_iqr_anomalies(weekly_returns, "return_rate", "week", "Weekly return rate"))
    return sorted(anomalies, key=lambda item: item["date"], reverse=True)[:80]
