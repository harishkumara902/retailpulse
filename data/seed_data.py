import random
import sys
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import get_connection, init_db, reset_business_tables


fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)

REGIONS = ["North", "South", "East", "West", "Central"]
AGE_GROUPS = ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
SEGMENTS = ["Premium", "Regular", "Budget"]
PAYMENTS = ["UPI", "Card", "Wallet", "COD"]
CATEGORIES = {
    "Electronics": ["Mobiles", "Audio", "Laptops", "Accessories"],
    "Fashion": ["Men", "Women", "Footwear", "Bags"],
    "Home": ["Kitchen", "Decor", "Furniture", "Storage"],
    "Beauty": ["Skincare", "Makeup", "Fragrance", "Haircare"],
    "Sports": ["Fitness", "Outdoor", "Team Sports", "Yoga"],
    "Books": ["Fiction", "Business", "Children", "Education"],
}


def weighted_order_date():
    start = date(2023, 1, 1)
    end = date(2025, 5, 31)
    while True:
        current = start + timedelta(days=random.randint(0, (end - start).days))
        weight = 1.0
        if current.month in (10, 11):
            weight *= 1.25
        if current.month == 12:
            weight *= 1.4
        if current.weekday() >= 5:
            weight *= 1.25
        if random.random() < min(weight / 1.8, 0.95):
            return current


def make_customers(conn):
    customers = []
    for customer_id in range(1, 501):
        segment = random.choices(SEGMENTS, weights=[0.22, 0.53, 0.25])[0]
        region = random.choices(REGIONS, weights=[0.19, 0.24, 0.18, 0.2, 0.19])[0]
        signup = date(2022, 6, 1) + timedelta(days=random.randint(0, 900))
        row = (
            customer_id,
            fake.name(),
            f"customer{customer_id}@example.com",
            fake.city(),
            region,
            signup.isoformat(),
            random.choice(AGE_GROUPS),
            segment,
        )
        customers.append(row)
    conn.executemany(
        """
        INSERT INTO customers
        (id, name, email, city, region, signup_date, age_group, segment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )
    return customers


def make_products(conn):
    products = []
    category_ranges = {
        "Electronics": (1200, 85000),
        "Fashion": (399, 7999),
        "Home": (299, 25000),
        "Beauty": (199, 5999),
        "Sports": (299, 18000),
        "Books": (149, 2499),
    }
    product_id = 1
    for category, subcats in CATEGORIES.items():
        for _ in range(34 if category in ("Electronics", "Fashion") else 33):
            low, high = category_ranges[category]
            price = round(random.uniform(low, high), 2)
            cost = round(price * random.uniform(0.46, 0.72), 2)
            subcat = random.choice(subcats)
            products.append(
                (
                    product_id,
                    f"{fake.word().title()} {subcat} {product_id}",
                    category,
                    subcat,
                    price,
                    cost,
                    random.randint(5, 600),
                )
            )
            product_id += 1
    conn.executemany(
        """
        INSERT INTO products (id, name, category, sub_category, price, cost, stock)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        products,
    )
    return products


def make_orders(conn, customers, products):
    product_lookup = {p[0]: p for p in products}
    customer_weights = []
    for customer in customers:
        segment = customer[7]
        customer_weights.append({"Premium": 3.0, "Regular": 1.0, "Budget": 0.65}[segment])

    orders = []
    items = []
    order_item_id = 1
    status_weights = ["completed", "completed", "completed", "completed", "cancelled", "pending", "refunded"]
    for order_id in range(1, 3001):
        customer = random.choices(customers, weights=customer_weights, k=1)[0]
        customer_id = customer[0]
        region = customer[4]
        order_date = weighted_order_date()
        status = random.choices(status_weights, weights=[76, 0, 0, 0, 8, 7, 4])[0]
        shipping_days = max(1, int(random.gauss(4.2, 1.3)))
        line_count = random.choices([1, 2, 3, 4], weights=[38, 38, 18, 6])[0]
        total = 0.0
        selected_products = random.sample(products, line_count)
        draft_lines = []
        for product in selected_products:
            quantity = random.choices([1, 2, 3, 4], weights=[62, 25, 10, 3])[0]
            discount = random.choice([0, 0, 0, 0.05, 0.1, 0.15])
            unit_price = round(product[4] * (1 - discount), 2)
            total += unit_price * quantity
            draft_lines.append((product[0], quantity, unit_price, discount))
        if order_date.month == 12:
            total *= 1.04
        total = round(total, 2)
        orders.append((order_id, customer_id, order_date.isoformat(), total, status, random.choice(PAYMENTS), region, shipping_days))
        for product_id, quantity, unit_price, discount in draft_lines:
            items.append((order_item_id, order_id, product_id, quantity, unit_price, discount))
            order_item_id += 1

    conn.executemany(
        """
        INSERT INTO orders
        (id, customer_id, order_date, total_amount, status, payment_method, region, shipping_days)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )
    conn.executemany(
        """
        INSERT INTO order_items
        (id, order_id, product_id, quantity, unit_price, discount)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        items,
    )
    return orders, items, product_lookup


def make_returns(conn, orders, items, product_lookup):
    completed_order_ids = {order[0]: order for order in orders if order[4] in ("completed", "refunded")}
    candidate_items = [item for item in items if item[1] in completed_order_ids]
    rates = {"Electronics": 0.15, "Fashion": 0.20, "Home": 0.08, "Beauty": 0.09, "Sports": 0.07, "Books": 0.05}
    weighted = []
    for item in candidate_items:
        product = product_lookup[item[2]]
        order = completed_order_ids[item[1]]
        rate = rates[product[2]]
        if order[6] == "South":
            rate *= 1.35
        weighted.append(rate)

    selected = set()
    while len(selected) < 400:
        item = random.choices(candidate_items, weights=weighted, k=1)[0]
        selected.add((item[1], item[2]))

    returns = []
    for return_id, (order_id, product_id) in enumerate(selected, 1):
        order = completed_order_ids[order_id]
        item = next(i for i in candidate_items if i[1] == order_id and i[2] == product_id)
        returned_at = date.fromisoformat(order[2]) + timedelta(days=random.randint(2, 21))
        refund = round(item[3] * item[4] * random.uniform(0.75, 1.0), 2)
        returns.append(
            (
                return_id,
                order_id,
                product_id,
                returned_at.isoformat(),
                random.choice(["Defective", "Wrong Item", "Not as Described", "Changed Mind"]),
                refund,
            )
        )
    conn.executemany(
        """
        INSERT INTO returns
        (id, order_id, product_id, return_date, reason, refund_amount)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        returns,
    )


def seed():
    init_db(seed_users=True)
    reset_business_tables()
    with get_connection() as conn:
        customers = make_customers(conn)
        products = make_products(conn)
        orders, items, product_lookup = make_orders(conn, customers, products)
        make_returns(conn, orders, items, product_lookup)
        conn.commit()
    print("RetailPulse database seeded: 500 customers, 200 products, 3000 orders, ~6000 items, 400 returns.")


if __name__ == "__main__":
    seed()
