import unittest
from annual_revenue import revenue_evidence
from equity_desk import selected_facts, calculations, DataError
from test_equity_desk import fixture, annual


def source(label='Total revenues', tag='Revenues', definition='', dimensional=False):
    return f'''<p>{definition}</p><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
<xbrli:context id="now"><xbrli:entity>{'<xbrldi:explicitMember>segment</xbrldi:explicitMember>' if dimensional else ''}</xbrli:entity><xbrli:period><xbrli:startDate>2024-07-01</xbrli:startDate><xbrli:endDate>2025-06-30</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="prior"><xbrli:period><xbrli:startDate>2023-07-01</xbrli:startDate><xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period></xbrli:context>
<table><tr><td>{label}</td><td><ix:nonFraction name="us-gaap:{tag}" contextRef="now" unitRef="u">120</ix:nonFraction></td><td><ix:nonFraction name="us-gaap:{tag}" contextRef="prior" unitRef="u">100</ix:nonFraction></td></tr>
<tr><td>Operating income</td><td><ix:nonFraction name="us-gaap:OperatingIncomeLoss">30</ix:nonFraction></td></tr></table>'''


class RevenueTests(unittest.TestCase):
    def proof(self, html):
        return revenue_evidence(html, 'https://www.sec.gov/example.htm', '0000000001-25-000001')

    def test_total_wins_over_same_year_contract_sales(self):
        raw=fixture()
        raw['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units']['USD']=[annual(115), annual(95,'2024-06-30','2023-07-01')]
        result=selected_facts(raw,self.proof(source()))
        self.assertEqual(result['concepts']['revenue']['current']['val'],120)
        self.assertEqual(result['concepts']['revenue']['prior']['val'],100)
        self.assertAlmostEqual(calculations(result)['revenue_growth']['value'],.2)

    def test_contract_tag_valid_when_total_label(self):
        tag='RevenueFromContractWithCustomerExcludingAssessedTax'
        raw=fixture()
        raw['facts']['us-gaap'][tag]['units']['USD']=[annual(120),annual(100,'2024-06-30','2023-07-01')]
        result=selected_facts(raw,self.proof(source(tag=tag)))
        self.assertEqual(result['concepts']['revenue']['current']['tag'],'us-gaap:'+tag)

    def test_sales_requires_inclusive_definition(self):
        self.assertFalse(self.proof(source(label='Net sales')))
        proof=self.proof(source(label='Net sales',definition='Net Sales includes Merchandise Sales and revenues from other sources, including advertising.'))
        self.assertEqual(len(proof),2)
        self.assertIn('advertising',proof[0]['definition'])

    def test_segment_excluded(self):
        proof=self.proof(source(dimensional=True))
        self.assertEqual([p['end'] for p in proof],['2024-06-30'])

    def test_mismatched_value_not_accepted(self):
        proof=self.proof(source().replace('>120<','>999<'))
        proof=[p for p in proof if p['end']=='2025-06-30']
        with self.assertRaises(DataError):selected_facts(fixture(),proof)

    def test_conflicting_totals_unavailable(self):
        proof=self.proof(source())
        raw=fixture()
        raw['facts']['us-gaap']['Revenues']['units']['USD'].append(annual(121))
        proof.append({**proof[0],'val':121})
        with self.assertRaises(DataError):selected_facts(raw,proof)

if __name__=='__main__':unittest.main()
