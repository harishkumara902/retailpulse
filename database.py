import os
import sqlite3
from contextlib import closing
from pathlib import Path

from werkzeug.security import generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DATABASE_URL", str(BASE_DIR / "retailpulse.db"))


def get_db_path():
    return os.getenv("DATABASE_URL", DB_PATH)


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed_users=True):
    Path(get_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with closing(get_connection()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'analyst',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                city TEXT,
                region TEXT,
                signup_date DATE,
                age_group TEXT,
                segment TEXT
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                sub_category TEXT,
                price REAL,
                cost REAL,
                stock INTEGER
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                order_date DATE,
                total_amount REAL,
                status TEXT,
                payment_method TEXT,
                region TEXT,
                shipping_days INTEGER
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                product_id INTEGER REFERENCES products(id),
                quantity INTEGER,
                unit_price REAL,
                discount REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS returns (
                id INTEGER PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                product_id INTEGER REFERENCES products(id),
                return_date DATE,
                reason TEXT,
                refund_amount REAL
            );

            CREATE TABLE IF NOT EXISTS ai_insights (
                id INTEGER PRIMARY KEY,
                insight_type TEXT,
                content TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_snapshot TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
            CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
            CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
            CREATE INDEX IF NOT EXISTS idx_returns_order_product ON returns(order_id, product_id);
            """
        )
        if seed_users:
            seed_demo_users(conn)
        conn.commit()


def seed_demo_users(conn):
    users = [
        ("admin", "admin123", "admin"),
        ("manager", "manager123", "manager"),
        ("analyst", "analyst123", "analyst"),
    ]
    for username, password, role in users:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, generate_password_hash(password), role),
        )


def reset_business_tables():
    with closing(get_connection()) as conn:
        conn.executescript(
            """
            DELETE FROM ai_insights;
            DELETE FROM returns;
            DELETE FROM order_items;
            DELETE FROM orders;
            DELETE FROM products;
            DELETE FROM customers;
            """
        )
        conn.commit()


def rows_to_dicts(rows):
    return [dict(row) for row in rows]
