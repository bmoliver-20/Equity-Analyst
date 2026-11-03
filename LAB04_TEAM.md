# Lab 04: fixed graph and independent Verifier

Code decides the next node. Models supply role outputs and revision requests; they cannot change graph edges.

This implements the [complete Lab 04 instruction](https://cinderzhang.github.io/FIN67110-Fall2026/week-03/lab-04-the-team.html) with the official [LangGraph StateGraph API](https://docs.langchain.com/oss/python/langgraph/graph-api). The graph is defined, connected, compiled, and invoked in Python. The Google Gen AI SDK and its private client configuration come from `report_workflow.py`; credentials never enter graph state or saved node records. Optional external LangSmith tracing is disabled.

## Install

```bash
.venv/bin/python -m pip install -r requirements-equity.txt
```

Installed in the existing virtual environment. `pip check` found no broken requirements. No model calls or SEC downloads were made during this implementation.

## Graph and boundaries

The first pass is always:

`steps → Research Analyst → Financial Analyst → Investment Advisor → Strategy Manager → Verifier`

Each role reads its own file in `roles/`. Each model call receives exactly `task`, `context`, and `expected_output`. Research receives only the allowed Business/MD&A/release lines. Financial receives the existing Python metric registry, source definitions, and required metric IDs. Advisor receives only the two analysts' outputs. Manager receives those outputs, the Advisor output, required report sections, and automated errors. Existing Lab 03 schemas and validation are reused; the Manager schema adds a list of per-role revision requests.

The Financial output must include the available registry's input metrics as well as calculated results, so the report quotes the inputs needed to recompute ratios. A defined subtotal can be checked by addition, with its input tags retained; it is not presented as a reported XBRL tag.

Every Manager edge goes directly to Verifier, including rejection and failure paths. After the first Verifier, code may run one fixed revision sweep: Research, Financial, Advisor, Manager, Verifier. Only requested role slots make another model call. If an analyst changes, Advisor synthesis is refreshed within its two-call cap. All revision requests must fit the remaining budget. No role, including Manager or Verifier, makes more than two calls. There are no automatic SDK retries beyond the single configured attempt, no dynamic model-selected edges, and no skip-Verifier option. A second revision request is rejected. The graph's only edge to END is from Verifier.

If an upstream API/schema/data error prevents compilation, the graph still reaches the Verifier node and saves an explicit unavailable result. It does not pretend to verify a nonexistent report. If the Verifier fails, no revision sweep follows and the CLI exits unsuccessfully. Rejected Manager drafts can be checked for numbers, but do not become approved reports. Legacy Lab 03 entry points remain separate; `lab04_team.py` is the Lab 04 agent-team entry point.

## Verifier

The Verifier receives only the report with Advisor thesis blocks removed, saved filing texts, and saved facts. It never receives the human audit, test-case expected answers, analyst drafts, Manager instructions, or other roles' instruction files. It gets its own verification task and output schema. The full original report is retained in the output; excluded thesis text is neither checked nor changed.

Python performs the deterministic tag, filing-line, and ratio checks from the saved evidence before model review. The model then receives compact claim packets only: the reported number and claim, period, definition, relevant saved facts, and the cited filing line with two surrounding saved lines. It never receives a complete filing text. Packets are split below a conservative 20,000-token input budget. Each request and its completion state are saved as `semantic_batch_N_M.json`. If one batch fails, deterministic marks remain saved and only that batch's semantic review is incomplete.

Python inventories numeric occurrences. Recognized accession/URL/date/page/form references and arithmetic constants are metadata. Unaccounted-for financial occurrences become unsupported rather than silently disappearing. The model maps numbers to real sources and checks meaning, scale, period, units, quarterly versus annual/YTD, GAAP versus adjusted EPS, revenue definitions, and debt/lease scope.

Code independently enforces:

- Exact saved fact value after explicit unit scaling, exact tag identity through the selected fact ID, start/end period and accession provenance. Direct facts receive no numeric tolerance.
- Real filing lines, normalized for spacing/formatting; source values must occur in the real row. A report's forged quotation is not accepted as filing evidence. Supplemental fact quotations must come from the same accession.
- Ratio arithmetic from the report's quoted inputs, each reconciled to saved evidence. Only a small arithmetic language is allowed; no `eval`, arbitrary functions, or code execution. Ratios are rounded to the report's displayed precision. Missing definitions, ambiguous meanings, mismatched units, unsupported formulas, zero denominators, and missing inputs remain unsupported.
- Source-less numbers are unsupported even if a matching value exists. A supported correction may add the actual source when its intended meaning and period are unambiguous. No correction is supplied when evidence is insufficient.

Marks are `correct`, `wrong`, or `unsupported`. The table contains supported corrections, actual tags/periods or filing lines and URLs, arithmetic, and limitations. Python applies only supported numeric replacements in the verified copy. Narrative rewriting and the Advisor thesis are outside correction scope. A user-supplied price is labelled a saved user input, never a filing fact; its missing effective date remains explicit. Without price, P/E remains unavailable.

A completed model review is not proof that its semantic judgments are right. Model mapping, surrounding-column interpretation, and definition judgments still need the course's human review. Existing custom debt ambiguities remain unavailable. Supported evidence is never replaced by an estimate to make a test pass.

## Files and provenance

Each invocation creates a company/date/time folder under `lab04_runs/`, including verify-only invocations. It copies allowlisted public evidence and facts and records hashes in `source_manifest.json`. Saved HTML is converted locally where peer statement text is needed. It never copies `.env`, credentials, model traces from earlier runs, or human audits as verifier evidence.

Each node saves its input and output. `report.md` is the Manager draft; `verified_report.md` contains the correction table directly under the original first filings line. Per-pass reports, verifier JSON (including its actual structured model output), and `run.json` preserve both passes when a revision occurs. API failures retain sanitized categories, HTTP status, provider message, quota metric/limit/value, and retry delay when supplied. No raw request headers, credentials, or response bodies are saved. New full runs also get a blank human-audit template. Nothing writes into the source run or changes an earlier audit. The verification-only original report stays byte-for-byte intact in its source folder.

## Live commands — not run during implementation

The model below was advertised by models.list but has not passed a generation test here. Previous `gemini-2.5-flash` generation returned HTTP 404 despite being listed. Model access is a genuine live-run uncertainty. Change `--model` if a different model is confirmed for the account.

Use saved COST evidence, with no SEC downloads and no invented price:

```bash
.venv/bin/python -B lab04_team.py COST --peers WMT,TGT,BJ --saved-run research_runs/COSTCO_WHOLESALE_CORP_NEW_2026-11-02_15-14-58_161484_UTC --model models/gemini-3.8-flash
```

For the required priced course run, first set `INSTRUCTOR_PRICE` to the actual instructor-supplied number. No such price has been supplied yet. This guard prevents an empty value or invented default. Run the same command twice to check that the second run uses a new folder:

```bash
.venv/bin/python -B lab04_team.py COST --peers WMT,TGT,BJ --price "${INSTRUCTOR_PRICE:?Set this to the actual instructor price}" --saved-run research_runs/COSTCO_WHOLESALE_CORP_NEW_2026-11-02_15-14-58_161484_UTC --model models/gemini-3.8-flash
```

Omit `--saved-run` only when you intend to download a new set of SEC evidence. The original seven steps, optional peer list, and optional price then run as the steps node.

Three separate verification-test inputs are prepared under `lab04_test_cases/2026-11-03_13-22-03_647642_UTC/`:

- `eps_error`: copied COST report with annual EPS increased by exactly $1 and a matching fabricated source quotation in the report. Actual saved filings and facts are unchanged.
- `invented_growth`: another COST copy with annual growth four percentage points too high and the true annual revenue inputs quoted.
- `clean_report`: unchanged Microsoft fallback report whose eleven core human-audit claims were marked Correct by Brody Oliver on 2026-11-03. Supplemental claims have not been certified clean. Original audits and Abraham's sign-off are preserved.

These are test inputs, not verified outputs. Their expected-answer metadata never enters the Verifier.

```bash
.venv/bin/python -B lab04_team.py --verify-only lab04_test_cases/2026-11-03_13-22-03_647642_UTC/eps_error --model models/gemini-3.8-flash
.venv/bin/python -B lab04_team.py --verify-only lab04_test_cases/2026-11-03_13-22-03_647642_UTC/invented_growth --model models/gemini-3.8-flash
.venv/bin/python -B lab04_team.py --verify-only lab04_test_cases/2026-11-03_13-22-03_647642_UTC/clean_report --model models/gemini-3.8-flash
```

Verify any new team run with `--verify-only PATH_TO_SAVED_RUN`. This invokes only Verifier, never the data steps or four authoring roles. Check `verification_round_1.json` for marks grouped by core claim; absent categories are not certified correct. Your partner must check the seeded EPS mark against the real 10-K per-share line. No program fills human review or partner fields.

## Offline tests

```bash
.venv/bin/python -B -m unittest -v test_equity_desk.py test_release_parser.py test_annual_revenue.py test_debt_selection.py test_report_workflow.py test_lab04.py
```

Tests use injected model responses and blocked sockets. They cover fixed graph edges, mandatory Verifier, failed upstream calls, per-role revision limits, verifier-only mode, context boundaries, report-header preservation, no-overwrite folders, secret/audit exclusion, fabricated source lines, wrong EPS, wrong growth arithmetic, missing definitions, exact periods and scaling, ambiguous evidence, source-less claims, omitted occurrences, unsupported code execution, and clean supported numbers. Synthetic all-eleven-core checks test deterministic behavior, not actual model verification. Saved-source fixture checks also confirm the original report hashes and real EPS evidence. Live seeded-error detection and live clean-report false-positive behavior remain untested until you run the commands above.

The complete suite passed 75 tests. It includes two full mocked graph runs against saved COST evidence, with sockets blocked, separate output folders, P/E unavailable, and original source hashes preserved. These temporary test reports are explicitly labelled mocked; they are not actual model-verified reports.

## Failure preservation

Before any Verifier model call, Python checks explicit annual tables against their saved tag/fiscal-period/accession values, real filing-line quotations, and displayed arithmetic. It saves these checks to `deterministic_round_N.json` before submitting a request. These are narrow code checks, not model judgments about meaning or definition. Ambiguous source matches remain unresolved.

If the model call or schema check fails, the final verifier JSON and node output retain the completed code checks and sanitized error details. The report shows an incomplete-verification notice and the independent checks without applying unreviewed changes. `model_checks_completed` and `overall_verification_success` remain false; model-dependent marks are not manufactured. Earlier failed-run artifacts are not rewritten.

Focused offline tests: `.venv/bin/python -B -m unittest -v test_verifier_failures.py`. They use varied synthetic EPS values, mocked quota/rate-limit errors, credential/header redaction checks, and on-disk checkpoints before failure. They do not call a provider or establish live model verification.
