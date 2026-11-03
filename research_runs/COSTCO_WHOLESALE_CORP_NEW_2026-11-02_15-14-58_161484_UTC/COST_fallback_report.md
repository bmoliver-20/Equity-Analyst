COSTCO WHOLESALE CORP /NEW: 10-K 0000909832-26-000093; 8-K / Exhibit 99.1 0000909832-26-000084; 10-Q metadata only 0000909832-26-000051; peer accessions listed below.
fallback

## Overview

**Scope and provenance.** This educational report was generated in ChatGPT from the supplied `fallback_input.txt` after the automated workflow encountered provider failures. It is not a successful four-call API run. The supplied annual statements, Business and MD&A excerpts, earnings release, and saved peer metrics are the evidence base; no current market data were added. The packet identifies the latest 10-Q, but supplies no substantive 10-Q text, so no claim below depends on reading that document. Human audit and partner verification remain pending.

**Business model — Research Analyst.** Costco operates membership warehouses and e-commerce sites with a low-price, high-volume model. The filing describes “offering low prices on a limited selection” and “high sales volumes and rapid inventory turnover” (K, Business, saved 10-K.txt:L97). Its distribution model supports this positioning: “This process creates freight volume and handling efficiencies” (K, L101). These are management's descriptions, not independent proof of superior efficiency.

**Financial Analyst evidence.** All monetary amounts below are **USD millions**, except EPS in USD per diluted share. FY26 and FY25 mean the respective 52-week fiscal years ended August 30, 2026 and August 31, 2025. Balance-sheet values are at those dates. K refers to accession **0000909832-26-000093**, Item 8; tags are in the `us-gaap` namespace.

| Annual fact | FY26 / current | FY25 / prior | Filing row and XBRL tag |
|---|---:|---:|---|
| Total revenue | 303,154 | 275,235 | K, income statement p.37, Total revenue; RevenueFromContractWithCustomerExcludingAssessedTax |
| Operating income | 11,685 | 10,383 | K, p.37, Operating income; OperatingIncomeLoss |
| Net income attributable to Costco | 9,226 | 8,099 | K, p.37, NET INCOME; NetIncomeLoss |
| GAAP diluted EPS | 20.76 | 18.21 | K, p.37, NET INCOME PER COMMON SHARE—Diluted; EarningsPerShareDiluted |
| Total equity | 35,803 | 29,164 | K, balance sheet p.39, TOTAL EQUITY; StockholdersEquity |
| Noncurrent long-term debt | 3,914 | 5,713 | K, p.39, Long-term debt, excluding current portion; LongTermDebtNoncurrent |
| Current portion of long-term debt | 2,248 | 75 | K, p.39, Current portion of long-term debt; LongTermDebtCurrent |
| Cash from operating activities | 15,817 | 13,335 | K, cash-flow statement p.41, Net cash provided by operating activities; NetCashProvidedByUsedInOperatingActivities |
| Capital expenditures, positive cash-spend magnitude | 6,435 | 5,498 | K, p.41, Additions to property and equipment; PaymentsToAcquirePropertyPlantAndEquipment |

The supplied income statement has no separate noncontrolling-interest allocation; its NET INCOME is used as attributable to Costco, rather than substituting comprehensive income. Total revenue includes membership fees: the FY26 statement reports net sales of 297,247 and membership fees of 5,907; FY25 reports 269,912 and 5,323 (K, p.37). Net sales alone is not used as the total-revenue denominator. Capital expenditure outflows appear in parentheses in the cash-flow statement; the calculator subtracts their positive magnitude.

## Market Positioning and Growth Outlook

**Position and competitive limits — Research Analyst.** Costco's stated differentiation includes private-label merchandise: management says Kirkland Signature products “help lower costs, differentiate our merchandise offerings, and generally earn higher margins” (K, Business, L156). This is explicitly management's belief, not a claim that the supplied statements separately measure Kirkland profitability. Competition remains significant: “Our industry is highly competitive” (K, L154); the same line identifies general retailers and competing warehouse clubs. A lower consolidated operating margin than a peer does not by itself show weaker execution because merchandise mix and business models differ.

**Growth evidence — Financial Analyst.** These calculations were checked in Python from the supplied statements; they are calculated results, not directly reported GAAP line items.

| Metric | Python arithmetic using USD millions | Result | Evidence / period |
|---|---|---:|---|
| Annual total-revenue growth | (303,154 − 275,235) / 275,235 × 100 | 10.1437% | K, p.37; FY26 versus FY25 |
| Latest-quarter total-revenue growth, year over year | (95,723 − 86,156) / 86,156 × 100 | 11.1043% | E, Total revenue row; 16 weeks ended Aug.30,2026 versus 16 weeks ended Aug.31,2025 |

E is Exhibit 99.1 under accession **0000909832-26-000084**, its unaudited consolidated statements of income. The same quarterly columns report **GAAP diluted EPS of 6.75 versus 5.87 USD/share** (E, NET INCOME PER COMMON SHARE—Diluted). These are quarterly, not annual or year-to-date values. E's 52-week EPS columns are 20.76 and 18.21 and are not substituted for the quarter. The release's headline net-sales growth uses a narrower revenue definition than this report's total-revenue growth.

**Catalysts and earnings quality — Research Analyst.** Expansion is a disclosed growth mechanism: MD&A states the remaining net-sales increase “was driven by sales at the 25 net new warehouses” (K, L425). Membership growth has several contributors: “new member sign-ups, membership fee increases, and upgrades to Executive memberships” (K, L434). The quarter also included a special benefit: E's paragraph beginning “Net income for the fourth quarter” reports a “non-recurring benefit of $0.15 per diluted share” from tariff refunds, after partial reinvestment in member value. The reported 6.75 EPS includes that benefit; this report does not relabel GAAP EPS as adjusted EPS or manufacture an adjusted series.

## Valuation Insights

**Price-based valuation is unavailable.** No instructor share price or effective date was supplied. Consequently, no P/E, target price, fair value, upside, or downside is asserted. The intended P/E arithmetic is supplied price in USD/share divided by FY26 diluted EPS of 20.76 USD/share (K, p.37); it remains unevaluated.

| Financial measure | Python arithmetic using USD millions | Result | Source and definition |
|---|---|---:|---|
| FY26 operating margin | 11,685 / 303,154 × 100 | 3.8545% | K p.37; operating income / total revenue |
| FY26 return on average equity | 9,226 / ((35,803 + 29,164) / 2) × 100 | 28.4021% | K pp.37,39; annual net income / mean of current and prior year-end equity |
| Current debt/equity | (3,914 + 2,248) / 35,803 | 0.1721 times | K p.39; current plus noncurrent long-term borrowings / current equity |
| FY26 free cash flow | 15,817 − 6,435 | 9,382 USD million | K p.41; operating cash flow less PP&E additions |

Debt/equity follows the saved program's **long-term-borrowings-only definition**, including the current portion and excluding finance leases, operating leases, and standalone short-term borrowings. It is not total liabilities/equity and should not be described as an all-obligations leverage measure. ROAE uses two year-end balances, not quarterly average equity. Free cash flow is a calculated cash-flow measure, not a GAAP statement subtotal or a valuation.

**Peer operating margins — saved Step 7 evidence.** Values and tags below come from the packet's saved peer summary, not complete peer filings supplied in this chat. This limitation must remain visible during human audit. The revenue tag for Walmart is Revenues; for Costco, Target, and BJ it is RevenueFromContractWithCustomerExcludingAssessedTax. Operating income uses OperatingIncomeLoss.

| Company | Annual period | Revenue / operating income, USD millions | Python margin arithmetic | Margin | 10-K accession |
|---|---|---|---|---:|---|
| COST | Sep.1,2025–Aug.30,2026 | 303,154 / 11,685 | 11,685 / 303,154 × 100 | 3.8545% | 0000909832-26-000093 |
| WMT | Feb.1,2025–Jan.31,2026 | 713,163 / 29,825 | 29,825 / 713,163 × 100 | 4.1821% | 0000104169-26-000055 |
| TGT | Feb.2,2025–Jan.31,2026 | 104,780 / 5,117 | 5,117 / 104,780 × 100 | 4.8836% | 0000027419-26-000016 |
| BJ | Feb.2,2025–Jan.31,2026 | 21,457.274 / 816.604 | 816.604 / 21,457.274 × 100 | 3.8057% | 0001531152-26-000007 |

Walmart's denominator is total revenues, not its narrower net-sales line. Target labels its measure Net sales; the saved selection accepts that measure as inclusive revenue, but the underlying definition note is not reproduced in this packet and needs checking against the peer filing. BJ uses total revenues. These fiscal windows differ and do not establish performance over an identical economic period. Peer debt/equity is unnecessary for this margin comparison; BJ's debt/equity remains **unavailable** under the saved debt definition, rather than zero.

## Future Developments and Strategic Recommendations

**Disclosed plan — Research Analyst.** MD&A states an intention “to spend approximately $7,500” during fiscal 2027 and to “open up to 33 new warehouses, including five relocations” (K, L495; capex in USD millions). The same line cautions, “There can be no assurance that current expectations will be realized.” These are management plans, not achieved openings or forecasts independently validated by this report.

**Analyst judgment.** Prioritize disciplined expansion and preservation of member value, then monitor whether operating cash generation supports investment. This recommendation is an inference from the stated expansion plan (K, L495) and Costco's stated pricing strategy, “prices we believe are consistently lower than elsewhere” (K, L104). It is not a claim that management has adopted a new strategy. Avoid projecting the quarter's special tariff benefit as recurring: the release expressly calls it a “non-recurring benefit” (E, fourth-quarter net-income paragraph). Maintain a separate view of total revenue, net sales, and membership fees so growth and margin comparisons retain consistent definitions.

## Investment Recommendation

**Hold — provisional educational judgment, not a price-based valuation conclusion.** The thesis combines Costco's disclosed low-price membership model with positive annual and quarterly total-revenue growth and operating cash generation. The deciding Financial Analyst metric is **FY26 free cash flow of 9,382 USD million**, calculated as **15,817 − 6,435** from K's cash-flow statement, p.41. It supports the operating-resilience thesis but does not establish an attractive purchase price.

The missing price prevents a supported Buy case based on valuation; it also prevents a claim that the shares are fairly valued. Here, Hold means defer a price-dependent trade decision, not that this report has established suitability for an existing shareholder. The recommendation is limited by the non-recurring quarterly benefit, differing peer periods, incomplete peer-source excerpts, and pending human audit. No unsupported market-share, price-target, or return forecast is added.

**Strategy Manager compilation note.** The five required report parts are present. Reported facts, Python-calculated ratios, management expectations, and analyst judgments are distinguished. This fallback was compiled in one chat response, not through four successful separate API role calls. The 10-Q was identified from metadata only. The packet's truncated dollar-prefixed summary entries were not used where intact primary statement rows were available. No human correctness marks, error counts, or partner sign-offs have been fabricated.

**Source register.**

- **K:** Costco FY26 10-K, accession 0000909832-26-000093, [primary document](https://www.sec.gov/Archives/edgar/data/909832/000090983226000093/cost-20260830.htm). Annual statements: printed pp.37,39,41; qualitative line numbers refer to the supplied saved 10-K.txt.
- **E:** Costco earnings 8-K / Exhibit 99.1, accession 0000909832-26-000084, [release](https://www.sec.gov/Archives/edgar/data/909832/000090983226000084/costex9918-k92426.htm). Quarterly financial references identify exact statement row labels.
- **Q, metadata only:** accession 0000909832-26-000051, [10-Q](https://www.sec.gov/Archives/edgar/data/909832/000090983226000051/cost-20260510.htm); no substantive claims rely on its contents.
- **Peer summaries:** supplied fallback_input.txt Section 2D and saved Step 7 evidence; accessions and fiscal periods are listed in the peer table. Complete peer filings were not included in the packet.

**Disclosure:** Prepared for coursework and learning, not investment advice. ChatGPT generated this fallback using user-supplied saved filing excerpts and metrics; Python checked the displayed ratio arithmetic. Source references support review but do not replace the required independent human verification. Recommendations are conditional analyst judgments. Errors and omissions may remain; student and partner audit are still required.
