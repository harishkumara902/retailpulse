from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def revenue_forecast(conn, days=30):
    df = pd.read_sql_query(
        """
        SELECT order_date AS date, SUM(total_amount) AS revenue
        FROM orders
        WHERE status='completed'
        GROUP BY order_date
        ORDER BY order_date
        """,
        conn,
    )
    if df.empty:
        return {"historical": [], "forecast": [], "confidence_band": {"upper": [], "lower": []}}

    df["date"] = pd.to_datetime(df["date"])
    df["day_index"] = (df["date"] - df["date"].min()).dt.days
    df["moving_average"] = df["revenue"].rolling(7, min_periods=1).mean()

    model = LinearRegression()
    model.fit(df[["day_index"]], df["revenue"])
    residual_std = float(np.std(df["revenue"] - model.predict(df[["day_index"]])))

    last_date = df["date"].max()
    future_rows = []
    for step in range(1, days + 1):
        next_date = last_date + timedelta(days=step)
        idx = int((next_date - df["date"].min()).days)
        prediction_input = pd.DataFrame({"day_index": [idx]})
        prediction = max(0.0, float(model.predict(prediction_input)[0]))
        future_rows.append(
            {
                "date": next_date.strftime("%Y-%m-%d"),
                "revenue": round(prediction, 2),
                "upper": round(prediction + residual_std, 2),
                "lower": round(max(0.0, prediction - residual_std), 2),
            }
        )

    historical = [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "revenue": round(float(row.revenue), 2),
            "moving_average": round(float(row.moving_average), 2),
        }
        for row in df.itertuples()
    ]
    return {
        "historical": historical,
        "forecast": [{"date": row["date"], "revenue": row["revenue"]} for row in future_rows],
        "confidence_band": {
            "upper": [{"date": row["date"], "revenue": row["upper"]} for row in future_rows],
            "lower": [{"date": row["date"], "revenue": row["lower"]} for row in future_rows],
        },
    }
