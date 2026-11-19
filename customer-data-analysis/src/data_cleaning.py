"""
Data cleaning for the UCI "Online Retail" transactions.

Every raw row is assigned to exactly ONE bucket, so the cleaning can be reconciled:

    raw rows = exact duplicates
             + non-product lines (postage, fees, manual adjustments ...)
             + zero / negative price lines (stock write-offs)
             + returns (cancellations) that are kept for netting
             + returns without a customer
             + guest sales (no CustomerID)
             + clean customer sales

Run from the project root:
    python src/data_cleaning.py
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "online_retail_raw.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

EXPECTED_COLUMNS = [
    "InvoiceNo", "StockCode", "Description", "Quantity",
    "InvoiceDate", "UnitPrice", "CustomerID", "Country",
]

# The raw file stores dates as month/day/year (checked: first number <= 12, second <= 31).
DATE_FORMAT = "%m/%d/%Y %H:%M"

# StockCodes that are services / accounting entries, not merchandise.
NON_PRODUCT_CODES = {
    "POST": "Postage",
    "DOT": "Dotcom postage",
    "M": "Manual entry",
    "C2": "Carriage",
    "D": "Discount line",
    "S": "Samples",
    "BANK CHARGES": "Bank charges",
    "AMAZONFEE": "Amazon fee",
    "CRUK": "Charity commission",
    "B": "Adjust bad debt",
    "PADS": "Placeholder item priced at 0.001",
    "ADJUST": "Adjustment",
    "ADJUST2": "Adjustment",
}

# Reasons, in the order the rules are applied (a row gets the FIRST reason that matches).
R_DUPLICATE = "exact_duplicate"
R_NON_PRODUCT = "non_product_code"
R_BAD_PRICE = "zero_or_negative_price"
R_RETURN_NO_CUSTOMER = "return_without_customer"
R_GUEST_SALE = "sale_without_customer"
KEPT_RETURN = "return_kept_for_netting"
KEPT_SALE = "clean_sale"


@dataclass
class CleaningResult:
    """All outputs of the cleaning step."""
    sales: pd.DataFrame      # clean sale lines that belong to a known customer
    returns: pd.DataFrame    # cancellation lines of known customers
    excluded: pd.DataFrame   # every row left out, with its reason
    guest_sales: pd.DataFrame  # valid sale lines without CustomerID (kept for context only)
    log: pd.DataFrame        # reconciliation table: rows and £ per bucket
    quality_report: pd.DataFrame  # before/after checks


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------
def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    """Read the raw CSV without changing any value. IDs are read as text to avoid float artefacts."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Raw data file not found: {path}")
    df = pd.read_csv(
        path,
        dtype={"InvoiceNo": "string", "StockCode": "string", "Description": "string",
               "InvoiceDate": "string", "Country": "string"},
        encoding="utf-8",
    )
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Raw file is missing columns: {missing}")
    if df.empty:
        raise ValueError("Raw file is empty")
    return df[EXPECTED_COLUMNS]


# --------------------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------------------
def _standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Type conversion and tidy text. No rows are dropped here."""
    out = df.copy()
    out["InvoiceNo"] = out["InvoiceNo"].str.strip()
    out["StockCode"] = out["StockCode"].str.strip()
    out["Description"] = out["Description"].str.strip().str.replace(r"\s+", " ", regex=True)
    out["Country"] = out["Country"].str.strip()

    parsed = pd.to_datetime(out["InvoiceDate"], format=DATE_FORMAT, errors="coerce")
    n_bad = int(parsed.isna().sum())
    if n_bad:
        raise ValueError(f"{n_bad} InvoiceDate values could not be parsed with {DATE_FORMAT}")
    out["InvoiceDate"] = parsed

    # CustomerID is stored as a float (17850.0) because of the missing values; convert to nullable integer.
    out["CustomerID"] = out["CustomerID"].astype("Int64")
    out["Revenue"] = (out["Quantity"] * out["UnitPrice"]).round(2)
    out["IsCancellation"] = out["InvoiceNo"].str.startswith("C")
    return out


def _classify(df: pd.DataFrame) -> pd.Series:
    """Return one 'bucket' label per row following the documented rule order."""
    bucket = pd.Series(KEPT_SALE, index=df.index, dtype="object")
    decided = pd.Series(False, index=df.index)

    def assign(mask: pd.Series, label: str) -> None:
        nonlocal decided
        hit = mask & ~decided
        bucket[hit] = label
        decided |= hit

    # 1. exact duplicates: all 8 original columns identical to an earlier row
    dup = df.duplicated(subset=EXPECTED_COLUMNS, keep="first")
    assign(dup, R_DUPLICATE)
    # 2. non-product lines
    assign(df["StockCode"].str.upper().isin(NON_PRODUCT_CODES.keys()), R_NON_PRODUCT)
    # 3. zero / negative price (stock write-offs, "damaged", "lost" ... never customer sales)
    assign(df["UnitPrice"] <= 0, R_BAD_PRICE)
    # 4. returns: kept only if the customer is known
    is_ret = df["IsCancellation"]
    no_cust = df["CustomerID"].isna()
    assign(is_ret & no_cust, R_RETURN_NO_CUSTOMER)
    assign(is_ret & ~no_cust, KEPT_RETURN)
    # 5. normal sale lines without a customer
    assign(~is_ret & no_cust, R_GUEST_SALE)
    return bucket


def _validate(sales: pd.DataFrame, returns: pd.DataFrame) -> None:
    """Hard checks: fail loudly instead of producing a silently wrong analysis."""
    problems = []
    if (sales["Quantity"] <= 0).any():
        problems.append("sales contain Quantity <= 0")
    if (sales["UnitPrice"] <= 0).any():
        problems.append("sales contain UnitPrice <= 0")
    if sales["CustomerID"].isna().any():
        problems.append("sales contain missing CustomerID")
    if sales["IsCancellation"].any():
        problems.append("sales contain cancellation invoices")
    if not sales["InvoiceNo"].str.fullmatch(r"\d{6}").all():
        problems.append("sales contain InvoiceNo that is not 6 digits")
    if (returns["Quantity"] >= 0).any():
        problems.append("returns contain Quantity >= 0")
    if not returns["InvoiceNo"].str.fullmatch(r"C\d{6}").all():
        problems.append("returns contain InvoiceNo not matching C + 6 digits")
    if sales.duplicated().any():
        problems.append("sales still contain duplicates")
    if problems:
        raise ValueError("Validation failed: " + "; ".join(problems))


def _build_log(std: pd.DataFrame, bucket: pd.Series) -> pd.DataFrame:
    labels = {
        R_DUPLICATE: "Exact duplicate rows removed",
        R_NON_PRODUCT: "Non-product lines (postage, fees, manual, discount, bad debt)",
        R_BAD_PRICE: "Zero / negative price lines (stock write-offs)",
        R_RETURN_NO_CUSTOMER: "Returns without a customer",
        R_GUEST_SALE: "Sales without a customer (guest)",
        KEPT_RETURN: "Returns kept (netted against customer spend)",
        KEPT_SALE: "Clean customer sales (analysis base)",
    }
    order = list(labels)
    grp = std.groupby(bucket).agg(rows=("Revenue", "size"), value_gbp=("Revenue", "sum"))
    grp = grp.reindex(order).fillna(0)
    log = grp.reset_index().rename(columns={"index": "bucket"})
    log.columns = ["bucket", "rows", "value_gbp"]
    log["description"] = log["bucket"].map(labels)
    log["rows"] = log["rows"].astype(int)
    log["value_gbp"] = log["value_gbp"].round(2)
    log["pct_of_raw_rows"] = (100 * log["rows"] / len(std)).round(2)
    total = pd.DataFrame([{
        "bucket": "TOTAL", "rows": int(log["rows"].sum()),
        "value_gbp": round(float(log["value_gbp"].sum()), 2),
        "description": "All raw rows", "pct_of_raw_rows": 100.0,
    }])
    log = pd.concat([log, total], ignore_index=True)
    if int(total["rows"].iloc[0]) != len(std):
        raise ValueError("Reconciliation failed: bucket rows do not add up to raw rows")
    return log[["bucket", "description", "rows", "pct_of_raw_rows", "value_gbp"]]


def _quality_report(raw: pd.DataFrame, std: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    def row(check, before, after):
        return {"check": check, "raw_data": before, "clean_sales": after}

    return pd.DataFrame([
        row("Rows", len(raw), len(sales)),
        row("Missing CustomerID", int(raw["CustomerID"].isna().sum()), int(sales["CustomerID"].isna().sum())),
        row("Missing Description", int(raw["Description"].isna().sum()), int(sales["Description"].isna().sum())),
        row("Exact duplicate rows", int(raw.duplicated().sum()), int(sales.duplicated().sum())),
        row("Quantity <= 0", int((raw["Quantity"] <= 0).sum()), int((sales["Quantity"] <= 0).sum())),
        row("UnitPrice <= 0", int((raw["UnitPrice"] <= 0).sum()), int((sales["UnitPrice"] <= 0).sum())),
        row("Cancellation invoices (rows)", int(std["IsCancellation"].sum()), int(sales["IsCancellation"].sum())),
        row("Unique customers", int(raw["CustomerID"].nunique()), int(sales["CustomerID"].nunique())),
        row("Unique invoices", int(raw["InvoiceNo"].nunique()), int(sales["InvoiceNo"].nunique())),
    ])


def clean_transactions(raw: pd.DataFrame) -> CleaningResult:
    """Clean the raw transactions and return all pieces needed downstream."""
    std = _standardise(raw)
    bucket = _classify(std)

    sales = std[bucket == KEPT_SALE].copy()
    returns = std[bucket == KEPT_RETURN].copy()
    guest = std[bucket == R_GUEST_SALE].copy()

    # A customer should be in one country; if the raw data has several, use the most recent one.
    latest_country = (
        sales.sort_values("InvoiceDate").groupby("CustomerID")["Country"].last()
    )
    for frame in (sales, returns):
        frame["Country"] = frame["CustomerID"].map(latest_country).fillna(frame["Country"])

    # Fill missing descriptions of product codes from the code's most common description.
    desc_map = (
        sales.dropna(subset=["Description"]).groupby("StockCode")["Description"]
        .agg(lambda s: s.mode().iloc[0])
    )
    sales["Description"] = sales["Description"].fillna(sales["StockCode"].map(desc_map))

    for frame in (sales, returns):
        frame["InvoiceMonth"] = frame["InvoiceDate"].dt.to_period("M").astype(str)
        frame["CustomerID"] = frame["CustomerID"].astype(int)
    returns["Description"] = returns["Description"].fillna(returns["StockCode"].map(desc_map))

    _validate(sales, returns)

    excluded = std[~bucket.isin([KEPT_SALE, KEPT_RETURN])].copy()
    excluded.insert(0, "exclusion_reason", bucket[excluded.index])
    log = _build_log(std, bucket)
    quality = _quality_report(raw.assign(CustomerID=raw["CustomerID"].astype("Int64")), std, sales)
    return CleaningResult(sales=sales.reset_index(drop=True), returns=returns.reset_index(drop=True),
                          excluded=excluded.reset_index(drop=True), guest_sales=guest.reset_index(drop=True),
                          log=log, quality_report=quality)


def save_outputs(result: CleaningResult, out_dir: Path = PROCESSED_DIR) -> dict[str, Path]:
    """Write all cleaned tables to data/processed/ (the raw file is never touched)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "cleaned_sales.csv": result.sales,
        "returns.csv": result.returns,
        "guest_sales.csv": result.guest_sales,
        "excluded_records.csv": result.excluded,
        "cleaning_log.csv": result.log,
        "quality_report.csv": result.quality_report,
    }
    paths = {}
    for name, frame in files.items():
        p = out_dir / name
        frame.to_csv(p, index=False, date_format="%Y-%m-%d %H:%M:%S")
        paths[name] = p
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean the Online Retail transactions.")
    parser.add_argument("--raw", type=Path, default=RAW_PATH, help="path to the raw CSV")
    parser.add_argument("--out", type=Path, default=PROCESSED_DIR, help="output folder")
    args = parser.parse_args(argv)
    try:
        raw = load_raw(args.raw)
        result = clean_transactions(raw)
        paths = save_outputs(result, args.out)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(result.log.to_string(index=False))
    print()
    print(result.quality_report.to_string(index=False))
    print("\nWritten:")
    for name, p in paths.items():
        print(f"  {p.relative_to(PROJECT_ROOT) if p.is_relative_to(PROJECT_ROOT) else p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
