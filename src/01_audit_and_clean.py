"""
Stage 3 + 4: Data audit and data cleaning.

Reads  : data/olist.db            (built by load_data.py)
Writes : data/processed/orders_clean.csv   one row per order
         data/processed/items_clean.csv    one row per order item
         reports/data_audit.md             every check, finding and decision

Run from the project root:  python src/01_audit_and_clean.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olist.db"
OUT = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

# Orders before/after this window are too sparse to compare month by month
WINDOW_START, WINDOW_END = "2017-01-01", "2018-08-31"

audit = []  # (check, finding, decision)


def log(check, finding, decision):
    audit.append((check, finding, decision))
    print(f"- {check}: {finding}  ->  {decision}")


def load(conn, table):
    return pd.read_sql(f"SELECT * FROM {table}", conn)


with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    orders = load(conn, "orders")
    items = load(conn, "order_items")
    customers = load(conn, "customers")
    products = load(conn, "products")
    reviews = load(conn, "reviews")
    payments = load(conn, "payments")
    translation = load(conn, "category_translation")

# ---------------------------------------------------------------- AUDIT
date_cols = [c for c in orders.columns if c.startswith("order_") and ("date" in c or c.endswith("_at"))]
date_cols.append("order_purchase_timestamp")
for c in set(date_cols):
    orders[c] = pd.to_datetime(orders[c])

log("Duplicate order_id in orders", f"{orders.order_id.duplicated().sum()} duplicates", "none needed")

no_items = ~orders.order_id.isin(items.order_id)
share = orders.loc[no_items, "order_status"].isin(["unavailable", "canceled"]).mean()
log("Orders without items", f"{no_items.sum()} orders ({share:.0%} are unavailable/canceled)",
    "kept in order table, flagged has_items=False, revenue = 0")

d = orders[(orders.order_status == "delivered") & orders.order_delivered_customer_date.isna()]
log("Delivered orders with no delivery date", f"{len(d)} orders",
    "excluded from delivery-time metrics only")

neg = (orders.order_delivered_customer_date < orders.order_purchase_timestamp).sum()
log("Delivery date before purchase date", f"{neg} orders", "none needed" if neg == 0 else "excluded from delivery metrics")

dup_rev = reviews.order_id.duplicated().sum()
log("Orders with more than one review", f"{dup_rev} extra review rows", "keep the latest review per order")

untranslated = products.product_category_name.isna().sum()
log("Products with no category", f"{untranslated} products", "labelled 'unknown'")
missing_tr = set(products.product_category_name.dropna()) - set(translation.product_category_name)
log("Categories with no English name", f"{len(missing_tr)}: {sorted(missing_tr)}", "keep the Portuguese name")

log("Item prices <= 0", f"{(items.price <= 0).sum()} items", "none needed")
log("Extreme item prices", f"max = {items.price.max():,.0f} (99.9th pct = {items.price.quantile(.999):,.0f})",
    "kept: real high-value items, reported as median where it matters")

per_cust = customers.groupby("customer_unique_id").size()
log("customer_id vs customer_unique_id",
    f"{customers.customer_id.nunique():,} customer_id but {customers.customer_unique_id.nunique():,} real people",
    "use customer_unique_id to count repeat buyers")

month = orders.order_purchase_timestamp.dt.to_period("M")
sparse = month.value_counts()[lambda s: s < 500].sort_index()
log("Months with very few orders", ", ".join(f"{p} ({n})" for p, n in sparse.items()),
    f"trends limited to {WINDOW_START[:7]} .. {WINDOW_END[:7]}")

# ---------------------------------------------------------------- CLEAN
items = items.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
items = items.merge(translation, on="product_category_name", how="left")
items["category"] = (items.product_category_name_english
                     .fillna(items.product_category_name)
                     .fillna("unknown"))
items = items.drop(columns=["product_category_name", "product_category_name_english"])

order_money = (items.groupby("order_id")
               .agg(revenue=("price", "sum"), freight=("freight_value", "sum"), n_items=("order_id", "size"))
               .reset_index())

review_latest = (reviews.sort_values("review_answer_timestamp")
                 .drop_duplicates("order_id", keep="last")[["order_id", "review_score"]])

pay_main = (payments.sort_values("payment_value", ascending=False)
            .drop_duplicates("order_id")[["order_id", "payment_type"]])

clean = (orders.merge(order_money, on="order_id", how="left")
         .merge(customers[["customer_id", "customer_unique_id", "customer_state", "customer_city"]],
                on="customer_id", how="left")
         .merge(review_latest, on="order_id", how="left")
         .merge(pay_main, on="order_id", how="left"))
clean["has_items"] = clean.n_items.notna()
clean[["revenue", "freight", "n_items"]] = clean[["revenue", "freight", "n_items"]].fillna(0)

clean["purchase_month"] = clean.order_purchase_timestamp.dt.to_period("M").astype(str)
valid_delivery = (clean.order_status == "delivered") & clean.order_delivered_customer_date.notna()
clean["delivery_days"] = ((clean.order_delivered_customer_date - clean.order_purchase_timestamp)
                          .dt.total_seconds() / 86400).where(valid_delivery)
clean["is_late"] = (clean.order_delivered_customer_date > clean.order_estimated_delivery_date).where(valid_delivery)

in_window = clean.order_purchase_timestamp.between(WINDOW_START, WINDOW_END + " 23:59:59")
log("Orders kept after window filter", f"{in_window.sum():,} of {len(clean):,}", "analysis table")
clean = clean[in_window].copy()
items = items[items.order_id.isin(clean.order_id)].merge(
    clean[["order_id", "order_status", "purchase_month", "customer_unique_id", "customer_state"]], on="order_id")

OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(exist_ok=True)
clean.to_csv(OUT / "orders_clean.csv", index=False)
items.to_csv(OUT / "items_clean.csv", index=False)

# ---------------------------------------------------------------- REPORT
lines = ["# Data audit and cleaning log", "",
         "Every check run before analysis, what it found, and what was decided.", "",
         "| # | Check | Finding | Decision |", "|---|---|---|---|"]
lines += [f"| {i} | {c} | {f} | {d} |" for i, (c, f, d) in enumerate(audit, 1)]
(REPORTS / "data_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\nSaved {len(clean):,} orders and {len(items):,} items to {OUT}")
