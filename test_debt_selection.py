import unittest
from debt_selection import select_debt

END='2026-01-31'
ACC='synthetic-filing'

def raw(values):
    return {'facts':{'us-gaap':{tag:{'units':{'USD':[{'val':value,'end':END,'accn':ACC,'form':'10-K'}]}} for tag,value in values.items()}}}

class DebtTests(unittest.TestCase):
    def test_target_structure_no_double_count(self):
        # Synthetic balances reproducing the reported aggregate/lease structure.
        d=select_debt(raw({'LongTermDebt':1000,'LongTermDebtAndCapitalLeaseObligations':1050,'LongTermDebtAndCapitalLeaseObligationsCurrent':150,'FinanceLeaseLiabilityNoncurrent':180,'FinanceLeaseLiabilityCurrent':20}),END,ACC)
        self.assertEqual(d['current_debt_only']['val'],130)
        self.assertEqual(d['noncurrent_debt_only']['val'],870)
        self.assertEqual(d['total_debt_only']['val'],1000)
        self.assertEqual(d['total_debt_including_finance_leases']['val'],1200)
        self.assertEqual(d['reported']['LongTermDebt']['status'],'reported')
        self.assertEqual(d['current_debt_only']['status'],'calculated')
        self.assertEqual(len(d['current_debt_only']['inputs']),2)

    def test_aggregate_never_added_to_current(self):
        d=select_debt(raw({'LongTermDebt':1000,'LongTermDebtCurrent':150}),END,ACC)
        self.assertIsNone(d['total_debt_only'])
        self.assertIn('Aggregate LongTermDebt',d['unavailable_reason'])

    def test_lease_inclusive_not_mixed(self):
        d=select_debt(raw({'LongTermDebtNoncurrent':900,'LongTermDebtAndCapitalLeaseObligationsCurrent':150}),END,ACC)
        self.assertIsNone(d['total_debt_only'])

    def test_direct_pair(self):
        d=select_debt(raw({'LongTermDebtNoncurrent':900,'LongTermDebtCurrent':150,'FinanceLeaseLiabilityCurrent':20}),END,ACC)
        self.assertEqual(d['total_debt_only']['val'],1050)
        self.assertEqual(d['current_debt_only']['status'],'reported')

    def test_same_filing_required(self):
        r=raw({'LongTermDebtNoncurrent':900,'LongTermDebtCurrent':150})
        r['facts']['us-gaap']['LongTermDebtCurrent']['units']['USD'][0]['accn']='other'
        self.assertIsNone(select_debt(r,END,ACC)['total_debt_only'])

    def test_conflicting_direct_and_derived(self):
        d=select_debt(raw({'LongTermDebtNoncurrent':900,'LongTermDebtCurrent':150,'LongTermDebtAndCapitalLeaseObligationsCurrent':200,'FinanceLeaseLiabilityCurrent':20}),END,ACC)
        self.assertIsNone(d['total_debt_only'])
        self.assertIn('mismatch',d['unavailable_reason'])

    def test_negative_derivation_unavailable(self):
        d=select_debt(raw({'LongTermDebtNoncurrent':900,'LongTermDebtAndCapitalLeaseObligationsCurrent':10,'FinanceLeaseLiabilityCurrent':20}),END,ACC)
        self.assertIsNone(d['total_debt_only'])

    def test_explicit_zero_valid_missing_not_zero(self):
        d=select_debt(raw({'LongTermDebtNoncurrent':900,'LongTermDebtCurrent':0}),END,ACC)
        self.assertEqual(d['total_debt_only']['val'],900)
        self.assertIsNone(select_debt(raw({'LongTermDebtNoncurrent':900}),END,ACC)['total_debt_only'])

    def test_short_term_footnote_tag_not_current_long_term(self):
        r=raw({'LongTermDebtNoncurrent':399099000,'LongTermDebtCurrent':120000000})
        evidence=[{'tag':'us-gaap:'+tag,'val':val,'end':END,'accn':ACC,'source_label':label,
                   'source_url':'https://www.sec.gov/synthetic.htm'}
                  for tag,val,label in [('LongTermDebtNoncurrent',399099000,'Long-term debt'),
                                        ('LongTermDebtCurrent',120000000,'Less: Short-term debt')]]
        d=select_debt(r,END,ACC,evidence)
        self.assertIsNone(d['current_debt_only'])
        self.assertIsNone(d['total_debt_only'])
        self.assertEqual(d['noncurrent_debt_only']['val'],399099000)
        self.assertEqual(d['excluded_current_candidates'][0]['val'],120000000)
        self.assertIn('short-term',d['unavailable_reason'])
        self.assertEqual(d['reported']['LongTermDebtCurrent']['sources'],[evidence[1]])

    def test_html_evidence_required_when_provided(self):
        self.assertIsNone(select_debt(raw({'LongTermDebtNoncurrent':900,'LongTermDebtCurrent':150}),END,ACC,[])['total_debt_only'])

if __name__=='__main__':unittest.main()
