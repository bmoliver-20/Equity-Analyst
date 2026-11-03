"""Offline tests only: injected models, blocked sockets, no credentials."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import report_workflow as desk
from lab04_team import Team, SCHEMAS, new_folder, evidence_copy
from lab04_verifier import (inventory, thesis_mask, check_claim, verify, saved_evidence,
                            evaluate_expression, evidence_value)
from test_report_workflow import MockRoles, data_fixture


def bundle():
    return {'saved_facts':{'F1':{'val':10.25,'unit':'USD/shares','tag':'us-gaap:EarningsPerShareDiluted',
            'start':'2025-01-01','end':'2025-12-31','accn':'test-k','url':'https://www.sec.gov/test'},
            'F2':{'val':120000000,'unit':'USD','tag':'us-gaap:Revenues','start':'2025-01-01','end':'2025-12-31','accn':'test-k','url':'https://www.sec.gov/test'},
            'F3':{'val':100000000,'unit':'USD','tag':'us-gaap:Revenues','start':'2024-01-01','end':'2024-12-31','accn':'test-k','url':'https://www.sec.gov/test'}},
            'filing_texts':{'10-K.txt:L1':{'text':'Diluted EPS | 10.25 | 9.50','accession':'test-k','url':'https://www.sec.gov/test'}}}


def ref(fid='F1',value='10.25',unit='USD/shares',start='2025-01-01',end='2025-12-31'):
    return {'fact_id':fid,'line_id':'','quote':'','value':value,'unit':unit,'start':start,'end':end}


def claim(key='N1'):
    return {'token_id':key,'kind':'fact','definition':'GAAP diluted EPS','period':'2025-12-31',
            'report_source':'EarningsPerShareDiluted','meaning':'supported','evidence':[ref()],
            'formula':'','input_token_ids':[],'core_claim':'5'}


class MockTeam:
    is_mock=True
    def __init__(self,revision=False,repeat=False,fail=None):
        self.old=MockRoles();self.revision=revision;self.repeat=repeat;self.fail=fail;self.calls=[]
    def generate_structured(self,role,packet,instructions,schema):
        self.calls.append((role,deepcopy(packet)))
        if role==self.fail:raise desk.ModelCallError(role,'network_or_timeout')
        if role == 'Verifier':
            return {'reviews': [{'token_id': claim['token_id'], 'meaning': 'supported',
                                 'definition': claim['claim']['definition'],
                                 'period': claim['claim']['period']}
                                for claim in packet['context']['semantic_claims']]}
        out=self.old.generate(role,packet)
        if role=='Strategy Manager':
            request=self.revision and (packet['context']['can_revise'] or self.repeat)
            out.update(decision='revise' if request else 'approve',revision_role='',
                revision_requests=[{'role':r,'instructions':'Revise within your evidence boundary.'} for r in desk.ROLES[:3]] if request else [])
        return out


class GraphTests(unittest.TestCase):
    def run_team(self,model,verify_only=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);source=root/'source';source.mkdir();dest=root/'run';dest.mkdir()
        report='Filings read: test-k\nRun time: test\n\nGAAP diluted EPS 10.25 EarningsPerShareDiluted\n'
        (source/'report.md').write_text(report)
        team=Team(dest,model,source=source,verify_only=verify_only)
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')),patch('lab04_team.evidence_copy'),patch('lab04_team.desk.prepare',return_value=data_fixture()),patch('lab04_team.desk.load',return_value={}),patch('lab04_team.saved_evidence',return_value=bundle()),contextlib.redirect_stdout(io.StringIO()):
            result=team.run()
        return team,result

    def test_fixed_order_and_mandatory_verifier(self):
        model=MockTeam();team,result=self.run_team(model)
        self.assertEqual(result['node_order'],['steps',*desk.ROLES,'Verifier'])
        self.assertTrue((team.folder/'report.md').exists())
        self.assertTrue((team.folder/'verified_report.md').exists())
        self.assertIn('MOCK RESPONSES',(team.folder/'verified_report.md').read_text())
        packets={r:p for r,p in model.calls}
        self.assertEqual(set(packets['Research Analyst']['context']),{'sources'})
        self.assertEqual(set(packets['Investment Advisor']['context']),{'research_analyst','financial_analyst'})
        vp=packets['Verifier']['context']
        self.assertEqual(set(vp), {'semantic_claims'})
        self.assertNotIn('Monitor the business', json.dumps(vp))
        self.assertNotIn('Investment Recommendation', json.dumps(vp))
        for _,packet in model.calls:self.assertEqual(set(packet),{'task','context','expected_output'})

    def test_all_roles_revision_and_two_call_cap(self):
        team,result=self.run_team(MockTeam(revision=True,repeat=True))
        for role,count in result['calls'].items():self.assertLessEqual(count,2)
        self.assertEqual(result['calls']['Verifier'],2)
        self.assertEqual(result['calls']['Strategy Manager'],2)
        self.assertIn('Revision budget exhausted; no third role call',result['errors'])
        for i,node in enumerate(result['node_order']):
            if node=='Strategy Manager':self.assertEqual(result['node_order'][i+1],'Verifier')

    def test_failed_role_still_reaches_verifier_no_false_success(self):
        team,result=self.run_team(MockTeam(fail='Research Analyst'))
        self.assertEqual(result['node_order'][-1],'Verifier')
        self.assertFalse(result['verification_completed'])
        self.assertIn('Verification unavailable',(team.folder/'verified_report.md').read_text())

    def test_verifier_failure_prevents_revision_calls(self):
        team,result=self.run_team(MockTeam(revision=True,fail='Verifier'))
        self.assertEqual(result['calls']['Strategy Manager'],1)
        self.assertFalse(result['verification_completed'])

    def test_verify_only_runs_no_other_node(self):
        model=MockTeam();team,result=self.run_team(model,True)
        self.assertEqual(result['node_order'],['Verifier'])
        self.assertEqual([r for r,_ in model.calls],['Verifier'])

    def test_new_folders_never_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            a=new_folder('Synthetic Issuer',d);b=new_folder('Synthetic Issuer',d)
            self.assertNotEqual(a,b)

    def test_copy_excludes_secrets_and_audits(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b';a.mkdir();b.mkdir()
            for name in ['.env','human_audit.md','report.md','10-K.txt']:(a/name).write_text('synthetic')
            evidence_copy(a,b)
            self.assertEqual(set(x.name for x in b.iterdir()),{'10-K.txt','source_manifest.json'})


class VerificationTests(unittest.TestCase):
    def test_exact_tag_period_and_eps_correction(self):
        report='Filings read: test\nRun time: test\nGAAP diluted EPS 11.25 EarningsPerShareDiluted\n'
        tokens=inventory(report);row=check_claim(tokens['N1'],claim(),bundle(),tokens,report)
        self.assertEqual(row['mark'],'wrong');self.assertEqual(row['correction'],'10.25')
        c=claim();c['evidence'][0]['end']='2024-12-31'
        self.assertEqual(check_claim(tokens['N1'],c,bundle(),tokens,report)['mark'],'unsupported')
        c=claim();c['evidence'][0]['value']='11.25'
        self.assertEqual(check_claim(tokens['N1'],c,bundle(),tokens,report)['mark'],'unsupported')

    def test_genuine_line_required_fabricated_quote_rejected(self):
        r=ref('',value='10.25');r.update(line_id='10-K.txt:L1',quote='Diluted EPS | 11.25 | 9.50')
        with self.assertRaises(ValueError):evidence_value(r,bundle())
        r['quote']='Diluted EPS   | 10.25 | 9.50'
        self.assertEqual(evidence_value(r,bundle())[0],10.25)

    def test_wrong_growth_recomputed_and_missing_definition_unsupported(self):
        report='Filings read: test\nRun time: test\nAnnual growth 24% from 120 and 100 USD million, Revenues.\n'
        tokens=inventory(report);c=claim();c.update(kind='ratio',definition='Annual growth',report_source='Revenues',
            formula='(x0-x1)/x1*100',input_token_ids=['N2','N3'],core_claim='2',
            evidence=[ref('F2','120','USD million'),ref('F3','100','USD million','2024-01-01','2024-12-31')])
        row=check_claim(tokens['N1'],c,bundle(),tokens,report)
        self.assertEqual(row['mark'],'wrong');self.assertEqual(row['correction'],'20%')
        self.assertIn('x0=120',row['arithmetic'])
        c['definition']=''
        self.assertEqual(check_claim(tokens['N1'],c,bundle(),tokens,report)['mark'],'unsupported')

    def test_no_source_is_unsupported_even_when_value_matches(self):
        report='Filings read: test\nRun time: test\nEPS 10.25\n';tokens=inventory(report)
        c=claim();c['report_source']=''
        row=check_claim(tokens['N1'],c,bundle(),tokens,report)
        self.assertEqual(row['mark'],'unsupported')
        self.assertTrue(row['sources'])

    def test_model_ambiguity_blocks_correction(self):
        report='Filings read: test\nRun time: test\nEPS 11.25 EarningsPerShareDiluted\n';tokens=inventory(report)
        for meaning in ['ambiguous','wrong_definition']:
            c=claim();c['meaning']=meaning
            row=check_claim(tokens['N1'],c,bundle(),tokens,report)
            self.assertEqual(row['mark'],'unsupported');self.assertIsNone(row['correction'])

    def test_rounding_only_for_calculated_values_not_direct_facts(self):
        report='Filings read: test\nRun time: test\nEPS 10.3 EarningsPerShareDiluted\n';tokens=inventory(report)
        self.assertEqual(check_claim(tokens['N1'],claim(),bundle(),tokens,report)['mark'],'wrong')

    def test_omission_is_unsupported_and_header_preserved(self):
        report='Filings read: test\nRun time: test\nEPS 10.25 EarningsPerShareDiluted\n'
        out,result=verify(report,bundle(),lambda role,packet:{'reviews':[]})
        self.assertEqual(out.splitlines()[0],report.splitlines()[0])
        self.assertEqual(result['marks'][0]['mark'],'unsupported')

    def test_clean_supported_number_remains_unchanged(self):
        report='Filings read: test\nRun time: test\nEPS 10.25 EarningsPerShareDiluted\n'
        out,result=verify(report,bundle(),lambda role,packet:{'reviews':[{'token_id': item['token_id'], 'meaning':'supported', 'definition':item['claim']['definition'], 'period':item['claim']['period']} for item in packet['context']['semantic_claims']]})
        self.assertTrue(result['model_checks_completed'])
        self.assertTrue(out.endswith('EPS 10.25 EarningsPerShareDiluted\n'))

    def test_thesis_and_monitoring_proposals_excluded(self):
        report='Filings read: test\nRun time: test\n## Future Developments and Strategic Recommendations\n\n**Analytical recommendations, not company guidance.** SECRET THESIS 55\n\n## Investment Recommendation\nSECRET THESIS 66\n'
        self.assertNotIn('SECRET THESIS',thesis_mask(report))

    def test_arithmetic_rejects_code_and_zero_denominator(self):
        with self.assertRaises(ValueError):evaluate_expression('__import__("os")',[])
        with self.assertRaises(ArithmeticError):evaluate_expression('x0/x1',[1,0])


class AdditionalGraphTests(unittest.TestCase):
    def test_only_verifier_can_end_graph(self):
        with tempfile.TemporaryDirectory() as d:
            team=Team(Path(d),MockTeam())
            edges=team.graph().get_graph().edges
            self.assertTrue(any(e.source=='Verifier' and e.target=='__end__' for e in edges))
            self.assertTrue(all(e.source=='Verifier' for e in edges if e.target=='__end__'))
            self.assertEqual([e.target for e in edges if e.source=='Strategy Manager'],['Verifier'])

    def test_clean_eleven_core_categories_with_mocked_meaning(self):
        # Synthetic independent facts; proves no automatic false flag for supported core numbers.
        b=bundle();lines=['Filings read: test-k','Run time: offline']
        responses=[]
        for i in range(1,12):
            value=str(30+i)
            b['saved_facts'][f'C{i}']={**b['saved_facts']['F1'],'val':value,'tag':f'us-gaap:TestMetric{i}'}
            lines.append(f'Core metric {value} USD/share; source us-gaap:TestMetric{i}.')
        report='\n'.join(lines)+'\n';tokens=inventory(report)
        for i,(key,t) in enumerate(tokens.items(),1):
            c=claim(key);c.update(core_claim=str(i),definition='Core metric',report_source=f'us-gaap:TestMetric{i}',
                evidence=[ref(f'C{i}',str(30+i),'USD/share')])
            responses.append(c)
        _,result=verify(report,b,lambda role,packet:{'reviews':[{'token_id': item['token_id'], 'meaning':'supported', 'definition':item['claim']['definition'], 'period':item['claim']['period']} for item in packet['context']['semantic_claims']]})
        self.assertTrue(result['model_checks_completed'])

    def test_real_seeded_copies_and_originals_preserved(self):
        root=Path(__file__).parent/'lab04_test_cases'
        candidates=sorted(root.glob('*/eps_error/test_case.json'))
        if not candidates:self.skipTest('Saved public fixture copies are not installed')
        batch=candidates[-1].parent.parent
        import hashlib
        for name in ['eps_error','invented_growth','clean_report']:
            p=batch/name;meta=json.loads((p/'test_case.json').read_text())
            original=Path(meta['source_report'])
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),meta['original_sha256'])
            self.assertEqual((p/'report.md').read_text().splitlines()[0],original.read_text().splitlines()[0])
            self.assertFalse(meta['model_verification_performed'])
        p=batch/'eps_error';meta=json.loads((p/'test_case.json').read_text())
        b=saved_evidence(p);report=(p/'report.md').read_text();tokens=inventory(thesis_mask(report))
        key=next(k for k,t in tokens.items() if t['text']==meta['seeded_eps'] and 'GAAP diluted EPS' in t['context'])
        fkey,row=next((k,r) for k,r in b['saved_facts'].items() if r['tag'].endswith(':EarningsPerShareDiluted') and str(r['val'])==meta['correct_eps'])
        c=claim(key);c.update(period=row['end'],evidence=[ref(fkey,meta['correct_eps'],row['unit'],row['start'],row['end'])])
        result=check_claim(tokens[key],c,b,tokens,report)
        self.assertEqual(result['mark'],'wrong');self.assertEqual(result['correction'],meta['correct_eps'])
        fabricated=next(x[2:] for x in report.splitlines() if x.startswith('> ') and meta['seeded_eps'] in x)
        self.assertNotEqual(fabricated,meta['real_source_quote'])
        self.assertEqual(b['filing_texts'][f"10-K.txt:L{meta['real_source_line']}"]['text'],meta['real_source_quote'])


class SavedRunIntegrationTests(unittest.TestCase):
    def test_two_full_offline_saved_runs_preserve_sources(self):
        sources=sorted((Path(__file__).parent/'lab04_test_cases').glob('*/eps_error'))
        if not sources:self.skipTest('Saved evidence fixtures unavailable')
        source=sources[-1]
        original=(source/'report.md').read_bytes()
        company=json.loads((source/'company.json').read_text())
        peers=list(json.loads((source/'peers.json').read_text()))
        import hashlib
        with tempfile.TemporaryDirectory() as d, patch('socket.socket',side_effect=AssertionError('Network forbidden')), contextlib.redirect_stdout(io.StringIO()):
            first=None;first_hash=None
            for index in range(2):
                folder=new_folder(company['ticker'],d)
                result=Team(folder,MockTeam(),source=source,ticker=company['ticker'],peers=peers).run()
                self.assertEqual(result['node_order'],['steps',*desk.ROLES,'Verifier'])
                self.assertEqual(result['errors'],[])
                self.assertEqual(result['mode'],'offline mock')
                text=(folder/'report.md').read_text()
                self.assertIn('P/E and price-based valuation are unavailable',text)
                self.assertIn('annual.current_debt',text)
                self.assertEqual((folder/'verified_report.md').read_text().splitlines()[0],text.splitlines()[0])
                if first is None:
                    first=folder
                    first_hash=hashlib.sha256((first/'report.md').read_bytes()).hexdigest()
                else:
                    self.assertNotEqual(folder,first)
                    self.assertEqual(hashlib.sha256((first/'report.md').read_bytes()).hexdigest(),first_hash)
        self.assertEqual((source/'report.md').read_bytes(),original)

if __name__=='__main__':unittest.main()
