"""
Builds reports/analysis_report.pdf (non-technical, 10 sections) from outputs/analysis_results.json and the charts.

Run after the notebook has produced the results:
    python src/report_builder.py
"""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
VIZ = ROOT / "visualizations"
OUT = ROOT / "outputs"
REPORT = ROOT / "reports" / "analysis_report.pdf"

BLUE = colors.HexColor("#1c5cab")
INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
GRID = colors.HexColor("#d9d8d0")
BAND = colors.HexColor("#f3f2ee")
SEG_COLORS = {
    "Champions": "#2a78d6", "Loyal Customers": "#eb6834", "Potential Loyalists": "#1baf7a",
    "New Customers": "#eda100", "At Risk": "#e87ba4", "Can't Lose Them": "#008300", "Hibernating": "#6250d6",
}
CLT = "Can't Lose Them"
PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


def gbp(x: float, short: bool = False) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if short and x >= 1e6:
        return f"{sign}£{x / 1e6:.2f}M"
    if short and x >= 1e4:
        return f"{sign}£{x / 1e3:.0f}k"
    return f"{sign}£{x:,.0f}"


def make_styles() -> dict:
    ss = getSampleStyleSheet()
    s = {
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=14.5,
                               textColor=INK, spaceAfter=6, alignment=TA_LEFT),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=INK2),
        "caption": ParagraphStyle("caption", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, textColor=INK2,
                                  spaceBefore=2, spaceAfter=10),
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=BLUE,
                             spaceBefore=4, spaceAfter=10),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=INK,
                             spaceBefore=10, spaceAfter=5),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK,
                                 leftIndent=14, bulletIndent=2, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.6, leading=11, textColor=INK),
        "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.6, leading=11, textColor=INK),
        "hdr": ParagraphStyle("hdr", fontName="Helvetica-Bold", fontSize=8.6, leading=11, textColor=colors.white),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=30, leading=36, textColor=INK),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=14, leading=20, textColor=INK2),
        "kpi_v": ParagraphStyle("kpi_v", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=BLUE),
        "kpi_l": ParagraphStyle("kpi_l", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK2),
    }
    return s


def P(text, style):
    return Paragraph(text, style)


def bullets(items, st):
    return [Paragraph(t, st["bullet"], bulletText="•") for t in items]


def table(header, rows, widths, st, align_right=(), zebra=True, bold_first=False):
    data = [[P(h, st["hdr"]) for h in header]]
    for r in rows:
        data.append([P(str(c), st["cellb"] if (bold_first and i == 0) else st["cell"]) for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1, splitByRow=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if zebra:
        for i in range(2, len(data), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    t.setStyle(TableStyle(style))
    return KeepTogether([t]) if len(rows) <= 12 else t


def chart(name: str, caption: str, st, width=CONTENT_W):
    from PIL import Image as PILImage
    path = VIZ / name
    with PILImage.open(path) as im:
        w, h = im.size
    img = Image(str(path), width=width, height=width * h / w)
    return KeepTogether([img, P(caption, st["caption"])])


def kpi_cards(items, st):
    cells = [[P(v, st["kpi_v"]), ] for v, _ in items]
    row1 = [[P(v, st["kpi_v"]), P(l, st["kpi_l"])] for v, l in items]
    n = len(row1)
    data = [[[c[0], c[1]] for c in row1]]
    t = Table(data, colWidths=[CONTENT_W / n] * n)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.6, GRID),
        ("BACKGROUND", (0, 0), (-1, -1), BAND), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=2.2 * cm,
                         bottomMargin=2.0 * cm, title="Customer Data Analysis & Insights",
                         author="Data Analyst", **kw)
        frame = Frame(MARGIN, 2.0 * cm, CONTENT_W, PAGE_H - 4.2 * cm, id="f", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame]),
                               PageTemplate(id="main", frames=[frame], onPage=self._decorate)])

    @staticmethod
    def _decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(INK2)
        canvas.drawString(MARGIN, PAGE_H - 1.3 * cm, "Customer Data Analysis & Insights  |  UCI Online Retail dataset")
        canvas.drawRightString(PAGE_W - MARGIN, 1.2 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(GRID)
        canvas.line(MARGIN, PAGE_H - 1.5 * cm, PAGE_W - MARGIN, PAGE_H - 1.5 * cm)
        canvas.restoreState()


def build_report(results: dict, out_path: Path = REPORT) -> Path:
    st = make_styles()
    k = results["kpis"]
    seg = pd.DataFrame(results["segments"]).set_index("segment")
    bt = pd.DataFrame(results["backtest"]).set_index("segment")
    conc = results["concentration"]
    clog = pd.DataFrame(results["cleaning_log"])
    q = pd.DataFrame(results["quality_report"])
    insights = results["insights"]
    rv = pd.DataFrame(results["repeat_vs_onetime"]).set_index("type")
    f: list = []

    # ---------------- cover ----------------
    f += [Spacer(1, 6 * cm), P("Customer Data Analysis<br/>&amp; Insights", st["title"]), Spacer(1, 0.5 * cm),
          P("Who our customers are, how they buy, who creates the value and who we are about to lose", st["subtitle"]),
          Spacer(1, 1.2 * cm),
          P(f"Analysis period: {k['period_start']} to {k['period_end']}<br/>"
            f"Data: UCI Online Retail dataset (real transactions of a UK online gift retailer)<br/>"
            f"Tools: Python, Pandas, NumPy, Matplotlib, Excel", st["body"]),
          Spacer(1, 6 * cm),
          P("Prepared by a freelance Data Analyst. Currency: pound sterling (£). "
            "All figures are calculated from the cleaned data and can be reproduced with the accompanying notebook.", st["small"])]
    from reportlab.platypus.doctemplate import NextPageTemplate
    f += [NextPageTemplate("main"), PageBreak()]

    # ---------------- 1. executive summary ----------------
    S = seg
    f += [P("1. Executive Summary", st["h1"]),
          P(f"We analysed {k['orders']:,} orders from {k['customers']:,} customers over thirteen months. "
            f"Together they spent {gbp(k['gross_revenue'], True)}; after returns the business earned "
            f"<b>{gbp(k['net_revenue'], True)}</b> in net revenue.", st["body"]),
          kpi_cards([(f"{k['customers']:,}", "customers"), (gbp(k["net_revenue"], True), "net revenue"),
                     (f"{k['orders']:,}", "orders"), (gbp(k["avg_order_value"]), "average order value"),
                     (f"{k['repeat_rate_pct']:.0f}%", "customers who repeat")], st),
          Spacer(1, 0.3 * cm), P("What we found", st["h2"])]
    f += bullets([
        f"<b>A small group carries the business.</b> The top 10% of customers deliver {conc['top_10pct_share']:.0f}% of net revenue; "
        f"the {S.loc['Champions', 'customers']:,.0f} <i>Champions</i> ({S.loc['Champions', 'pct_customers']:.0f}% of customers) deliver "
        f"{S.loc['Champions', 'pct_revenue']:.0f}%.",
        f"<b>Value comes from repeat buying.</b> Repeat customers are {rv.loc['Repeat customers', 'pct_customers']:.0f}% of customers and bring "
        f"{rv.loc['Repeat customers', 'pct_net_revenue']:.0f}% of revenue. Champions place {S.loc['Champions', 'avg_frequency']:.1f} orders on average "
        f"versus {S.loc['Hibernating', 'avg_frequency']:.1f} for Hibernating customers, while the size of an order is similar.",
        f"<b>Valuable customers are going quiet.</b> {int(S.loc['At Risk', 'customers'] + S.loc[CLT, 'customers'])} customers who "
        f"spent {gbp(S.loc['At Risk', 'net_revenue'] + S.loc[CLT, 'net_revenue'], True)} have been inactive for about four to five months on average.",
        f"<b>Revenue is seasonal.</b> September to November delivers the largest share of the year's sales, driven by more customers rather than bigger baskets.",
        f"<b>The segmentation works.</b> In a back-test, {bt.loc['Champions', 'repurchase_rate_pct']:.0f}% of Champions bought again in the next 90 days "
        f"compared with {bt.loc['Hibernating', 'repurchase_rate_pct']:.0f}% of Hibernating customers.",
    ], st)
    f += [P("What we recommend", st["h2"])]
    f += bullets([
        "Protect the top accounts with named contacts and early access to new products.",
        "Launch a win-back programme for At Risk and Can't Lose Them customers, triggered after about 90 days without an order.",
        "Build a 90-day onboarding journey so that more first-time buyers place a second and third order.",
        "Plan stock, staffing and campaigns around the autumn peak, and keep low-value inactive customers on low-cost campaigns only.",
    ], st)
    f += [PageBreak()]

    # ---------------- 2. objectives ----------------
    f += [P("2. Project Objectives", st["h1"]),
          P("The retailer sells gifts online, to consumers and to many business buyers. Marketing budget and account-management time are limited, "
            "so the business needs to know where to spend them. This project answers five questions:", st["body"])]
    f += bullets([
        "<b>Who are our customers</b> and how many orders, how much revenue and how much per order do they generate?",
        "<b>How do they buy?</b> Over time, on which days and hours, how often, and how many come back?",
        "<b>Which customers are the most valuable</b> and how concentrated is our revenue?",
        "<b>Which customers are at risk</b> of being lost, and which new customers could become loyal?",
        "<b>What should we do about it?</b> Practical, evidence-based actions for each customer group.",
    ], st)
    f += [P("The main method is <b>RFM segmentation</b>: every customer is described by <b>R</b>ecency (how recently they bought), "
            "<b>F</b>requency (how often) and <b>M</b>onetary value (how much they spent) and placed in one of seven named groups.", st["body"]),
          Spacer(1, 0.3 * cm)]

    # ---------------- 3. dataset ----------------
    f += [P("3. Dataset Overview", st["h1"]),
          P("<b>Source.</b> Online Retail dataset, UCI Machine Learning Repository (Chen, D., 2015, DOI 10.24432/C5BW33, licence CC BY 4.0). "
            "It contains the real transactions of a UK-based online retailer that sells mainly unique all-occasion gifts; many customers are wholesalers. "
            "No data in this project is synthetic.", st["body"]),
          table(["Item", "Value"], [
              ["Rows / columns", "541,909 transaction lines / 8 columns"],
              ["Period", "1 December 2010 to 9 December 2011 (13 months; December 2011 is incomplete)"],
              ["Columns", "InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country"],
              ["Currency", "Pound sterling (£)"],
              ["Customers / countries", f"{k['customers']:,} customers with a purchase, {k['countries']} countries"],
          ], [4.2 * cm, CONTENT_W - 4.2 * cm], st, bold_first=True),
          Spacer(1, 0.3 * cm), P("Limitations to keep in mind", st["h2"])]
    f += bullets([
        "<b>No categories, demographics or channels.</b> We can analyse behaviour and products, but not age, gender or product category.",
        "<b>About 25% of rows have no customer number.</b> They cannot be linked to a person, so they are left out of the customer analysis and reported separately. "
        "(The UCI page states that the data has no missing values; the file shows otherwise.)",
        "<b>Returns cannot be linked to the original order.</b> They are netted against each customer's total spending.",
        "<b>Only 13 months of history.</b> Long-term loyalty and lifetime value cannot be measured; retention means repeat buying inside this window.",
        "<b>Wholesale mix.</b> A few customers buy very large quantities, so revenue is highly concentrated.",
    ], st)
    f += [PageBreak()]

    # ---------------- 4. cleaning ----------------
    f += [P("4. Data Cleaning Process", st["h1"]),
          P("Raw transaction data is never ready for analysis. Every raw row was placed in exactly one group, so that nothing disappears "
            "without a record and the totals can be checked against the original file.", st["body"])]
    rows = []
    for r in clog.itertuples():
        rows.append([r.description, f"{r.rows:,}", f"{r.pct_of_raw_rows:.1f}%", gbp(r.value_gbp)])
    f += [table(["What happened to the rows", "Rows", "% of file", "Value"], rows,
                [CONTENT_W - 9.2 * cm, 2.6 * cm, 2.6 * cm, 4 * cm], st),
          P("Value = quantity x unit price. Returns are negative. The last line shows that all 541,909 rows and the full original value are accounted for.", st["caption"]),
          P("Decisions and why they were taken", st["h2"])]
    f += [table(["Problem", "Decision", "Why it matters"], [
        ["Duplicate rows", "Removed exact duplicates", "Counting the same line twice would overstate revenue and order size"],
        ["Postage, fees, manual and bad-debt entries", "Excluded from customer spending", "They are not purchases of goods and would distort frequency and spend"],
        ["Zero or negative prices", "Excluded", "These are stock write-offs, not sales"],
        ["Cancelled orders (returns)", "Kept and subtracted from each customer's spend", "Customer value is what the customer really paid for"],
        ["Missing customer number", "Left out of customer analysis, reported separately", "Cannot be assigned to a customer; guessing would be wrong"],
        ["Two huge orders, cancelled at once", "Handled by netting, not deleted", "Their net value is zero; removing outliers by a statistical rule would have cut real wholesale customers"],
        ["Date format (month/day/year)", "Parsed with an explicit format", "A wrong guess would swap days and months"],
    ], [4.6 * cm, 5.0 * cm, CONTENT_W - 9.6 * cm], st)]
    qrows = [[r["check"], f"{int(r['raw_data']):,}", f"{int(r['clean_sales']):,}"] for r in q.to_dict(orient="records")]
    f += [KeepTogether([Spacer(1, 0.3 * cm), P("Before and after", st["h2"]),
                        table(["Check", "Raw data", "Clean sales"], qrows, [CONTENT_W - 7 * cm, 3.5 * cm, 3.5 * cm], st)]),
          Spacer(1, 0.6 * cm)]

    # ---------------- 5. EDA ----------------
    f += [P("5. Exploratory Data Analysis", st["h1"]),
          table(["Measure", "Value", "Comment"], [
              ["Customers", f"{k['customers']:,}", "With at least one valid purchase"],
              ["Orders", f"{k['orders']:,}", f"{k['orders_per_customer']:.1f} per customer on average, median {k['median_orders_per_customer']:.0f}"],
              ["Gross revenue", gbp(k["gross_revenue"]), "Before returns"],
              ["Returns", gbp(k["returns_value"]), f"{k['return_rate_pct']:.1f}% of gross revenue"],
              ["Net revenue", gbp(k["net_revenue"]), f"{gbp(k['net_revenue_per_customer'])} per customer"],
              ["Average order value", gbp(k["avg_order_value"]), f"Median is only {gbp(k['median_order_value'])}: a few very large orders lift the average"],
              ["Repeat customers", f"{k['repeat_customers']:,} ({k['repeat_rate_pct']:.0f}%)", f"{k['one_time_customers']:,} bought only once"],
              ["UK share", f"{k['uk_customer_share_pct']:.0f}% of customers", f"{k['uk_revenue_share_pct']:.0f}% of gross revenue"],
          ], [4.0 * cm, 4.2 * cm, CONTENT_W - 8.2 * cm], st, bold_first=True),
          Spacer(1, 0.4 * cm),
          chart("01_monthly_revenue_trend.png", "Net revenue by month. The hatched December 2011 bar covers only nine days.", st),
          chart("02_new_vs_returning_customers.png", "Active customers per month: most of the growth comes from customers who have bought before.", st),
          chart("14_weekday_hour_patterns.png", "Orders by weekday and hour of day.", st),
          chart("17_order_value_distribution.png", "Order values: the typical order is far below the average.", st),
          chart("09_repeat_vs_onetime.png", "Repeat customers are about two-thirds of customers and almost all of the revenue.", st),
          chart("10_purchase_frequency.png", "How many orders customers placed.", st),
          chart("11_days_between_purchases.png", "Time between two purchases by the same customer.", st),
          chart("12_revenue_concentration.png", "Revenue concentration curve: the further the curve bows above the diagonal, the more concentrated the revenue.", st, width=CONTENT_W * 0.78),
          chart("13_cohort_retention.png", "Retention by monthly cohort (share of each month's new customers who purchase again in later months).", st),
          chart("15_revenue_by_country.png", "Net revenue by country.", st)]
    f += [KeepTogether([P("Top products by net revenue", st["h2"]),
          table(["Product", "Description", "Net revenue", "Customers"],
                [[p["StockCode"], p["description"], gbp(p["net_revenue"]), f"{int(p['customers']):,}"] for p in results["products"][:8]],
                [2.4 * cm, CONTENT_W - 9.4 * cm, 3.6 * cm, 3.4 * cm], st)]),
          P("Products are ranked by net revenue so that a product whose largest order was cancelled does not look like a best seller.", st["caption"]),
          PageBreak()]

    # ---------------- 6. RFM methodology ----------------
    cp = pd.DataFrame(results["cut_points"]).set_index("metric")
    f += [P("6. RFM Methodology", st["h1"]),
          P("Each customer is described by three numbers, measured at the snapshot date " + results["snapshot_date"] + " (the day after the last transaction):", st["body"]),
          table(["Measure", "What it is", "Better is"], [
              ["Recency (R)", "Days since the customer's last purchase", "Lower"],
              ["Frequency (F)", "Number of separate orders in the period", "Higher"],
              ["Monetary (M)", "Net spend: purchases minus returns", "Higher"],
          ], [3.6 * cm, CONTENT_W - 7.2 * cm, 3.6 * cm], st, bold_first=True),
          Spacer(1, 0.2 * cm),
          P("<b>Scoring.</b> Each measure is turned into a score from 1 (worst) to 5 (best) using the 20th, 40th, 60th and 80th percentiles of all customers as boundaries. "
            "We use boundaries based on the data instead of fixed numbers, so the scores adapt to this business. "
            "We did not split customers into equal-size groups, because about a third of customers bought exactly once and an equal split would have separated identical customers at random.", st["body"]),
          table(["Measure", "20th", "40th", "60th", "80th"],
                [["Recency (days)"] + [f"{cp.loc['recency_days', c]:,.0f}" for c in ("p20", "p40", "p60", "p80")],
                 ["Frequency (orders)"] + [f"{cp.loc['frequency', c]:,.0f}" for c in ("p20", "p40", "p60", "p80")],
                 ["Net spend (£)"] + [f"{cp.loc['net_revenue', c]:,.0f}" for c in ("p20", "p40", "p60", "p80")]],
                [CONTENT_W - 4 * 2.6 * cm] + [2.6 * cm] * 4, st, bold_first=True),
          P(f"Example: a customer with more than {cp.loc['frequency', 'p80']:.0f} orders is above the 80th percentile for frequency and scores 5; one with a single order scores 1. For recency the scale is reversed: {cp.loc['recency_days', 'p20']:.0f} days or fewer scores 5.", st["caption"]),
          P("<b>Segments.</b> The scores are combined with a simple rule table, so anyone can read and adjust it. No customer is placed in a segment by a black-box model.", st["body"])]
    from rfm_analysis import SEGMENT_ORDER, SEGMENT_RULES
    f += [table(["Segment", "Rule (scores 1-5)"], [[s, escape(SEGMENT_RULES[s])] for s in SEGMENT_ORDER],
                [4.0 * cm, CONTENT_W - 4.0 * cm], st, bold_first=True),
          Spacer(1, 0.3 * cm),
          P(f"<b>Who is scored.</b> {results['rfm_customers']:,} customers are scored. {results['unscored_customers']} customers are not scored because their returns cancelled all their spending (net spend of zero or less); they are listed in the Excel workbook.", st["body"]),
          P("<b>Does it work? A back-test.</b> The segments were rebuilt using only data before " + results["backtest_cutoff"] +
            ", then compared with what the same customers did in the following 90 days. A useful segmentation should predict that behaviour.", st["body"]),
          chart("16_segment_backtest.png", "Share of each segment that bought again in the 90 days after the cut-off date.", st),
          PageBreak()]

    # ---------------- 7. segmentation results ----------------
    rows = []
    for name in SEGMENT_ORDER:
        r = seg.loc[name]
        rows.append([f"<font color='{SEG_COLORS[name]}'>■</font> {name}", f"{int(r['customers']):,}", f"{r['pct_customers']:.1f}%",
                     gbp(r["net_revenue"]), f"{r['pct_revenue']:.1f}%", gbp(r["avg_net_revenue"]),
                     f"{r['avg_frequency']:.1f}", f"{r['avg_recency_days']:.0f}"])
    f += [P("7. Customer Segmentation Results", st["h1"]),
          table(["Segment", "Customers", "% cust.", "Net revenue", "% rev.", "Avg spend", "Avg orders", "Avg days idle"], rows,
                [3.5 * cm, 2.1 * cm, 1.5 * cm, 2.4 * cm, 1.4 * cm, 2.0 * cm, 1.8 * cm, CONTENT_W - 14.7 * cm], st, bold_first=False),
          Spacer(1, 0.3 * cm),
          chart("03_segment_distribution.png", "Number of customers in each segment.", st),
          chart("04_revenue_by_segment.png", "Net revenue earned by each segment.", st),
          chart("05_customer_vs_revenue_share.png", "Share of customers compared with share of revenue.", st),
          chart("06_rfm_heatmap.png", "Customers and average value by recency and frequency score.", st),
          chart("07_rfm_distributions.png", "How the three RFM measures are distributed.", st),
          chart("08_top10_customers.png", "The ten most valuable customers.", st),
          PageBreak()]

    # ---------------- 8. insights ----------------
    f += [P("8. Key Business Insights", st["h1"]),
          P("Every statement below is calculated from the data in this project.", st["body"])]
    for i, it in enumerate(insights, 1):
        f += [KeepTogether([P(f"{i}. {it['title']}", st["h2"]),
                            P(f"<b>Evidence.</b> {it['evidence']}", st["body"]),
                            P(f"<b>What it means.</b> {it['interpretation']}", st["body"])])]
    f += [PageBreak()]

    # ---------------- 9. recommendations ----------------
    f += [P("9. Strategic Recommendations", st["h1"]),
          P("Actions are ordered by the revenue they protect or can unlock.", st["body"])]
    for i, it in enumerate(insights[:6], 1):
        f += [KeepTogether([P(f"{i}. {it['title']}", st["h2"]), P(it["recommendation"], st["body"])])]
    from rfm_analysis import SEGMENT_ACTIONS
    f += [KeepTogether([P("Action plan by segment", st["h2"]), table(["Segment", "Customers", "Net revenue", "Recommended action"],
                [[s, f"{int(seg.loc[s, 'customers']):,}", gbp(seg.loc[s, "net_revenue"], True), escape(SEGMENT_ACTIONS[s])] for s in SEGMENT_ORDER],
                [3.4 * cm, 2.0 * cm, 2.4 * cm, CONTENT_W - 7.8 * cm], st, bold_first=True)]),
          Spacer(1, 0.3 * cm), P("How to measure success", st["h2"])]
    f += bullets([
        f"<b>Repeat rate</b>: share of customers with 2 or more orders (today {k['repeat_rate_pct']:.0f}%).",
        f"<b>Second order within 90 days</b> of the first (today {results['repeat_within_90']['rate_pct']:.0f}%).",
        f"<b>Win-back rate</b>: share of At Risk and Can't Lose Them customers who order again within 90 days of being contacted "
        f"(back-test baseline: {bt.loc['At Risk', 'repurchase_rate_pct']:.0f}% and {bt.loc[CLT, 'repurchase_rate_pct']:.0f}% without any campaign).",
        f"<b>Movement up the ladder</b>: share of New Customers and Potential Loyalists that reach Loyal Customers or Champions each quarter.",
        f"<b>Revenue concentration</b>: share of revenue from the top 10% of customers (today {conc['top_10pct_share']:.0f}%).",
    ], st)
    f += [PageBreak()]

    # ---------------- 10. conclusion ----------------
    f += [P("10. Conclusion", st["h1"]),
          P(f"The retailer's revenue rests on a relatively small group of frequent, recent customers: {S.loc['Champions', 'pct_customers']:.0f}% of customers "
            f"deliver {S.loc['Champions', 'pct_revenue']:.0f}% of net revenue. The largest opportunities are (1) keeping that group, (2) bringing back valuable customers who have gone quiet "
            f"and (3) turning more first-time buyers into repeat buyers during their first 90 days. A back-test shows that the segments are not just labels: "
            f"they separate customers who come back from customers who do not.", st["body"]),
          P("Limitations", st["h2"])]
    f += bullets([
        "Results describe thirteen months of one retailer; seasonality is based on a single year, so the autumn peak should be confirmed with more history.",
        "RFM describes past behaviour. It does not explain <i>why</i> customers stop buying; that needs customer feedback or product-level analysis.",
        "Returns are netted at customer level, not matched to the original order, so order-level return rates are not available.",
        "Guest purchases (about a quarter of the file) are not part of the customer analysis.",
        "Segment boundaries are rule-based and can be tuned. The back-test shows they are informative, not perfect: a share of Hibernating customers still buys again.",
    ], st)
    f += [Spacer(1, 0.4 * cm), P("Deliverables", st["h2"])]
    f += bullets([
        "<b>notebooks/customer_analysis.ipynb</b> - full, reproducible analysis",
        "<b>outputs/customer_segments.csv</b> - every customer with scores, segment and recommended action",
        "<b>outputs/customer_analysis.xlsx</b> - Excel workbook with summary, segments, trends, cohorts and cleaning log",
        "<b>visualizations/</b> - 17 charts used in this report",
        "<b>src/</b> - cleaning, RFM, metrics, charts and report code",
    ], st)
    f += [P("Data source: Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 (CC BY 4.0).", st["small"])]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Doc(out_path)
    doc.build(f)
    return out_path


def main() -> int:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    path = OUT / "analysis_results.json"
    if not path.exists():
        print(f"ERROR: {path} not found - run the notebook first.")
        return 1
    results = json.loads(path.read_text(encoding="utf-8"))
    print("Written:", build_report(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
