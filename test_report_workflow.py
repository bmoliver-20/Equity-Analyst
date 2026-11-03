"""All model responses are mocked. No credentials or external services used."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from report_workflow import (CORE, ROLES, TOPICS, SECTIONS, GeminiModel, ReportError,
                             quarter_metrics, run_report, schema_check, SCHEMAS, validate, prepare)


def data_fixture():
    sources={f'10-K.txt:L{i}': {'text':text,'file':'10-K.txt','line':i,'url':'https://www.sec.gov/example.htm','accession':'synthetic-k','section':'business'}
             for i,text in enumerate(['The issuer operates membership stores.', 'The issuer competes through low prices.', 'Expansion may depend on demand.', 'New stores may support growth.', 'The issuer opened stores during the period.'],1)}
    metrics={k:{'value':10.0,'unit':'USD','definition':'Synthetic evidence','sources':[{'url':'https://www.sec.gov/example.htm','accession':'synthetic-k','tag':'us-gaap:Revenues','end':'2025-12-31','start':'2025-01-01'}],'formula':None} for k in CORE}
    metrics['ratio.price_to_earnings']={'value':None,'unit':'multiple','definition':'P/E','sources':[],'formula':'Unavailable: no price supplied'}
    metrics['peer.PEER.operating_margin']={'value':.1,'unit':'fraction','definition':'Operating income / total revenue','sources':[],'formula':'10 / 100 × 100 = 10%'}
    return {'company':{'ticker':'TEST','cik':1},'filings':{form:{'accessionNumber':'synthetic-'+form,'document_url':'https://www.sec.gov/'+form,'exhibit_99_1_urls':['https://www.sec.gov/release.htm']} for form in ['10-K','10-Q','8-K']},'sources':sources,'metrics':metrics,'price':None}


class MockRoles:
    is_mock = True
    def __init__(self, revision=None, repeat=False, bad_quote=False, omit_metric=False):
        self.calls=[];self.revision=revision;self.repeat=repeat;self.bad_quote=bad_quote;self.omit_metric=omit_metric
        self.revised=False

    def generate(self,role,packet):
        self.calls.append((role,deepcopy(packet)))
        if packet.get('revision'):self.revised=True
        if role=='Research Analyst':
            sources=list(packet['context']['sources'].items())
            result={topic:[{'text':sources[i%len(sources)][1]['text'],'source_id':sources[i%len(sources)][0],'quote':sources[i%len(sources)][1]['text']}] for i,topic in enumerate(TOPICS)}
            if self.bad_quote and not self.revised:result['business_model'][0]['quote']='A fabricated line.'
            return result
        if role=='Financial Analyst':
            ids=list(packet['context']['required_metric_ids'])
            if self.omit_metric and not self.revised:ids.remove('quarter.revenue_growth')
            return {'metric_ids':ids,'analysis':[{'text':'The reported evidence should be assessed with its stated definitions and limitations.','metric_ids':['annual.revenue']}]}
        if role=='Investment Advisor':
            return {'recommendation':'Hold','thesis':'Monitor the business while assessing the reported revenue evidence.','deciding_metric_id':'annual.revenue','evidence_ids':['annual.revenue','R.business_model.0'],'limitations':'Price-based valuation is unavailable without a supplied share price.'}
        if self.revision and (not self.revised or self.repeat):
            return {'decision':'revise','revision_role':self.revision,'instructions':'Correct the failing part within the original task and evidence.','reason':'Draft needs correction.','sections':SECTIONS}
        return {'decision':'approve','revision_role':'','instructions':'','reason':'Draft consistent with supplied evidence.','sections':SECTIONS}


class WorkflowTests(unittest.TestCase):
    def run_mock(self,model,data=None):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        folder=Path(directory.name)
        with patch('socket.socket',side_effect=AssertionError('No network permitted')), contextlib.redirect_stdout(io.StringIO()):
            paths=run_report(folder,model,data=data or data_fixture())
        return folder,paths

    def test_four_roles_boundaries_report_and_blank_audit(self):
        mock=MockRoles();folder,(report,audit)=self.run_mock(mock)
        self.assertEqual([r for r,_ in mock.calls],ROLES)
        packets={r:p for r,p in mock.calls}
        self.assertEqual(set(packets['Research Analyst']['context']),{'sources'})
        self.assertEqual(set(packets['Financial Analyst']['context']),{'metrics','required_metric_ids'})
        self.assertEqual(set(packets['Investment Advisor']['context']),{'research_analyst','financial_analyst'})
        text=report.read_text();lines=text.splitlines()
        self.assertTrue(lines[0].startswith('Filings read:'))
        self.assertTrue(lines[1].startswith('Run time:'))
        self.assertEqual([l[3:] for l in lines if l.startswith('## ')],SECTIONS)
        self.assertIn('P/E and price-based valuation are unavailable',text)
        for line in audit.read_text().splitlines():
            if line.startswith('| ') and not line.startswith('| #'):
                self.assertEqual(line.split('|')[5].strip(),'')
        self.assertIn('Errors (Wrong + Unsupported): \n',audit.read_text())
        self.assertIn('Partner sign-off: \n',audit.read_text())

    def test_one_revision_and_advisor_refreshed(self):
        model=MockRoles(revision='Financial Analyst',omit_metric=True)
        folder,paths=self.run_mock(model)
        self.assertEqual([r for r,_ in model.calls],ROLES+['Financial Analyst','Investment Advisor','Strategy Manager'])
        self.assertEqual(sum('revision' in p for _,p in model.calls),1)
        self.assertFalse(model.calls[-1][1]['context']['can_revise'])
        first=model.calls[1][1]['context'];revised=model.calls[4][1]['context']
        self.assertEqual(first,revised)

    def test_second_revision_rejected(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ReportError):run_report(Path(d),MockRoles(revision='Investment Advisor',repeat=True),data=data_fixture())
            self.assertFalse(list(Path(d).glob('*_report.md')))
            self.assertTrue(list(Path(d).glob('*_audit.md')))

    def test_manager_cannot_approve_fake_quote(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ReportError):run_report(Path(d),MockRoles(bad_quote=True),data=data_fixture())
            self.assertFalse(list(Path(d).glob('*_report.md')))

    def test_fake_quote_can_be_revised_once(self):
        self.run_mock(MockRoles(revision='Research Analyst',bad_quote=True))

    def test_unknown_financial_number_rejected(self):
        d=data_fixture();out={'metric_ids':list(d['metrics']),'analysis':[{'text':'The ratio equals 123.','metric_ids':['annual.revenue']}]}
        self.assertTrue(validate('Financial Analyst',out,d))

    def test_advisor_cannot_use_unavailable_metric_or_raw_source(self):
        d=data_fixture();r=MockRoles().generate('Research Analyst',{'context':{'sources':d['sources']}})
        out={'recommendation':'Buy','thesis':'The business is undervalued.','deciding_metric_id':'ratio.price_to_earnings','evidence_ids':['10-K.txt:L1'],'limitations':'Valuation is unavailable.'}
        self.assertGreaterEqual(len(validate('Investment Advisor',out,d,r,{'metric_ids':list(d['metrics'])})),3)

    def test_gemini_adapter_is_mocked_and_sdk_errors_sanitized(self):
        client=Mock();valid={topic:[] for topic in TOPICS};client.models.generate_content.return_value.text=json.dumps(valid)
        adapter=GeminiModel(client,'configurable-model')
        self.assertEqual(adapter.generate('Research Analyst',{'task':'test','context':{},'expected_output':{}}),valid)
        kw=client.models.generate_content.call_args.kwargs
        self.assertEqual(kw['model'],'configurable-model')
        self.assertEqual(kw['config']['response_mime_type'],'application/json')
        client.models.generate_content.side_effect=RuntimeError('DO_NOT_PRINT_PROVIDER_REQUEST')
        with self.assertRaises(ReportError) as error:adapter.generate('Research Analyst',{})
        self.assertNotIn('DO_NOT_PRINT',str(error.exception))

    def test_sanitized_error_categories(self):
        from google.genai.errors import APIError
        import httpx
        from report_workflow import ModelCallError
        secret = 'SYNTHETIC_DO_NOT_EXPOSE'
        cases = [(APIError(code, {'error': {'message': secret}}), category)
                 for code, category in [(400,'api_request_rejected'),(401,'authentication'),
                 (403,'permission_or_authentication'),(404,'model_or_resource_not_found'),
                 (429,'quota_or_rate_limit'),(500,'api_error')]]
        cases += [(httpx.ConnectError(secret),'network_or_timeout'),
                  (httpx.ReadTimeout(secret),'network_or_timeout'),
                  (RuntimeError(secret),'sdk_or_local_error'),
                  (APIError(400, {'error': {'message': secret, 'details':
                    [{'reason':'API_KEY_INVALID'}]}}),'authentication')]
        for failure, category in cases:
            with self.subTest(category=category):
                client=Mock();client.models.generate_content.side_effect=failure
                with self.assertRaises(ModelCallError) as caught:
                    GeminiModel(client,'test').generate('Research Analyst',{})
                self.assertEqual(caught.exception.details['category'],category)
                self.assertNotIn(secret,str(caught.exception))
                self.assertNotIn(secret,json.dumps(caught.exception.details))

    def test_response_errors_separate_from_api_errors(self):
        from report_workflow import ModelCallError
        for text,category in [(None,'empty_response'),('', 'empty_response'),
                ('not JSON SYNTHETIC_SECRET','json_parse_error'),
                ('{"unexpected":"SYNTHETIC_SECRET"}','schema_validation_error')]:
            client=Mock();client.models.generate_content.return_value.text=text
            with self.assertRaises(ModelCallError) as caught:
                GeminiModel(client,'test').generate('Research Analyst',{})
            self.assertEqual(caught.exception.details['category'],category)
            self.assertNotIn('SYNTHETIC_SECRET',str(caught.exception))

    def test_failed_attempt_is_saved_without_provider_details(self):
        from google.genai.errors import APIError
        client=Mock();client.models.generate_content.side_effect=APIError(429,
            {'error':{'message':'SYNTHETIC_SECRET'}})
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), patch(
                'socket.socket',side_effect=AssertionError('No network')):
            with self.assertRaises(ReportError):
                run_report(Path(d),GeminiModel(client,'test'),data=data_fixture())
            text=next(Path(d).glob('*_workflow.json')).read_text()
            self.assertNotIn('SYNTHETIC_SECRET',text)
            record=json.loads(text)
            self.assertEqual(record['status']['error']['category'],'quota_or_rate_limit')
            self.assertEqual(len(record['calls']),1)
            self.assertEqual(record['calls'][0]['error']['http_status'],429)
            self.assertFalse(list(Path(d).glob('*_report.md')))

    def test_schema_rejects_extra_fields(self):
        self.assertTrue(schema_check({'unexpected':'field'},SCHEMAS['Research Analyst']))

    def test_no_files_overwritten(self):
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
            folder=Path(d);first,_=run_report(folder,MockRoles(),data=data_fixture());before=first.read_bytes()
            second,_=run_report(folder,MockRoles(),data=data_fixture())
            self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),before)

    def test_resume_from_failed_step(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            folder = Path(d)
            stem = 'lab03_20261102_120000_000000'
            wf_file = folder / f'{stem}_workflow.json'
            ra_output = {topic: [{'text': 'Claim text', 'source_id': '10-K.txt:L1', 'quote': 'The issuer operates membership stores.'}] for topic in TOPICS}
            saved_wf = {
                'status': {'status': 'failed; no report compiled', 'audit': f'{stem}_audit.md', 'error': {'role': 'Financial Analyst', 'category': 'api_error', 'http_status': 503}},
                'calls': [
                    {'role': 'Research Analyst', 'handoff': {'task': 'test'}, 'output': ra_output},
                    {'role': 'Financial Analyst', 'handoff': {'task': 'test'}, 'error': {'role': 'Financial Analyst', 'category': 'api_error', 'http_status': 503}}
                ]
            }
            wf_file.write_text(json.dumps(saved_wf), encoding='utf-8')
            mock = MockRoles()
            with patch('socket.socket', side_effect=AssertionError('No network permitted')):
                report, audit = run_report(folder, mock, data=data_fixture(), resume_from=wf_file)
            called_roles = [r for r, _ in mock.calls]
            self.assertNotIn('Research Analyst', called_roles)
            self.assertIn('Financial Analyst', called_roles)
            self.assertIn('Investment Advisor', called_roles)
            self.assertIn('Strategy Manager', called_roles)
            self.assertTrue(report.exists())
            self.assertEqual(report.name, f'{stem}_report.md')
            self.assertEqual(audit.name, f'{stem}_audit.md')


class QuarterTests(unittest.TestCase):
    def fixture(self):
        def record(label,values,unit):
            return {'source_url':'https://www.sec.gov/release','source_line':label,'header_lines':['Three Months Ended','2026 | 2025'],'units_source':unit,
                    'values':[{'value':str(value),'period_kind':'quarter','period_end':end,'duration':'Three Months Ended','accounting_basis':'GAAP (reported)'} for value,end in values]}
        return {'revenue':[record('Total revenue | 120 | 100',[(120,'2026-06-30'),(100,'2025-06-30')],'Dollars in millions')],
                'diluted_eps':[record('Diluted EPS | 2 | 1',[(2,'2026-06-30'),(1,'2025-06-30')],'Dollars per share')]},'Total revenue | 120 | 100\nDiluted EPS | 2 | 1'

    def test_python_growth_and_units(self):
        records,text=self.fixture();m=quarter_metrics(records,text,'release-accession')
        self.assertEqual(m['quarter.revenue']['value'],120000000)
        self.assertAlmostEqual(m['quarter.revenue_growth']['value'],.2)
        self.assertEqual(m['quarter.diluted_eps']['value'],2)
        self.assertEqual(m['quarter.revenue']['sources'][0]['line'],1)

    def test_conflict_and_zero_prior_unavailable(self):
        records,text=self.fixture();records['revenue'][0]['values'][1]['value']='0'
        self.assertIsNone(quarter_metrics(records,text,'a')['quarter.revenue_growth']['value'])
        records,text=self.fixture();bad=deepcopy(records['revenue'][0]);bad['values'][0]['value']='121';records['revenue'].append(bad)
        self.assertIsNone(quarter_metrics(records,text,'a')['quarter.revenue']['value'])

    def test_adjusted_eps_and_ytd_excluded(self):
        records,text=self.fixture();records['diluted_eps'][0]['values'][0]['accounting_basis']='adjusted (non-GAAP)'
        self.assertIsNone(quarter_metrics(records,text,'a')['quarter.diluted_eps']['value'])
        records,text=self.fixture();records['revenue'][0]['values'][0]['period_kind']='year-to-date'
        self.assertIsNone(quarter_metrics(records,text,'a')['quarter.revenue_growth']['value'])

    def test_different_quarter_lengths_not_blended(self):
        records,text=self.fixture();records['revenue'][0]['values'][1]['duration']='Sixteen Weeks Ended'
        self.assertIsNone(quarter_metrics(records,text,'a')['quarter.revenue_growth']['value'])


if __name__=='__main__':unittest.main()
