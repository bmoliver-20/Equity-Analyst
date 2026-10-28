"""SEC research data pipeline. Python 3. No model calls or API keys required."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from functools import cached_property
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from dotenv import dotenv_values
import requests

from annual_revenue import revenue_evidence
from debt_selection import debt_evidence, select_debt, RATIO_BASIS
from release_parser import extract_release, print_release

ROOT = Path(__file__).resolve().parent
SEC = 'https://www.sec.gov'
DATA = 'https://data.sec.gov'
# Candidate order breaks ties only. The newest annual period wins first.
CONCEPTS = {
    'revenue': ('USD', False, ['RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax', 'Revenues', 'SalesRevenueNet']),
    'operating_income': ('USD', False, ['OperatingIncomeLoss']),
    'net_income': ('USD', False, ['NetIncomeLoss', 'ProfitLoss']),
    'diluted_eps': ('USD/shares', False, ['EarningsPerShareDiluted']),
    'equity': ('USD', True, ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest']),
    'long_term_debt': ('USD', True, ['LongTermDebtNoncurrent']),
    'current_debt': ('USD', True, ['LongTermDebtCurrent']),
    'operating_cash_flow': ('USD', False, ['NetCashProvidedByUsedInOperatingActivities']),
    'capital_expenditures': ('USD', False, ['PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsForAdditionsToPropertyPlantAndEquipment']),
}


class DataError(Exception):
    pass


class SECClient:
    def __init__(self, user_agent):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent, 'Accept-Encoding': 'gzip, deflate'})
        self.last_request = 0.0
        self.cache = {}

    def get(self, url):
        if url in self.cache:
            return self.cache[url]
        if urlparse(url).hostname not in {'www.sec.gov', 'data.sec.gov'}:
            raise DataError('Refusing a document URL outside SEC hosts.')
        for attempt in range(4):
            time.sleep(max(0, 0.2 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.get(url, timeout=60)
            except requests.RequestException:
                if attempt == 3:
                    raise DataError('SEC connection failed. Check network access and retry.') from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                raise DataError(f'SEC returned HTTP {response.status_code} for {url}.')
            self.cache[url] = response
            return response
        raise DataError('SEC remained unavailable after 4 attempts.')

    def json(self, url):
        try:
            return self.get(url).json()
        except ValueError:
            raise DataError('SEC returned invalid JSON.') from None

    @cached_property
    def tickers(self):
        return self.json(SEC + '/files/company_tickers.json')

    def resolve(self, ticker):
        matches = [row for row in self.tickers.values() if row['ticker'].upper() == ticker.upper()]
        if not matches:
            raise DataError(f'Ticker {ticker} was not found in SEC company_tickers.json.')
        row = matches[0]
        return {'ticker': row['ticker'], 'cik': int(row['cik_str']), 'name': row['title']}


def plain_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.find_all(['script', 'style', 'ix:header', 'ix:hidden']):
        node.decompose()
    # Preserve table rows (including column headings) instead of one line per cell.
    for row in soup.find_all('tr'):
        row.replace_with('\n' + ' | '.join(cell.get_text(' ', strip=True) for cell in row.find_all(['th', 'td'], recursive=False)) + '\n')
    for node in soup.find_all(['p', 'div', 'li', 'br', 'h1', 'h2', 'h3', 'h4']):
        node.insert_before('\n')
        node.insert_after('\n')
    return '\n'.join(line for raw in soup.get_text(' ').splitlines() if (line := ' '.join(raw.split())))


def filing_rows(block):
    return [{key: values[i] for key, values in block.items() if isinstance(values, list) and i < len(values)}
            for i in range(len(block.get('accessionNumber', [])))]


def archive_url(cik, accession, document):
    return f'{SEC}/Archives/edgar/data/{cik}/{accession.replace("-", "")}/{document}'


def index_details(html, index_url):
    soup = BeautifulSoup(html, 'html.parser')
    accepted = None
    for label in soup.select('.infoHead'):
        if label.get_text(strip=True) == 'Accepted':
            value = label.find_next_sibling(class_='info')
            if value:
                accepted = value.get_text(' ', strip=True)
    if not accepted:
        raise DataError('The EDGAR index page has no readable Accepted time.')
    exhibits = []
    for row in soup.select('table.tableFile tr'):
        cells = row.find_all('td')
        if len(cells) >= 4 and re.fullmatch(r'EX-99\.0?1', cells[3].get_text(strip=True), re.I):
            link = cells[2].find('a', href=True)
            if link:
                url = urljoin(index_url, link['href'])
                if '/ix' in urlparse(url).path:
                    doc = parse_qs(urlparse(url).query).get('doc')
                    if doc:
                        url = urljoin(SEC, doc[0])
                exhibits.append(url)
    return accepted, exhibits


def annual_entries(facts, tag, unit, instant):
    entries = facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get(unit, [])
    result = []
    for entry in entries:
        if entry.get('form') not in {'10-K', '10-K/A'} or not entry.get('end'):
            continue
        if not instant:
            if not entry.get('start'):
                continue
            days = (date.fromisoformat(entry['end']) - date.fromisoformat(entry['start'])).days
            if not 330 <= days <= 380:
                continue
        result.append(entry)
    return result


def selected_facts(raw, revenue_sources=None, debt_sources=None):
    candidates = {}
    for concept, (unit, instant, tags) in CONCEPTS.items():
        choices = [(tag, annual_entries(raw, tag, unit, instant)) for tag in tags]
        choices = [(tag, rows) for tag, rows in choices if rows]
        candidates[concept] = sorted(choices, key=lambda item: max(row['end'] for row in item[1]), reverse=True)
    expected_end = max((r['end'] for _, rows in candidates['revenue'] for r in rows), default=None)
    if revenue_sources is None:
        # Only the broad total-revenue concept is safe without filing evidence.
        candidates['revenue'] = [(tag, rows) for tag, rows in candidates['revenue'] if tag == 'Revenues']
    else:
        validated = []
        for tag, rows in candidates['revenue']:
            for row in rows:
                proofs = [proof for proof in revenue_sources if proof['tag'] == 'us-gaap:' + tag and all(proof[k] == row.get(k) for k in ['start', 'end', 'val', 'accn'])]
                if proofs:
                    validated.append((tag, [{**row, 'revenue_definition': proofs[0]}]))
        candidates['revenue'] = validated
    revenue_rows = [row for _, rows in candidates['revenue'] for row in rows]
    if not revenue_rows:
        raise DataError('No consolidated total revenue could be matched to filing definitions and XBRL. Net sales is not substituted.')
    newest_end = max(row['end'] for row in revenue_rows)
    if revenue_sources is not None and newest_end != expected_end:
        raise DataError('Total revenue is unconfirmed for the latest annual period; an older year is not substituted.')
    if revenue_sources is not None and len({row['val'] for row in revenue_rows if row['end'] == newest_end}) != 1:
        raise DataError('Conflicting total-revenue evidence for the latest year; selection is unavailable.')
    current = max(revenue_rows, key=lambda row: (row['end'], row.get('filed', ''), row.get('accn', '')))
    end, start = current['end'], current['start']
    previous_rows = [r for r in revenue_rows if 330 <= (date.fromisoformat(end) - date.fromisoformat(r['end'])).days <= 380]
    # Search older candidate tags when revenue taxonomy changed.
    if not previous_rows:
        previous_rows = [r for _, rows in candidates['revenue'] for r in rows if 330 <= (date.fromisoformat(end) - date.fromisoformat(r['end'])).days <= 380]
    if len({r['val'] for r in previous_rows}) > 1 and revenue_sources is not None:
        raise DataError('Conflicting prior-year total-revenue evidence; selection is unavailable.')
    previous = max(previous_rows, key=lambda r: (r['end'], r.get('filed', '')), default=None)
    periods = {'current': {'start': start, 'end': end}, 'prior': {'start': previous['start'], 'end': previous['end']} if previous else None}
    output = {'periods': periods, 'concepts': {}, 'basis': 'Annual US-GAAP, USD; latest filed values for matching periods; missing values are not zero.'}
    for concept, (unit, instant, _) in CONCEPTS.items():
        output['concepts'][concept] = {}
        for name, period in periods.items():
            selected = None
            if period:
                for tag, rows in candidates[concept]:
                    matching = [r for r in rows if r['end'] == period['end'] and (instant or r.get('start') == period['start'])]
                    if matching:
                        row = max(matching, key=lambda r: (r.get('filed', ''), r.get('accn', '')))
                        selected = {**row, 'tag': 'us-gaap:' + tag, 'unit': unit}
                        break
            output['concepts'][concept][name] = selected
    output['debt'] = {}
    for name, period in periods.items():
        revenue = output['concepts']['revenue'][name]
        if period and revenue:
            debt = select_debt(raw, period['end'], revenue['accn'], debt_sources)
            output['debt'][name] = debt
            output['concepts']['long_term_debt'][name] = debt['noncurrent_debt_only']
            output['concepts']['current_debt'][name] = debt['current_debt_only']
    return output


def print_facts(facts):
    print('Fiscal periods: ' + json.dumps(facts['periods']))
    print(facts['basis'])
    print('Debt/equity basis: ' + RATIO_BASIS)
    for concept, pair in facts['concepts'].items():
        parts = []
        for period in ['current', 'prior']:
            row = pair[period]
            parts.append(f'{period}: MISSING' if row is None else f"{period}: {row['val']:,.4f} {row['unit']} | {row['tag']} | end {row['end']} | filing {row.get('accn')} ({row.get('filed')})")
        print(concept + ': ' + ' || '.join(parts))
        if concept == 'revenue':
            for period, row in pair.items():
                if row and row.get('revenue_definition'):
                    proof = row['revenue_definition']
                    print(f"  {period} revenue definition: {proof['filing_label']} — {proof['definition']} | {proof['source_url']}")

    for period, debt in facts.get('debt', {}).items():
        print(f'{period} debt classifications:')
        for row in debt['reported'].values():
            print(f"  reported: {row['source_label']} | {row['val']} USD | {row['tag']} | {row['end']} | {row['accn']} | {row['definition']}")
        for key in ['current_debt_only', 'noncurrent_debt_only', 'total_debt_only', 'total_debt_including_finance_leases']:
            row = debt[key]
            print(f"  {key}: " + (f"{row['status']} | {row.get('arithmetic', row['val'])}" if row else 'unavailable'))
        if debt['unavailable_reason']:
            print('  ' + debt['unavailable_reason'])


def calculations(facts, price=None):
    def value(name, period='current'):
        row = facts['concepts'][name][period]
        return row['val'] if row else None
    rev, prev = value('revenue'), value('revenue', 'prior')
    op, net = value('operating_income'), value('net_income')
    eq, old_eq = value('equity'), value('equity', 'prior')
    debt_selection = facts.get('debt', {}).get('current', {})
    debt_total = debt_selection.get('total_debt_only')
    debt = debt_total['val'] if debt_total else None
    cfo, capex, eps = value('operating_cash_flow'), value('capital_expenditures'), value('diluted_eps')
    results = {}
    def record(name, inputs, expression, operation, percent=False):
        if any(x is None for x in inputs):
            results[name] = {'value': None, 'arithmetic': 'Unavailable: a required input is missing.'}
            return
        try:
            number = operation()
            results[name] = {'value': number, 'arithmetic': f'{expression} = {number * 100 if percent else number:,.4f}' + ('%' if percent else '')}
        except ZeroDivisionError:
            results[name] = {'value': None, 'arithmetic': 'Unavailable: denominator is zero.'}
    record('revenue_growth', [rev, prev], f'({rev} - {prev}) / {prev} × 100', lambda: (rev-prev)/prev, True)
    record('operating_margin', [op, rev], f'{op} / {rev} × 100', lambda: op/rev, True)
    record('return_on_average_equity', [net, eq, old_eq], f'{net} / (({eq} + {old_eq}) / 2) × 100', lambda: net/((eq+old_eq)/2), True)
    record('debt_to_equity', [debt, eq], f'{debt} / {eq}', lambda: debt/eq)
    results['debt_to_equity']['basis'] = RATIO_BASIS
    if debt_total:
        results['debt_to_equity']['debt_arithmetic'] = debt_total['arithmetic']
        results['debt_to_equity']['inputs'] = debt_total
    else:
        results['debt_to_equity']['arithmetic'] = 'Unavailable: ' + debt_selection.get('unavailable_reason', 'No debt classification evidence; legacy debt fields are not used.')
    record('free_cash_flow', [cfo, capex], f'{cfo} - {capex}', lambda: cfo-capex)
    record('price_to_earnings', [price, eps], f'{price} / {eps}', lambda: price/eps)
    if price is None:
        results['price_to_earnings']['arithmetic'] = 'Unavailable: supply --price in USD per share.'
    elif eps is not None and eps <= 0:
        results['price_to_earnings'] = {'value': None, 'arithmetic': f'Not meaningful: annual diluted EPS is {eps} (not positive).'}
    return results


class Desk:
    def __init__(self, client, ticker, peers, price, output_root=ROOT / 'research_runs'):
        self.client, self.ticker, self.peers, self.price = client, ticker, peers, price
        self.output_root = Path(output_root)
        self.debt_sources = {}

    @cached_property
    def company(self):
        return self.client.resolve(self.ticker)

    @cached_property
    def folder(self):
        name = re.sub(r'[^\w.-]+', '_', self.company['name']).strip('_')
        folder = self.output_root / f'{name}_{datetime.now(timezone.utc):%Y-%m-%d_%H-%M-%S_%f_UTC}'
        folder.mkdir(parents=True, exist_ok=False)
        self.save_to(folder / 'company.json', self.company)
        return folder

    @staticmethod
    def save_to(path, obj):
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    def save(self, name, obj):
        self.save_to(self.folder / name, obj)

    @cached_property
    def filings(self):
        cik = self.company['cik']
        submissions = self.client.json(f'{DATA}/submissions/CIK{cik:010d}.json')
        rows = filing_rows(submissions['filings']['recent'])
        history = sorted(submissions['filings'].get('files', []), key=lambda x: x.get('filingTo', ''), reverse=True)
        selected = {}
        examined = set()
        while True:
            for row in sorted(rows, key=lambda r: (r.get('filingDate', ''), r['accessionNumber']), reverse=True):
                form, acc = row['form'], row['accessionNumber']
                if form not in {'10-K', '10-Q', '8-K'} or form in selected or acc in examined:
                    continue
                examined.add(acc)
                document_url = archive_url(cik, acc, row['primaryDocument'])
                if form == '8-K':
                    text = plain_text(self.client.get(document_url).text)
                    if not re.search(r'\bItem\s*2\s*\.\s*02\b', text, re.I):
                        continue
                index_url = archive_url(cik, acc, acc + '-index.html')
                accepted, exhibits = index_details(self.client.get(index_url).text, index_url)
                selected[form] = {**row, 'document_url': document_url, 'index_url': index_url, 'accepted': accepted, 'exhibit_99_1_urls': exhibits}
            if len(selected) == 3 or not history:
                break
            file = history.pop(0)
            rows.extend(filing_rows(self.client.json(DATA + '/submissions/' + file['name'])))
        self.save('filings.json', {'selected': selected, 'filings_examined': rows})
        return selected

    def document_text(self, url):
        response = self.client.get(url)
        if response.content.startswith(b'%PDF'):
            raise DataError('A selected document is PDF; this version supports HTML and plain text only.')
        return plain_text(response.text)

    @cached_property
    def release(self):
        filing = self.filings.get('8-K')
        if not filing:
            raise DataError('No 8-K document reporting Item 2.02 was found.')
        urls = filing['exhibit_99_1_urls']
        if not urls:
            raise DataError('The latest Item 2.02 8-K has no Exhibit 99.1 on its index page.')
        texts = []
        for i, url in enumerate(urls, 1):
            response = self.client.get(url)
            if response.content.startswith(b'%PDF'):
                raise DataError('Release is PDF; HTML table extraction is unavailable.')
            suffix = '' if len(urls) == 1 else f'_{i}'
            (self.folder / f'earnings_release_99_1{suffix}.html').write_text(response.text, encoding='utf-8')
            texts.append(plain_text(response.text))
        result = '\n\n'.join(texts)
        (self.folder / 'earnings_release_99_1.txt').write_text(result, encoding='utf-8')
        return result

    def revenue_sources(self, company):
        cik = company['cik']
        sub = self.client.json(f'{DATA}/submissions/CIK{cik:010d}.json')
        rows = filing_rows(sub['filings']['recent'])
        history = iter(sub['filings'].get('files', []))
        while not any(r['form'] == '10-K' for r in rows):
            item = next(history, None)
            if item is None:
                raise DataError('No annual filing available for revenue definition checks.')
            rows.extend(filing_rows(self.client.json(DATA + '/submissions/' + item['name'])))
        row = max((r for r in rows if r['form'] == '10-K'), key=lambda r: (r['filingDate'], r['accessionNumber']))
        url = archive_url(cik, row['accessionNumber'], row['primaryDocument'])
        html = self.client.get(url).text
        (self.folder / f'annual_revenue_source_{cik}.html').write_text(html, encoding='utf-8')
        self.debt_sources[cik] = debt_evidence(html, url, row['accessionNumber'])
        self.save(f'annual_debt_evidence_{cik}.json', self.debt_sources[cik])
        evidence = revenue_evidence(html, url, row['accessionNumber'])
        self.save(f'annual_revenue_evidence_{cik}.json', evidence)
        return evidence

    @cached_property
    def facts(self):
        cik = self.company['cik']
        raw = self.client.json(f'{DATA}/api/xbrl/companyfacts/CIK{cik:010d}.json')
        self.save('companyfacts_raw.json', raw)
        facts = selected_facts(raw, self.revenue_sources(self.company), self.debt_sources.get(cik))
        self.save('facts.json', facts)
        return facts

    def step1(self):
        print(f"{self.company['ticker']}: {self.company['name']} | CIK {self.company['cik']:010d}")
        self.save('company.json', self.company)

    def step2(self):
        for form in ['10-K', '10-Q', '8-K']:
            row = self.filings.get(form)
            if row:
                print(f"{form}: {row['accessionNumber']} | Accepted {row['accepted']} | {row['index_url']}")
            else:
                print(f'{form}: not found in available filing history.')
        print('Full examined filing list saved in filings.json.')

    def step3(self):
        for form in ['10-K', '10-Q', '8-K']:
            if form not in self.filings:
                print(f'{form}: unavailable.')
                continue
            text = self.document_text(self.filings[form]['document_url'])
            (self.folder / (form + '.txt')).write_text(text, encoding='utf-8')
            print(f'Saved {form}.txt')
        _ = self.release
        print('Saved earnings_release_99_1.txt')

    def step4(self):
        print_facts(self.facts)

    def step5(self):
        results = calculations(self.facts, self.price)
        self.save('calculations.json', results)
        for name, result in results.items():
            print(f"{name}: {result['arithmetic']}")

    def step6(self):
        _ = self.release  # Save both the source HTML and the plain text.
        results = {'revenue': [], 'diluted_eps': []}
        for url in self.filings['8-K']['exhibit_99_1_urls']:
            extracted = extract_release(self.client.get(url).text, url)
            for metric in results:
                results[metric].extend(extracted[metric])
        self.save('release_lines.json', results)
        print_release(results)

    def step7(self):
        if not self.peers:
            print('No peers supplied; use --peers TICKER TICKER.')
        peer_results = {}
        for ticker in self.peers:
            print(f'Peer {ticker}:')
            try:
                company = self.client.resolve(ticker)
                raw = self.client.json(f"{DATA}/api/xbrl/companyfacts/CIK{company['cik']:010d}.json")
                facts = selected_facts(raw, self.revenue_sources(company), self.debt_sources.get(company['cik']))
                margin = calculations(facts)['operating_margin']
                peer_results[ticker] = {'company': company, 'facts': facts, 'operating_margin': margin}
                self.save(f"peer_{company['cik']}_companyfacts_raw.json", raw)
                print_facts(facts)
                print('operating_margin: ' + margin['arithmetic'])
            except DataError as exc:
                peer_results[ticker] = {'error': str(exc)}
                print(str(exc))
        self.save('peers.json', peer_results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker')
    parser.add_argument('--peers', nargs='+', default=[], help='Peer tickers, separated by spaces or commas')
    parser.add_argument('--price', type=float, help='USD price per share for annual P/E')
    parser.add_argument('--step', type=int, choices=range(1, 8), help='Run only this step; fetch its inputs as needed')
    args = parser.parse_args()
    if args.price is not None and (not math.isfinite(args.price) or args.price <= 0):
        parser.error('--price must be finite and greater than zero')
    user_agent = dotenv_values(ROOT / '.env').get('SEC_USER_AGENT')
    if not user_agent or not user_agent.strip():
        parser.error('Add SEC_USER_AGENT with your name and contact email to .env.')
    peers = list(dict.fromkeys(t.upper() for part in args.peers for t in part.split(',') if t))
    desk = Desk(SECClient(user_agent), args.ticker.upper(), peers, args.price)
    names = ['Resolve ticker', 'Select filings and Accepted times', 'Download and convert documents', 'Annual company facts', 'Calculate ratios', 'Quarterly release lines', 'Peer facts and operating margins']
    failed = False
    for number in ([args.step] if args.step else range(1, 8)):
        print(f'\nStep {number}: {names[number-1]}', flush=True)
        try:
            getattr(desk, f'step{number}')()
        except DataError as exc:
            print(f'Unavailable: {exc}')
            failed = True
    if 'folder' in desk.__dict__:
        print(f'\nSaved results: {desk.folder}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
