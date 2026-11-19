# Data source

## Dataset
**Online Retail** - real transactions of a UK-based, registered online retailer that sells mainly
unique all-occasion gifts. Many of its customers are wholesalers.

| Item | Value |
|---|---|
| Publisher | UCI Machine Learning Repository |
| Page | https://archive.ics.uci.edu/dataset/352/online+retail |
| DOI | https://doi.org/10.24432/C5BW33 |
| Donor / citation | Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 |
| Related paper | Chen, D., Sain, S. L., & Guo, K. (2012). Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining. *Journal of Database Marketing & Customer Strategy Management*, 19(3), 197-208. |
| Licence | Creative Commons Attribution 4.0 (CC BY 4.0) - free to use, share and adapt with attribution |
| Period covered | 2010-12-01 to 2011-12-09 (transactions) |
| Currency | Pound sterling (GBP, £) |

## The file in this folder
`online_retail_raw.csv` is the **unmodified raw data**. It is never edited by any script in this
project; every cleaning step reads it and writes its results to `data/processed/`.

* Rows: **541,909** · Columns: **8**
* SHA-256: `a2f79bbd...817b05` (run `sha256sum online_retail_raw.csv` to get the full value)
* Where the copy came from: the UCI download site is not reachable from the build environment,
  so the CSV copy that ships with the public GitHub repository *databricks/Spark-The-Definitive-Guide*
  (`data/retail-data/all/online-retail-dataset.csv`) was used. Its row count, date range, number
  of customers (4,372) and number of invoices (25,900) match the numbers published for the
  UCI file. A byte-for-byte comparison with UCI's original `.xlsx` was **not** possible, so this is
  stated here rather than assumed.

## Columns
| Column | Meaning |
|---|---|
| `InvoiceNo` | 6-digit invoice number. A leading **C** means the invoice is a **cancellation / return**. A leading **A** marks three "adjust bad debt" accounting rows. |
| `StockCode` | Product code (5 digits, sometimes plus a letter). Some codes are not products (postage, fees, manual adjustments). |
| `Description` | Product name (some blank). |
| `Quantity` | Units on the line; negative on cancellations and stock adjustments. |
| `InvoiceDate` | Date and time of the invoice, text in **month/day/year hour:minute** format (checked: the first number reaches 12, the second reaches 31). |
| `UnitPrice` | Price per unit in £. |
| `CustomerID` | 5-digit customer number. **Missing on 135,080 rows (24.9%)**. |
| `Country` | Customer's country. |

## Known limitations (important for how results are read)
1. **No categories, demographics or channel.** The data has no product category, customer age/gender,
   or marketing channel, so category analysis is done on products only and no demographic segmentation is possible.
2. **Guest rows.** About 25% of rows have no `CustomerID`. They cannot be tied to a customer, so they are
   left out of all customer-level analysis (RFM, retention) but are counted and reported separately.
3. **Documentation mismatch.** The UCI page says the dataset has *no missing values*; the file in fact has
   missing `CustomerID` and `Description` values. This is documented, not hidden.
4. **Cancellations have no link to the original invoice.** A return cannot be matched to the sale it reverses,
   so returns are netted against the customer's total spend instead of being matched line by line.
5. **Partial last month.** The data stops on 9 December 2011, so December 2011 is incomplete and is flagged on trend charts.
6. **One year of history.** Only ~13 months exist, so long-run retention and lifetime value cannot be measured;
   "retention" here means repeat purchasing inside this window.
7. **Wholesale mix.** Some customers buy very large quantities. Their behaviour is real but different from a typical shopper,
   and revenue is therefore highly concentrated.
