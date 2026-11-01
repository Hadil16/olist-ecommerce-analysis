"""
Generate the Power BI project (PBIP format) for the Olist dashboard.

Writes powerbi/olist_dashboard.pbip + olist_dashboard.SemanticModel/ + olist_dashboard.Report/
Open olist_dashboard.pbip in Power BI Desktop, click Refresh, then File > Save as .pbix.

Run from the project root:  python powerbi/build_pbip.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NAME = "olist_dashboard"
SM = PBI / f"{NAME}.SemanticModel"
RP = PBI / f"{NAME}.Report"
DATA_DIR = str(ROOT / "data" / "processed")

T = "\t"


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def wj(path, obj):
    w(path, json.dumps(obj, indent=2))


# =====================================================================
# SEMANTIC MODEL (TMDL)
# =====================================================================
def col(name, dtype, source=None, fmt=None, summarize="none", hidden=False):
    n = f"'{name}'" if " " in name else name
    s = [f"{T}column {n}", f"{T}{T}dataType: {dtype}"]
    if fmt:
        s.append(f"{T}{T}formatString: {fmt}")
    s.append(f"{T}{T}summarizeBy: {summarize}")
    if hidden:
        s.append(f"{T}{T}isHidden")
    s.append(f"{T}{T}sourceColumn: {source or name}")
    return "\n".join(s) + "\n"


def calc_col(name, dtype, dax):
    n = f"'{name}'" if " " in name else name
    lines = dax.strip().splitlines()
    body = f"{T}column {n} = ```\n" + "\n".join(f"{T}{T}{T}{l}" for l in lines) + f"\n{T}{T}{T}```\n"
    return body + f"{T}{T}dataType: {dtype}\n{T}{T}summarizeBy: none\n{T}{T}isDataTypeInferred\n"


def measure(name, dax, fmt=None, folder=None):
    n = f"'{name}'" if " " in name else name
    lines = dax.strip().splitlines()
    if len(lines) == 1:
        s = f"{T}measure {n} = {lines[0]}\n"
    else:
        s = f"{T}measure {n} = ```\n" + "\n".join(f"{T}{T}{T}{l}" for l in lines) + f"\n{T}{T}{T}```\n"
    if fmt:
        s += f"{T}{T}formatString: {fmt}\n"
    if folder:
        s += f"{T}{T}displayFolder: {folder}\n"
    return s


def m_partition(table, m_code):
    lines = m_code.strip().splitlines()
    return (f"{T}partition {table} = m\n{T}{T}mode: import\n{T}{T}source = ```\n"
            + "\n".join(f"{T}{T}{T}{l}" for l in lines) + f"\n{T}{T}{T}```\n")


ORDERS_COLS = [
    ("order_id", "text", "string"), ("order_status", "text", "string"),
    ("order_purchase_timestamp", "datetime", "dateTime"),
    ("order_delivered_customer_date", "datetime", "dateTime"),
    ("order_estimated_delivery_date", "datetime", "dateTime"),
    ("revenue", "number", "double"), ("freight", "number", "double"),
    ("customer_unique_id", "text", "string"), ("customer_state", "text", "string"),
    ("review_score", "number", "double"), ("payment_type", "text", "string"),
    ("purchase_month", "text", "string"), ("delivery_days", "number", "double"),
    ("is_late", "logical", "boolean"),
]
ITEMS_COLS = [("order_id", "text", "string"), ("price", "number", "double"),
              ("freight_value", "number", "double"), ("category", "text", "string")]


def m_csv(file, cols, extra="", last="Typed"):
    names = ", ".join(f'"{c}"' for c, _, _ in cols)
    types = ", ".join(f'{{"{c}", type {t}}}' for c, t, _ in cols)
    return f"""let
    Source = Csv.Document(File.Contents(DataFolder & "\\{file}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Kept = Table.SelectColumns(Promoted, {{{names}}}),
    Typed = Table.TransformColumnTypes(Kept, {{{types}}}, "en-US"){extra}
in
    {last}"""


orders_m = m_csv("orders_clean.csv", ORDERS_COLS,
                 ',\n    Dated = Table.AddColumn(Typed, "Purchase Date", each Date.From([order_purchase_timestamp]), type date)',
                 last="Dated")
items_m = m_csv("items_clean.csv", ITEMS_COLS,
                ',\n    Pretty = Table.TransformColumns(Typed, {{"category", each Text.Proper(Text.Replace(_, "_", " ")), type text}})',
                last="Pretty")

FMT = {"revenue": "#,0", "freight": "#,0", "review_score": "0.00", "delivery_days": "0.0"}
orders_tmdl = f"table orders\n\n"
for c, _, dt in ORDERS_COLS:
    orders_tmdl += col(c, dt, fmt=FMT.get(c)) + "\n"
orders_tmdl += col("Purchase Date", "dateTime", fmt="dd/MM/yyyy") + "\n"
orders_tmdl += calc_col("Delivery Status", "string", """SWITCH (
    TRUE (),
    ISBLANK ( orders[is_late] ), "n/a",
    orders[is_late] = TRUE (), "Late",
    "On time"
)""") + "\n"
orders_tmdl += calc_col("Delivery Bucket", "string", """SWITCH (
    TRUE (),
    ISBLANK ( orders[delivery_days] ), "n/a",
    orders[delivery_days] <= 7, "1. <= 7 days",
    orders[delivery_days] <= 14, "2. 8-14 days",
    orders[delivery_days] <= 21, "3. 15-21 days",
    orders[delivery_days] <= 28, "4. 22-28 days",
    "5. > 28 days"
)""") + "\n"
orders_tmdl += m_partition("orders", orders_m)

items_tmdl = "table items\n\n"
for c, _, dt in ITEMS_COLS:
    items_tmdl += col(c, dt, fmt="#,0.00" if c in ("price", "freight_value") else None) + "\n"
items_tmdl += m_partition("items", items_m)

calendar_tmdl = f"""table Calendar
{T}dataCategory: Time

{col("Date", "dateTime", source="[Date]", fmt="dd/MM/yyyy").replace(f"{T}{T}summarizeBy: none", f"{T}{T}isKey{chr(10)}{T}{T}summarizeBy: none")}
{col("Year", "int64", source="[Year]")}
{col("Month", "string", source="[Month]")}
{T}partition Calendar = calculated
{T}{T}mode: import
{T}{T}source = ```
{T}{T}{T}ADDCOLUMNS (
{T}{T}{T}    CALENDAR ( DATE ( 2017, 1, 1 ), DATE ( 2018, 8, 31 ) ),
{T}{T}{T}    "Year", YEAR ( [Date] ),
{T}{T}{T}    "Month", FORMAT ( [Date], "yyyy-MM" )
{T}{T}{T})
{T}{T}{T}```
"""

M = []
M.append(measure("Revenue", 'CALCULATE ( SUM ( orders[revenue] ), orders[order_status] = "delivered" )', "#,0", "Core KPIs"))
M.append(measure("Delivered Orders", 'CALCULATE ( COUNTROWS ( orders ), orders[order_status] = "delivered" )', "#,0", "Core KPIs"))
M.append(measure("Average Order Value", "DIVIDE ( [Revenue], [Delivered Orders] )", "#,0.00", "Core KPIs"))
M.append(measure("Customers", 'CALCULATE ( DISTINCTCOUNT ( orders[customer_unique_id] ), orders[order_status] = "delivered" )', "#,0", "Core KPIs"))
M.append(measure("Average Review Score", 'CALCULATE ( AVERAGE ( orders[review_score] ), orders[order_status] = "delivered" )', "0.00", "Customer experience"))
M.append(measure("Average Delivery Days", "AVERAGE ( orders[delivery_days] )", "0.0", "Delivery"))
M.append(measure("Late Rate", """DIVIDE (
    CALCULATE ( COUNTROWS ( orders ), orders[is_late] = TRUE () ),
    CALCULATE ( COUNTROWS ( orders ), NOT ( ISBLANK ( orders[is_late] ) ) )
)""", "0.0%", "Delivery"))
M.append(measure("Avg Review (dated deliveries)", """CALCULATE (
    AVERAGE ( orders[review_score] ),
    orders[order_status] = "delivered",
    NOT ( ISBLANK ( orders[is_late] ) )
)""", "0.00", "Customer experience"))
M.append(measure("Repeat Customers", """COUNTROWS (
    FILTER (
        VALUES ( orders[customer_unique_id] ),
        CALCULATE ( DISTINCTCOUNT ( orders[order_id] ), orders[order_status] = "delivered" ) > 1
    )
)""", "#,0", "Customer experience"))
M.append(measure("Repeat Rate", "DIVIDE ( [Repeat Customers], [Customers] )", "0.0%", "Customer experience"))
M.append(measure("Revenue Same Period Last Year", "CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( Calendar[Date] ) )", "#,0", "Time intelligence"))
M.append(measure("Revenue YoY %", "DIVIDE ( [Revenue] - [Revenue Same Period Last Year], [Revenue Same Period Last Year] )", "0.0%", "Time intelligence"))
M.append(measure("Item Revenue", 'CALCULATE ( SUM ( items[price] ), orders[order_status] = "delivered" )', "#,0", "Core KPIs"))
M.append(measure("Item Revenue Top 10 Categories", """IF (
    RANKX ( ALL ( items[category] ), [Item Revenue] ) <= 10,
    [Item Revenue]
)""", "#,0", "Chart helpers"))
M.append(measure("Revenue Top 10 States", """IF (
    RANKX ( ALL ( orders[customer_state] ), [Revenue] ) <= 10,
    [Revenue]
)""", "#,0", "Chart helpers"))

M.append(measure("YoY Trend", """VAR v = [Revenue YoY %]
RETURN
    IF (
        ISBLANK ( v ), BLANK (),
        IF ( v > 0, "▲ " & FORMAT ( v, "0.0%" ), IF ( v < 0, "▼ " & FORMAT ( v, "0.0%" ), "= 0.0%" ) )
    )""", None, "Time intelligence"))
M.append(measure("YoY Color", """VAR v = [Revenue YoY %]
RETURN
    IF ( ISBLANK ( v ), BLANK (), IF ( v >= 0, "#1E8449", "#C0392B" ) )""", None, "Chart helpers"))

measures_tmdl = (f"table _Measures\n\n{T}column Dummy\n{T}{T}dataType: int64\n{T}{T}isHidden\n{T}{T}summarizeBy: none\n"
                 f"{T}{T}sourceColumn: [Dummy]\n\n" + "\n".join(M) +
                 f"\n{T}partition _Measures = calculated\n{T}{T}mode: import\n{T}{T}source = ROW ( \"Dummy\", 1 )\n")

expressions_tmdl = (f'expression DataFolder = "{DATA_DIR}" meta [IsParameterQuery = true, Type = "Text", '
                    f'IsParameterQueryRequired = true]\n')

relationships_tmdl = """relationship items_to_orders
	fromColumn: items.order_id
	toColumn: orders.order_id

relationship orders_to_calendar
	fromColumn: orders.'Purchase Date'
	toColumn: Calendar.Date
"""

model_tmdl = """model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	discourageImplicitMeasures
	sourceQueryCulture: en-US

ref table orders
ref table items
ref table Calendar
ref table _Measures
"""

# fresh build
for p in (SM, RP):
    if p.exists():
        shutil.rmtree(p)
wj(SM / "definition.pbism", {"version": "4.0", "settings": {}})
w(SM / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
w(SM / "definition" / "model.tmdl", model_tmdl)
w(SM / "definition" / "expressions.tmdl", expressions_tmdl)
w(SM / "definition" / "relationships.tmdl", relationships_tmdl)
w(SM / "definition" / "tables" / "orders.tmdl", orders_tmdl)
w(SM / "definition" / "tables" / "items.tmdl", items_tmdl)
w(SM / "definition" / "tables" / "Calendar.tmdl", calendar_tmdl)
w(SM / "definition" / "tables" / "_Measures.tmdl", measures_tmdl)

# =====================================================================
# REPORT (PBIR)
# =====================================================================
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
BLUE, ORANGE, RED, GREY = "#1F5FA8", "#E8833A", "#C0392B", "#9AA5B1"


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def fld(table, prop, kind="Column"):
    return {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(table, prop, kind="Column", active=None):
    d = {"field": fld(table, prop, kind), "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}
    if active:
        d["active"] = True
    return d


def title(text):
    return {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{text}'"),
                                      "fontSize": lit("12D"), "bold": lit("true")}}]}


def visual(name, x, y, w_, h, vtype, query=None, objects=None, container=None, z=1000):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if query:
        v["query"] = query
    if objects:
        v["objects"] = objects
    d = {"$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json", "name": name,
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w_, "tabOrder": z}, "visual": v}
    if container:
        d["visual"]["visualContainerObjects"] = container
    return d


def card(name, x, y, measure_name, label, units=None, precision=None):
    props = {"fontSize": lit("24D")}
    if units is not None:
        props["labelDisplayUnits"] = lit(f"{units}D")
        if precision is not None:
            props["labelPrecision"] = lit(f"{precision}L")
    objects = {"labels": [{"properties": props}],
               "categoryLabels": [{"properties": {"show": lit("false")}}]}
    return visual(name, x, y, 195, 80, "card",
                  {"queryState": {"Values": {"projections": [proj("_Measures", measure_name, "Measure")]}}},
                  objects=objects,
                  container={"title": [{"properties": {"show": lit("true"), "text": lit(f"'{label}'"),
                                                       "fontSize": lit("10D")}}]})


def chart(name, x, y, w_, h, vtype, cat, vals, ttl, sort_measure=None, y2=None, labels=False, color=None):
    qs = {"Category": {"projections": [proj(*cat, active=True)]},
          "Y": {"projections": [proj(t, p, "Measure") for t, p in vals]}}
    if y2:
        qs["Y2"] = {"projections": [proj(t, p, "Measure") for t, p in y2]}
    q = {"queryState": qs}
    if sort_measure:
        q["sortDefinition"] = {"sort": [{"field": fld("_Measures", sort_measure, "Measure"), "direction": "Descending"}]}
    no_title = {"properties": {"showAxisTitle": lit("false")}}
    objects = {"categoryAxis": [no_title], "valueAxis": [no_title]}
    if labels:
        objects["labels"] = [{"properties": {"show": lit("true"), "labelPrecision": lit("2L")}}]
    if color:
        objects["dataPoint"] = [{"properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{color}'"}}}}}}}]
    return visual(name, x, y, w_, h, vtype, q, objects=objects, container=title(ttl))


def textbox(name, x, y, w_, h, paragraphs):
    paras = []
    for text, bold, size, *rest in paragraphs:
        run = {"value": text, "textStyle": {"fontSize": f"{size}pt"}}
        if rest:
            run["textStyle"]["color"] = rest[0]
        if bold:
            run["textStyle"]["fontWeight"] = "bold"
        paras.append({"textRuns": [run]})
    return visual(name, x, y, w_, h, "textbox", objects={"general": [{"properties": {"paragraphs": paras}}]})


def slicer(name, x, y, w_, h, table, prop, ttl):
    q = {"queryState": {"Values": {"projections": [proj(table, prop, active=True)]}}}
    return visual(name, x, y, w_, h, "slicer", q,
                  objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}, container=title(ttl))


page1 = [
    textbox("title1", 20, 8, 760, 44, [("Olist E-Commerce Performance", True, 20, "#FFFFFF")]),
    slicer("slicer_year", 800, 10, 200, 50, "Calendar", "Year", "Year"),
    slicer("slicer_state", 1020, 10, 240, 50, "orders", "customer_state", "State"),
    card("c_revenue", 20, 70, "Revenue", "Revenue (BRL)", units=1000000, precision=1),
    card("c_orders", 225, 70, "Delivered Orders", "Delivered orders", units=1),
    card("c_aov", 430, 70, "Average Order Value", "Avg order value (BRL)"),
    card("c_review", 635, 70, "Average Review Score", "Avg review score"),
    card("c_late", 840, 70, "Late Rate", "Late deliveries"),
    card("c_repeat", 1045, 70, "Repeat Rate", "Repeat customers"),
    chart("ch_monthly", 20, 160, 620, 270, "lineClusteredColumnComboChart", ("Calendar", "Month"),
          [("_Measures", "Revenue")], "Monthly revenue and delivered orders", y2=[("_Measures", "Delivered Orders")]),
    chart("ch_cat", 660, 160, 600, 270, "barChart", ("items", "category"),
          [("_Measures", "Item Revenue Top 10 Categories")], "Top 10 categories by revenue",
          sort_measure="Item Revenue Top 10 Categories"),
    chart("ch_state", 20, 445, 620, 265, "barChart", ("orders", "customer_state"),
          [("_Measures", "Revenue Top 10 States")], "Top 10 states by revenue", sort_measure="Revenue Top 10 States"),
    textbox("findings1", 660, 445, 600, 265, [
        ("Key findings", True, 14),
        ("1. Growth came from more orders, not bigger baskets: Jan-Aug revenue +141% year over year, average order value flat (about 137 BRL). Revenue plateaued after Nov 2017.", False, 11),
        ("2. Sao Paulo alone is 38% of revenue and the top 3 states 63%.", False, 11),
        ("3. 18 of 74 categories make 80% of revenue, led by health and beauty (9.3%).", False, 11),
    ]),
]
page2 = [
    textbox("title2", 20, 8, 900, 44, [("Delivery and Customer Experience", True, 20, "#FFFFFF")]),
    card("d_days", 20, 70, "Average Delivery Days", "Avg delivery days"),
    card("d_late", 225, 70, "Late Rate", "Late deliveries"),
    card("d_review", 430, 70, "Average Review Score", "Avg review score"),
    card("d_repeat", 635, 70, "Repeat Customers", "Repeat customers (2+ orders)"),
    card("d_rrate", 840, 70, "Repeat Rate", "Repeat rate"),
    chart("ch_late", 20, 160, 620, 270, "lineChart", ("Calendar", "Month"),
          [("_Measures", "Late Rate")], "Share of orders delivered after the promised date", color=RED),
    chart("ch_bucket", 660, 160, 600, 270, "clusteredColumnChart", ("orders", "Delivery Bucket"),
          [("_Measures", "Avg Review (dated deliveries)")], "Slower delivery, lower review score", labels=True),
    chart("ch_status", 20, 445, 620, 265, "clusteredColumnChart", ("orders", "Delivery Status"),
          [("_Measures", "Avg Review (dated deliveries)")], "Average review score: late vs on time", labels=True),
    textbox("findings2", 660, 445, 600, 265, [
        ("What this shows", True, 14),
        ("Late orders score 2.57 stars vs 4.29 on time, and 46% of late orders get 1 star. The gap holds inside every large state.", False, 11),
        ("Only 3.0% of customers bought twice or more.", False, 11),
        ("This is an association, not proof of cause. Revenue is not profit: the data has no costs.", False, 11),
    ]),
]

# ---------------------------------------------------------------------
# Upgrades inspired by the dashboard-design videos: navigation menu, "clear filters" button,
# rounded borders, a year-over-year table and an order details page.
# ---------------------------------------------------------------------
def reposition(visuals, name, x=None, y=None, w_=None, h=None):
    for v in visuals:
        if v["name"] == name:
            for k, val in (("x", x), ("y", y), ("width", w_), ("height", h)):
                if val is not None:
                    v["position"][k] = val


def solid(color):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{color}'"}}}}}


def nav(name):
    selected = {"properties": {"fillColor": solid("#F2C200")}, "selector": {"id": "selected"}}
    selected_text = {"properties": {"fontColor": solid("#1B3A6B")}, "selector": {"id": "selected"}}
    return visual(name, 500, 8, 400, 44, "pageNavigator", objects={"fill": [selected], "text": [selected_text]})


def band(name):
    objs = {"shape": [{"properties": {"tileShape": lit("'rectangle'")}}],
            "fill": [{"properties": {"fillColor": solid("#00843D")}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit("false")}}]}
    return visual(name, 0, 0, 1280, 64, "shape", objects=objs, z=0)


def clear_button(name):
    objs = {"text": [{"properties": {"show": lit("true"), "text": lit("'Clear filters'"),
                                     "fontColor": solid("#1B3A6B")}, "selector": {"id": "default"}}],
            "fill": [{"properties": {"show": lit("true"), "fillColor": solid("#FFFFFF"), "transparency": lit("0D")},
                      "selector": {"id": "default"}}],
            "icon": [{"properties": {"shapeType": lit("'blank'")}, "selector": {"id": "default"}}]}
    link = {"visualLink": [{"properties": {"show": lit("true"), "type": lit("'ClearAllSlicers'")}}]}
    return visual(name, 910, 8, 140, 44, "actionButton", objects=objs, container=link)


def table(name, x, y, w_, h, cols, ttl, objects=None, sort_desc=None):
    q = {"queryState": {"Values": {"projections": [proj(t, p, k) for t, p, k in cols]}}}
    if sort_desc:
        q["sortDefinition"] = {"sort": [{"field": fld(*sort_desc), "direction": "Descending"}]}
    return visual(name, x, y, w_, h, "tableEx", q, objects=objects, container=title(ttl))


reposition(page1, "title1", w_=470)
reposition(page2, "title2", w_=470)
reposition(page1, "slicer_year", x=1060, y=8, w_=200, h=50)
reposition(page1, "slicer_state", x=1055, y=70, w_=205, h=80)
for i, n in enumerate(["c_revenue", "c_orders", "c_aov", "c_review", "c_late", "c_repeat"]):
    reposition(page1, n, x=20 + i * 172, w_=165)
for i, n in enumerate(["d_days", "d_late", "d_review", "d_repeat", "d_rrate"]):
    reposition(page2, n, x=20 + i * 172, w_=165)
page1 += [nav("nav1"), clear_button("clear1")]
page2 += [nav("nav2"), clear_button("clear2")]

yoy_color = {"values": [{"properties": {"fontColor": {"solid": {"color": {"expr": {"Measure": {
    "Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "YoY Color"}}}}}},
    "selector": {"metadata": "_Measures.YoY Trend"}}],
    "total": [{"properties": {"totals": lit("false")}}]}
page3 = [
    textbox("title3", 20, 8, 470, 44, [("Trends and Order Details", True, 20, "#FFFFFF")]),
    nav("nav3"), clear_button("clear3"),
    slicer("slicer_year3", 1060, 8, 200, 50, "Calendar", "Year", "Year"),
    slicer("slicer_state3", 20, 62, 300, 50, "orders", "customer_state", "State"),
    slicer("slicer_status3", 330, 62, 300, 50, "orders", "Delivery Status", "Delivery"),
    table("t_yoy", 20, 122, 1240, 250,
          [("Calendar", "Month", "Column"), ("_Measures", "Revenue", "Measure"),
           ("_Measures", "Revenue Same Period Last Year", "Measure"), ("_Measures", "YoY Trend", "Measure")],
          "Revenue vs the same month last year (2017 has no previous year)", objects=yoy_color,
          sort_desc=("Calendar", "Month")),
    table("t_orders", 20, 382, 1240, 328,
          [("orders", "order_id", "Column"), ("orders", "Purchase Date", "Column"), ("orders", "customer_state", "Column"),
           ("orders", "order_status", "Column"), ("orders", "revenue", "Column"), ("orders", "delivery_days", "Column"),
           ("orders", "Delivery Status", "Column"), ("orders", "review_score", "Column")],
          "Order details (filtered by the selections above)"),
]

BORDER = {"border": [{"properties": {"show": lit("true"), "color": lit("'#CFE3D6'"), "radius": lit("10D")}}],
          "background": [{"properties": {"show": lit("true"), "color": solid("#FFFFFF"), "transparency": lit("0D")}}]}
for pg, band_name in ((page1, "band1"), (page2, "band2"), (page3, "band3")):
    pg.insert(0, band(band_name))
    for v in pg:
        if v["name"].startswith("title"):  # white title text must sit on the green band, not on a white box
            v["visual"].setdefault("visualContainerObjects", {})["background"] = [{"properties": {"show": lit("false")}}]
        if v["visual"]["visualType"] not in ("pageNavigator", "actionButton", "shape") and not v["name"].startswith("title"):
            v["visual"].setdefault("visualContainerObjects", {}).update(BORDER)

wj(PBI / f"{NAME}.pbip", {"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                          "settings": {"enableAutoRecovery": True}})
wj(RP / "definition.pbir", {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
wj(RP / "definition" / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
VERSION_AT_IMPORT = {"visual": "1.8.50", "report": "2.0.50", "page": "1.3.50"}
wj(RP / "StaticResources" / "RegisteredResources" / "OlistTheme.json", {
    "name": "OlistTheme",
    "dataColors": ["#1B3A6B", "#009C3B", "#F2C200", RED, "#4A78B5", "#7F8C8D", "#6FBF8B", "#9AA5B1"],
    "background": "#FFFFFF", "foreground": "#1C2733", "tableAccent": "#00843D"})
wj(RP / "definition" / "report.json", {
    "$schema": f"{SCHEMA}/report/3.0.0/schema.json",
    "themeCollection": {
        "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": VERSION_AT_IMPORT, "type": "SharedResources"},
        "customTheme": {"name": "OlistTheme.json", "reportVersionAtImport": VERSION_AT_IMPORT, "type": "RegisteredResources"}},
    "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                          "items": [{"name": "OlistTheme.json", "path": "OlistTheme.json", "type": "CustomTheme"}]}],
    "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                 "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                 "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
wj(RP / "definition" / "pages" / "pages.json", {"$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
                                                "pageOrder": ["page_overview", "page_delivery", "page_trends"], "activePageName": "page_overview"})
for pname, disp, visuals in (("page_overview", "Executive Overview", page1), ("page_delivery", "Delivery & Customer Experience", page2),
                              ("page_trends", "Trends & Order Details", page3)):
    wj(RP / "definition" / "pages" / pname / "page.json",
       {"$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": pname, "displayName": disp,
        "displayOption": "FitToPage", "height": 720, "width": 1280,
        "objects": {"background": [{"properties": {"color": solid("#F2F5F3"), "transparency": lit("0D")}}]}})
    for v in visuals:
        wj(RP / "definition" / "pages" / pname / "visuals" / v["name"] / "visual.json", v)

w(PBI / ".gitignore", ".pbi/\n*.pbix.bak\n")
print("Built", PBI / f"{NAME}.pbip")
