# Customer Data Analysis & Insights Using Python

An end-to-end customer analytics project on **real retail transactions**: data cleaning with a full audit trail, exploratory analysis, **RFM segmentation** (7 segments) validated by a back-test, business insights, an Excel workbook and a non-technical PDF report.

**Tools:** Python, Pandas, NumPy, Matplotlib, Jupyter Notebook, Microsoft Excel (XlsxWriter), ReportLab (PDF)

## Business problem

An online gift retailer (UK-based, many wholesale customers) has 13 months of transactions but no view of its customers. Marketing budget and account-manager time are limited, so the business needs to know **who creates the value, who is about to leave, and which new customers could become loyal**.

## Objectives

1. Describe customer behaviour: customers, orders, revenue, average order value, purchase frequency, trends, repeat vs one-time.
2. Measure how concentrated revenue is and how well customers are retained.
3. Segment customers with RFM (Recency, Frequency, Monetary) using a transparent, justified method, and prove the segments mean something.
4. Turn the results into practical recommendations per segment.

## Dataset

**UCI Online Retail** - real transactions of a UK online gift retailer, 1 Dec 2010 - 9 Dec 2011, 541,909 rows x 8 columns, currency £.
Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 - licence **CC BY 4.0**.

* No data in this project is synthetic or fabricated.
* The CSV copy in `data/raw/` comes from a public GitHub mirror because the UCI site was not reachable from the build environment; its row count, date range, number of customers (4,372) and number of invoices (25,900) match the published UCI description, but a byte-for-byte comparison with the original `.xlsx` was not possible.
* Structure, column meanings and **limitations** (no categories/demographics, 25% of rows without a customer, returns not linked to orders, one year of history) are documented in [`data/raw/DATA_SOURCE.md`](data/raw/DATA_SOURCE.md).

## Workflow

```
raw CSV ──> inspect ──> clean (every row in exactly one bucket, reconciled) ──> customer table
        ──> EDA (KPIs, trends, patterns, repeat, Pareto, cohorts, products, countries)
        ──> RFM scoring ──> 7 segments ──> back-test ──> insights ──> CSV / Excel / JSON ──> PDF report
```

## Analytical methods

| Step | Method | Why |
|---|---|---|
| Cleaning | Each raw row gets one reason/bucket; rows **and** £ reconcile to the raw file | Nothing is dropped silently; every exclusion has a business impact figure |
| Returns | Cancellations are kept and netted against each customer's spend (`net = sales - returns`) | A customer's value is what they really paid for; two giant orders that were cancelled become £0 instead of being deleted as "outliers" |
| Customer value | Net revenue, distinct invoices as frequency, snapshot date = day after last transaction | Avoids counting invoice lines as purchases |
| RFM scores | 1-5 using the 20/40/60/80th percentile of the customers as cut-points | Identical customers get identical scores (about a third bought once, so equal-size bins would split them at random) |
| Segments | Rule table on R/F/M scores (Champions, Loyal Customers, Potential Loyalists, New Customers, At Risk, Can't Lose Them, Hibernating) | Readable and adjustable by a marketer; no black-box clustering |
| Validation | Back-test: rebuild segments with data before 11 Sep 2011, measure the next 90 days | Segments must predict behaviour |
| Concentration | Pareto/Lorenz curve, top-N shares, Gini | Shows dependence on a few customers |
| Retention | Monthly cohorts, 60/90-day second-order rate, days between purchases | Measures repeat buying inside the data window |
| Independent check | Totals recomputed from the raw file with plain filters and compared with the pipeline | Catches pipeline errors |

SQL was deliberately **not** used: the analysis needs no database or joins across tables, so Pandas is enough.

## Main findings

| Measure | Value |
|---|---|
| Customers / orders | 4,334 / 18,402 |
| Gross revenue / returns / **net revenue** | £8,737,228 / £471,751 (5.4%) / **£8,265,477** |
| Average order value (gross) / median | £474.80 / £301.65 |
| Repeat customers | 65% of customers, 94% of net revenue |
| Revenue concentration | Top 10% of customers = 60% of revenue; top 1% (43 customers) = 30%; Gini 0.71 |
| Median days between purchases | 28 |
| Second order within 90 days of the first | 47% |

| Segment | Customers | % cust. | % net revenue | Avg orders | Avg days since last order | Repurchase in next 90 days (back-test) |
|---|---:|---:|---:|---:|---:|---:|
| Champions | 1,023 | 23.7% | 67.0% | 10.7 | 13 | 84% |
| Loyal Customers | 591 | 13.7% | 12.7% | 4.5 | 39 | 65% |
| Potential Loyalists | 754 | 17.4% | 5.0% | 1.6 | 39 | 45% |
| New Customers | 236 | 5.5% | 0.9% | 1.0 | 19 | 45% |
| At Risk | 242 | 5.6% | 3.3% | 3.5 | 144 | 47% |
| Can't Lose Them | 142 | 3.3% | 4.0% | 5.9 | 122 | 68% |
| Hibernating | 1,332 | 30.8% | 7.1% | 1.3 | 209 | 34% |

Each finding in the report has evidence, business interpretation and a recommendation. In short: protect the top accounts (named contacts), run a win-back programme for At Risk / Can't Lose Them (384 customers, £603k lifetime spend), build a 90-day onboarding journey to convert first-time buyers, and plan around the September-November peak. See the full text in `reports/analysis_report.pdf` (sections 8-9).

## Visualizations

17 charts in [`visualizations/`](visualizations/), all in one consistent style with a colour-blind-checked palette; each segment keeps the same colour in every chart.

| Chart | File |
|---|---|
| Monthly revenue trend | `01_monthly_revenue_trend.png` |
| New vs returning customers | `02_new_vs_returning_customers.png` |
| Segment distribution / revenue by segment / customers vs revenue share | `03_`, `04_`, `05_` |
| RFM heatmap and distributions | `06_rfm_heatmap.png`, `07_rfm_distributions.png` |
| Top 10 customers | `08_top10_customers.png` |
| Repeat vs one-time, purchase frequency, days between purchases | `09_`, `10_`, `11_` |
| Revenue concentration (Pareto) | `12_revenue_concentration.png` |
| Cohort retention | `13_cohort_retention.png` |
| Weekday / hour patterns, country revenue, segment back-test, order value | `14_`, `15_`, `16_`, `17_` |

![Revenue by segment](visualizations/05_customer_vs_revenue_share.png)

## Install and run

Requires Python 3.10 or newer (built and tested on Python 3.13; older Python/pandas versions were not tested).

```bash
pip install -r requirements.txt

# 1. Clean the raw data (writes data/processed/*.csv and prints the reconciliation)
python src/data_cleaning.py

# 2. Run the whole analysis: open notebooks/customer_analysis.ipynb in Jupyter and choose "Run All"
#    or from the terminal:
jupyter nbconvert --to notebook --execute --inplace notebooks/customer_analysis.ipynb
#    -> creates the charts, outputs/customer_segments.csv, outputs/customer_analysis.xlsx, outputs/analysis_results.json

# 3. Build the PDF report from the results
python src/report_builder.py
```

The last notebook section runs the independent checks and stops with an error if any total does not match.
The notebook included in this repository was executed with a small custom runner (Jupyter was not installed in the build environment), so its stored outputs are real but it was not run through `nbconvert` here.

## Project structure

```
customer-data-analysis/
├── data/
│   ├── raw/
│   │   ├── online_retail_raw.csv        # original data, never modified
│   │   └── DATA_SOURCE.md               # source, licence, columns, limitations
│   └── processed/                       # regenerated by src/data_cleaning.py
│       ├── cleaned_sales.csv            # valid sale lines of known customers
│       ├── returns.csv                  # cancellations of known customers (netted)
│       ├── guest_sales.csv              # valid sales without CustomerID (context only)
│       ├── excluded_records.csv         # every excluded row with its reason
│       ├── cleaning_log.csv             # reconciliation: rows and £ per bucket
│       └── quality_report.csv           # before / after checks
├── notebooks/
│   └── customer_analysis.ipynb          # full analysis with explanations
├── src/
│   ├── data_cleaning.py                 # load, clean, validate, reconcile, save
│   ├── rfm_analysis.py                  # customer table, RFM scores, segments, back-test
│   ├── customer_metrics.py              # KPIs, trends, repeat, Pareto, cohorts, products
│   ├── visualization.py                 # the 17 charts
│   ├── insights.py                      # data-driven insights and recommendations
│   ├── excel_export.py                  # Excel workbook
│   └── report_builder.py                # PDF report
├── outputs/
│   ├── customer_segments.csv            # every customer: scores, segment, recommended action
│   ├── segment_summary.csv
│   ├── customer_analysis.xlsx           # summary, segments, trends, cohorts, top customers, cleaning log ...
│   └── analysis_results.json            # numbers used by the report
├── reports/
│   └── analysis_report.pdf              # 10-section report for non-technical readers
├── visualizations/                      # 17 PNG charts
├── requirements.txt
└── README.md
```

## Assumptions and limitations

* Rows without `CustomerID` (24% of raw rows, £1.51M of sale value) are excluded from customer analysis; they are reported in the cleaning log.
* Exact duplicate rows are removed (5,268). Some may be genuine repeated scans of the same item, so this is a judgement; its impact is £21,741 (0.2% of raw value).
* Returns cannot be matched to the original order, so they are netted at customer level, and average order value is shown before returns.
* 14 customers whose returns cancelled all their spending are not scored.
* Only 13 months of data: seasonality rests on one year, and "retention" means repeat buying inside this window, not lifetime value.
* December 2011 is incomplete (data ends 9 Dec) and is flagged in the charts.
* No Saturday orders appear in the data; whether this is a trading rule or a recording gap is unknown.
* Segment rules are a modelling choice; the back-test shows they are informative, not perfect (34% of Hibernating customers still bought in the next 90 days).
* Excel values are calculated in Python and written to the workbook (they are not live formulas).
