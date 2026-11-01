"""
Stage 5 + 6 + 7: KPIs, business analysis and charts.

Reads  : data/processed/orders_clean.csv, items_clean.csv   (from 01_audit_and_clean.py)
Writes : reports/kpis.json, reports/tables/*.csv, reports/figures/*.png

Run from the project root:  python src/02_analysis.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"
TAB = ROOT / "reports" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, GREY, RED = "#1F5FA8", "#E8833A", "#9AA5B1", "#C0392B"
plt.rcParams.update({
    "figure.figsize": (10, 5.2), "figure.dpi": 150, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 14, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelcolor": "#333", "font.size": 10.5,
})

orders = pd.read_csv(PROC / "orders_clean.csv", parse_dates=[
    "order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"])
items = pd.read_csv(PROC / "items_clean.csv")

# Business definition: revenue = item prices of DELIVERED orders (freight excluded)
delivered = orders[orders.order_status == "delivered"].copy()
d_items = items[items.order_status == "delivered"]
k = {}  # all KPIs end up here, so the README never contains a hand-typed number

# ------------------------------------------------------------- headline KPIs
k["orders_analysed"] = len(orders)
k["delivered_orders"] = len(delivered)
k["revenue_total"] = float(delivered.revenue.sum())
k["aov"] = float(delivered.loc[delivered.revenue > 0, "revenue"].mean())
k["aov_median"] = float(delivered.loc[delivered.revenue > 0, "revenue"].median())
k["unique_customers"] = int(delivered.customer_unique_id.nunique())
k["avg_review_score"] = float(delivered.review_score.mean())
k["pct_delivered"] = float((orders.order_status == "delivered").mean())
k["period"] = f"{orders.purchase_month.min()} to {orders.purchase_month.max()}"

# ------------------------------------------------------------- Q1: revenue trend
monthly = (delivered.groupby("purchase_month")
           .agg(revenue=("revenue", "sum"), orders=("order_id", "size")).reset_index())
monthly["aov"] = monthly.revenue / monthly.orders
monthly.to_csv(TAB / "monthly_revenue.csv", index=False)

jan_aug = lambda y: monthly[monthly.purchase_month.between(f"{y}-01", f"{y}-08")]
r17, r18 = jan_aug(2017).revenue.sum(), jan_aug(2018).revenue.sum()
k["revenue_jan_aug_2017"], k["revenue_jan_aug_2018"] = float(r17), float(r18)
k["revenue_growth_yoy"] = float(r18 / r17 - 1)
k["orders_growth_yoy"] = float(jan_aug(2018).orders.sum() / jan_aug(2017).orders.sum() - 1)
k["aov_2017"] = float(jan_aug(2017).revenue.sum() / jan_aug(2017).orders.sum())
k["aov_2018"] = float(jan_aug(2018).revenue.sum() / jan_aug(2018).orders.sum())
peak = monthly.loc[monthly.revenue.idxmax()]
k["peak_month"], k["peak_month_revenue"] = peak.purchase_month, float(peak.revenue)
k["peak_vs_prev_month"] = float(peak.revenue / monthly.revenue.shift(1)[monthly.revenue.idxmax()] - 1)
k["peak_vs_next_month"] = float(monthly.revenue.shift(-1)[monthly.revenue.idxmax()] / peak.revenue - 1)

fig, ax = plt.subplots()
ax.bar(monthly.purchase_month, monthly.revenue, color=BLUE, width=.7)
ax.set_title("Monthly revenue (delivered orders), Jan 2017 - Aug 2018")
ax.set_ylabel("Revenue (BRL)")
ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v/1e3:,.0f}k"))
ax.set_xticks(range(len(monthly)))
ax.set_xticklabels(monthly.purchase_month, rotation=60, ha="right")
i = monthly.revenue.idxmax()
ax.patches[i].set_color(ORANGE)
ax.annotate(f"{peak.purchase_month}: peak\n{peak.revenue/1e3:,.0f}k BRL", (i, peak.revenue),
            xytext=(i - 5.2, peak.revenue * 0.98), arrowprops=dict(arrowstyle="->", color="#555"), fontsize=9.5)
fig.savefig(FIG / "01_monthly_revenue.png"); plt.close(fig)

# ------------------------------------------------------------- Q2: categories (Pareto)
cat = (d_items.groupby("category").agg(revenue=("price", "sum"), items=("price", "size"),
                                       avg_price=("price", "mean")).sort_values("revenue", ascending=False))
cat["share"] = cat.revenue / cat.revenue.sum()
cat["cum_share"] = cat.share.cumsum()
cat.to_csv(TAB / "categories.csv")
k["n_categories"] = int(len(cat))
k["top10_category_share"] = float(cat.share.head(10).sum())
k["categories_for_80pct"] = int((cat.cum_share < 0.8).sum() + 1)
k["top_category"], k["top_category_share"] = cat.index[0], float(cat.share.iloc[0])
k["unknown_category_share"] = float(cat.loc["unknown", "share"]) if "unknown" in cat.index else 0.0

top = cat.head(10).iloc[::-1]
fig, ax = plt.subplots()
ax.barh(top.index.str.replace("_", " "), top.revenue, color=BLUE)
ax.set_title("Top 10 product categories by revenue")
ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v/1e3:,.0f}k"))
ax.set_xlabel("Revenue (BRL)")
for y, (rev, sh) in enumerate(zip(top.revenue, top.share)):
    ax.text(rev, y, f"  {sh:.1%}", va="center", fontsize=9.5)
fig.savefig(FIG / "02_top_categories.png"); plt.close(fig)

# ------------------------------------------------------------- Q3: geography
state = (delivered.groupby("customer_state")
         .agg(revenue=("revenue", "sum"), orders=("order_id", "size"),
              avg_delivery_days=("delivery_days", "mean"), late_rate=("is_late", "mean"),
              avg_review=("review_score", "mean")).sort_values("revenue", ascending=False))
state["share"] = state.revenue / state.revenue.sum()
state.to_csv(TAB / "states.csv")
k["top_state"], k["top_state_share"] = state.index[0], float(state.share.iloc[0])
k["top3_states"] = list(state.index[:3])
k["top3_states_share"] = float(state.share.head(3).sum())
k["n_states"] = int(len(state))

big = state[state.orders >= 500]  # avoid noisy tiny states
slow = big.sort_values("avg_delivery_days")
k["fastest_big_state"], k["fastest_big_state_days"] = slow.index[0], float(slow.avg_delivery_days.iloc[0])
k["slowest_big_state"], k["slowest_big_state_days"] = slow.index[-1], float(slow.avg_delivery_days.iloc[-1])
k["late_rate_by_state_range"] = [float(big.late_rate.min()), float(big.late_rate.max())]

top_s = state.head(10).iloc[::-1]
fig, ax = plt.subplots()
ax.barh(top_s.index, top_s.share, color=BLUE)
ax.set_title("Share of revenue by customer state (top 10)")
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
for y, v in enumerate(top_s.share):
    ax.text(v, y, f"  {v:.1%}", va="center", fontsize=9.5)
fig.savefig(FIG / "03_revenue_by_state.png"); plt.close(fig)

# ------------------------------------------------------------- Q4: delivery performance
dd = delivered.dropna(subset=["delivery_days"])
k["avg_delivery_days"] = float(dd.delivery_days.mean())
k["median_delivery_days"] = float(dd.delivery_days.median())
k["late_rate"] = float(dd.is_late.mean())
k["avg_estimated_days"] = float(((dd.order_estimated_delivery_date - dd.order_purchase_timestamp).dt.total_seconds() / 86400).mean())

late_m = dd.groupby("purchase_month").is_late.mean()
late_m.to_csv(TAB / "late_rate_by_month.csv")
k["worst_late_month"], k["worst_late_rate"] = late_m.idxmax(), float(late_m.max())
k["late_rate_2017_11"], k["late_rate_2018_02"] = float(late_m["2017-11"]), float(late_m["2018-02"])
k["orders_2018_03"] = int(monthly.set_index("purchase_month").orders["2018-03"])
k["orders_2018_02"] = int(monthly.set_index("purchase_month").orders["2018-02"])
k["orders_2017_11"] = int(monthly.set_index("purchase_month").orders["2017-11"])
k["best_late_rate"] = float(late_m.min())

fig, ax = plt.subplots()
ax.plot(late_m.index, late_m.values, color=RED, marker="o", lw=2)
ax.set_title("Share of orders delivered after the promised date")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_xticks(range(len(late_m)))
ax.set_xticklabels(late_m.index, rotation=60, ha="right")
ax.set_ylim(0, None)
fig.savefig(FIG / "04_late_rate_by_month.png"); plt.close(fig)

# ------------------------------------------------------------- Q5: late delivery vs reviews
rv = dd.dropna(subset=["review_score"])
on_time, late = rv[~rv.is_late.astype(bool)].review_score, rv[rv.is_late.astype(bool)].review_score
k["review_on_time"], k["review_late"] = float(on_time.mean()), float(late.mean())
k["one_star_on_time"], k["one_star_late"] = float((on_time == 1).mean()), float((late == 1).mean())
k["n_late_reviewed"], k["n_on_time_reviewed"] = int(len(late)), int(len(on_time))
u, p = stats.mannwhitneyu(on_time, late, alternative="greater")
k["mannwhitney_p"] = float(p)
k["rank_biserial"] = float(2 * u / (len(on_time) * len(late)) - 1)  # effect size, -1..1
rho, p_rho = stats.spearmanr(rv.delivery_days, rv.review_score)
k["spearman_rho_days_score"] = float(rho)
# Robustness: is the gap just geography? Compare late vs on-time inside each big state
rv_state = rv.assign(late=rv.is_late.astype(bool))
gap = (rv_state[rv_state.customer_state.isin(state.index[:6])]
       .groupby(["customer_state", "late"]).review_score.mean().unstack())
gap["gap"] = gap[False] - gap[True]
gap.to_csv(TAB / "review_gap_by_state.csv")
k["review_gap_within_state_min"], k["review_gap_within_state_max"] = float(gap.gap.min()), float(gap.gap.max())
k["review_gap_states_checked"] = list(gap.index)
rv = rv.assign(bucket=pd.cut(rv.delivery_days, [0, 7, 14, 21, 28, 1000],
                             labels=["<= 7 days", "8-14", "15-21", "22-28", "> 28"]))
by_bucket = rv.groupby("bucket", observed=True).review_score.agg(["mean", "size"])
by_bucket.to_csv(TAB / "review_by_delivery_time.csv")
k["review_by_bucket"] = {str(i): float(v) for i, v in by_bucket["mean"].items()}

fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1, 1.25]})
ax = axes[0]
ax.bar(["On time", "Late"], [k["review_on_time"], k["review_late"]], color=[BLUE, RED], width=.55)
ax.set_ylim(0, 5); ax.set_title("Average review score")
for x, v in enumerate([k["review_on_time"], k["review_late"]]):
    ax.text(x, v + .08, f"{v:.2f}", ha="center", fontweight="bold")
ax = axes[1]
ax.bar(by_bucket.index.astype(str), by_bucket["mean"], color=GREY, width=.6)
ax.set_ylim(0, 5); ax.set_title("Average review score by delivery time")
for x, v in enumerate(by_bucket["mean"]):
    ax.text(x, v + .08, f"{v:.2f}", ha="center", fontweight="bold")
fig.savefig(FIG / "05_reviews_vs_delivery.png"); plt.close(fig)

# ------------------------------------------------------------- Q6: repeat customers
per_cust = delivered.groupby("customer_unique_id").order_id.nunique()
k["repeat_rate"] = float((per_cust > 1).mean())
k["customers_1_order"] = int((per_cust == 1).sum())
k["customers_2plus_orders"] = int((per_cust > 1).sum())
k["max_orders_one_customer"] = int(per_cust.max())
rev_c = delivered.groupby("customer_unique_id").revenue.sum()
k["repeat_revenue_share"] = float(rev_c[per_cust > 1].sum() / rev_c.sum())

fig, ax = plt.subplots(figsize=(7, 4.6))
vals = [k["customers_1_order"], k["customers_2plus_orders"]]
ax.bar(["Bought once", "Bought 2+ times"], vals, color=[GREY, BLUE], width=.55)
ax.set_title("Most customers buy only once")
ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v/1e3:,.0f}k"))
for x, v in enumerate(vals):
    ax.text(x, v, f"{v:,}\n({v/sum(vals):.1%})", ha="center", va="bottom", fontsize=10)
ax.set_ylim(0, max(vals) * 1.18)
fig.savefig(FIG / "06_repeat_customers.png"); plt.close(fig)

# ------------------------------------------------------------- Q7: payments
pay = delivered.groupby("payment_type").agg(orders=("order_id", "size"), revenue=("revenue", "sum"))
pay["share_orders"] = pay.orders / pay.orders.sum()
pay.to_csv(TAB / "payments.csv")
k["credit_card_share"] = float(pay.loc["credit_card", "share_orders"])
k["boleto_share"] = float(pay.loc["boleto", "share_orders"])

# ------------------------------------------------------------- save
(ROOT / "reports" / "kpis.json").write_text(json.dumps(k, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(k, indent=2, ensure_ascii=False))
