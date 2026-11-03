"""Independent saved-evidence verifier. No network or credentials in this module."""
from __future__ import annotations
import ast
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import re
import unicodedata

from report_workflow import STRING, arr, obj, ReportError, schema_check

REFERENCE = obj({'fact_id': STRING, 'line_id': STRING, 'quote': STRING,
                 'value': STRING, 'unit': STRING, 'start': STRING, 'end': STRING})
CLAIM = obj({'token_id': STRING, 'kind': {'type':'string','enum':['fact','line','ratio','metadata']},
             'definition': STRING, 'period': STRING, 'report_source': STRING, 'meaning': {'type':'string','enum':['supported','ambiguous','wrong_definition']},
             'evidence': arr(REFERENCE), 'formula': STRING, 'input_token_ids': arr(STRING),
             'core_claim': {'type':'string','enum':['',*[str(i) for i in range(1,12)]]}})
VERIFIER_SCHEMA = obj({'claims': arr(CLAIM)})
SEMANTIC_REVIEW = obj({'token_id': STRING,
                       'meaning': {'type': 'string', 'enum': ['supported', 'ambiguous', 'wrong_definition']},
                       'definition': STRING, 'period': STRING})
SEMANTIC_SCHEMA = obj({'reviews': arr(SEMANTIC_REVIEW)})
SEMANTIC_INPUT_TOKEN_BUDGET = 20_000
SOURCE_WINDOW_RADIUS = 2


def normalize(text):
    return re.sub(r'[^\w.%+-]', '', unicodedata.normalize('NFKC',text).replace('−','-')).casefold()


def number(text):
    text=text.strip().replace(',','').replace('$','').replace('%','').replace('−','-')
    if text.startswith('(') and text.endswith(')'): text='-'+text[1:-1]
    value=Decimal(text)
    if not value.is_finite(): raise InvalidOperation
    return value


SCALES={'USD':Decimal(1),'USD million':Decimal(1000000),'USD billion':Decimal(1000000000),
        'USD thousand':Decimal(1000),'USD/share':Decimal(1),'USD/shares':Decimal(1),
        'fraction':Decimal(1),'percent':Decimal('.01'),'multiple':Decimal(1),'count':Decimal(1)}


def canonical(value, unit):
    if unit not in SCALES: raise ValueError('Unsupported unit')
    base='USD' if unit.startswith('USD') and '/' not in unit else 'USD/share' if '/' in unit else 'fraction' if unit in ('fraction','percent') else unit
    return number(str(value))*SCALES[unit],base


def thesis_mask(report):
    """Remove the Advisor section and explicit strategic-thesis blocks before any model sees it."""
    out=[];skip=False;paragraph_skip=False
    for line in report.splitlines(keepends=True):
        if line.startswith('## '):
            skip=line.strip()=='## Investment Recommendation'
            paragraph_skip=False
        if re.match(r'(Strategic recommendation \(qualitative judgment\):|\*\*Analytical recommendations, not company guidance\.\*\*|\*\*Analyst judgment\.\*\*)',line):
            paragraph_skip=True
        if not line.strip(): paragraph_skip=False
        out.append('\n' if skip or paragraph_skip else line)
    return ''.join(out)


TOKEN_RE=re.compile(r'(?<![\w])[-−]?\d[\d,]*(?:\.\d+)?%?(?![\w])')

def inventory(report):
    """Every numeric occurrence gets an ID; citations/dates are explicitly metadata, not claims."""
    tokens={};offset=0
    for line_no,line in enumerate(report.splitlines(keepends=True),1):
        if line_no<=2: offset+=len(line);continue
        spans=[]
        for pattern in [r'https?://\S+',r'\b\d{10}-\d{2}-\d{6}\b',r'\b\d{4}-\d{2}-\d{2}\b',r'\b(?:10-[KQ]|8-K)\b',
                        r'\b(?:FY|L)\d+\b',r'\b(?:p\.|pp\.|line|lines|Item|Exhibit)\s*[\d., -]+',
                        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)\s*\d{1,2}(?:,?\s*\d{4})?',
                        r'\b(?:fiscal|year|ended|versus|vs\.?|and|through)\s+(?:19|20)\d{2}\b']:
            spans.extend((m.start(),m.end()) for m in re.finditer(pattern,line,re.I))
        for m in TOKEN_RE.finditer(line):
            key=f'N{len(tokens)+1}'
            constant=(m.group()=='100' and bool(re.search(r'[×*]\s*$',line[:m.start()]))) or (
                m.group()=='2' and bool(re.search(r'/\s*$',line[:m.start()])) and bool(re.match(r'\s*\)',line[m.end():])))
            tokens[key]={'text':m.group(),'line':line_no,'start':offset+m.start(),'stop':offset+m.end(),
                         'metadata':constant or any(a<=m.start()<b for a,b in spans),'context':line.rstrip()}
        offset+=len(line)
    return tokens


def saved_evidence(folder):
    """Allowlist only saved filing texts/facts. Never read audits, roles, traces, or .env."""
    folder=Path(folder)
    filings=json.loads((folder/'filings.json').read_text())['selected']
    company=json.loads((folder/'company.json').read_text())
    lines={};facts={}
    for filename,form in [('10-K.txt','10-K'),('10-Q.txt','10-Q'),('8-K.txt','8-K'),('earnings_release_99_1.txt','8-K')]:
        path=folder/filename
        if not path.exists(): continue
        meta=filings[form]
        url=meta['exhibit_99_1_urls'][0] if filename.startswith('earnings') else meta['document_url']
        for i,text in enumerate(path.read_text().splitlines(),1):
            if text.strip():lines[f'{filename}:L{i}']={'text':text,'file':filename,'line':i,'accession':meta['accessionNumber'],'url':url}
    def walk(value,cik):
        if isinstance(value,dict):
            if all(k in value for k in ['tag','val','end','accn','unit']) and value.get('status')!='calculated':
                row={k:value.get(k) for k in ['tag','val','start','end','accn','unit','source_label','definition']}
                row['url']=f"https://www.sec.gov/Archives/edgar/data/{cik}/{row['accn'].replace('-','')}/{row['accn']}-index.html"
                if row not in facts.values():facts[f'F{len(facts)+1}']=row
            for child in value.values():walk(child,cik)
        elif isinstance(value,list):
            for child in value:walk(child,cik)
    walk(json.loads((folder/'facts.json').read_text()),company['cik'])
    peers=json.loads((folder/'peers.json').read_text()) if (folder/'peers.json').exists() else {}
    for peer in peers.values():
        if 'facts' in peer:walk(peer['facts'],peer['company']['cik'])
    user_inputs=folder/'user_inputs.json'
    if user_inputs.exists():
        supplied=json.loads(user_inputs.read_text()).get('price')
        if supplied is not None:
            facts[f'F{len(facts)+1}']={'val':supplied,'unit':'USD/share','tag':'user:price',
                'start':'','end':'','accn':'user-supplied --price','url':'',
                'definition':'User input, not a filing fact; price date not supplied'}
    # Peer annual HTML is already saved. Convert it locally with the existing text tool.
    from equity_desk import plain_text
    for path in sorted(folder.glob('annual_revenue_source_*.html')):
        cik=path.stem.rsplit('_',1)[-1]
        if int(cik)==int(company['cik']):continue
        matching=[x for x in facts.values() if f'/data/{int(cik)}/' in x['url']]
        if not matching:continue
        for i,text in enumerate(plain_text(path.read_text()).splitlines(),1):
            if text.strip():lines[f'{path.stem}.txt:L{i}']={'text':text,'file':path.name,'line':i,
                'accession':matching[0]['accn'],'url':matching[0]['url']}
    return {'filing_texts':lines,'saved_facts':facts}


def evaluate_expression(expression, values):
    """Small arithmetic language: x0..xN and 2/100; no eval, functions, or code."""
    tree=ast.parse(expression,mode='eval')
    def calc(node):
        if isinstance(node,ast.Expression):return calc(node.body)
        if isinstance(node,ast.Name) and re.fullmatch(r'x\d+',node.id):return values[int(node.id[1:])]
        if isinstance(node,ast.Constant) and type(node.value) is int and node.value in (2,100):return Decimal(node.value)
        if isinstance(node,ast.BinOp):
            a,b=calc(node.left),calc(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
        raise ValueError('Unsupported arithmetic')
    return calc(tree)


FORMULAS={'(x0-x1)/x1*100','x0/x1*100','x0/((x1+x2)/2)*100','(x0+x1)/x2','x0-x1','x0/x1','x0+x1'}

def evidence_value(ref, bundle):
    """Return a source value only when its exact tag-period or real line is established."""
    if ref['fact_id']:
        row=bundle['saved_facts'].get(ref['fact_id'])
        if not row or (row.get('start') or '')!=ref['start'] or row['end']!=ref['end']:
            raise ValueError('Exact fact period absent')
        expected,base=canonical(row['val'],row['unit'])
        proposed,pbase=canonical(ref['value'],ref['unit'])
        if (expected,base)!=(proposed,pbase):raise ValueError('Evidence value does not match saved fact exactly')
        source=(f"User-supplied --price (not a filing fact; price date not supplied): {row['val']} {row['unit']}"
                if row['tag']=='user:price' else
                f"[{row['accn']}]({row['url']}); {row['tag']}; {row.get('start') or 'instant'} through {row['end']}; {row['val']} {row['unit']}")
        if ref['line_id']:
            line=bundle['filing_texts'].get(ref['line_id'])
            if not line or line['accession']!=row['accn'] or normalize(ref['quote'])!=normalize(line['text']):
                raise ValueError('Supplemental filing quote is not real')
            source+=f"; [{ref['line_id']}]({line['url']}): {line['text']}"
        return proposed,pbase,source
    line=bundle['filing_texts'].get(ref['line_id'])
    if not line or not ref['quote'] or normalize(ref['quote'])!=normalize(line['text']):
        raise ValueError('Quoted source line absent from saved filing')
    candidates=[number(m.group()) for m in TOKEN_RE.finditer(line['text'])]
    if number(ref['value']) not in candidates:raise ValueError('Value absent from source line')
    if not ref['end']:raise ValueError('Source period unspecified')
    expected,base=canonical(ref['value'],ref['unit'])
    source=f"[{ref['line_id']}]({line['url']}); {line['accession']}; period {ref['start']} through {ref['end']}; {line['text']}"
    return expected,base,source


def _line_window(bundle, line_id, radius=SOURCE_WINDOW_RADIUS):
    """Return at most five already-saved lines from the cited filing only."""
    line = bundle['filing_texts'].get(line_id)
    if not line:
        return []
    prefix = line_id.rsplit(':L', 1)[0]
    line_number = line.get('line')
    if line_number is None:
        try:
            line_number = int(line_id.rsplit(':L', 1)[1])
        except (IndexError, ValueError):
            return []
    rows = []
    for number_ in range(max(1, line_number - radius), line_number + radius + 1):
        key = f'{prefix}:L{number_}'
        saved = bundle['filing_texts'].get(key)
        if saved:
            rows.append({'line_id': key, 'text': saved['text'], 'accession': saved['accession'],
                         'url': saved['url']})
    return rows


def _source_hints(report_lines, line_number, bundle):
    """Find source references in the report row and its small local context."""
    # Tags and line citations belong to the same report row; using neighbouring table
    # rows would attach unrelated statement facts to the claim.
    text = report_lines[line_number] if 0 <= line_number < len(report_lines) else ''
    line_ids = list(dict.fromkeys(re.findall(r'([\w.-]+\.txt:L\d+)', text)))
    tags = []
    for fact_id, row in bundle['saved_facts'].items():
        tag = row.get('tag', '')
        short = tag.split(':')[-1]
        if tag and (tag in text or re.search(r'(?<!\w)' + re.escape(short) + r'(?!\w)', text)):
            tags.append((fact_id, row))
    return line_ids, tags


def _all_tag_line_refs(report_lines, bundle):
    """Map fact tags to real filing line references named by the report."""
    mapping = {}
    for index, line in enumerate(report_lines):
        local = '\n'.join(report_lines[max(0, index - 2):index + 1])
        line_ids = re.findall(r'([\w.-]+\.txt:L\d+)', line)
        for fact_id, row in bundle['saved_facts'].items():
            tag = row.get('tag', '')
            if tag and (tag in local or re.search(r'(?<!\w)' + re.escape(tag.split(':')[-1]) + r'(?!\w)', local)):
                mapping.setdefault(fact_id, []).extend(line_ids)
    return {key: list(dict.fromkeys(value)) for key, value in mapping.items()}


def _fact_value_line_refs(token, fact, bundle):
    """Find one saved statement line that prints this report value for this fact's filing."""
    shown = token['text'].strip().lstrip('$')
    if not shown:
        return []
    # The report's display form is safer than converting a raw XBRL value: it
    # preserves the report's units and does not guess a scale.
    pattern = re.compile(r'(?<![\d.])' + re.escape(shown) + r'(?![\d.])')
    for line_id, line in bundle['filing_texts'].items():
        if line.get('accession') == fact['accn'] and pattern.search(line.get('text', '')):
            return [line_id]
    return []


def semantic_claim_packets(report, bundle):
    """Build compact model inputs. Filing texts are never placed in a model packet wholesale."""
    masked = thesis_mask(report)
    lines = masked.splitlines()
    tokens = inventory(masked)
    tag_line_refs = _all_tag_line_refs(lines, bundle)
    claims = []
    for token_id, token in tokens.items():
        if token['metadata']:
            continue
        line_ids, facts = _source_hints(lines, token['line'] - 1, bundle)
        if not line_ids and not facts:
            continue
        source_lines = []
        for line_id in line_ids:
            source_lines.extend(_line_window(bundle, line_id))
        fact_rows = []
        for fact_id, row in facts:
            related_line_ids = list(dict.fromkeys(
                line_ids + tag_line_refs.get(fact_id, []) + _fact_value_line_refs(token, row, bundle)))
            related_accessions = {bundle['filing_texts'][line_id]['accession'] for line_id in related_line_ids
                                  if line_id in bundle['filing_texts']}
            if related_accessions and row['accn'] not in related_accessions:
                continue
            # A report row can name a standard tag that also occurs in peer facts.
            # Without a cited filing line, retain only facts whose reported scale
            # can plausibly match this specific printed number.
            if not related_accessions:
                try:
                    stated = number(token['text'])
                    raw = Decimal(str(row['val']))
                    if not any(stated == raw / Decimal(scale)
                               for scale in (1, 1_000, 1_000_000, 1_000_000_000)):
                        continue
                except (InvalidOperation, ValueError):
                    continue
            fact_rows.append({'fact_id': fact_id, 'tag': row['tag'], 'value': row['val'], 'unit': row['unit'],
                              'start': row.get('start') or '', 'end': row['end'], 'accession': row['accn'],
                              'definition': row.get('definition') or row.get('source_label') or '',
                              'url': row['url']})
            for line_id in related_line_ids:
                source_lines.extend(_line_window(bundle, line_id))
        deduplicated = {row['line_id']: row for row in source_lines}
        source_lines = list(deduplicated.values())
        # A model semantic review needs a real, local filing excerpt.  Facts
        # without one remain available to deterministic checks but are not sent
        # as semantic model claims.
        if not source_lines:
            continue
        claim_text = '\n'.join(lines[max(0, token['line'] - 2):token['line'] + 1])
        fact_periods = list(dict.fromkeys(f"{fact['start'] or 'instant'} through {fact['end']}"
                                           for fact in fact_rows))
        fact_definitions = [fact['definition'] for fact in fact_rows if fact['definition']]
        claims.append({'token_id': token_id,
                       'claim': {'report_value': token['text'], 'report_line': token['line'],
                                 'text': claim_text,
                                 'definition': fact_definitions[0] if fact_definitions else token['context'],
                                 'period': '; '.join(fact_periods) if fact_periods else
                                           '\n'.join(lines[max(0, token['line'] - 3):token['line'] + 1])},
                       'source_references': {'filing_lines': source_lines, 'facts': fact_rows}})
    return claims, tokens, masked


def semantic_batches(claims, token_budget=SEMANTIC_INPUT_TOKEN_BUDGET):
    """Estimate conservatively from serialized JSON and never exceed the configured budget."""
    batches, current = [], []
    for claim in claims:
        candidate = current + [claim]
        estimated = (len(json.dumps({'claims': candidate}, ensure_ascii=False)) + 3) // 4
        if current and estimated > token_budget:
            batches.append(current)
            current = [claim]
        else:
            current = candidate
        if (len(json.dumps({'claims': current}, ensure_ascii=False)) + 3) // 4 > token_budget:
            raise ReportError('One compact semantic claim exceeds the configured input budget.')
    if current:
        batches.append(current)
    return batches


def _check_tokens(checks, tokens):
    """Attach deterministic results to the actual report occurrence without a hard-coded answer."""
    for check in checks:
        if 'token_id' in check:
            continue
        candidates = [key for key, token in tokens.items()
                      if not token['metadata'] and token['line'] == check.get('report_line')
                      and token['text'] == check.get('reported')]
        if len(candidates) == 1:
            check['token_id'] = candidates[0]
    return checks


def _deterministic_wrong_marks(checks, tokens):
    """Make final Wrong marks from exact filing conflicts before any model call."""
    marks = []
    for check in checks:
        if check.get('status') != 'mismatch' or not check.get('token_id') or 'source_value' not in check:
            continue
        token = tokens.get(check['token_id'])
        if not token or token['metadata']:
            continue
        # A quoted saved filing line may be a different report line from the
        # annual-table value. Match its explicit before/after numbers to retain
        # the most precise filing citation with the final deterministic mark.
        cited = next((line for line in checks if line.get('check') == 'filing_line'
                      and line.get('status') == 'mismatch'
                      and any(diff.get('reported') == check['reported']
                              and diff.get('source_value') == check['source_value']
                              for diff in line.get('numeric_differences', []))), None)
        citation = cited.get('source_id', '') if cited else ''
        sources = [citation, check.get('url', ''), cited.get('actual_quote', '') if cited else '']
        marks.append({'token_id': check['token_id'], 'report_line': token['line'],
                      'original': token['text'], 'mark': 'wrong',
                      'correction': check['source_value'], 'citation': citation,
                      'sources': [source for source in sources if source],
                      'reason': 'Deterministic filing evidence conflicts with the reported value.',
                      'core_claim': ''})
    # A source can create two identical deterministic checks; keep one final mark.
    return list({mark['token_id']: mark for mark in marks}.values())


def check_claim(token, claim, bundle, tokens, report):
    result={'token_id':claim['token_id'],'report_line':token['line'],'original':token['text'],
            'mark':'unsupported','correction':None,'sources':[],'reason':'Insufficient evidence',
            'core_claim':claim['core_claim']}
    if token['metadata']:
        result.update(mark='metadata',reason='Citation/date metadata; not a financial assertion');return result
    if claim['kind']=='metadata':return result
    if claim['meaning']!='supported' or not claim['definition'].strip() or not claim['period'].strip():
        result['reason']='Meaning, period, or definition is ambiguous or unsupported';return result
    try:
        cited=bool(claim['report_source'].strip()) and claim['report_source'] in report
        refs=claim['evidence']
        values=[evidence_value(ref,bundle) for ref in refs]
        if not values:raise ValueError('No source')
        result['sources']=[v[2] for v in values]
        if claim['kind']=='ratio':
            if normalize(claim['definition']) not in normalize(report):
                raise ValueError('Ratio definition is absent from report')
            expression=claim['formula'].replace(' ','')
            if expression not in FORMULAS:raise ValueError('Ratio definition is absent or unsupported')
            ids=claim['input_token_ids']
            if len(ids)!=len(values) or len(set(ids))!=len(ids):raise ValueError('Missing quoted inputs')
            quoted=[]
            for key,ref,(value,base,_) in zip(ids,refs,values):
                if key not in tokens or tokens[key]['metadata']:raise ValueError('Input is not a report number')
                stated,sbase=canonical(tokens[key]['text'],ref['unit'])
                if (stated,sbase)!=(value,base):raise ValueError('Quoted input differs from source')
                quoted.append(number(tokens[key]['text']))
            # Inputs must share units, except an explicit price/earnings ratio.
            if len({ref['unit'] for ref in refs})!=1:raise ValueError('Mixed ratio input units')
            expected=evaluate_expression(expression,quoted)
            result['arithmetic']=expression+' with '+', '.join(f'x{i}={v}' for i,v in enumerate(quoted))+f' = {expected}'
            places=len(token['text'].rstrip('%').split('.')[-1]) if '.' in token['text'] else 0
            expected=expected.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
        else:
            if len(values)!=1:raise ValueError('Conflicting/multiple direct sources')
            # The source unit is also the report display unit, explicitly reviewed by the model.
            expected=values[0][0]/SCALES[refs[0]['unit']]
        actual=number(token['text'])
        result['mark']=('correct' if actual==expected else 'wrong') if cited else 'unsupported'
        result['reason']='Exact source value and model meaning/period/definition agree' if actual==expected else 'Report value differs from the supported source or arithmetic'
        if not cited:result['reason']='No original source citation; supported source supplied in the correction table'
        if actual!=expected or not cited:
            corrected=format(expected,'f')
            if ',' in token['text']:corrected=format(expected,',f')
            if token['text'].endswith('%'):corrected+='%'
            result['correction']=corrected
    except (ValueError,InvalidOperation,ArithmeticError,SyntaxError,IndexError,KeyError):
        result['reason']='Source, exact period, unit, quoted inputs, or arithmetic could not be established'
        result['correction']=None
    return result


def verify(report, bundle, generate, checkpoint=None, batch_checkpoint=None):
    compact_claims, tokens, masked = semantic_claim_packets(report, bundle)
    from verifier_prechecks import run_prechecks, incomplete_report
    from report_workflow import ModelCallError
    independent = _check_tokens(run_prechecks(masked, bundle), tokens)
    deterministic_marks = _deterministic_wrong_marks(independent, tokens)
    partial={'deterministic_checks':independent,'model_checks_completed':False,
             'model_judgments':'incomplete','status':'incomplete','overall_verification_success':False,
             'marks':deterministic_marks}
    if checkpoint:checkpoint(partial)
    # The Verifier itself remains mandatory even if a minimal report has no
    # source-linked numbers.  Its one empty packet is still compact and lets the
    # provider record that the semantic pass was attempted.
    batches = semantic_batches(compact_claims) or [[]]
    reviews, batch_records = {}, []
    for number_, claims in enumerate(batches, 1):
        packet = {'task': (Path(__file__).parent/'roles/verifier.md').read_text(),
                  'context': {'semantic_claims': claims}, 'expected_output': SEMANTIC_SCHEMA}
        try:
            output = generate('Verifier', packet)
            if schema_check(output, SEMANTIC_SCHEMA):
                raise ReportError('Verifier semantic-batch schema validation failed')
            allowed = {claim['token_id'] for claim in claims}
            seen = set()
            for review in output['reviews']:
                if review['token_id'] in allowed and review['token_id'] not in seen:
                    reviews[review['token_id']] = review
                    seen.add(review['token_id'])
            record = {'batch': number_, 'status': 'completed', 'claim_count': len(claims),
                      'estimated_input_tokens': (len(json.dumps({'claims': claims}, ensure_ascii=False)) + 3) // 4,
                      'review_count': len(seen), 'model_response': output}
        except Exception as error:
            detail = error.details if isinstance(error, ModelCallError) else {'category': 'schema_or_local_error', 'role': 'Verifier'}
            record = {'batch': number_, 'status': 'incomplete', 'claim_count': len(claims),
                      'estimated_input_tokens': (len(json.dumps({'claims': claims}, ensure_ascii=False)) + 3) // 4,
                      'error': detail}
        batch_records.append(record)
        if batch_checkpoint:
            batch_checkpoint(record, packet)
    incomplete = [record for record in batch_records if record['status'] != 'completed']
    # Exact saved-filing conflicts are final code marks. Model semantics can add
    # context, but cannot downgrade, erase, or replace those corrections.
    rows = deterministic_marks
    final_wrong_tokens = {row['token_id'] for row in rows}
    checks_by_token = {}
    for check in independent:
        if check.get('token_id'):
            checks_by_token.setdefault(check['token_id'], []).append(check)
    for token_id, token in tokens.items():
        if token['metadata']:
            continue
        review = reviews.get(token_id)
        checks = checks_by_token.get(token_id, [])
        mismatch = next((check for check in checks if check['status'] == 'mismatch' and 'source_value' in check), None)
        match = next((check for check in checks if check['status'] == 'match'), None)
        if token_id in final_wrong_tokens:
            continue
        if not review:
            rows.append({'token_id': token_id, 'report_line': token['line'], 'original': token['text'],
                         'mark': 'unsupported', 'correction': None, 'sources': [],
                         'reason': 'Model semantic review omitted this sourced occurrence.', 'core_claim': ''})
            continue
        if review['meaning'] != 'supported':
            rows.append({'token_id': token_id, 'report_line': token['line'], 'original': token['text'],
                         'mark': 'unsupported', 'correction': None, 'sources': [],
                         'reason': 'Model semantic review found meaning, period, or definition ambiguous.', 'core_claim': ''})
        elif match:
            rows.append({'token_id': token_id, 'report_line': token['line'], 'original': token['text'],
                         'mark': 'correct', 'correction': None, 'sources': [match.get('url', '')],
                         'reason': 'Saved evidence and completed semantic review agree.', 'core_claim': ''})
        else:
            rows.append({'token_id': token_id, 'report_line': token['line'], 'original': token['text'],
                         'mark': 'unsupported', 'correction': None, 'sources': [],
                         'reason': 'No deterministic source check establishes this occurrence.', 'core_claim': ''})
    if incomplete:
        partial.update(marks=rows, semantic_batches=batch_records, semantic_claim_count=len(compact_claims),
                       error=incomplete[0]['error'])
        return incomplete_report(report, partial), partial
    # Apply supported numeric corrections by line-relative offsets in the unmasked original.
    original_lines=report.splitlines(keepends=True);masked_lines=masked.splitlines(keepends=True)
    for row in sorted(rows,key=lambda r:tokens[r['token_id']]['start'],reverse=True):
        if row['correction'] is None:continue
        t=tokens[row['token_id']];i=t['line']-1
        start=t['start']-sum(len(x) for x in masked_lines[:i]);stop=start+len(t['text'])
        original_lines[i]=original_lines[i][:start]+row['correction']+original_lines[i][stop:]
    corrected=''.join(original_lines)
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    table=['','Automated verification — model and code checks; not human verification.',
           '| Occurrence / report line | Report | Mark | Supported correction | Evidence / arithmetic / limitation |',
           '|---|---|---|---|---|']
    for row in rows:
        evidence='; '.join(row['sources'])+'; '+row.get('arithmetic',row['reason'])
        table.append('| '+' | '.join(map(cell,[f"{row['token_id']} / {row['report_line']}",row['original'],row['mark'],row['correction'] or '',evidence]))+' |')
    table+=['','Investment Advisor thesis excluded. Unsupported entries without sufficient evidence remain unchanged.','']
    first,sep,rest=corrected.partition('\n')
    return first+'\n'+'\n'.join(table)+rest,{'marks':rows,'model_checks_completed':True,
          'deterministic_checks':independent,'semantic_batches':batch_records,
          'semantic_claim_count':len(compact_claims),'model_judgments':'completed','status':'complete',
          'core_claims':{str(i):[r['mark'] for r in rows if r['core_claim']==str(i)] for i in range(1,12)}}
