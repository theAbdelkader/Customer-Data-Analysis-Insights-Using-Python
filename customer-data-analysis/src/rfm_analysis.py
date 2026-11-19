"""
RFM customer segmentation.

Method (kept deliberately simple and explainable):

* Recency   (R) = days from the customer's last purchase to the snapshot date (smaller is better)
* Frequency (F) = number of distinct purchase invoices
* Monetary  (M) = NET spend in £ = sales - returns

Scoring: each metric is scored 1-5 with the 20th/40th/60th/80th percentile of the customer base as
cut-points ("quintile cut-points"). A customer scores 5 on Frequency when they are above the 80th
percentile, and 5 on Recency when they are at or below the 20th percentile (most recent).
Unlike rank-based binning, equal values always receive the same score, so the many customers
with exactly one purchase are not split arbitrarily.

Segments come from a transparent rule table on the R, F and M scores (see SEGMENT_RULES).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QUANTILES = (0.2, 0.4, 0.6, 0.8)

SEGMENT_ORDER = [
    "Champions",
    "Loyal Customers",
    "Potential Loyalists",
    "New Customers",
    "At Risk",
    "Can't Lose Them",
    "Hibernating",
]

SEGMENT_RULES = {
    "Champions": "R >= 4 and F >= 4: bought very recently and buy often",
    "Loyal Customers": "R >= 3 and F >= 3 (not Champions): regular buyers, reasonably recent",
    "New Customers": "R >= 4 and F = 1: first purchase very recently",
    "Potential Loyalists": "R >= 3 and F <= 2 (not New): recent, but only 1-2 purchases so far",
    "Can't Lose Them": "R <= 2 and F >= 4 and M >= 4: our best spenders/frequent buyers who have gone quiet",
    "At Risk": "R <= 2 and F >= 3 (not Can't Lose Them): used to buy repeatedly, now quiet",
    "Hibernating": "R <= 2 and F <= 2: long inactive with little purchase history",
}

SEGMENT_ACTIONS = {
    "Champions": "Reward and retain: named contact, early access to new products, loyalty perks; ask for referrals",
    "Loyal Customers": "Upsell and cross-sell; reorder reminders; invite into a loyalty / trade programme",
    "Potential Loyalists": "Encourage the 3rd and 4th order: bundles, next-best-product offers, reorder reminders",
    "New Customers": "Onboarding: thank-you, product-care tips, welcome offer valid for a second order",
    "At Risk": "Automated win-back sequence after ~90 days of silence; offer on previously bought products",
    "Can't Lose Them": "Personal outreach by an account manager; understand why they stopped; tailored win-back offer",
    "Hibernating": "Low-cost seasonal campaigns only; suppress from paid channels; reactivate with best sellers",
}


# --------------------------------------------------------------------------------------
# Customer table
# --------------------------------------------------------------------------------------
def snapshot_date(sales: pd.DataFrame) -> pd.Timestamp:
    """Day after the last transaction: recency of a customer who bought on the last day is 1."""
    return sales["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)


def build_customer_table(sales: pd.DataFrame, returns: pd.DataFrame,
                         snapshot: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per customer with purchase history, value and return metrics."""
    if snapshot is None:
        snapshot = snapshot_date(sales)
    sales = sales[sales["InvoiceDate"] < snapshot]
    returns = returns[returns["InvoiceDate"] < snapshot]

    inv = sales.groupby(["CustomerID", "InvoiceNo"]).agg(
        invoice_date=("InvoiceDate", "min"), invoice_value=("Revenue", "sum")).reset_index()
    cust = inv.groupby("CustomerID").agg(
        first_purchase=("invoice_date", "min"),
        last_purchase=("invoice_date", "max"),
        frequency=("InvoiceNo", "nunique"),
        gross_revenue=("invoice_value", "sum"),
    )
    cust["recency_days"] = (snapshot - cust["last_purchase"].dt.normalize()).dt.days
    cust["units"] = sales.groupby("CustomerID")["Quantity"].sum()
    cust["distinct_products"] = sales.groupby("CustomerID")["StockCode"].nunique()
    cust["country"] = sales.sort_values("InvoiceDate").groupby("CustomerID")["Country"].last()
    cust["return_value"] = (-returns.groupby("CustomerID")["Revenue"].sum()).reindex(cust.index).fillna(0.0)
    cust["net_revenue"] = (cust["gross_revenue"] - cust["return_value"]).round(2)
    cust["avg_order_value"] = cust["gross_revenue"] / cust["frequency"]
    cust["return_rate_pct"] = np.where(cust["gross_revenue"] > 0,
                                       100 * cust["return_value"] / cust["gross_revenue"], 0.0)
    cust["tenure_days"] = (cust["last_purchase"].dt.normalize() - cust["first_purchase"].dt.normalize()).dt.days
    cust["active_months"] = sales.groupby("CustomerID")["InvoiceMonth"].nunique() \
        if "InvoiceMonth" in sales.columns else sales.groupby("CustomerID")["InvoiceDate"].apply(
            lambda s: s.dt.to_period("M").nunique())
    for col in ("gross_revenue", "return_value", "avg_order_value", "return_rate_pct"):
        cust[col] = cust[col].round(2)
    return cust.reset_index()


# --------------------------------------------------------------------------------------
# Scoring and segmentation
# --------------------------------------------------------------------------------------
def quintile_cutpoints(values: pd.Series) -> list[float]:
    return [float(values.quantile(q)) for q in QUANTILES]


def _score(values: pd.Series, cuts: list[float], higher_is_better: bool) -> pd.Series:
    # number of cut-points strictly below the value: 0..4
    below = np.searchsorted(np.asarray(cuts), values.to_numpy(), side="left")
    score = below + 1 if higher_is_better else 5 - below
    return pd.Series(score.astype(int), index=values.index)


def score_rfm(cust: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add R/F/M scores. Returns the scored table and a cut-point table for documentation."""
    out = cust.copy()
    cuts = {
        "recency_days": quintile_cutpoints(out["recency_days"]),
        "frequency": quintile_cutpoints(out["frequency"]),
        "net_revenue": quintile_cutpoints(out["net_revenue"]),
    }
    out["R_score"] = _score(out["recency_days"], cuts["recency_days"], higher_is_better=False)
    out["F_score"] = _score(out["frequency"], cuts["frequency"], higher_is_better=True)
    out["M_score"] = _score(out["net_revenue"], cuts["net_revenue"], higher_is_better=True)
    out["RFM_score"] = out["R_score"].astype(str) + out["F_score"].astype(str) + out["M_score"].astype(str)
    cut_table = pd.DataFrame(
        {"metric": list(cuts), "p20": [c[0] for c in cuts.values()], "p40": [c[1] for c in cuts.values()],
         "p60": [c[2] for c in cuts.values()], "p80": [c[3] for c in cuts.values()]})
    return out, cut_table


def assign_segment(r: int, f: int, m: int) -> str:
    if r >= 3:
        if r >= 4 and f >= 4:
            return "Champions"
        if f >= 3:
            return "Loyal Customers"
        if r >= 4 and f == 1:
            return "New Customers"
        return "Potential Loyalists"
    if f >= 3:
        return "Can't Lose Them" if (f >= 4 and m >= 4) else "At Risk"
    return "Hibernating"


def assign_segments(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    out["segment"] = [assign_segment(r, f, m) for r, f, m in zip(out["R_score"], out["F_score"], out["M_score"])]
    out["segment"] = pd.Categorical(out["segment"], categories=SEGMENT_ORDER, ordered=True)
    return out


def rfm_population(cust: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Customers with positive net spend enter RFM; the rest (fully refunded) are listed separately."""
    keep = cust["net_revenue"] > 0
    return cust[keep].copy(), cust[~keep].copy()


def segment_summary(seg: pd.DataFrame) -> pd.DataFrame:
    g = seg.groupby("segment", observed=False)
    out = g.agg(
        customers=("CustomerID", "size"),
        net_revenue=("net_revenue", "sum"),
        avg_recency_days=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_net_revenue=("net_revenue", "mean"),
        median_net_revenue=("net_revenue", "median"),
        avg_order_value=("avg_order_value", "mean"),
        avg_return_rate_pct=("return_rate_pct", "mean"),
    ).reset_index()
    out["pct_customers"] = 100 * out["customers"] / out["customers"].sum()
    out["pct_revenue"] = 100 * out["net_revenue"] / out["net_revenue"].sum()
    out["revenue_per_customer_index"] = out["pct_revenue"] / out["pct_customers"]
    return out.round(2)


# --------------------------------------------------------------------------------------
# Validation: do the segments predict future behaviour?
# --------------------------------------------------------------------------------------
def backtest_segments(sales: pd.DataFrame, returns: pd.DataFrame, holdout_days: int = 90) -> pd.DataFrame:
    """Build segments using only data before a cut-off date, then look at the following `holdout_days`.

    If the segmentation is meaningful, 'good' segments should buy again more often and spend more
    in the holdout than 'bad' ones. Returns one row per segment.
    """
    end = sales["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)
    cutoff = end - pd.Timedelta(days=holdout_days)
    cust = build_customer_table(sales, returns, snapshot=cutoff)
    pop, _ = rfm_population(cust)
    seg = assign_segments(score_rfm(pop)[0])

    future = sales[(sales["InvoiceDate"] >= cutoff) & (sales["InvoiceDate"] < end)]
    fut = future.groupby("CustomerID").agg(future_orders=("InvoiceNo", "nunique"), future_revenue=("Revenue", "sum"))
    seg = seg.merge(fut, left_on="CustomerID", right_index=True, how="left").fillna(
        {"future_orders": 0, "future_revenue": 0.0})
    seg["bought_again"] = seg["future_orders"] > 0
    out = seg.groupby("segment", observed=False).agg(
        customers=("CustomerID", "size"),
        repurchase_rate_pct=("bought_again", lambda s: 100 * s.mean()),
        avg_future_revenue=("future_revenue", "mean"),
        total_future_revenue=("future_revenue", "sum"),
    ).reset_index()
    out["pct_of_future_revenue"] = 100 * out["total_future_revenue"] / out["total_future_revenue"].sum()
    out.attrs["cutoff"] = cutoff
    out.attrs["end"] = end
    return out.round(2)
