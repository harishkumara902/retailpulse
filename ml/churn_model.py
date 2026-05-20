import sqlite3

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_customer_features(conn: sqlite3.Connection):
    query = """
        SELECT c.id, c.name, c.email, c.segment, c.region,
               COUNT(DISTINCT o.id) AS total_orders,
               COALESCE(AVG(CASE WHEN o.status='completed' THEN o.total_amount END), 0) AS avg_order_value,
               COALESCE(SUM(CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END), 0) AS return_count,
               COALESCE(JULIANDAY((SELECT MAX(order_date) FROM orders)) - JULIANDAY(MAX(o.order_date)), 999) AS days_since_last_order
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        LEFT JOIN returns r ON o.id = r.order_id
        GROUP BY c.id
    """
    return pd.read_sql_query(query, conn)


def predict_churn(conn: sqlite3.Connection, limit=50):
    df = load_customer_features(conn)
    if df.empty:
        return []

    df["churned"] = (df["days_since_last_order"] > 90).astype(int)
    features = ["days_since_last_order", "total_orders", "avg_order_value", "return_count", "segment"]
    X = df[features]
    y = df["churned"]

    if y.nunique() < 2:
        probability = np.where(y == 1, 0.86, 0.14)
    else:
        model = Pipeline(
            steps=[
                (
                    "prep",
                    ColumnTransformer(
                        transformers=[
                            ("num", StandardScaler(), ["days_since_last_order", "total_orders", "avg_order_value", "return_count"]),
                            ("cat", OneHotEncoder(handle_unknown="ignore"), ["segment"]),
                        ]
                    ),
                ),
                ("clf", LogisticRegression(max_iter=1000, random_state=42)),
            ]
        )
        model.fit(X, y)
        probability = model.predict_proba(X)[:, 1]

    df["churn_probability"] = probability
    df["risk_level"] = pd.cut(
        df["churn_probability"],
        bins=[-0.01, 0.35, 0.7, 1.0],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    df = df.sort_values("churn_probability", ascending=False).head(limit)
    return df[
        [
            "id",
            "name",
            "email",
            "segment",
            "region",
            "total_orders",
            "avg_order_value",
            "return_count",
            "days_since_last_order",
            "churn_probability",
            "risk_level",
        ]
    ].round(3).to_dict(orient="records")
