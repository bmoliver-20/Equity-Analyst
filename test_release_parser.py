"""Regression tests with synthetic values and no issuer-specific branches."""
import unittest
from release_parser import extract_release, table_grid
from bs4 import BeautifulSoup


TABLE = '''<p>(dollars in millions, except per share data) (unaudited)</p>
<table>
<tr><th rowspan="2">Metric</th><th colspan="2">16 Weeks Ended</th><th colspan="2">52 Weeks Ended</th></tr>
<tr><th>August 30, 2026</th><th>August 31, 2025</th><th>August 30, 2026</th><th>August 31, 2025</th></tr>
<tr><td>Net sales</td><td>110</td><td>90</td><td>450</td><td>400</td></tr>
<tr><td>Membership fees</td><td>10</td><td>9</td><td>40</td><td>35</td></tr>
<tr><td>Total revenue</td><td>120</td><td>99</td><td>490</td><td>435</td></tr>
<tr><td colspan="5">NET INCOME PER COMMON SHARE:</td></tr>
<tr><td>Basic</td><td>2.20</td><td>1.90</td><td>8.50</td><td>7.00</td></tr>
<tr><td>Diluted</td><td>2.10</td><td>1.80</td><td>8.40</td><td>6.90</td></tr>
<tr><td colspan="5">Shares used in calculation (000's):</td></tr>
<tr><td>Diluted</td><td>500</td><td>510</td><td>520</td><td>530</td></tr>
</table>'''
URL = 'https://www.sec.gov/example.htm'


class ReleaseTests(unittest.TestCase):
    def test_total_and_eps_with_annual_comparatives(self):
        result = extract_release(TABLE, URL)
        revenue = result['revenue'][0]
        self.assertEqual([v['value'] for v in revenue['values']], ['120', '99', '490', '435'])
        self.assertEqual([v['period_kind'] for v in revenue['values']], ['quarter', 'quarter', 'annual', 'annual'])
        self.assertEqual(revenue['values'][0]['period_end'], '2026-08-30')
        self.assertEqual(revenue['source_url'], URL)
        self.assertEqual(revenue['basis'], 'reported, not calculated')
        self.assertEqual(revenue['source_line'], 'Total revenue | 120 | 99 | 490 | 435')
        self.assertEqual(len(result['diluted_eps']), 1)
        self.assertEqual(result['diluted_eps'][0]['values'][0]['value'], '2.10')
        self.assertEqual(result['diluted_eps'][0]['section_line'], 'NET INCOME PER COMMON SHARE:')

    def test_sales_never_substituted(self):
        html = TABLE.replace('<tr><td>Total revenue</td><td>120</td><td>99</td><td>490</td><td>435</td></tr>', '')
        self.assertEqual(extract_release(html, URL)['revenue'], [])

    def test_no_header_no_assignment(self):
        html = '<table><tr><td>Total revenue</td><td>123</td></tr><tr><td>Diluted EPS</td><td>5</td></tr></table>'
        self.assertEqual(extract_release(html, URL), {'revenue': [], 'diluted_eps': []})

    def test_annual_not_quarter(self):
        self.assertFalse(extract_release(TABLE.replace('16 Weeks Ended', '52 Weeks Ended'), URL)['revenue'])

    def test_rowspan_column_alignment(self):
        grid = table_grid(BeautifulSoup(TABLE, 'html.parser').table)
        self.assertEqual(grid[1]['grid'][0], 'Metric')
        self.assertEqual(grid[1]['cells'][0]['column'], 1)

    def test_currency_and_different_data_colspans(self):
        html = '''<table><tr><td></td><td colspan="3">Three Months Ended</td></tr>
<tr><td></td><td colspan="3">June 30, 2025</td></tr>
<tr><td>Total revenue</td><td colspan="2">123</td><td></td></tr>
<tr><td>Diluted EPS</td><td>$</td><td>1.25</td><td></td></tr></table>'''
        result = extract_release(html, URL)
        self.assertEqual(result['revenue'][0]['values'][0]['value'], '123')
        self.assertEqual(result['diluted_eps'][0]['values'][0]['value'], '1.25')

    def test_current_year_not_assumed_first(self):
        html = TABLE.replace('August 30, 2026', 'August 30, 2024')
        values = extract_release(html, URL)['revenue'][0]['values']
        self.assertEqual(values[0]['comparison'], 'comparative quarter')
        self.assertEqual(values[1]['comparison'], 'current quarter')

    def test_split_headers_exclude_percentage_and_preserve_ytd(self):
        html = """<p>Condensed Consolidated Statements of Income</p><table>
<tr><th></th><th colspan="3">Three Months Ended</th><th>Six Months Ended</th></tr>
<tr><th></th><th colspan="3">July 31,</th><th>July 31,</th></tr>
<tr><th>(Amounts in millions, except per share data)</th><th>2026</th><th>2025</th><th>Percent Change</th><th>2026</th></tr>
<tr><td>Total revenues</td><td>123</td><td>100</td><td>23</td><td>250</td></tr>
<tr><td>Diluted net income per common share</td><td>1.20</td><td>1.00</td><td>20</td><td>2.30</td></tr></table>"""
        result = extract_release(html, URL)
        values = result['revenue'][0]['values']
        self.assertEqual([v['value'] for v in values], ['123', '100', '250'])
        self.assertEqual([v['period_kind'] for v in values], ['quarter', 'quarter', 'year-to-date'])
        self.assertEqual(values[0]['period_end'], '2026-07-31')
        self.assertEqual(result['revenue'][0]['units_source'], '(Amounts in millions, except per share data)')
        self.assertEqual(result['diluted_eps'][0]['values'][0]['accounting_basis'], 'GAAP (reported)')
        self.assertEqual(len(result['revenue'][0]['header_lines']), 3)

    def test_reported_adjusted_separate_year_tables(self):
        def table(year):
            return f"""<table><tr><th></th><th>Three Months Ended July 31, {year} 1</th></tr>
<tr><td>Diluted earnings per share:</td><td></td></tr>
<tr><td>Reported EPS</td><td>$1.20</td></tr>
<tr><td>Adjusted EPS</td><td>$1.30</td></tr></table>"""
        result = extract_release(table(2026) + table(2025), URL)['diluted_eps']
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]['values'][0]['accounting_basis'], 'GAAP (reported)')
        self.assertEqual(result[1]['values'][0]['accounting_basis'], 'adjusted (non-GAAP)')
        self.assertEqual(result[2]['values'][0]['comparison'], 'comparative quarter')
        self.assertEqual(result[0]['values'][0]['duration'], 'Three Months Ended')

    def test_incomplete_date_stays_unavailable(self):
        html = '<table><tr><th></th><th>Three Months Ended</th></tr><tr><th></th><th>July 31,</th></tr><tr><td>Total revenues</td><td>123</td></tr></table>'
        self.assertFalse(extract_release(html, URL)['revenue'])

    def test_conflicting_headers_stay_unavailable(self):
        html = '<table><tr><th></th><th colspan="2">Three Months Ended</th></tr><tr><th></th><th>July 31, 2026</th><th>July 31, 2025</th></tr><tr><td>Total revenue</td><td colspan="2">123</td></tr></table>'
        self.assertFalse(extract_release(html, URL)['revenue'])

    def test_no_header_leak_across_tables(self):
        html = TABLE + '<table><tr><td>Total revenue</td><td>999</td></tr></table>'
        self.assertEqual(len(extract_release(html, URL)['revenue']), 1)


if __name__ == '__main__':
    unittest.main()
