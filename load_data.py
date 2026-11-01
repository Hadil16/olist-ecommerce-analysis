"""
Load the Olist e-commerce CSV files into a SQLite database (data/olist.db).

Usage:
    1. Download the dataset from Kaggle:
       https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
    2. Unzip the CSV files into the data/ folder.
    3. Run:  python load_data.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "olist.db"

# CSV file -> short table name used in the SQL queries
TABLES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_customers_dataset.csv": "customers",
    "olist_order_payments_dataset.csv": "payments",
    "olist_order_reviews_dataset.csv": "reviews",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}

# Zip codes keep their leading zeros, so they are read as text
TEXT_COLUMNS = {"customer_zip_code_prefix": str, "seller_zip_code_prefix": str}


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()  # rebuild from scratch every time

    with sqlite3.connect(DB_PATH) as conn:
        for csv_name, table in TABLES.items():
            df = pd.read_csv(DATA_DIR / csv_name, dtype=TEXT_COLUMNS)
            df.to_sql(table, conn, index=False)
            print(f"{table:<22} {len(df):>8,} rows")

    print(f"\nDatabase created: {DB_PATH}")


if __name__ == "__main__":
    main()
