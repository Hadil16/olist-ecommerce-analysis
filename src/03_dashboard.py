"""
Stage 7: Interactive dashboard (single self-contained HTML file, works offline).

Reads  : reports/kpis.json, reports/tables/*.csv
Writes : dashboard/olist_dashboard.html

Run from the project root:  python src/03_dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "reports" / "tables"
k = json.loads((ROOT / "reports" / "kpis.json").read_text(encoding="utf-8"))

BLUE, ORANGE, GREY, RED = "#1F5FA8", "#E8833A", "#9AA5B1", "#C0392B"
LAYOUT = dict(template="plotly_white", margin=dict(l=50, r=20, t=10, b=50), height=340,
              font=dict(family="Segoe UI, system-ui, sans-serif", size=12), paper_bgcolor="white",
              plot_bgcolor="white")


def div(fig):
    fig.update_layout(**LAYOUT)
    return fig.to_html(full_html=False, include_plotlyjs=False, default_width="100%",
                       config={"displayModeBar": False, "responsive": True})


# 1 monthly revenue + orders
m = pd.read_csv(TAB / "monthly_revenue.csv")
f1 = go.Figure()
f1.add_bar(x=m.purchase_month, y=m.revenue, name="Revenue (BRL)", marker_color=BLUE,
           hovertemplate="%{x}<br>Revenue: %{y:,.0f} BRL<extra></extra>")
f1.add_scatter(x=m.purchase_month, y=m.orders, name="Orders", yaxis="y2", line=dict(color=ORANGE, width=3),
               hovertemplate="%{x}<br>Orders: %{y:,}<extra></extra>")
f1.update_layout(yaxis=dict(title="Revenue (BRL)", tickformat=",.0f"),
                 yaxis2=dict(title="Orders", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
                 legend=dict(orientation="h", y=1.12), xaxis=dict(tickangle=-60),
                 margin=dict(l=60, r=60, t=10, b=50))

# 2 categories
c = pd.read_csv(TAB / "categories.csv").head(10).iloc[::-1]
f2 = go.Figure(go.Bar(x=c.revenue, y=c.category.str.replace("_", " "), orientation="h", marker_color=BLUE,
                      customdata=c.share, hovertemplate="%{y}<br>%{x:,.0f} BRL (%{customdata:.1%})<extra></extra>"))
f2.update_layout(xaxis=dict(title="Revenue (BRL)", tickformat=",.0f"), margin=dict(l=140, r=20, t=10, b=50))

# 3 states
s = pd.read_csv(TAB / "states.csv").head(10).iloc[::-1]
f3 = go.Figure(go.Bar(x=s.share, y=s.customer_state, orientation="h", marker_color=BLUE,
                      hovertemplate="%{y}: %{x:.1%} of revenue<extra></extra>"))
f3.update_layout(xaxis=dict(title="Share of revenue", tickformat=".0%"))

# 4 late rate by month
lm = pd.read_csv(TAB / "late_rate_by_month.csv")
f4 = go.Figure(go.Scatter(x=lm.purchase_month, y=lm.is_late, mode="lines+markers", line=dict(color=RED, width=3),
                          hovertemplate="%{x}<br>Late: %{y:.1%}<extra></extra>"))
f4.update_layout(yaxis=dict(title="Delivered after promised date", tickformat=".0%", rangemode="tozero"),
                 xaxis=dict(tickangle=-60))

# 5 review score by delivery time
rb = pd.read_csv(TAB / "review_by_delivery_time.csv")
f5 = go.Figure(go.Bar(x=rb.bucket, y=rb["mean"], marker_color=[BLUE, BLUE, GREY, ORANGE, RED],
                      customdata=rb["size"], text=rb["mean"].round(2), textposition="outside",
                      hovertemplate="%{x}: %{y:.2f} avg score<br>%{customdata:,} reviews<extra></extra>"))
f5.update_layout(yaxis=dict(title="Average review score (1-5)", range=[0, 5]),
                 xaxis=dict(title="Days from purchase to delivery"))

# 6 repeat customers
f6 = go.Figure(go.Bar(x=["Bought once", "Bought 2+ times"], y=[k["customers_1_order"], k["customers_2plus_orders"]],
                      marker_color=[GREY, BLUE],
                      text=[f"{k['customers_1_order']:,}", f"{k['customers_2plus_orders']:,}"], textposition="outside",
                      hovertemplate="%{x}: %{y:,} customers<extra></extra>"))
f6.update_layout(yaxis=dict(title="Customers", tickformat=",.0f"))

cards = [
    (f"{k['revenue_total']/1e6:.1f}M BRL", "Revenue (delivered orders)"),
    (f"{k['delivered_orders']:,}", "Delivered orders"),
    (f"{k['aov']:.0f} BRL", f"Average order value (median {k['aov_median']:.0f})"),
    (f"{k['avg_review_score']:.2f} / 5", "Average review score"),
    (f"{k['late_rate']:.1%}", "Orders delivered late"),
    (f"{k['repeat_rate']:.1%}", "Customers who bought again"),
]
findings = [
    ("Growth came from volume, not bigger baskets",
     f"Jan-Aug revenue grew {k['revenue_growth_yoy']:.0%} year over year while average order value stayed flat "
     f"({k['aov_2017']:.0f} to {k['aov_2018']:.0f} BRL). After Nov 2017 monthly revenue plateaued."),
    ("Late delivery is the clearest customer-experience problem",
     f"Late orders score {k['review_late']:.2f} vs {k['review_on_time']:.2f} on time, and "
     f"{k['one_star_late']:.0%} of late orders get 1 star (vs {k['one_star_on_time']:.0%}). The gap holds inside every "
     "big state. This is an association, not proof of cause."),
    ("Almost nobody comes back",
     f"Only {k['repeat_rate']:.1%} of customers bought twice or more, and they bring "
     f"{k['repeat_revenue_share']:.1%} of revenue. Retention is the largest untested opportunity."),
]

card_html = "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in cards)
find_html = "".join(f"<div class='find'><h3>{t}</h3><p>{b}</p></div>" for t, b in findings)
charts = [
    ("Monthly revenue and orders", div(f1)), ("Top 10 categories by revenue", div(f2)),
    ("Where the money comes from (customer state)", div(f3)), ("Late deliveries by month", div(f4)),
    ("Slower delivery, lower review scores", div(f5)), ("Repeat customers", div(f6)),
]
chart_html = "".join(f"<section class='card'><h2>{t}</h2>{h}</section>" for t, h in charts)

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Olist E-Commerce Dashboard</title>
<style>
:root{{--bg:#f4f6f9;--card:#fff;--ink:#1c2733;--mute:#5c6b7a;--line:#e3e8ee;--accent:#1F5FA8}}
:root{{color-scheme:light}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",system-ui,sans-serif;line-height:1.45}}
.wrap{{max-width:1180px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--mute);margin:0 0 20px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:20px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.kpi .v{{font-size:24px;font-weight:700;color:var(--accent)}} .kpi .l{{font-size:12.5px;color:var(--mute)}}
.finds{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-bottom:20px}}
.find{{background:var(--card);border:1px solid var(--line);border-left:4px solid {ORANGE};border-radius:10px;padding:14px 16px}}
.find h3{{margin:0 0 6px;font-size:15px}} .find p{{margin:0;font-size:13.5px;color:var(--mute)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:14px}}
@media (max-width:560px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 14px 8px;overflow:hidden;min-width:0}}
.card h2{{font-size:15px;margin:0 0 8px}}
footer{{margin-top:24px;color:var(--mute);font-size:12.5px}}
</style></head><body><div class="wrap">
<h1>Olist E-Commerce Performance</h1>
<p class="sub">Brazilian marketplace, orders from {k['period'].replace(' to ', ' to ')} &middot; {k['orders_analysed']:,} orders &middot; amounts in Brazilian reais (BRL)</p>
<div class="kpis">{card_html}</div>
<div class="finds">{find_html}</div>
<div class="grid">{chart_html}</div>
<footer>Revenue = item prices of delivered orders, freight excluded. Source: Olist Brazilian E-Commerce Public Dataset (Kaggle).
Built with SQL, Python (pandas, plotly).</footer>
</div><script>{get_plotlyjs()}</script></body></html>"""
# plotly.js must load before the chart scripts, so move it to the top of body
html = html.replace(f"<script>{get_plotlyjs()}</script>", "")
html = html.replace('<div class="wrap">', f"<script>{get_plotlyjs()}</script><div class=\"wrap\">", 1)
# charts that drew before the grid settled get re-measured once the page has loaded
html = html.replace("</body>", "<script>window.addEventListener('load',function(){"
                    "setTimeout(function(){window.dispatchEvent(new Event('resize'))},150)})</script></body>")

out = ROOT / "dashboard"
out.mkdir(exist_ok=True)
(out / "olist_dashboard.html").write_text(html, encoding="utf-8")
print("Saved", out / "olist_dashboard.html", f"({len(html)/1e6:.1f} MB)")
