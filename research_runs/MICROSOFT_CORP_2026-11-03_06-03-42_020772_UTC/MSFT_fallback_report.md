MICROSOFT CORP (MSFT): 10-K 0001193125-26-323660; 8-K / Exhibit 99.1 0001193125-26-436122; 10-Q 0001193125-26-436133 identified in metadata only; peer accessions below.
fallback

## Overview

**Purpose and provenance.** This is Brody Oliver's educational report for the company selected by partner Abraham Blaesing. ChatGPT prepared it from `MSFT_fallback_input.txt` after provider failures in the automated desk. It represents the four role tasks in one fallback response, not four successful SDK calls. Human audit marks and partner verification must be recorded separately by the reviewers. No market price was supplied.

**Sources.** K means Microsoft's fiscal 2026 10-K, accession **0001193125-26-323660**, covering July 1, 2025–June 30, 2026, with the comparative year July 1, 2024–June 30, 2025. E means the October 28, 2026 earnings release, Exhibit 99.1 of accession **0001193125-26-436122**, covering the three months ended September 30, 2026 and September 30, 2025. The supplied packet identifies 10-Q **0001193125-26-436133** but does not provide its substantive text as a separate source; no conclusion claims that document was read. K line references retain the packet's `10-K.txt:L...` labels. E packet-line references are physical lines in the supplied `MSFT_fallback_input.txt`, not SEC page numbers.

**Business model — Research Analyst.** Microsoft sells software and cloud services to enterprises and consumers. Its business description calls Azure a “comprehensive set of cloud services” (K, Business, `10-K.txt:L219`) and describes Microsoft's commercial productivity offering as an “AI-powered business and productivity solutions platform” (K, `L193`). These statements support a thesis based on cloud consumption and business subscriptions; they are management descriptions, not independent evidence of a lasting competitive advantage.

**Annual Financial Analyst evidence.** All monetary amounts in this report are **USD millions**, except EPS in **USD per diluted common share**. The two annual columns below use the K periods defined above. Equity and debt are balances at the respective June 30 dates. All tag names use the `us-gaap:` namespace.

| Annual fact | FY26 | FY25 | Filing evidence / tag |
|---|---:|---:|---|
| Consolidated total revenue | 331,839 | 281,724 | K p. 50, Total revenue; RevenueFromContractWithCustomerExcludingAssessedTax |
| Operating income | 155,237 | 128,528 | K p. 50, Operating income; OperatingIncomeLoss |
| Net income | 133,749 | 101,832 | K p. 50, Net income; NetIncomeLoss |
| GAAP diluted EPS | 17.95 | 13.64 | K p. 50, Diluted; EarningsPerShareDiluted |
| Total stockholders' equity | 442,387 | 343,479 | K p. 52, Total stockholders' equity; StockholdersEquity |
| Noncurrent long-term debt | 31,067 | 40,152 | K p. 52, Long-term debt; LongTermDebtNoncurrent |
| Current portion of long-term debt | 9,227 | 2,999 | K p. 52, Current portion of long-term debt; LongTermDebtCurrent |
| Net cash from operations | 182,935 | 136,162 | K p. 53, Net cash from operations; NetCashProvidedByUsedInOperatingActivities |
| Cash additions to property and equipment, magnitude | 115,948 | 64,551 | K p. 53, Additions to property and equipment; PaymentsToAcquirePropertyPlantAndEquipment |

**Revenue definition.** The selected revenue is consolidated total revenue, comprising product and service/other revenue, rather than a segment, cloud-only measure, or gross margin. K p. 50 reports FY26 product revenue **64,696** plus service and other **267,143**; FY25 product **63,946** plus service and other **217,778**. Cash capital spending is shown as an outflow in the statement; the table uses its positive magnitude for free cash flow. Annual EPS and net income are GAAP figures, not the adjusted measures in management's discussion.

## Market Positioning and Growth Outlook

**Competitive position — Research Analyst.** The company states that it competes through “secure, integrated industry-specific, and easy-to-use productivity and collaboration tools and services” (K, Business, `L204`). However, the same filing says Azure faces “diverse competition from cloud service providers and open-source offerings” (K, `L226`). Integration can support customer adoption, but the quoted evidence does not establish market share or guarantee pricing power.

**Annual growth — Financial Analyst.** Python verification gives **17.7887%** annual revenue growth: `(331,839 − 281,724) / 281,724 × 100`. Inputs are the consolidated total-revenue row in K p. 50 for FY26 and FY25, accession K above. This is annual growth and must not be substituted for the latest quarter's comparison.

**Latest quarter — Financial Analyst.** The following figures are from E's consolidated income statement and GAAP reconciliation, with the periods defined in Overview. E's accession is **0001193125-26-436122**. These are standalone three-month figures; they are not cumulative six- or nine-month figures.

| Quarterly measure | September 30, 2026 quarter | September 30, 2025 quarter | Evidence / definition |
|---|---:|---:|---|
| Consolidated total revenue | 92,279 | 77,673 | E, income statement Total revenue and constant-currency reconciliation Revenue row |
| GAAP operating income | 45,915 | 37,961 | E, income statement Operating income / reconciliation |
| GAAP net income | 36,629 | 27,747 | E, income statement Net income; packet lines 1063, 1107 |
| GAAP diluted EPS | 4.92 | 3.72 | E, Diluted earnings per share, As Reported (GAAP); packet lines 1064, 1108 |
| Adjusted diluted EPS, non-GAAP | 4.89 | 4.13 | E, same reconciliation, As Adjusted (non-GAAP); not the core GAAP EPS claim |

Quarter revenue growth is **18.8045%**, calculated in Python as `(92,279 − 77,673) / 77,673 × 100`. The release's headline rounds revenue growth to **19%** (E, packet line 1047). The difference is rounding, not an alternative revenue definition. Reported GAAP diluted EPS is **4.92**, rather than adjusted EPS **4.89**. E explains that its adjustment excludes investment effects from OpenAI; these adjusted measures must not replace GAAP in the core claims (E, Non-GAAP Definition and reconciliation).

**Catalysts and recent developments — Research Analyst.** The release states “Azure revenue increased 48%” (E, Business Highlights, packet line 1073), which supports a cloud-demand catalyst. It also states “Windows OEM and Devices revenue decreased 22%” (E, packet line 1086), showing that growth is uneven. These percentages are reported business metrics, not ratios independently inferred from the annual statements. The release warns that it has “recast certain prior period amounts” to reflect segment changes announced in September 2026 (E, packet line 1116). Therefore, this report uses consolidated comparisons and does not join the annual segment structure to the new quarterly segments as if the classifications were unchanged.

## Valuation Insights

**Price limitation.** No instructor share price or effective price date was supplied. P/E is **unavailable**, not zero. Its required arithmetic would be `supplied USD share price / FY26 GAAP diluted EPS of 17.95` (K p. 50, EarningsPerShareDiluted). No current market price, target price, fair value, or price-based upside is invented here.

**Statement-based ratios — Financial Analyst.** These results were checked with Python using the supplied financial inputs. Percentages below are displayed as percentages; debt/equity is a multiple. The numerator and denominator units cancel where appropriate.

| Measure | Arithmetic | Result | Source and period |
|---|---|---:|---|
| Annual revenue growth | (331,839 − 281,724) / 281,724 × 100 | 17.7887% | K p. 50, total revenue, FY26 vs FY25 |
| Annual operating margin | 155,237 / 331,839 × 100 | 46.7808% | K p. 50, operating income / consolidated revenue, FY26 |
| Return on average equity | 133,749 / ((442,387 + 343,479) / 2) × 100 | 34.0386% | K pp. 50, 52; FY26 net income / average June 30 equity |
| Debt/equity | (31,067 + 9,227) / 442,387 | 0.0911 times | K p. 52; June 30, 2026 balances |
| Free cash flow | 182,935 − 115,948 | 66,987 USD million | K p. 53; FY26 cash from operations less cash PP&E additions |
| Latest-quarter revenue growth | (92,279 − 77,673) / 77,673 × 100 | 18.8045% | E, three months ended September 30, 2026 vs 2025 |

**Debt and cash-flow definitions.** Debt/equity uses current plus noncurrent long-term borrowings, **40,294** in total. It excludes operating leases, finance leases, and standalone short-term borrowings under the desk's stated definition. It is not total liabilities/equity. Free cash flow uses cash additions to property and equipment; it is not a measure of all infrastructure commitments or lease-financed investment. These definitions limit comparisons with metrics that include lease obligations.

**Peer margins.** The packet supplies saved peer metrics and accession/tag summaries, not complete peer primary statement excerpts. Accordingly, these peer values remain subject to primary-filing human verification. Both available margins use GAAP operating income divided by consolidated annual revenue, matching the Microsoft definition. Fiscal windows differ, so the table is not a synchronized-quarter comparison.

| Issuer | Annual period | Revenue | Operating income | Python arithmetic and margin | Evidence |
|---|---|---:|---:|---|---|
| Microsoft | July 1, 2025–June 30, 2026 | 331,839 | 155,237 | 155,237 / 331,839 × 100 = 46.7808% | K p. 50; operating income and total revenue tags above |
| Alphabet (GOOGL) | January 1–December 31, 2025 | 402,836 | 129,039 | 129,039 / 402,836 × 100 = 32.0326% | 10-K 0001652044-26-000018; packet Section 2.D saved consolidated revenue and operating income |
| Oracle (ORCL) | June 1, 2025–May 31, 2026 | 67,357 | 20,606 | 20,606 / 67,357 × 100 = 30.5922% | 10-K 0001193125-26-277521; packet Section 2.D saved consolidated revenue and operating income |
| Apple (AAPL) | Automated run references 10-K 0000320193-25-000079 | Unavailable | Not supplied in this packet | Unavailable; no supported denominator in supplied peer output | Packet Section 2.D: automated revenue-definition reconciliation failed |

Apple's unavailable result reflects a **desk extraction/reconciliation limitation**, not a conclusion that Apple has no revenue or that total net sales can never be an appropriate consolidated revenue measure. Its reported definition requires reconciliation before calculating a comparable margin. No estimate substitutes for missing evidence. Oracle debt/equity is also unavailable in the packet; its debt-only balance selection could not establish both comparable components. Neither missing value is treated as zero.

**Interpretation.** Microsoft's available annual margin exceeds the two available peer margins in the supplied dataset. That comparison alone does not establish superior value: business mix, accounting judgments, fiscal windows, investment intensity, and Apple's unavailable comparison limit the inference.

## Future Developments and Strategic Recommendations

**Research evidence.** The annual MD&A says infrastructure investment “will continue to increase our operating costs and may decrease our operating margins” (K, `10-K.txt:L654`). It also says capital spending will support “growth in our cloud offerings and our investments in AI training and other infrastructure” (K, `L998`). Thus, expanding AI capacity is both a growth opportunity and a cost risk. No forecast return on that spending is established by the supplied filings.

**Analytical recommendations, not company guidance.** Track whether cloud demand converts into operating cash flow after cash capital spending. Compare future statements using the same debt and capital-spending definitions before interpreting a change as an economic improvement. Reconcile Apple's consolidated revenue definition and verify the two available peers against their primary statements. Use the release's recast comparisons when examining the changed quarterly segments. Finally, obtain the required share price and date before forming a price-based investment judgment. These are the Advisor's monitoring proposals derived from the Research and Financial Analyst evidence; they are not claims that management announced these actions.

## Investment Recommendation

**Provisional HOLD. Deciding Financial Analyst metric: FY26 free cash flow of 66,987 USD million**, calculated as **182,935 − 115,948**, from K's cash-flow statement, p. 53, accession **0001193125-26-323660**. Positive cash generation after cash PP&E additions supports a constructive operating thesis. The Research Analyst's cloud-demand evidence supports that thesis, while its competition and infrastructure-cost evidence limits confidence in extrapolating it.

This Hold is a provisional educational stance, **not a finding that the shares are fairly valued**. Without a supplied share price, P/E and price-based valuation cannot be evaluated. Cash free flow excludes lease-financed infrastructure additions under the chosen definition. Peer evidence is incomplete and subject to human review. A stronger Buy or Sell decision would require the missing price evidence and an explicit valuation case, which this packet does not provide.

**Strategy Manager fallback check.** The five required report parts are present. Annual and quarterly periods are separate; GAAP and adjusted EPS are distinguished; ratios show Python-checked arithmetic; unavailable inputs remain unavailable. This consistency check is AI assistance, not a human audit or partner sign-off. The two partner marks and the full human audit must be entered by the reviewers in a separate audit file.

Source links:
- K: https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm
- E: https://www.sec.gov/Archives/edgar/data/789019/000119312526436122/msft-ex99_1.htm
- Earnings 8-K: https://www.sec.gov/Archives/edgar/data/789019/000119312526436122/msft-20261028.htm
- 10-Q metadata only: https://www.sec.gov/Archives/edgar/data/789019/000119312526436133/msft-20260930.htm
- Evidence packet: MSFT_fallback_input.txt, Sections 1–5. Preserve this packet beside the report for its line references.

This is a learning exercise, not financial advice.
AI assistance: ChatGPT drafted this fallback report from the supplied evidence; Codex and Antigravity assisted with the desk and source preparation. Human source verification and judgments must be documented in the accompanying audit; this report itself does not certify their completion.
Any remaining errors are my own.
