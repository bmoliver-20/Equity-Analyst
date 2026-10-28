"""Offline tests using fictional filings and financial facts."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from equity_desk import Desk, SECClient, calculations, index_details, plain_text, selected_facts


def annual(value, end='2025-06-30', start='2024-07-01', filed='2025-08-01'):
    return dict(val=value, start=start, end=end, filed=filed, accn='0000000001-25-000001', form='10-K', fy=2025, fp='FY')


def fixture():
    tags = {}
    values = {'Revenues': (120, 100), 'OperatingIncomeLoss': (30, 20), 'NetIncomeLoss': (20, 15), 'EarningsPerShareDiluted': (2, 1.5), 'StockholdersEquity': (100, 80), 'LongTermDebtNoncurrent': (30, 25), 'LongTermDebtCurrent': (5, 4), 'NetCashProvidedByUsedInOperatingActivities': (40, 30), 'PaymentsToAcquirePropertyPlantAndEquipment': (10, 8)}
    for tag, (now, before) in values.items():
        rows = [annual(now), annual(before, '2024-06-30', '2023-07-01')]
        if tag in {'StockholdersEquity', 'LongTermDebtNoncurrent', 'LongTermDebtCurrent'}:
            for row in rows:
                row.pop('start')
        tags[tag] = {'units': {'USD/shares' if tag == 'EarningsPerShareDiluted' else 'USD': rows}}
    # Preferred tag is stale; newest annual end must win over candidate order.
    tags['RevenueFromContractWithCustomerExcludingAssessedTax'] = {'units': {'USD': [annual(90, '2023-06-30', '2022-07-01')]}}
    return {'facts': {'us-gaap': tags}}


INDEX = '''<div class="infoHead">Accepted</div><div class="info">2025-08-01 16:05:10</div><table class="tableFile"><tr><td>2</td><td>Release</td><td><a href="release.htm">release.htm</a></td><td>EX-99.1</td></tr></table>'''


class DeskTests(unittest.TestCase):
    def test_newest_tag_and_same_fiscal_period(self):
        raw = fixture()
        raw['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'].append(annual(999, '2026-06-30', '2025-07-01'))
        facts = selected_facts(raw)
        self.assertEqual(facts['concepts']['revenue']['current']['tag'], 'us-gaap:Revenues')
        self.assertEqual(facts['concepts']['operating_income']['current']['val'], 30)
        self.assertEqual(facts['concepts']['revenue']['prior']['val'], 100)

    def test_quarter_not_mistaken_for_year_and_restated_value(self):
        raw = fixture()
        rows = raw['facts']['us-gaap']['Revenues']['units']['USD']
        rows.extend([annual(999, '2026-06-30', '2026-04-01'), annual(125, filed='2026-08-01')])
        self.assertEqual(selected_facts(raw)['concepts']['revenue']['current']['val'], 125)

    def test_arithmetic_and_current_debt(self):
        result = calculations(selected_facts(fixture()), 50)
        for name, expected in {'revenue_growth': .2, 'operating_margin': .25, 'return_on_average_equity': 20/90, 'debt_to_equity': .35, 'free_cash_flow': 30, 'price_to_earnings': 25}.items():
            self.assertAlmostEqual(result[name]['value'], expected)

    def test_missing_is_not_zero(self):
        raw = fixture()
        del raw['facts']['us-gaap']['LongTermDebtCurrent']
        self.assertIsNone(calculations(selected_facts(raw))['debt_to_equity']['value'])

    def test_zero_and_negative_eps(self):
        facts = selected_facts(fixture())
        facts['concepts']['revenue']['current']['val'] = 0
        facts['concepts']['diluted_eps']['current']['val'] = -1
        result = calculations(facts, 50)
        self.assertIsNone(result['operating_margin']['value'])
        self.assertIsNone(result['price_to_earnings']['value'])

    def test_index_and_table_text(self):
        accepted, urls = index_details(INDEX, 'https://www.sec.gov/folder/index.html')
        self.assertEqual(accepted, '2025-08-01 16:05:10')
        self.assertEqual(urls, ['https://www.sec.gov/folder/release.htm'])
        text = plain_text('<ix:header>HIDDEN</ix:header><p>Quarter ended June 30</p><table><tr><td>Total revenue</td><td>120</td></tr><tr><td>Diluted EPS</td><td>2.00</td></tr></table>')
        self.assertNotIn('HIDDEN', text)
        self.assertIn('Total revenue | 120', text)

    def test_user_agent(self):
        client = SECClient('Test Contact test@example.invalid')
        with patch.object(client.session, 'get') as get:
            get.return_value.status_code = 200
            client.get('https://www.sec.gov/files/company_tickers.json')
            self.assertEqual(client.session.headers['User-Agent'], 'Test Contact test@example.invalid')

    def test_full_pipeline_and_history(self):
        class Response:
            def __init__(self, text):
                self.text = text
                self.content = text.encode()
        class Client:
            def resolve(self, ticker):
                return {'ticker': ticker, 'name': 'Synthetic Issuer', 'cik': 1}
            def json(self, url):
                if 'companyfacts' in url:
                    return fixture()
                def block(forms, documents, accessions):
                    return {'form': forms, 'primaryDocument': documents, 'accessionNumber': accessions, 'filingDate': ['2025-08-01'] * len(forms)}
                if 'older.json' in url:
                    return block(['10-K'], ['annual.htm'], ['0000000001-25-000001'])
                return {'filings': {'recent': block(['8-K', '8-K', '10-Q'], ['other.htm', 'earnings.htm', 'quarter.htm'], ['0000000001-25-000004', '0000000001-25-000003', '0000000001-25-000002']), 'files': [{'name': 'older.json', 'filingTo': '2025-07-01'}]}}
            def get(self, url):
                if url.endswith('-index.html'):
                    return Response(INDEX)
                if url.endswith('earnings.htm'):
                    return Response('<p>Item 2.02 Results of Operations and Financial Condition</p>')
                if url.endswith('annual.htm'):
                    from test_annual_revenue import source
                    return Response(source())
                if url.endswith('release.htm'):
                    return Response('<p>Quarter ended June 30</p><p>Total revenue was 120.</p><p>Diluted EPS was 2.00.</p>')
                return Response('<p>Other filing</p>')
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            desk = Desk(Client(), 'TEST', ['PEER'], 50, directory)
            for i in range(1, 8):
                getattr(desk, f'step{i}')()
            self.assertEqual(desk.filings['8-K']['primaryDocument'], 'earnings.htm')
            for name in ['10-K.txt', '10-Q.txt', '8-K.txt', 'earnings_release_99_1.txt', 'facts.json', 'calculations.json', 'peers.json']:
                self.assertTrue((desk.folder / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
