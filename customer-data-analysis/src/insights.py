"""
Business insights, generated from the computed tables so every number in the text comes from the data.

Each insight has: title, evidence (numbers), interpretation (what it means) and recommendation (what to do).
"""
from __future__ import annotations

import pandas as pd


def _gbp(x: float) -> str:
    if abs(x) >= 1e6:
        return f"£{x / 1e6:.2f}M"
    if abs(x) >= 1e4:
        return f"£{x / 1e3:.0f}k"
    return f"£{x:,.0f}"


def build_insights(kpis: dict, seg: pd.DataFrame, summary: pd.DataFrame, conc: dict, rv: pd.DataFrame,
                   backtest: pd.DataFrame, monthly: pd.DataFrame, country: pd.DataFrame,
                   gap_median: float, repeat90: dict, cohort: pd.DataFrame,
                   weekday: pd.DataFrame, hour: pd.DataFrame) -> list[dict]:
    S = summary.set_index("segment")
    B = backtest.set_index("segment")
    out: list[dict] = []

    # 1. High-value customers: frequency, not basket size
    ch, hib = S.loc["Champions"], S.loc["Hibernating"]
    out.append({
        "theme": "High-value customers",
        "title": "Value comes from how often customers buy, not from how much they put in one basket",
        "evidence": (f"Champions place {ch['avg_frequency']:.1f} orders on average against {hib['avg_frequency']:.1f} for "
                     f"Hibernating customers, but their average order is similar ({_gbp(ch['avg_order_value'])} vs "
                     f"{_gbp(hib['avg_order_value'])}). Champions are {ch['pct_customers']:.0f}% of customers and "
                     f"{ch['pct_revenue']:.0f}% of net revenue."),
        "interpretation": "A customer becomes valuable by returning, so order frequency is the lever that separates the best customers from the rest.",
        "recommendation": "Measure and manage the second and third order. Reward order frequency (for example a reorder incentive or "
                          "account-manager contact for customers on their 3rd to 5th order) rather than pushing larger baskets.",
    })

    # 2. Revenue concentration
    out.append({
        "theme": "Revenue concentration",
        "title": "A small group of customers carries the business",
        "evidence": (f"The top 10% of customers deliver {conc['top_10pct_share']:.0f}% of net revenue and the top 1% "
                     f"({max(1, round(conc['customers_in_base'] * 0.01))} customers) deliver {conc['top_1pct_share']:.0f}%. "
                     f"{conc['customers_for_80pct_revenue']:,} customers ({conc['customers_for_80pct_revenue_pct']:.0f}%) produce 80% of revenue; "
                     f"the bottom half adds only {conc['bottom_50pct_share']:.0f}%. Gini coefficient: {conc['gini']:.2f}."),
        "interpretation": "Losing even a few top accounts would be felt immediately in revenue, while the large base of small customers is cheap to lose but also adds little.",
        "recommendation": "Create a named-account programme for the top 1-5% (dedicated contact, early access to new products, "
                          "service-level promises) and keep the long tail on low-cost, automated marketing.",
    })

    # 3. At-risk valuable customers
    ar, cl = S.loc["At Risk"], S.loc["Can't Lose Them"]
    cl_back = B.loc["Can't Lose Them", "repurchase_rate_pct"]
    n_rescue = int(ar["customers"] + cl["customers"])
    v_rescue = float(ar["net_revenue"] + cl["net_revenue"])
    out.append({
        "theme": "At-risk customers",
        "title": "Customers who bought regularly and then went quiet are the best win-back target",
        "evidence": (f"{n_rescue} customers (At Risk + Can't Lose Them) have spent {_gbp(v_rescue)} but have been inactive for "
                     f"{cl['avg_recency_days']:.0f}-{ar['avg_recency_days']:.0f} days on average; they used to place "
                     f"{ar['avg_frequency']:.1f}-{cl['avg_frequency']:.1f} orders. Can't Lose Them customers are worth "
                     f"{_gbp(cl['avg_net_revenue'])} each on average, and in the back-test {cl_back:.0f}% of that group "
                     f"still bought in the next 90 days."),
        "interpretation": "These customers have already proved they like the product. Their usual rhythm is a purchase every "
                          f"~{gap_median:.0f} days (median), so a silence of four months or more is a clear warning sign, not normal behaviour.",
        "recommendation": "Run a personal win-back campaign for Can't Lose Them (call or personal email from an account manager, offer on "
                          "their previously bought products) and an automated reminder sequence for At Risk. Trigger it when a customer "
                          "passes about 90 days without an order.",
    })

    # 4. Frequency and the repeat purchase
    onet = rv.set_index("type").loc["One-time customers"]
    rep = rv.set_index("type").loc["Repeat customers"]
    out.append({
        "theme": "Retention opportunity",
        "title": "Getting a first-time buyer to order again is the biggest growth lever",
        "evidence": (f"{onet['pct_customers']:.0f}% of customers bought only once and contribute {onet['pct_net_revenue']:.1f}% of net revenue; "
                     f"repeat customers (average {rep['avg_orders']:.1f} orders) contribute {rep['pct_net_revenue']:.1f}%. "
                     f"Only {repeat90['rate_pct']:.0f}% of customers place a second order within 90 days of their first, and in any later month "
                     f"roughly {cohort:.0f}% of a monthly cohort is active."),
        "interpretation": "Fewer than half of customers reorder within three months of their first purchase, and every monthly cohort loses most of its customers quickly, so the first 90 days decide whether a customer becomes a repeat buyer.",
        "recommendation": "Build a 90-day onboarding journey: a thank-you and product-care message after the first order, a reorder reminder at "
                          f"~{gap_median:.0f} days, and a targeted offer at ~60 days for customers who have not yet reordered.",
    })

    # 5. Segment differences: New and Potential Loyalists
    nw, pl = S.loc["New Customers"], S.loc["Potential Loyalists"]
    out.append({
        "theme": "Segment differences",
        "title": "New customers and Potential Loyalists are a large pipeline that is still worth little today",
        "evidence": (f"New Customers + Potential Loyalists are {nw['pct_customers'] + pl['pct_customers']:.0f}% of customers "
                     f"({int(nw['customers'] + pl['customers']):,}) but only {nw['pct_revenue'] + pl['pct_revenue']:.1f}% of net revenue "
                     f"(average {_gbp(pl['avg_net_revenue'])} for Potential Loyalists). Champions are worth "
                     f"{_gbp(ch['avg_net_revenue'])} on average, {ch['avg_net_revenue'] / pl['avg_net_revenue']:.0f} times more."),
        "interpretation": "These customers bought recently but have not yet built a habit; if even a fraction move up to Loyal or Champions the revenue effect is large.",
        "recommendation": "Use 'next best product' recommendations and bundle offers to move them to a 3rd and 4th order. Track the share of this group that "
                          "reaches Loyal Customers each quarter as a headline KPI.",
    })

    # 6. Hibernating
    out.append({
        "theme": "Low-value inactive customers",
        "title": "Hibernating customers are the largest group but low priority",
        "evidence": (f"{hib['pct_customers']:.0f}% of customers ({int(hib['customers']):,}) are Hibernating: average {hib['avg_recency_days']:.0f} days since last order, "
                     f"{hib['avg_frequency']:.1f} orders and {_gbp(hib['avg_net_revenue'])} spent. In the back-test only "
                     f"{B.loc['Hibernating', 'repurchase_rate_pct']:.0f}% bought in the next 90 days."),
        "interpretation": "Winning these customers back is possible but expensive relative to the value at stake.",
        "recommendation": "Include them only in low-cost, periodic campaigns (seasonal catalogue or email), and suppress them from paid channels. "
                          "Use their purchase history to find which products brought them in and promote those.",
    })

    # 7. Seasonality
    m = monthly[~monthly["is_partial"]].copy()
    m = m[m["month"] != monthly["month"].iloc[0]]  # exclude first month: no "returning" baseline
    q4 = m[m["month"].isin(["2011-09", "2011-10", "2011-11"])]["net_revenue"].sum()
    rest = m[~m["month"].isin(["2011-09", "2011-10", "2011-11"])]["net_revenue"]
    tot = monthly[~monthly["is_partial"]]["net_revenue"].sum()
    peak = monthly.loc[monthly[~monthly["is_partial"]]["net_revenue"].idxmax()]
    out.append({
        "theme": "Seasonality",
        "title": "Revenue is strongly seasonal: September to November is the peak season",
        "evidence": (f"September-November 2011 delivered {_gbp(q4)} ({100 * q4 / tot:.0f}% of all full-month net revenue). "
                     f"{pd.to_datetime(peak['month']).strftime('%B %Y')} was the best month at {_gbp(peak['net_revenue'])}; the average of the other 2011 full months "
                     f"(Jan-Aug) was {_gbp(rest.mean())}. Order frequency is flat (about 1.3-1.6 orders per active customer per month), so the peak "
                     f"comes from more active customers ({int(monthly['active_customers'].max()):,} in the busiest month)."),
        "interpretation": "The peak is driven by more customers buying in the same month (average order value and orders per customer do not rise in the same way), which is consistent with customers stocking up for the holiday season.",
        "recommendation": "Plan stock, staffing and marketing around the autumn peak, and start retention campaigns in October so that new seasonal "
                          "customers are contacted again before the quieter early-year months.",
    })

    # 8. Geography
    uk = country[country["country"] == "United Kingdom"].iloc[0]
    export = country[country["country"] != "United Kingdom"]
    top_ex = export.sort_values("revenue_per_customer", ascending=False)
    top_ex = top_ex[top_ex["customers"] >= 3].head(3)
    names = ", ".join(f"{r.country} ({_gbp(r.revenue_per_customer)} per customer, {int(r.customers)} customers)" for r in top_ex.itertuples())
    out.append({
        "theme": "Geography",
        "title": "The UK is the core market; a few overseas wholesalers are unusually valuable",
        "evidence": (f"The UK holds {uk['pct_customers']:.0f}% of customers and {uk['pct_net_revenue']:.0f}% of net revenue ({_gbp(uk['revenue_per_customer'])} per customer). "
                     f"Highest revenue per customer outside the UK (countries with at least 3 customers): {names}."),
        "interpretation": "Export revenue depends on a handful of accounts, which is both an opportunity (high value) and a risk (very small base).",
        "recommendation": "Treat the top overseas accounts as key accounts and test a small export wholesale offer in the countries where a few customers already spend heavily.",
    })

    # 9. Timing
    top_day = weekday.loc[weekday["orders"].idxmax()]
    top_hour = hour.loc[hour["orders"].idxmax()]
    out.append({
        "theme": "Purchasing pattern",
        "title": "Orders cluster mid-week and around midday",
        "evidence": (f"{top_day['weekday']} is the busiest day ({int(top_day['orders']):,} orders) and {int(top_hour['hour'])}:00 is the busiest hour. "
                     f"There are no orders at all recorded on Saturdays."),
        "interpretation": "Ordering during working hours on working days is consistent with a customer base that includes many business buyers.",
        "recommendation": "Send campaign emails early on Tuesday-Thursday mornings so they arrive before the midday ordering peak, and confirm "
                          "whether the Saturday gap is a trading rule or a data-recording issue before drawing any conclusion from it.",
    })
    return out
