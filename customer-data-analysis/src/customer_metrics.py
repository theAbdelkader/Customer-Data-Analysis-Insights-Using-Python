"""
Descriptive customer analytics: KPIs, trends, repeat behaviour, concentration, retention, products.

All functions take the cleaned tables produced by src/data_cleaning.py (sales, returns) and,
where needed, the customer table from src/rfm_analysis.py. Nothing here reads files.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------------------
# Headline KPIs
# --------------------------------------------------------------------------------------
def headline_kpis(sales: pd.DataFrame, returns: pd.DataFrame, cust: pd.DataFrame) -> dict:
    orders = sales["InvoiceNo"].nunique()
    gross = float(sales["Revenue"].sum())
    ret = float(-returns["Revenue"].sum())
    n_cust = int(cust["CustomerID"].nunique())
    repeat = int((cust["frequency"] >= 2).sum())
    return {
        "period_start": sales["InvoiceDate"].min().strftime("%Y-%m-%d"),
        "period_end": sales["InvoiceDate"].max().strftime("%Y-%m-%d"),
        "customers": n_cust,
        "orders": int(orders),
        "gross_revenue": round(gross, 2),
        "returns_value": round(ret, 2),
        "net_revenue": round(gross - ret, 2),
        "return_rate_pct": round(100 * ret / gross, 2),
        "avg_order_value": round(gross / orders, 2),
        "net_avg_order_value": round((gross - ret) / orders, 2),
        "median_order_value": round(float(sales.groupby("InvoiceNo")["Revenue"].sum().median()), 2),
        "orders_per_customer": round(orders / n_cust, 2),
        "median_orders_per_customer": float(cust["frequency"].median()),
        "revenue_per_customer": round(gross / n_cust, 2),
        "net_revenue_per_customer": round((gross - ret) / n_cust, 2),
        "units_sold": int(sales["Quantity"].sum()),
        "products": int(sales["StockCode"].nunique()),
        "countries": int(cust["country"].nunique()),
        "repeat_customers": repeat,
        "one_time_customers": n_cust - repeat,
        "repeat_rate_pct": round(100 * repeat / n_cust, 2),
        "uk_customer_share_pct": round(100 * (cust["country"] == "United Kingdom").mean(), 2),
        "uk_revenue_share_pct": round(
            100 * sales.loc[sales["Country"] == "United Kingdom", "Revenue"].sum() / gross, 2),
    }


# --------------------------------------------------------------------------------------
# Time trends
# --------------------------------------------------------------------------------------
def monthly_trends(sales: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Revenue, orders, active/new/returning customers and AOV per calendar month.

    The final month is flagged `is_partial` because the data stops on 9 Dec 2011.
    """
    s = sales.assign(month=sales["InvoiceDate"].dt.to_period("M"))
    first_month = s.groupby("CustomerID")["month"].min()
    s["is_new"] = s["month"] == s["CustomerID"].map(first_month)

    inv = s.groupby(["month", "InvoiceNo"]).agg(value=("Revenue", "sum")).reset_index()
    m = inv.groupby("month").agg(orders=("InvoiceNo", "nunique"), gross_revenue=("value", "sum"))
    m["active_customers"] = s.groupby("month")["CustomerID"].nunique()
    m["new_customers"] = s[s["is_new"]].groupby("month")["CustomerID"].nunique()
    m["new_customers"] = m["new_customers"].fillna(0).astype(int)
    m["returning_customers"] = m["active_customers"] - m["new_customers"]
    m["units"] = s.groupby("month")["Quantity"].sum()
    ret = (-returns.assign(month=returns["InvoiceDate"].dt.to_period("M")).groupby("month")["Revenue"].sum())
    m["returns_value"] = ret.reindex(m.index).fillna(0.0)
    m["net_revenue"] = m["gross_revenue"] - m["returns_value"]
    m["avg_order_value"] = m["gross_revenue"] / m["orders"]
    m["orders_per_active_customer"] = m["orders"] / m["active_customers"]
    m["is_partial"] = False
    last_day = sales["InvoiceDate"].max()
    m.loc[m.index[-1], "is_partial"] = last_day.day < last_day.days_in_month
    m["mom_growth_pct"] = m["gross_revenue"].pct_change() * 100
    m = m.reset_index()
    m["month"] = m["month"].astype(str)
    return m.round(2)


def weekday_hour_patterns(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Orders and revenue by weekday and by hour of day (invoice level)."""
    inv = sales.groupby("InvoiceNo").agg(date=("InvoiceDate", "min"), value=("Revenue", "sum")).reset_index()
    inv["weekday"] = inv["date"].dt.day_name()
    inv["hour"] = inv["date"].dt.hour
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    wd = inv.groupby("weekday").agg(orders=("InvoiceNo", "size"), revenue=("value", "sum")).reindex(order).fillna(0)
    hr = inv.groupby("hour").agg(orders=("InvoiceNo", "size"), revenue=("value", "sum"))
    return wd.reset_index().round(2), hr.reset_index().round(2)


# --------------------------------------------------------------------------------------
# Repeat vs one-time, frequency, gaps
# --------------------------------------------------------------------------------------
def repeat_vs_onetime(cust: pd.DataFrame) -> pd.DataFrame:
    c = cust.assign(type=np.where(cust["frequency"] >= 2, "Repeat customers", "One-time customers"))
    out = c.groupby("type").agg(customers=("CustomerID", "size"), gross_revenue=("gross_revenue", "sum"),
                                net_revenue=("net_revenue", "sum"), avg_orders=("frequency", "mean"),
                                avg_order_value=("avg_order_value", "mean")).reset_index()
    out["pct_customers"] = 100 * out["customers"] / out["customers"].sum()
    out["pct_net_revenue"] = 100 * out["net_revenue"] / out["net_revenue"].sum()
    return out.round(2)


def frequency_distribution(cust: pd.DataFrame) -> pd.DataFrame:
    """Customers by number of orders (1, 2, 3, 4, 5, 6-9, 10-19, 20+)."""
    bins = [0, 1, 2, 3, 4, 5, 9, 19, np.inf]
    labels = ["1", "2", "3", "4", "5", "6-9", "10-19", "20+"]
    b = pd.cut(cust["frequency"], bins=bins, labels=labels)
    out = cust.groupby(b, observed=False).agg(customers=("CustomerID", "size"),
                                              net_revenue=("net_revenue", "sum")).reset_index()
    out.columns = ["orders", "customers", "net_revenue"]
    out["pct_customers"] = 100 * out["customers"] / out["customers"].sum()
    out["pct_net_revenue"] = 100 * out["net_revenue"] / out["net_revenue"].sum()
    return out.round(2)


def purchase_gaps(sales: pd.DataFrame) -> pd.Series:
    """Days between consecutive purchase days of the same customer (repeat customers only)."""
    days = sales.assign(day=sales["InvoiceDate"].dt.normalize()).drop_duplicates(["CustomerID", "day"])
    days = days.sort_values(["CustomerID", "day"])
    gap = days.groupby("CustomerID")["day"].diff().dt.days.dropna()
    return gap[gap > 0]


def repeat_within_days(sales: pd.DataFrame, days: int = 90) -> dict:
    """Share of customers who bought again within `days` of their first purchase.

    Only customers whose first purchase is at least `days` before the end of the data are counted,
    so every customer in the base had a full observation window.
    """
    end = sales["InvoiceDate"].max()
    inv = (sales.groupby(["CustomerID", "InvoiceNo"])["InvoiceDate"].min().reset_index()
           .sort_values(["CustomerID", "InvoiceDate", "InvoiceNo"]))
    inv["order_number"] = inv.groupby("CustomerID").cumcount() + 1
    first = inv.loc[inv["order_number"] == 1].set_index("CustomerID")["InvoiceDate"]
    eligible = first[first <= end - pd.Timedelta(days=days)]
    inv = inv[inv["CustomerID"].isin(eligible.index)].copy()
    inv["first"] = inv["CustomerID"].map(first)
    later = inv[(inv["order_number"] > 1) & (inv["InvoiceDate"] <= inv["first"] + pd.Timedelta(days=days))]
    n_back = later["CustomerID"].nunique()
    return {"window_days": days, "eligible_customers": int(len(eligible)),
            "repeat_within_window": int(n_back),
            "rate_pct": round(100 * n_back / len(eligible), 2)}


# --------------------------------------------------------------------------------------
# Value concentration
# --------------------------------------------------------------------------------------
def gini(values: np.ndarray) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    n = len(v)
    cum = np.cumsum(v)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


def revenue_concentration(cust: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Pareto curve (customers ranked by net revenue) and headline concentration numbers."""
    c = cust[cust["net_revenue"] > 0].sort_values("net_revenue", ascending=False).reset_index(drop=True)
    n = len(c)
    total = c["net_revenue"].sum()
    curve = pd.DataFrame({
        "cum_customer_pct": 100 * (np.arange(1, n + 1) / n),
        "cum_revenue_pct": 100 * c["net_revenue"].cumsum() / total,
    })

    def share(top_pct: float) -> float:
        k = max(1, int(round(n * top_pct / 100)))
        return round(float(100 * c["net_revenue"].head(k).sum() / total), 2)

    summary = {
        "customers_in_base": n,
        "top_1pct_share": share(1), "top_5pct_share": share(5),
        "top_10pct_share": share(10), "top_20pct_share": share(20),
        "bottom_50pct_share": round(float(100 * c["net_revenue"].tail(n // 2).sum() / total), 2),
        "gini": round(gini(c["net_revenue"].to_numpy()), 3),
        "customers_for_80pct_revenue": int((curve["cum_revenue_pct"] < 80).sum() + 1),
    }
    summary["customers_for_80pct_revenue_pct"] = round(100 * summary["customers_for_80pct_revenue"] / n, 2)
    summary["top_customer_share"] = round(float(100 * c["net_revenue"].iloc[0] / total), 2)
    return curve, summary


def top_customers(seg: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    cols = ["CustomerID", "country", "segment", "net_revenue", "frequency", "recency_days",
            "avg_order_value", "return_rate_pct"]
    t = seg.sort_values("net_revenue", ascending=False).head(n)[cols].copy()
    t.insert(0, "rank", range(1, len(t) + 1))
    t["share_of_net_revenue_pct"] = (100 * t["net_revenue"] / seg["net_revenue"].sum()).round(2)
    return t


# --------------------------------------------------------------------------------------
# Cohort retention
# --------------------------------------------------------------------------------------
def cohort_retention(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monthly cohorts: % of each cohort that purchased again k months after its first month.

    The first data month (Dec 2010) holds every customer that was already active, so it is
    not a true 'new customer' cohort; the partial last month (Dec 2011) is dropped from the matrix.
    Returns (retention %, cohort sizes).
    """
    last_day = sales["InvoiceDate"].max()
    s = sales.assign(month=sales["InvoiceDate"].dt.to_period("M"))
    if last_day.day < last_day.days_in_month:
        s = s[s["month"] < s["month"].max()]
    first = s.groupby("CustomerID")["month"].min().rename("cohort")
    s = s.join(first, on="CustomerID")
    s["k"] = (s["month"] - s["cohort"]).apply(lambda x: x.n)
    act = s.groupby(["cohort", "k"])["CustomerID"].nunique().unstack(fill_value=0)
    size = act[0]
    ret = act.div(size, axis=0) * 100
    # blank out months that lie beyond the end of the (complete) data
    last_full = s["month"].max()
    for cohort in ret.index:
        max_k = (last_full - cohort).n
        ret.loc[cohort, ret.columns > max_k] = np.nan
    ret.index = ret.index.astype(str)
    sizes = size.rename("cohort_size")
    sizes.index = sizes.index.astype(str)
    return ret.round(1), sizes.reset_index()


# --------------------------------------------------------------------------------------
# Products and countries
# --------------------------------------------------------------------------------------
def product_summary(sales: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    p = sales.groupby("StockCode").agg(
        description=("Description", lambda s: s.mode().iloc[0] if s.notna().any() else ""),
        revenue=("Revenue", "sum"), units=("Quantity", "sum"),
        orders=("InvoiceNo", "nunique"), customers=("CustomerID", "nunique")).reset_index()
    r = returns.groupby("StockCode").agg(returned_value=("Revenue", lambda s: -s.sum()),
                                         returned_units=("Quantity", lambda s: -s.sum()))
    p = p.join(r, on="StockCode").fillna({"returned_value": 0.0, "returned_units": 0})
    p["return_rate_pct"] = 100 * p["returned_value"] / p["revenue"]
    # Rank on NET revenue: a product whose only big order was cancelled must not look like a best seller.
    p["net_revenue"] = p["revenue"] - p["returned_value"]
    p["net_units"] = p["units"] - p["returned_units"]
    return p.sort_values("net_revenue", ascending=False).reset_index(drop=True).round(2)


def country_summary(cust: pd.DataFrame) -> pd.DataFrame:
    c = cust.groupby("country").agg(customers=("CustomerID", "size"), net_revenue=("net_revenue", "sum"),
                                    avg_orders=("frequency", "mean")).reset_index()
    c["pct_customers"] = 100 * c["customers"] / c["customers"].sum()
    c["pct_net_revenue"] = 100 * c["net_revenue"] / c["net_revenue"].sum()
    c["revenue_per_customer"] = c["net_revenue"] / c["customers"]
    return c.sort_values("net_revenue", ascending=False).reset_index(drop=True).round(2)


def basket_stats(sales: pd.DataFrame) -> pd.DataFrame:
    """Order-level size: lines, units and value per invoice (used for AOV distribution chart)."""
    return sales.groupby("InvoiceNo").agg(lines=("StockCode", "size"), units=("Quantity", "sum"),
                                          value=("Revenue", "sum"), customer=("CustomerID", "first")).reset_index()
