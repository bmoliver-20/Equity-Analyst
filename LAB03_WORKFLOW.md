# Lab 03 four-role report workflow

This workflow extends the existing seven steps. It does not replace the saved definitions, evidence, or calculator. No live model call has been used to build or test it. Gemini access has not yet been tested against a live model.

## Install and first live run

```bash
.venv/bin/python -m pip install -r requirements-equity.txt
.venv/bin/python -B equity_desk.py COST --peers WMT,TGT,BJ --report --model gemini-2.5-flash
```

The second command makes live Gemini API calls; it is not a dry run. The model name is configurable and must be available to your Gemini account. The command deliberately omits price until the required price is supplied. P/E and price-based valuation remain unavailable. Once the instructor confirms the price and effective date, supply its numeric value with `--price`; record the effective date in the human audit. Do not invent a price.

To generate a report from a saved run, without new SEC downloads:

```bash
.venv/bin/python -B report_workflow.py --run-folder research_runs/COST_saved_source_refresh_2026-10-28_19-52-46_526073_UTC --model gemini-2.5-flash
```

This also makes live Gemini calls. Saved source dates are retained; using a saved run does not make its filings current. The model client reads only `API_KEY` from the project's `.env` at initialization. Neither the key nor the client enters model handoffs or saved traces. SDK exceptions are reported without their original request/error content. Importing the module, preparing evidence, running `--help`, and using injected test models do not read `.env` or initialize Gemini.

## Four separate model roles

The Python Strategy Manager harness controls the allowable context and sends each role JSON with `task`, `context`, and `expected_output`. The Manager itself is a separate model call that reviews the drafts. Each SDK call is stateless; no shared chat history or browsing/function tools are supplied.

- **Research Analyst:** only numbered source lines from 10-K Item 1 (Business), Item 7 (MD&A), and the earnings release. It covers business model, competitive position, growth outlook, catalysts, and recent developments. Every claim must quote an exact supplied line and name its source ID. Unsupported section layouts stop before model calls rather than falling back to the entire filing.
- **Financial Analyst:** only a Python-built registry of annual facts, calculator results, quarterly facts/growth, and peer figures. It selects metric IDs and supplies qualitative commentary linked to those IDs. Python inserts values, definitions, source references, and arithmetic into the report. Numeric literals in free-form financial commentary are rejected. There is no model arithmetic or arbitrary code execution.
- **Investment Advisor:** only the two analyst outputs. The Financial Analyst's selected IDs are expanded with their original evidence before handoff. The Advisor supplies Buy/Hold/Sell, a thesis, limitations, references to analyst claims, and one available numeric deciding metric. No raw filing access, extra facts, or credentials are supplied. No unsupported fair-value, target-price, cheap/expensive, or upside/downside claim is accepted. Without a price, the limitation must state that valuation is unavailable. A qualitative recommendation is not a valuation estimate.
- **Strategy Manager:** analyst outputs, recommendation, required five sections, deterministic check errors, and whether a revision remains available. It checks semantic support, definitions, consistency, and completeness. It may approve, reject, or request one revision from one role. The same context boundary is used for revision. If an analyst changes, the Advisor is rerun on the updated outputs. The Manager reviews again with revision disabled. A second revision request, rejection, or unresolved deterministic error stops compilation.

A normal report uses four role calls. The maximum is seven calls: four initial calls, one analyst revision, one refreshed Advisor call, and one final Manager review. If only the Advisor is revised, the maximum is six. Provider retry attempts are limited to one. Invalid JSON/schema or API failure stops rather than running an unbounded repair loop.

The renderer, not a model, supplies the five headings: Overview; Market Positioning and Growth Outlook; Valuation Insights; Future Developments and Strategic Recommendations; Investment Recommendation. Financial evidence is included under Valuation Insights. It does not replace the source definitions with stronger conclusions.

## Evidence and arithmetic

Quarterly year-over-year growth is calculated in Python:

`(current quarterly total revenue − comparative quarterly total revenue) / comparative quarterly total revenue × 100`

The inputs must be GAAP quarterly entries with matching duration labels, year-apart dates, known units, and source rows present in the saved release text. Conflicting totals, missing inputs, unknown units, differing quarter lengths, and zero prior revenue make growth unavailable. Annual, standalone YTD, and adjusted-EPS entries are not substituted for the required quarterly claims.

The annual and peer figures retain tag, filing accession, period, definitions, and source URLs. Calculated debt keeps its input provenance. BJ's unavailable current long-term debt does not become zero. Report source lines reference the saved text, not HTML physical line numbers. Full release column headings accompany quarterly citations.

Exact quote matching and numeric-ID checks do not prove semantic entailment or the quality of a recommendation. The Manager provides a model consistency review; the required human audit remains separate. Unsupported general prose may still require human correction.

## Saved artifacts and human audit

Each report attempt uses a unique `lab03_<timestamp>` prefix inside the run folder, preserving earlier reports and data:

- `_report.md`: five-part report; filings/accessions on line 1 and UTC run time on line 2. Created only after approval and passing automated checks.
- `_audit.md`: human audit with all marks, counts, reviewer fields, and partner sign-off blank. It contains the eleven core claims, additional financial metrics, template, and recommendation checks.
- `_workflow.json`: role instructions, JSON handoffs, responses, and compilation status. No credential fields.
- `_metrics.json`: Python values, formulas, definitions, and source provenance for a successful report.

A failed attempt retains its blank audit and workflow record but no compiled report. `LAB03_HUMAN_AUDIT_TEMPLATE.md` is also provided as a blank starting template. Humans must enter Correct/Wrong/Unsupported/Missing/Not in filings, count errors (Wrong + Unsupported) and missing claims separately, and perform partner sign-off. Automated success never fills those marks.

## Offline tests

Model failures now retain a sanitized category and, when available, HTTP status in the workflow record, including the failed role attempt. Categories distinguish authentication, permission/authentication (403), quota/rate limit (429), model/resource not found (404), other API request failures, network/timeouts, SDK/local errors, empty responses, JSON parsing, and output-schema validation. A 400 alone does not establish an invalid key or unsupported model. Only allowlisted structured invalid/expired-key reasons are classified as authentication. Provider messages, headers, response bodies, and exception text are never copied into diagnostics. No automatic retry or extra revision is added.

The first live COST failure record contained zero completed calls and no error category or response. Its original cause cannot be recovered from that record. A future authorized attempt from the saved run can capture the new diagnostics without repeating SEC downloads. No diagnostic live retry has been made.

```bash
.venv/bin/python -B -m unittest -v test_equity_desk.py test_release_parser.py test_annual_revenue.py test_debt_selection.py test_report_workflow.py
```

Tests inject mocked role responses and a mocked SDK client. They cover boundaries, provenance, source-quote failures, manager approval limits, one revision, Advisor refresh, unavailable P/E, valuation restrictions, report layout, blank audit fields, sanitized API failures, quarterly growth, units, and ambiguous/adjusted/YTD exclusions.

Sources: [Lab 03](https://cinderzhang.github.io/FIN67110-Fall2026/week-02/lab-03-make-it-yours.html), [human report audit](https://cinderzhang.github.io/FIN67110-Fall2026/reference/audit-checklist.html), and [official Google Gen AI Python SDK](https://github.com/googleapis/python-genai).
