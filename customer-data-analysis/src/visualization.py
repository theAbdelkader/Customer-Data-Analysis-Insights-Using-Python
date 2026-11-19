"""
Charts for the customer analysis. One function per chart; every function saves a PNG and returns its path.

Design rules (validated palette, light surface):
* one categorical colour per segment, always in the same order, so a segment keeps its colour in every chart
* single-series charts use the first palette colour; magnitude heatmaps use one blue ramp
* direct value labels instead of legends wherever possible; light grid; no dual axes
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

# ---- palette (validated with the dataviz validator: all checks pass, light surface #fcfcfb) ------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, GREEN, AMBER, PINK, DKGREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")

SEGMENT_COLORS = {
    "Champions": BLUE, "Loyal Customers": ORANGE, "Potential Loyalists": GREEN,
    "New Customers": AMBER, "At Risk": PINK, "Can't Lose Them": DKGREEN, "Hibernating": VIOLET,
}
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#1c5cab", "#104281", "#0d366b"]
SEQ_CMAP = LinearSegmentedColormap.from_list("seq_blue", BLUE_RAMP)
PARTIAL_NOTE = "Dec 2011 is incomplete (data ends 9 Dec)"
SOURCE = "Source: UCI Online Retail dataset (cleaned), 1 Dec 2010 - 9 Dec 2011"


def _setup_style() -> None:
    names = {f.name for f in font_manager.fontManager.ttflist}
    family = "Inter" if "Inter" in names else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": family, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "text.color": INK, "axes.labelcolor": INK2,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": AXIS,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
        "axes.grid": False, "font.size": 10.5, "axes.titlesize": 10.5, "legend.frameon": False,
    })


_setup_style()


# ---- helpers -----------------------------------------------------------------------------------
def _gbp(x, _pos=None) -> str:
    if abs(x) >= 1e6:
        return f"£{x / 1e6:.1f}M"
    if abs(x) >= 1e4:
        return f"£{x / 1e3:.0f}k"
    if abs(x) >= 1e3:
        return f"£{x / 1e3:.1f}k"
    return f"£{x:.0f}"


def _title(fig, title: str, subtitle: str | None = None, top: float = 0.965) -> None:
    fig.text(0.012, top, title, fontsize=15, fontweight="bold", color=INK, ha="left", va="top")
    if subtitle:
        fig.text(0.012, top - 0.058, subtitle, fontsize=10.5, color=INK2, ha="left", va="top")


def _footer(fig, note: str | None = None) -> None:
    txt = SOURCE + (f". {note}" if note else "")
    fig.text(0.012, 0.012, txt, fontsize=8, color=MUTED, ha="left", va="bottom")


def _hgrid(ax, axis="y") -> None:
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left" if axis == "y" else "bottom"].set_visible(False)


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path


def _new(w=11, h=6.2, top=0.80, bottom=0.15, left=0.08, right=0.97):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([left, bottom, right - left, top - bottom])
    return fig, ax


# ---- 1. revenue trend --------------------------------------------------------------------------
def monthly_revenue(m: pd.DataFrame, out: Path) -> Path:
    fig, ax = _new()
    x = np.arange(len(m))
    colors = [BLUE] * len(m)
    bars = ax.bar(x, m["net_revenue"], color=colors, width=0.68)
    for b, partial in zip(bars, m["is_partial"]):
        if partial:
            b.set_alpha(0.45)
            b.set_hatch("///")
            b.set_edgecolor(BLUE)
    ax.set_xticks(x, pd.to_datetime(m["month"]).dt.strftime("%b\n%y"))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_gbp))
    _hgrid(ax)
    for i, v in enumerate(m["net_revenue"]):
        if i in (0, int(m["net_revenue"].idxmax()), int(m["net_revenue"].idxmin()), len(m) - 1):
            ax.text(i, v + m["net_revenue"].max() * 0.015, _gbp(v), ha="center", fontsize=9.5, color=INK)
    peak = m.loc[m["net_revenue"].idxmax()]
    first_full = m[~m["is_partial"]]
    summer_low = first_full.loc[first_full["net_revenue"].idxmin()]
    _title(fig, f"Revenue builds through the year and peaks in {pd.to_datetime(peak['month']).strftime('%B')}",
           f"Monthly net revenue (sales minus returns). Lowest full month: "
           f"{pd.to_datetime(summer_low['month']).strftime('%b %Y')} ({_gbp(summer_low['net_revenue'])})")
    ax.set_ylabel("Net revenue")
    _footer(fig, PARTIAL_NOTE + " (hatched)")
    return _save(fig, out, "01_monthly_revenue_trend.png")


def customers_new_vs_returning(m: pd.DataFrame, out: Path) -> Path:
    fig, ax = _new()
    x = np.arange(len(m))
    ax.bar(x, m["returning_customers"], color=BLUE, width=0.68, label="Returning customers")
    ax.bar(x, m["new_customers"], bottom=m["returning_customers"], color=ORANGE, width=0.68,
           edgecolor=SURFACE, linewidth=1.5, label="New customers")
    ax.set_xticks(x, pd.to_datetime(m["month"]).dt.strftime("%b\n%y"))
    _hgrid(ax)
    ax.set_ylabel("Active customers in month")
    for i, (r, n) in enumerate(zip(m["returning_customers"], m["new_customers"])):
        ax.text(i, r + n + 18, f"{r + n:,}", ha="center", fontsize=9, color=INK2)
    ax.legend(loc="upper left", ncols=2)
    _title(fig, "Growth is driven by returning customers, not new sign-ups",
           "Customers who purchased in each month, split by first-ever purchase month. "
           "Dec 2010 has no 'returning' bar because it is the first month of data")
    _footer(fig, PARTIAL_NOTE)
    return _save(fig, out, "02_new_vs_returning_customers.png")


# ---- 2. segmentation ---------------------------------------------------------------------------
def segment_distribution(summary: pd.DataFrame, out: Path) -> Path:
    s = summary.sort_values("customers")
    fig, ax = _new(top=0.80, left=0.17)
    ax.barh(s["segment"].astype(str), s["customers"], color=[SEGMENT_COLORS[x] for x in s["segment"]], height=0.66)
    for i, (c, p) in enumerate(zip(s["customers"], s["pct_customers"])):
        ax.text(c + s["customers"].max() * 0.012, i, f"{c:,}  ({p:.1f}%)", va="center", fontsize=10, color=INK)
    ax.set_xlim(0, s["customers"].max() * 1.22)
    ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    _hgrid(ax, "x")
    ax.tick_params(axis="y", labelcolor=INK, labelsize=11)
    top = summary.sort_values("customers", ascending=False).iloc[0]
    _title(fig, f"{top['segment']} is the largest group, with {top['pct_customers']:.0f}% of customers",
           f"Number of customers per RFM segment (n = {int(summary['customers'].sum()):,})")
    _footer(fig)
    ax.set_xlabel("Customers")
    return _save(fig, out, "03_segment_distribution.png")


def revenue_by_segment(summary: pd.DataFrame, out: Path) -> Path:
    s = summary.sort_values("net_revenue")
    fig, ax = _new(left=0.17)
    ax.barh(s["segment"].astype(str), s["net_revenue"], color=[SEGMENT_COLORS[x] for x in s["segment"]], height=0.66)
    for i, (v, p) in enumerate(zip(s["net_revenue"], s["pct_revenue"])):
        ax.text(v + s["net_revenue"].max() * 0.012, i, f"{_gbp(v)}  ({p:.1f}%)", va="center", fontsize=10, color=INK)
    ax.set_xlim(0, s["net_revenue"].max() * 1.2)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_gbp))
    _hgrid(ax, "x")
    ax.tick_params(axis="y", labelcolor=INK, labelsize=11)
    top = summary.sort_values("net_revenue", ascending=False).iloc[0]
    _title(fig, f"{top['segment']} generate {top['pct_revenue']:.0f}% of net revenue",
           "Net revenue (sales minus returns) per RFM segment, with share of total")
    ax.set_xlabel("Net revenue")
    _footer(fig)
    return _save(fig, out, "04_revenue_by_segment.png")


def customers_vs_revenue_share(summary: pd.DataFrame, out: Path) -> Path:
    s = summary.copy()
    s["segment"] = s["segment"].astype(str)
    fig, ax = _new(h=6.4, left=0.17)
    y = np.arange(len(s))[::-1]
    h = 0.36
    ax.barh(y + h / 2, s["pct_customers"], height=h, color=MUTED, label="% of customers")
    ax.barh(y - h / 2, s["pct_revenue"], height=h, color=BLUE, label="% of net revenue")
    for yi, a, b in zip(y, s["pct_customers"], s["pct_revenue"]):
        ax.text(a + 0.8, yi + h / 2, f"{a:.1f}%", va="center", fontsize=9.5, color=INK2)
        ax.text(b + 0.8, yi - h / 2, f"{b:.1f}%", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(y, s["segment"])
    ax.tick_params(axis="y", labelcolor=INK, labelsize=11)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(0, max(s["pct_revenue"].max(), s["pct_customers"].max()) * 1.15)
    _hgrid(ax, "x")
    ax.legend(loc="lower right")
    _title(fig, "A quarter of customers, two-thirds of revenue",
           "Share of customers versus share of net revenue by segment. Where the blue bar is longer, "
           "a segment earns more than its headcount")
    _footer(fig)
    return _save(fig, out, "05_customer_vs_revenue_share.png")


# ---- 3. RFM analysis ---------------------------------------------------------------------------
def rfm_heatmap(seg: pd.DataFrame, out: Path) -> Path:
    piv_n = seg.pivot_table(index="R_score", columns="F_score", values="CustomerID", aggfunc="count").fillna(0)
    piv_m = seg.pivot_table(index="R_score", columns="F_score", values="net_revenue", aggfunc="mean")
    fig = plt.figure(figsize=(12.5, 6.4))
    axes = [fig.add_axes([0.06, 0.12, 0.40, 0.66]), fig.add_axes([0.56, 0.12, 0.40, 0.66])]
    for ax, piv, fmt, label in ((axes[0], piv_n, "{:,.0f}", "Customers"),
                                (axes[1], piv_m, _gbp, "Average net revenue per customer")):
        vals = piv.reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5])
        norm = (vals - np.nanmin(vals.values)) / (np.nanmax(vals.values) - np.nanmin(vals.values))
        ax.imshow(norm.values, cmap=SEQ_CMAP, aspect="auto", vmin=0, vmax=1)
        for i in range(5):
            for j in range(5):
                v = vals.values[i, j]
                if np.isnan(v):
                    continue
                txt = fmt.format(v) if isinstance(fmt, str) else fmt(v)
                ax.text(j, i, txt, ha="center", va="center", fontsize=10.5,
                        color="white" if norm.values[i, j] > 0.45 else INK)
        ax.set_xticks(range(5), [1, 2, 3, 4, 5])
        ax.set_yticks(range(5), [5, 4, 3, 2, 1])
        ax.set_xlabel("Frequency score (5 = buys most often)")
        ax.set_ylabel("Recency score (5 = bought most recently)")
        ax.set_title(label, loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=8)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
    _title(fig, "Value sits where customers are both recent and frequent",
           "Recency x Frequency score grid. Left: how many customers; right: how much each is worth")
    _footer(fig)
    return _save(fig, out, "06_rfm_heatmap.png")


def rfm_distributions(cust: pd.DataFrame, out: Path) -> Path:
    fig = plt.figure(figsize=(12.5, 5.4))
    specs = [("recency_days", "Recency (days since last purchase)", False),
             ("frequency", "Frequency (number of orders)", True),
             ("net_revenue", "Monetary (net spend, £)", True)]
    for i, (col, label, log) in enumerate(specs):
        ax = fig.add_axes([0.05 + i * 0.32, 0.14, 0.27, 0.62])
        vals = cust[col].clip(lower=1e-9)
        if log:
            bins = np.logspace(np.log10(vals.min()), np.log10(vals.max()), 36)
            ax.set_xscale("log")
        else:
            bins = 36
        ax.hist(vals, bins=bins, color=BLUE, edgecolor=SURFACE, linewidth=0.6)
        med = cust[col].median()
        ax.axvline(med, color=ORANGE, linewidth=2)
        ax.text(med, ax.get_ylim()[1] * 0.96, f" median {med:,.0f}", color=INK, fontsize=9.5, va="top")
        ax.set_xlabel(label + (" - log scale" if log else ""))
        _hgrid(ax)
        if i == 0:
            ax.set_ylabel("Customers")
    _title(fig, "Most customers are recent or modest, a few are extreme",
           "Distribution of the three RFM measures (frequency and spend use a log axis because of the long tail)")
    _footer(fig)
    return _save(fig, out, "07_rfm_distributions.png")


def top_customers_chart(top: pd.DataFrame, out: Path) -> Path:
    t = top.sort_values("net_revenue")
    fig, ax = _new(h=6.4, left=0.21)
    labels = [f"{int(c)}  ({co})" for c, co in zip(t["CustomerID"], t["country"])]
    colors = [SEGMENT_COLORS[str(s)] for s in t["segment"]]
    ax.barh(labels, t["net_revenue"], color=colors, height=0.66)
    for i, (v, p, f) in enumerate(zip(t["net_revenue"], t["share_of_net_revenue_pct"], t["frequency"])):
        ax.text(v + t["net_revenue"].max() * 0.012, i, f"{_gbp(v)}  |  {p:.1f}% of revenue  |  {int(f)} orders",
                va="center", fontsize=9.5, color=INK)
    ax.set_xlim(0, t["net_revenue"].max() * 1.5)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_gbp))
    _hgrid(ax, "x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlabel("Net revenue")
    present = [s for s in SEGMENT_COLORS if s in set(t["segment"].astype(str))]
    ax.legend(handles=[Patch(color=SEGMENT_COLORS[s], label=s) for s in present], loc="lower right", title="Segment")
    share = t["share_of_net_revenue_pct"].sum()
    _title(fig, f"The top 10 customers account for {share:.0f}% of net revenue",
           "Customer ID (country), coloured by RFM segment")
    _footer(fig)
    return _save(fig, out, "08_top10_customers.png")


# ---- 4. repeat behaviour -----------------------------------------------------------------------
def repeat_vs_onetime_chart(rv: pd.DataFrame, out: Path) -> Path:
    fig, ax = _new(h=5.2, top=0.77, left=0.12, bottom=0.2)
    cats = ["Customers", "Net revenue"]
    rep = rv.set_index("type").loc["Repeat customers"]
    one = rv.set_index("type").loc["One-time customers"]
    rep_v = [rep["pct_customers"], rep["pct_net_revenue"]]
    one_v = [one["pct_customers"], one["pct_net_revenue"]]
    y = [1, 0]
    ax.barh(y, rep_v, color=BLUE, height=0.55, label="Repeat customers (2+ orders)")
    ax.barh(y, one_v, left=rep_v, color=ORANGE, height=0.55, edgecolor=SURFACE, linewidth=2,
            label="One-time customers")
    for yi, a, b in zip(y, rep_v, one_v):
        ax.text(a / 2, yi, f"{a:.1f}%", color="white", ha="center", va="center", fontsize=12, fontweight="bold")
        ax.text(a + b / 2, yi, f"{b:.1f}%", color=INK, ha="center", va="center", fontsize=12, fontweight="bold")
    ax.set_yticks(y, cats)
    ax.tick_params(axis="y", labelsize=11.5, labelcolor=INK)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.spines["left"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncols=2)
    _title(fig, f"{rep['pct_customers']:.0f}% of customers repeat, and they bring {rep['pct_net_revenue']:.0f}% of revenue",
           f"Share of customers and of net revenue: repeat vs one-time (n = {int(rv['customers'].sum()):,})")
    _footer(fig)
    return _save(fig, out, "09_repeat_vs_onetime.png")


def purchase_frequency_chart(fd: pd.DataFrame, out: Path) -> Path:
    fig, ax = _new()
    x = np.arange(len(fd))
    ax.bar(x, fd["customers"], color=BLUE, width=0.7)
    for i, (c, p) in enumerate(zip(fd["customers"], fd["pct_customers"])):
        ax.text(i, c + fd["customers"].max() * 0.015, f"{c:,}\n{p:.0f}%", ha="center", fontsize=9.5, color=INK)
    ax.set_xticks(x, fd["orders"].astype(str))
    ax.set_xlabel("Number of orders placed in the period")
    ax.set_ylabel("Customers")
    ax.set_ylim(0, fd["customers"].max() * 1.18)
    _hgrid(ax)
    one = fd.iloc[0]["pct_customers"]
    heavy = fd.iloc[-1]
    _title(fig, f"{one:.0f}% bought once, while {heavy['pct_customers']:.1f}% placed 20+ orders",
           f"Customers by number of orders; the 20+ group alone brings {heavy['pct_net_revenue']:.0f}% of net revenue")
    _footer(fig)
    return _save(fig, out, "10_purchase_frequency.png")


def purchase_gap_chart(gaps: pd.Series, out: Path) -> Path:
    fig, ax = _new()
    g = gaps.clip(upper=180)
    ax.hist(g, bins=np.arange(0, 186, 6), color=BLUE, edgecolor=SURFACE, linewidth=0.6)
    med = float(gaps.median())
    ax.axvline(med, color=ORANGE, linewidth=2)
    ax.text(med + 2, ax.get_ylim()[1] * 0.95, f"median {med:.0f} days", fontsize=10.5, va="top", color=INK)
    ax.set_xlabel("Days between two purchase days of the same customer (180 = 180 or more)")
    ax.set_ylabel("Purchase gaps")
    _hgrid(ax)
    within = 100 * (gaps <= 60).mean()
    _title(fig, f"Half of repeat purchases come within {med:.0f} days of the previous one",
           f"{within:.0f}% of gaps are 60 days or shorter, so 60-90 days of silence is a sensible early-warning line")
    _footer(fig)
    return _save(fig, out, "11_days_between_purchases.png")


# ---- 5. concentration and retention -------------------------------------------------------------
def pareto_chart(curve: pd.DataFrame, summary: dict, out: Path) -> Path:
    fig, ax = _new(w=9.5, h=6.6, left=0.1, right=0.95)
    ax.plot(curve["cum_customer_pct"], curve["cum_revenue_pct"], color=BLUE, linewidth=2.4)
    ax.plot([0, 100], [0, 100], color=MUTED, linewidth=1.2, linestyle=(0, (4, 4)))
    ax.text(62, 54, "equal share line", color=MUTED, fontsize=9.5, rotation=34)
    for x, key in ((10, "top_10pct_share"), (20, "top_20pct_share")):
        y = summary[key]
        ax.scatter([x], [y], color=ORANGE, zorder=5, s=55, edgecolor=SURFACE, linewidth=1.5)
        ax.text(x + 2, y - 5, f"top {x}% of customers = {y:.0f}% of revenue", fontsize=10, color=INK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlabel("Cumulative share of customers (best customers first)")
    ax.set_ylabel("Cumulative share of net revenue")
    _hgrid(ax)
    _title(fig, f"Revenue is concentrated: the top 20% of customers earn {summary['top_20pct_share']:.0f}%",
           f"Customer revenue concentration curve (Gini coefficient {summary['gini']:.2f}; 0 = equal, 1 = one customer)")
    _footer(fig)
    return _save(fig, out, "12_revenue_concentration.png")


def cohort_heatmap(ret: pd.DataFrame, sizes: pd.DataFrame, out: Path) -> Path:
    fig = plt.figure(figsize=(12.5, 6.8))
    ax = fig.add_axes([0.13, 0.10, 0.80, 0.68])
    vals = ret.values
    ax.imshow(np.where(np.isnan(vals), np.nan, vals), cmap=SEQ_CMAP, vmin=0, vmax=45, aspect="auto")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if not np.isnan(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:.0f}", ha="center", va="center", fontsize=9.5,
                        color="white" if vals[i, j] > 24 else INK)
    ylabels = [f"{pd.Period(c).strftime('%b %y')}  (n={int(n):,})" for c, n in zip(ret.index, sizes["cohort_size"])]
    ax.set_yticks(range(len(ylabels)), ylabels)
    ax.set_xticks(range(vals.shape[1]), [f"M+{k}" for k in ret.columns])
    ax.set_xlabel("Months since first purchase (% of the cohort that purchased again in that month)")
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    _title(fig, "Roughly 1 in 5 new customers is active again in any later month",
           "Monthly cohort retention. The Dec 2010 cohort contains every customer already active when the data starts, so it looks stronger")
    _footer(fig, "Dec 2011 excluded (incomplete)")
    return _save(fig, out, "13_cohort_retention.png")


# ---- 6. patterns, geography, validation ----------------------------------------------------------
def weekday_hour_chart(wd: pd.DataFrame, hr: pd.DataFrame, out: Path) -> Path:
    fig = plt.figure(figsize=(12.5, 5.6))
    ax1 = fig.add_axes([0.06, 0.14, 0.40, 0.62])
    ax2 = fig.add_axes([0.56, 0.14, 0.40, 0.62])
    ax1.bar(wd["weekday"].str[:3], wd["orders"], color=BLUE, width=0.65)
    for i, v in enumerate(wd["orders"]):
        ax1.text(i, v + wd["orders"].max() * 0.015, f"{int(v):,}", ha="center", fontsize=9.5, color=INK if v else MUTED)
    ax1.set_title("Orders by weekday", loc="left", fontsize=11.5, fontweight="bold", color=INK)
    ax1.set_ylim(0, wd["orders"].max() * 1.15)
    _hgrid(ax1)
    ax2.bar(hr["hour"], hr["orders"], color=BLUE, width=0.72)
    ax2.set_title("Orders by hour of day", loc="left", fontsize=11.5, fontweight="bold", color=INK)
    ax2.set_xlabel("Hour (24h)")
    _hgrid(ax2)
    ax2.set_xticks(range(int(hr["hour"].min()), int(hr["hour"].max()) + 1, 2))
    peak_day = wd.loc[wd["orders"].idxmax(), "weekday"]
    peak_h = int(hr.loc[hr["orders"].idxmax(), "hour"])
    _title(fig, f"Customers order mid-week and around midday: {peak_day} and {peak_h}:00 peak",
           "Number of orders (invoices). The data contains no Saturday invoices")
    _footer(fig)
    return _save(fig, out, "14_weekday_hour_patterns.png")


def country_chart(cs: pd.DataFrame, out: Path, top_n: int = 10) -> Path:
    t = cs.head(top_n).sort_values("net_revenue")
    fig, ax = _new(h=6.4, left=0.15)
    ax.barh(t["country"], t["net_revenue"], color=BLUE, height=0.66)
    for i, (v, p, c) in enumerate(zip(t["net_revenue"], t["pct_net_revenue"], t["customers"])):
        ax.text(v + t["net_revenue"].max() * 0.01, i, f"{_gbp(v)}  ({p:.1f}%)  |  {int(c):,} customers",
                va="center", fontsize=9.5, color=INK)
    ax.set_xlim(0, t["net_revenue"].max() * 1.42)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_gbp))
    ax.tick_params(axis="y", labelcolor=INK)
    _hgrid(ax, "x")
    uk = cs[cs["country"] == "United Kingdom"].iloc[0]
    _title(fig, f"The UK delivers {uk['pct_net_revenue']:.0f}% of revenue; export customers are few but valuable",
           f"Net revenue by country, top {top_n}. A handful of overseas wholesalers spend far more per customer than UK buyers")
    ax.set_xlabel("Net revenue")
    _footer(fig)
    return _save(fig, out, "15_revenue_by_country.png")


def backtest_chart(bt: pd.DataFrame, out: Path) -> Path:
    s = bt.copy()
    s["segment"] = s["segment"].astype(str)
    fig, ax = _new(h=6.2)
    x = np.arange(len(s))
    ax.bar(x, s["repurchase_rate_pct"], color=[SEGMENT_COLORS[v] for v in s["segment"]], width=0.68)
    for i, (r, n, f) in enumerate(zip(s["repurchase_rate_pct"], s["customers"], s["avg_future_revenue"])):
        ax.text(i, r + 1.5, f"{r:.0f}%", ha="center", fontsize=11, color=INK, fontweight="bold")
        light = s["segment"].iloc[i] in ("New Customers", "At Risk", "Potential Loyalists")
        ax.text(i, 3, f"n={int(n):,}\n{_gbp(f)}/cust", ha="center", fontsize=8.5, color=INK if light else "white")
    ax.set_xticks(x, [v.replace(" ", "\n", 1) for v in s["segment"]], fontsize=9.5)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(0, 100)
    ax.set_ylabel("Customers who purchased in the next 90 days")
    _hgrid(ax)
    cut = bt.attrs.get("cutoff")
    _title(fig, "The segments predict who comes back: Champions 84% vs Hibernating 34%".replace(
        "84%", f"{s.loc[s['segment'] == 'Champions', 'repurchase_rate_pct'].iloc[0]:.0f}%").replace(
        "34%", f"{s.loc[s['segment'] == 'Hibernating', 'repurchase_rate_pct'].iloc[0]:.0f}%"),
        "Back-test: segments built with data up to "
        f"{cut.strftime('%d %b %Y') if cut is not None else 'the cut-off'}, then compared with the following 90 days")
    _footer(fig)
    return _save(fig, out, "16_segment_backtest.png")


def order_value_chart(basket: pd.DataFrame, out: Path) -> Path:
    fig, ax = _new()
    v = basket["value"].clip(lower=1)
    bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 45)
    ax.hist(v, bins=bins, color=BLUE, edgecolor=SURFACE, linewidth=0.6)
    ax.set_xscale("log")
    med, mean = basket["value"].median(), basket["value"].mean()
    ax.axvline(med, color=ORANGE, linewidth=2)
    ax.axvline(mean, color=INK2, linewidth=1.6, linestyle=(0, (5, 3)))
    ytop = ax.get_ylim()[1]
    ax.text(med / 1.08, ytop * 0.95, f"median {_gbp(med)} ", ha="right", va="top", fontsize=10, color=INK)
    ax.text(mean * 1.08, ytop * 0.95, f" mean {_gbp(mean)}", ha="left", va="top", fontsize=10, color=INK)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_gbp))
    ax.set_xlabel("Order value (log scale)")
    ax.set_ylabel("Orders")
    _hgrid(ax)
    _title(fig, f"The typical order is {_gbp(med)}, but a few very large orders pull the average up to {_gbp(mean)}",
           "Distribution of order (invoice) value before returns")
    _footer(fig)
    return _save(fig, out, "17_order_value_distribution.png")
