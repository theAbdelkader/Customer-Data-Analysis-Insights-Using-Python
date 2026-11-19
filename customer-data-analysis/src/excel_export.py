"""Excel workbook with the customer analysis results (values calculated in Python, formatted for business users)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HEADER_BG = "#1c5cab"
FONT = "Arial"


def _formats(wb):
    base = {"font_name": FONT, "font_size": 10}
    return {
        "title": wb.add_format({**base, "bold": True, "font_size": 16, "font_color": "#0b0b0b"}),
        "sub": wb.add_format({**base, "italic": True, "font_color": "#52514e"}),
        "hdr": wb.add_format({**base, "bold": True, "font_color": "white", "bg_color": HEADER_BG,
                              "border": 1, "border_color": "#c3c2b7", "text_wrap": True, "valign": "vcenter"}),
        "txt": wb.add_format({**base}),
        "wrap": wb.add_format({**base, "text_wrap": True, "valign": "top"}),
        "int": wb.add_format({**base, "num_format": "#,##0"}),
        "gbp": wb.add_format({**base, "num_format": "£#,##0.00"}),
        "gbp0": wb.add_format({**base, "num_format": "£#,##0"}),
        "pct": wb.add_format({**base, "num_format": "0.0\"%\""}),
        "dec": wb.add_format({**base, "num_format": "0.00"}),
        "date": wb.add_format({**base, "num_format": "yyyy-mm-dd"}),
        "bold": wb.add_format({**base, "bold": True}),
    }


def _fmt_for(col: str, series: pd.Series, f: dict):
    c = col.lower()
    if pd.api.types.is_datetime64_any_dtype(series):
        return f["date"]
    if any(k in c for k in ("pct", "rate_pct", "share")) or c.endswith("_pct"):
        return f["pct"]
    if any(k in c for k in ("revenue", "value", "gbp", "spend")) and "customers" not in c and "index" not in c:
        return f["gbp"]
    if "avg_order" in c or c in ("p20", "p40", "p60", "p80"):
        return f["dec"]
    if pd.api.types.is_integer_dtype(series):
        return f["int"]
    if pd.api.types.is_float_dtype(series):
        return f["dec"]
    return f["txt"]


def write_table(ws, df: pd.DataFrame, f: dict, row: int = 0, col: int = 0, autofilter: bool = True,
                freeze: bool = True, widths: dict | None = None) -> int:
    """Write a DataFrame as a formatted table; returns the next free row."""
    ws.set_row(row, 30)
    for j, name in enumerate(df.columns):
        ws.write_string(row, col + j, str(name), f["hdr"])
    for j, name in enumerate(df.columns):
        series = df[name]
        fmt = _fmt_for(str(name), series, f)
        for i, v in enumerate(series.tolist()):
            r = row + 1 + i
            if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT or (v is pd.NA):
                ws.write_blank(r, col + j, None, fmt)
            elif isinstance(v, pd.Timestamp):
                ws.write_datetime(r, col + j, v.to_pydatetime(), fmt)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                ws.write_number(r, col + j, v, fmt)
            else:
                ws.write_string(r, col + j, str(v), fmt)  # write_string: text that starts with "=" must not become a formula
        w = max(len(str(name)) * 0.9, min(40, series.astype(str).str.len().max() if len(series) else 8) + 2)
        ws.set_column(col + j, col + j, (widths or {}).get(name, max(11, min(w, 44))))
    if autofilter and len(df):
        ws.autofilter(row, col, row + len(df), col + len(df.columns) - 1)
    if freeze:
        ws.freeze_panes(row + 1, 0)
    return row + len(df) + 2


def export_workbook(path: Path, *, kpis: dict, summary: pd.DataFrame, segment_rules: dict, cuts: pd.DataFrame,
                    customers: pd.DataFrame, monthly: pd.DataFrame, cohort: pd.DataFrame, top: pd.DataFrame,
                    products: pd.DataFrame, country: pd.DataFrame, backtest: pd.DataFrame,
                    clean_log: pd.DataFrame, quality: pd.DataFrame, insights: list[dict],
                    excluded_customers: pd.DataFrame) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as xw:
        wb = xw.book
        f = _formats(wb)

        # ---- Summary ----
        ws = wb.add_worksheet("Summary")
        xw.sheets["Summary"] = ws
        ws.hide_gridlines(2)
        ws.set_column(0, 0, 38)
        ws.set_column(1, 1, 22)
        ws.set_column(2, 2, 70)
        ws.write_string(0, 0, "Customer Data Analysis - Summary", f["title"])
        ws.write_string(1, 0, "UCI Online Retail dataset, 1 Dec 2010 - 9 Dec 2011. Currency: GBP. All figures use cleaned data.", f["sub"])
        rows = [
            ("Customers (with at least one purchase)", kpis["customers"], "int", "Customers with a known CustomerID and a valid sale"),
            ("Orders (invoices)", kpis["orders"], "int", "Distinct sale invoices after cleaning"),
            ("Gross revenue", kpis["gross_revenue"], "gbp", "Sum of Quantity x UnitPrice on clean sale lines"),
            ("Returns (cancellations)", kpis["returns_value"], "gbp", "Value of cancellation invoices of known customers"),
            ("Net revenue", kpis["net_revenue"], "gbp", "Gross revenue minus returns"),
            ("Return rate", kpis["return_rate_pct"], "pct", "Returns as % of gross revenue"),
            ("Average order value (gross)", kpis["avg_order_value"], "gbp", "Gross revenue / orders"),
            ("Median order value", kpis["median_order_value"], "gbp", "Half of orders are below this value"),
            ("Orders per customer (mean)", kpis["orders_per_customer"], "dec", "Orders / customers"),
            ("Orders per customer (median)", kpis["median_orders_per_customer"], "dec", "Typical customer"),
            ("Net revenue per customer", kpis["net_revenue_per_customer"], "gbp", "Net revenue / customers"),
            ("Repeat customers (2+ orders)", kpis["repeat_customers"], "int", "Customers with at least two distinct invoices"),
            ("Repeat rate", kpis["repeat_rate_pct"], "pct", "Repeat customers / customers"),
            ("Countries", kpis["countries"], "int", ""),
            ("UK share of net customers", kpis["uk_customer_share_pct"], "pct", ""),
        ]
        ws.write_string(3, 0, "KPI", f["hdr"]); ws.write_string(3, 1, "Value", f["hdr"]); ws.write_string(3, 2, "Definition", f["hdr"])
        for i, (k, v, fmt, d) in enumerate(rows):
            ws.write_string(4 + i, 0, k, f["bold"])
            ws.write_number(4 + i, 1, v, f[fmt])
            ws.write_string(4 + i, 2, d, f["txt"])
        r = 4 + len(rows) + 2
        ws.write_string(r, 0, "Key business insights", f["bold"])
        for i, ins in enumerate(insights):
            ws.write_string(r + 1 + i, 0, f"{i + 1}. {ins['title']}", f["wrap"])
            ws.merge_range(r + 1 + i, 1, r + 1 + i, 2, ins["recommendation"], f["wrap"])
            ws.set_row(r + 1 + i, 62)

        # ---- Segment summary + methodology ----
        ws = wb.add_worksheet("Segment_Summary")
        xw.sheets["Segment_Summary"] = ws
        s = summary.copy()
        s["segment"] = s["segment"].astype(str)
        nxt = write_table(ws, s, f, freeze=False, autofilter=False)
        ws.write_string(nxt, 0, "Segment rules (R, F, M scores run from 1 = worst to 5 = best)", f["bold"])
        for i, (k, v) in enumerate(segment_rules.items()):
            ws.write_string(nxt + 1 + i, 0, k, f["bold"])
            ws.merge_range(nxt + 1 + i, 1, nxt + 1 + i, 6, v, f["txt"])
        nxt = nxt + len(segment_rules) + 3
        ws.write_string(nxt, 0, "Score cut-points (20th / 40th / 60th / 80th percentile of the customer base)", f["bold"])
        write_table(ws, cuts, f, row=nxt + 1, freeze=False, autofilter=False)
        ws.set_column(0, 0, 26)

        # ---- Customer table ----
        ws = wb.add_worksheet("Customer_Segments")
        xw.sheets["Customer_Segments"] = ws
        c = customers.copy()
        c["segment"] = c["segment"].astype(str)
        write_table(ws, c, f)

        ws = wb.add_worksheet("Monthly_Trends"); xw.sheets["Monthly_Trends"] = ws
        write_table(ws, monthly, f)
        ws.write_string(len(monthly) + 3, 0, "is_partial = True: December 2011 ends on 9 December, so it is incomplete.", f["sub"])

        ws = wb.add_worksheet("Cohort_Retention"); xw.sheets["Cohort_Retention"] = ws
        co = cohort.copy().reset_index().rename(columns={"index": "cohort", "cohort": "cohort"})
        co.columns = [str(x) if i == 0 else f"M+{x}" for i, x in enumerate(co.columns)]
        write_table(ws, co, f, autofilter=False)
        ws.write_string(len(co) + 3, 0, "Values are % of the cohort active k months after its first purchase month. Dec 2010 contains all customers already active at the start of the data.", f["sub"])

        ws = wb.add_worksheet("Top_Customers"); xw.sheets["Top_Customers"] = ws
        t = top.copy(); t["segment"] = t["segment"].astype(str)
        write_table(ws, t, f)

        ws = wb.add_worksheet("Products_Top50"); xw.sheets["Products_Top50"] = ws
        write_table(ws, products.head(50), f)

        ws = wb.add_worksheet("Countries"); xw.sheets["Countries"] = ws
        write_table(ws, country, f)

        ws = wb.add_worksheet("Segment_Backtest"); xw.sheets["Segment_Backtest"] = ws
        b = backtest.copy(); b["segment"] = b["segment"].astype(str)
        nxt = write_table(ws, b, f, freeze=False, autofilter=False)
        cut = backtest.attrs.get("cutoff")
        ws.write_string(nxt, 0, f"Segments built from data before {cut:%Y-%m-%d}; behaviour measured in the following 90 days.", f["sub"])

        ws = wb.add_worksheet("Cleaning_Log"); xw.sheets["Cleaning_Log"] = ws
        nxt = write_table(ws, clean_log, f, freeze=False, autofilter=False)
        ws.write_string(nxt, 0, "Data quality before and after", f["bold"])
        nxt = write_table(ws, quality, f, row=nxt + 1, freeze=False, autofilter=False)
        if len(excluded_customers):
            ws.write_string(nxt, 0, "Customers left out of RFM because returns cancelled all of their spending", f["bold"])
            write_table(ws, excluded_customers[["CustomerID", "country", "frequency", "gross_revenue", "return_value", "net_revenue"]],
                        f, row=nxt + 1, freeze=False, autofilter=False)
        ws.set_column(0, 0, 28); ws.set_column(1, 1, 58)
    return path
