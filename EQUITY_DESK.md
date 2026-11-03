# Equity research data desk

Use Python 3. Run commands from this project folder.

```bash
.venv/bin/python -m pip install -r requirements-equity.txt
.venv/bin/python equity_desk.py MSFT --peers AAPL GOOGL --price 400
.venv/bin/python equity_desk.py MSFT --step 4
```

The price above is an example input, not a market quote. Supply a price in USD per share. Peer tickers can be separated by spaces or commas. `--step` accepts 1 through 7. It prints and executes only the requested step, fetching and saving required inputs as needed. Each invocation creates its own run folder.

The program reads `SEC_USER_AGENT` from `.env` beside the script using python-dotenv. It sends that header on every SEC request. It does not use, print, or save API keys. It does not change `.env`. Requests are spaced by at least 0.2 seconds; transient errors have bounded retries.

## Steps and outputs

1. Resolve the supplied ticker using SEC company_tickers.json.
2. Read recent submissions and, when necessary, older submission files. Select the latest 10-K, 10-Q, and 8-K whose primary document contains Item 2.02. Read Accepted directly from each EDGAR index page, preserving its displayed time. Save the examined filing list, selected accessions, document URLs, and index times in filings.json.
3. Save plain text for the three primary documents and the selected 8-K's Exhibit 99.1. Preserve table rows and remove hidden inline XBRL metadata. If Exhibit 99.1 is absent, report it; do not silently substitute another exhibit or an older release.
4. Save raw companyfacts JSON and facts.json. Select annual US-GAAP facts in USD (USD/share for EPS). For revenue, inspect the annual filing income-statement labels and inline XBRL. Require a consolidated, non-dimensional total-revenue row, or a net-sales row with an explicit inclusive definition (merchandise sales plus other revenues). Match its tag, scaled USD value, period, and accession to companyfacts. Save the HTML and evidence JSON. Do not infer total revenue from the newest tag or largest value. Other concepts rank candidate tags by newest annual period end, with configured preference only breaking ties. Revenue defines the current and prior periods. Match all duration facts to those exact starts and ends; match balance-sheet facts to those ends. Use the latest filed observation for each matching period. Each value includes its tag, unit, accession, filing date, and period. The SEC `fy` field can describe the filing year rather than a comparative value's year, so it is not used to align values.
5. Save calculations.json and print substituted arithmetic: revenue growth, operating margin, net income divided by average opening/closing equity, noncurrent long-term debt plus its current portion divided by closing equity, operating cash flow minus PP&E additions, and supplied price divided by annual diluted EPS. Percentage results are saved as fractions. Missing values and zero denominators produce no ratio. P/E is unavailable without price and not meaningful for nonpositive EPS.
6. Save the source Exhibit 99.1 HTML, plain text, and release_lines.json. Expand HTML colspan/rowspan and assemble split month/day/year headers to associate total revenue and diluted EPS cells with duration and full date headers. Print exact source rows (cell text with pipe separators), source URL, units, and separately labelled quarterly, year-to-date, and annual values. Preserve reported GAAP versus adjusted/non-GAAP rows and column headings, and exclude percent-change columns from metric values. Resolve a bare Diluted label using the per-share section heading; exclude share-count rows. Never substitute net sales or calculate an unstated total. If no supported, unambiguous quarterly table exists, report extraction as unavailable. Prose-only releases and unsupported date/header layouts require source review.
7. Save each peer's raw company facts and peers.json. Apply the same annual selection and operating-income/revenue margin definition. Each peer uses its own latest fiscal year, which may differ from the subject company's year; periods are printed.

Files are under `research_runs/<company>_<UTC date and time>/`. Company names and CIKs come from SEC responses, with no issuer-specific branches in the program.

## Scope and validation

This version supports annual US-GAAP USD facts and HTML/plain-text filings. It reports unavailable data for unsupported taxonomies, currencies, PDF documents, and missing standard tags. It does not assume missing debt is zero, and it does not use a broader investing-cash-flow tag as capital expenditures. Annual periods must span 330–380 days, so transition periods are not treated as full years. A combined equity tag can include noncontrolling interests; the exact chosen tag is visible for review. Latest-filed comparative figures can reflect restatements, so these are not point-in-time backtest inputs.

```bash
.venv/bin/python -B -m unittest -v test_equity_desk.py test_release_parser.py test_annual_revenue.py
```

Tests cover all seven steps with synthetic SEC responses, historical submissions, Item 2.02 selection, annual/quarterly separation, newer candidate tags, restatements, period alignment, current debt, missing data, zero denominators, negative EPS, source parsing, and the User-Agent session header. A live seven-step run also completed with one peer.

Implementation follows the requested seven-step specification. The Francis–Zhang (2026) article was identified, but Section 3.1 was not accessible during development, so exact conformity to that section has not been verified. The optional Lab 03 four-role report workflow is documented in [LAB03_WORKFLOW.md](LAB03_WORKFLOW.md). Model calls require explicit `--report --model MODEL` options; the seven data steps do not make model calls.

Sources:
- SEC APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC access rules: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Francis and Zhang (2026): https://doi.org/10.1016/j.frl.2026.110127


## Debt definitions and comparability

Debt/equity uses current plus noncurrent long-term borrowings, excluding finance leases, operating leases, and standalone short-term borrowings. This scope is printed explicitly; it is not a measure of every liability or all financing obligations.

`LongTermDebtNoncurrent` and `LongTermDebtCurrent` remain distinct. The aggregate `LongTermDebt` is retained with its source label and is never used as a noncurrent fallback or added to current debt. Lease-inclusive balances and finance leases remain separate reported entries. When both corresponding amounts exist, debt-only current/noncurrent values may be calculated by subtracting finance leases from lease-inclusive balances. Inputs must have the same period end, USD unit, and filing accession. The calculated total is the sum of those two non-overlapping debt-only balances. Missing lease amounts are not assumed to be zero. Conflicting, negative, or incomplete derivations leave debt/equity unavailable with a reason.

New runs save `annual_debt_evidence_<CIK>.json`; facts contain reported labels, tags, periods, accession, source URL, contexts, custom evidence, and calculated amounts with their nested inputs and arithmetic. Custom debt/lease tags are retained as evidence but are not classified automatically. Calculated amounts carry no invented XBRL tag. Earlier runs and checklists are not rewritten.

```bash
.venv/bin/python -B -m unittest -v test_equity_desk.py test_release_parser.py test_annual_revenue.py test_debt_selection.py
```
