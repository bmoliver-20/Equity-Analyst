"""Failure-path tests: synthetic provider errors, blocked network, no .env reads."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from google.genai.errors import APIError
from report_workflow import classify_api_error, ReportError
from lab04_verifier import verify, saved_evidence, semantic_batches, semantic_claim_packets
from lab04_team import Team
from verifier_prechecks import run_prechecks


def evidence(value='7.40'):
    return {'saved_facts':{'F1':{'tag':'us-gaap:EarningsPerShareDiluted','val':value,'unit':'USD/shares',
         'start':'2024-07-01','end':'2025-06-30','accn':'0001234567-25-000001','url':'https://www.sec.gov/example'}},
         'filing_texts':{'10-K.txt:L12':{'text':f'Diluted earnings per share | {value}',
             'accession':'0001234567-25-000001','url':'https://www.sec.gov/example'}}}


def report(value='8.40'):
    return ('Filings read: 10-K 0001234567-25-000001\nRun time: offline test\n\n'
            '| Annual fact | FY25 | Source |\n|---|---|---|\n'
            f'| GAAP diluted EPS | {value} | EarningsPerShareDiluted |\n\n'
            'Cited source: 10-K.txt:L12\n'
            f'> Diluted earnings per share | {value}\n')


def quota_error(message='Daily request quota exceeded. Retry after the reset.'):
    return APIError(429,{'error':{'message':message,'details':[
        {'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[
            {'quotaMetric':'generativelanguage.googleapis.com/generate_content_free_tier_requests',
             'quotaId':'GenerateRequestsPerDayPerProjectPerModel-FreeTier','quotaValue':'20',
             'quotaDimensions':{'private':'SHOULD_NOT_SAVE'}}]},
        {'@type':'type.googleapis.com/google.rpc.RetryInfo','retryDelay':'41.5s'}]}})


class ErrorDetailTests(unittest.TestCase):
    def test_quota_message_metric_limit_and_delay_retained(self):
        detail=classify_api_error('Verifier',quota_error()).details
        self.assertEqual(detail['message'],'Daily request quota exceeded. Retry after the reset.')
        self.assertEqual(detail['retry_delay'],'41.5s')
        self.assertEqual(detail['quota_violations'][0]['quota_limit'],'GenerateRequestsPerDayPerProjectPerModel-FreeTier')
        self.assertEqual(detail['quota_violations'][0]['quota_value'],'20')
        self.assertIn('generate_content_free_tier_requests',detail['quota_violations'][0]['quota_metric'])
        self.assertNotIn('SHOULD_NOT_SAVE',json.dumps(detail))

    def test_credentials_and_headers_are_removed(self):
        secret='private-test-key-value'
        message=f'Quota exhausted for key {secret}. API_KEY="small-key". https://example.test/?key={secret}\nRequest headers: Authorization: Bearer hidden-token'
        detail=classify_api_error('Verifier',quota_error(message),secrets=(secret,)).details
        encoded=json.dumps(detail)
        for forbidden in [secret,'small-key','hidden-token','Authorization','Request headers']:
            self.assertNotIn(forbidden,encoded)
        self.assertIn('Quota exhausted',detail['message'])

    def test_retry_after_is_whitelisted_not_header_collection(self):
        error=APIError(429,{'error':{'message':'Temporary rate limit'}},
            response=SimpleNamespace(headers={'retry-after':'12','authorization':'private','x-request-key':'private'}))
        detail=classify_api_error('Verifier',error).details
        self.assertEqual(detail['retry_delay'],'12s')
        self.assertNotIn('private',json.dumps(detail))
        self.assertNotIn('quota_violations',detail)

    def test_missing_detail_is_not_invented(self):
        detail=classify_api_error('Verifier',APIError(429,{})).details
        self.assertNotIn('retry_delay',detail)
        self.assertNotIn('quota_violations',detail)

    def test_structured_retry_duration(self):
        error=APIError(429,{'error':{'message':'Rate limit','details':[{'retryDelay':{'seconds':'3','nanos':250000000}}]}})
        self.assertEqual(classify_api_error('Verifier',error).details['retry_delay'],'3.25s')


class PartialCheckTests(unittest.TestCase):
    def test_checks_run_before_model_and_survive_failure(self):
        checkpoints=[]
        def failed(role,packet):
            self.assertTrue(checkpoints)
            self.assertTrue(any(c['status']=='mismatch' for c in checkpoints[0]['deterministic_checks']))
            self.assertTrue(any(mark['mark']=='wrong' for mark in checkpoints[0]['marks']))
            raise classify_api_error(role,quota_error())
        with patch('socket.socket',side_effect=AssertionError('No network')):
            text,result=verify(report(),evidence(),failed,checkpoint=lambda x:checkpoints.append(deepcopy(x)))
        self.assertFalse(result['model_checks_completed'])
        self.assertFalse(result['overall_verification_success'])
        self.assertEqual(result['model_judgments'],'incomplete')
        mark = next(row for row in result['marks'] if row['original'] == '8.40')
        self.assertEqual(mark['mark'], 'wrong')
        self.assertEqual(mark['correction'], '7.40')
        self.assertEqual(mark['citation'], '10-K.txt:L12')
        checks=result['deterministic_checks']
        numeric=next(c for c in checks if c['check']=='annual_tag_value')
        self.assertEqual(numeric['status'],'mismatch')
        self.assertEqual(numeric['reported'],'8.40')
        self.assertEqual(numeric['source_value'],'7.40')
        quote=next(c for c in checks if c['check']=='filing_line')
        self.assertEqual(quote['numeric_differences'],[{'reported':'8.40','source_value':'7.40'}])
        self.assertIn('Verification incomplete',text)
        self.assertEqual(text.splitlines()[0],report().splitlines()[0])
        self.assertTrue(text.endswith(report().partition('\n')[2]))

    def test_different_values_no_seed_constants(self):
        for actual,claimed in [('2.13','9.91'),('15.78','15.78')]:
            checks=run_prechecks(report(claimed),evidence(actual))
            row=next(c for c in checks if c['check']=='annual_tag_value')
            self.assertEqual(row['status'],'match' if actual==claimed else 'mismatch')
            self.assertEqual(row['source_value'],actual)

    def test_ambiguous_fact_remains_unresolved(self):
        data=evidence();data['saved_facts']['F2']={**data['saved_facts']['F1'],'val':'6.00'}
        row=next(c for c in run_prechecks(report(),data) if c['check']=='annual_tag_value')
        self.assertEqual(row['status'],'unresolved')
        self.assertNotIn('source_value',row)

    def test_arithmetic_retained_but_provenance_not_certified(self):
        text='Filings read: test\nRun time: test\n| Growth | (150 - 100) / 100 × 100 | 54% |\n'
        row=next(c for c in run_prechecks(text,evidence()) if c['check']=='quoted_arithmetic')
        self.assertEqual(row['calculated'],'50')
        self.assertEqual(row['status'],'mismatch')
        self.assertEqual(row['model_judgment'],'incomplete')

    def test_schema_failure_also_retains_code_checks(self):
        _,result=verify(report(),evidence(),lambda role,packet:{'invalid':'schema'})
        self.assertEqual(result['error']['category'],'schema_or_local_error')
        self.assertTrue(result['deterministic_checks'])
        self.assertFalse(result['model_checks_completed'])

    def test_team_writes_partial_result_before_call_and_failure_after(self):
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            folder=Path(directory)
            class FailingModel:
                def generate_structured(inner,*args):
                    saved=json.loads((folder/'deterministic_round_1.json').read_text())
                    self.assertTrue(saved['deterministic_checks'])
                    raise classify_api_error('Verifier',quota_error())
            team=Team(folder,FailingModel())
            with patch('lab04_team.saved_evidence',return_value=evidence()),patch('socket.socket',side_effect=AssertionError('No network')):
                state=team.verifier({'report':report(),'counts':{}})
            saved=json.loads((folder/'verification_round_1.json').read_text())
            node=json.loads(next(folder.glob('node_*')).read_text())
            self.assertEqual(node['output']['deterministic_checks'],saved['deterministic_checks'])
            self.assertEqual(saved['error']['retry_delay'],'41.5s')
            self.assertFalse(state['verification']['model_checks_completed'])
            self.assertFalse(saved['overall_verification_success'])
            self.assertIn('Verification incomplete',(folder/'verified_report.md').read_text())


class CompactSemanticPacketTests(unittest.TestCase):
    def seeded_case(self):
        root = Path(__file__).parent / 'lab04_test_cases'
        candidates = sorted(root.glob('*/eps_error'))
        if not candidates:
            self.skipTest('Prepared seeded case is unavailable')
        folder = candidates[-1]
        return folder, (folder / 'report.md').read_text(), saved_evidence(folder)

    def test_full_filing_texts_are_not_sent(self):
        folder, report_text, evidence_bundle = self.seeded_case()
        claims, _, _ = semantic_claim_packets(report_text, evidence_bundle)
        packet = {'context': {'semantic_claims': claims}}
        serialized = json.dumps(packet)
        self.assertNotIn('filing_texts', packet['context'])
        all_saved_lines = [row['text'] for row in evidence_bundle['filing_texts'].values()]
        self.assertGreater(len(all_saved_lines), 100)
        self.assertLess(sum(len(row['text']) for claim in claims
                            for row in claim['source_references']['filing_lines']),
                        sum(len(text) for text in all_saved_lines) // 10)
        self.assertTrue(all(claim['source_references']['filing_lines'] for claim in claims))
        # A shared filing identifier may appear in a line citation.  A sequence
        # of saved filing lines cannot appear unless whole filing text was sent.
        self.assertNotIn('\n'.join(all_saved_lines[:20]), serialized)

    def test_seeded_eps_packet_has_report_value_real_source_line_period_and_definition(self):
        _, report_text, evidence_bundle = self.seeded_case()
        claims, _, _ = semantic_claim_packets(report_text, evidence_bundle)
        item = next(claim for claim in claims if claim['claim']['report_value'] == '21.76'
                    and 'GAAP diluted EPS' in claim['claim']['definition'])
        self.assertIn('GAAP diluted EPS', item['claim']['definition'])
        self.assertIn('2025-09-01 through 2026-08-30', item['claim']['period'])
        self.assertIn('20.76', [str(fact['value']) for fact in item['source_references']['facts']])
        self.assertTrue(any('20.76 per diluted share' in row['text']
                            for row in item['source_references']['filing_lines']))

    def test_oversized_collection_splits_under_budget(self):
        claims = [{'token_id': f'N{i}', 'claim': {'text': 'x' * 220},
                   'source_references': {'filing_lines': [], 'facts': []}} for i in range(12)]
        batches = semantic_batches(claims, token_budget=400)
        self.assertGreater(len(batches), 1)
        self.assertEqual([claim['token_id'] for batch in batches for claim in batch],
                         [claim['token_id'] for claim in claims])
        for batch in batches:
            self.assertLessEqual((len(json.dumps({'claims': batch})) + 3) // 4, 400)

    def test_failed_batch_preserves_deterministic_checks_and_records_completion(self):
        callbacks = []
        def failed(role, packet):
            raise classify_api_error(role, quota_error())
        _, result = verify(report(), evidence(), failed,
                           batch_checkpoint=lambda record, packet: callbacks.append((record, packet)))
        self.assertTrue(result['deterministic_checks'])
        self.assertFalse(result['model_checks_completed'])
        self.assertEqual(callbacks[0][0]['status'], 'incomplete')
        self.assertTrue(callbacks[0][1]['context']['semantic_claims'])

    def test_seeded_eps_is_final_wrong_when_semantic_review_is_unavailable(self):
        _, report_text, evidence_bundle = self.seeded_case()
        def unavailable(role, packet):
            raise classify_api_error(role, quota_error())
        _, result = verify(report_text, evidence_bundle, unavailable)
        mark = next(row for row in result['marks'] if row['original'] == '21.76')
        self.assertEqual(mark['mark'], 'wrong')
        self.assertEqual(mark['correction'], '20.76')
        self.assertEqual(mark['citation'], '10-K.txt:L394')
        self.assertFalse(result['model_checks_completed'])

if __name__=='__main__':unittest.main()
