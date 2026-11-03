"""Conservative, model-independent checks of explicit report evidence and arithmetic."""
import ast
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from lab04_verifier import normalize, number, TOKEN_RE, canonical


def arithmetic(expression):
    expression=expression.replace('−','-').replace('×','*').replace(',','').strip()
    tree=ast.parse(expression,mode='eval')
    def visit(node):
        if isinstance(node,ast.Expression):return visit(node.body)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return Decimal(str(node.value))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            return -visit(node.operand) if isinstance(node.op,ast.USub) else visit(node.operand)
        if isinstance(node,ast.BinOp):
            a,b=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
        raise ValueError('Not numeric arithmetic')
    return visit(tree)


def run_prechecks(report,bundle):
    """Check explicit links/annual table tags. Never infer a semantic verdict."""
    results=[];lines=report.splitlines()
    def record(kind,line,status,**details):
        results.append({'check':kind,'report_line':line,'status':status,
                        'model_judgment':'incomplete',**details})
    # A report quote is data, never the authoritative filing text.
    for index,line in enumerate(lines):
        if not line.lstrip().startswith('>'):continue
        previous=next((text for text in reversed(lines[:index]) if text.strip()),'')
        match=re.search(r'([\w.-]+\.txt):L(\d+)',previous)
        if not match:continue
        source_id=match.group(0);source=bundle['filing_texts'].get(source_id)
        quote=line.lstrip()[1:].strip()
        if not source:
            record('filing_line',index+1,'unresolved',source_id=source_id,reason='Referenced saved line is absent');continue
        same=normalize(quote)==normalize(source['text'])
        left=[m.group() for m in TOKEN_RE.finditer(quote)]
        right=[m.group() for m in TOKEN_RE.finditer(source['text'])]
        changes=[]
        if len(left)==len(right):
            changes=[{'reported':a,'source_value':b} for a,b in zip(left,right) if number(a)!=number(b)]
        record('filing_line',index+1,'match' if same else 'mismatch',
               source_id=source_id,reported_quote=quote,actual_quote=source['text'],
               accession=source['accession'],url=source['url'],numeric_differences=changes)
    # Explicit annual tables: tag + fiscal-year column + filing accession must resolve uniquely.
    accession=re.search(r'10-K\s+(\d{10}-\d{2}-\d{6})',lines[0] if lines else '')
    annual_header=None
    for index,line in enumerate(lines):
        if not line.startswith('|'):
            if line.strip():annual_header=None
            continue
        cells=[x.strip() for x in line.split('|')[1:-1]]
        if cells and 'annual' in cells[0].lower() and any(re.search(r'\bFY\d{2,4}\b',x,re.I) for x in cells):
            annual_header=cells;continue
        if not annual_header or not accession:continue
        tags={row['tag'] for row in bundle['saved_facts'].values() if row.get('tag') and row['tag']!='user:price'
              and re.search(r'(?<!\w)'+re.escape(row['tag'].split(':')[-1])+r'(?!\w)',line)}
        if len(tags)!=1:continue
        tag=next(iter(tags))
        for col,header in enumerate(annual_header):
            fy=re.search(r'\bFY(\d{2,4})\b',header,re.I)
            if not fy or col>=len(cells):continue
            try:actual=number(cells[col])
            except InvalidOperation:continue
            candidates=[r for r in bundle['saved_facts'].values() if r.get('tag')==tag and r['accn']==accession.group(1)
                        and r['end'][:4].endswith(fy.group(1))]
            unique={(str(r['val']),r.get('start'),r['end'],r['unit']):r for r in candidates}
            if len(unique)!=1:
                record('annual_tag_value',index+1,'unresolved',tag=tag,column=header,reason='Fiscal-year/tag source is absent or ambiguous');continue
            row=next(iter(unique.values()))
            context=' '.join(lines[:index]).lower()
            if row['unit'] in ('USD/shares','USD/share') and re.search(r'eps|per.share',cells[0],re.I):unit='USD/share'
            elif row['unit']=='USD' and re.search(r'usd\s+millions',context):unit='USD million'
            elif row['unit']=='USD' and re.search(r'amounts.*?\busd\b',context) and not re.search(r'\b(?:million|billion|thousand)s?\b',context):unit='USD'
            else:continue
            expected,base=canonical(row['val'],row['unit']);stated,sbase=canonical(actual,unit)
            if base!=sbase:continue
            from lab04_verifier import SCALES
            record('annual_tag_value',index+1,'match' if expected==stated else 'mismatch',
                   reported=str(actual),source_value=str(expected/SCALES[unit]),display_unit=unit,
                   tag=tag,start=row.get('start'),end=row['end'],accession=row['accn'],url=row['url'],column=header,
                   limitation='Explicit annual column/tag comparison only; meaning and definition await model review')
    # Arithmetic checks prove arithmetic only, not the provenance or definition of inputs.
    for index,line in enumerate(lines):
        if not line.startswith('|'):continue
        cells=[x.strip().strip('`') for x in line.split('|')[1:-1]]
        for i,expression in enumerate(cells[:-1]):
            if not re.fullmatch(r'[\d\s,.()+*/×−-]+',expression) or not re.search(r'[+*/×−-]',expression):continue
            match=re.fullmatch(r'([-−]?\d[\d,]*(?:\.\d+)?)(%|\s+times|\s+USD million)?',cells[i+1])
            if not match:continue
            try:
                value=arithmetic(expression);stated=number(match.group(1))
                places=len(match.group(1).split('.')[1]) if '.' in match.group(1) else 0
                rounded=value.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
            except (ValueError,SyntaxError,ArithmeticError):continue
            record('quoted_arithmetic',index+1,'match' if rounded==stated else 'mismatch',
                   expression=expression,reported=str(stated),calculated=str(rounded),
                   limitation='Quoted-input arithmetic only; source/period/definition judgments incomplete')
    return results


def incomplete_report(report,result):
    first,_,rest=report.partition('\n')
    rows=['','Verification incomplete: model check failed or was unavailable. No overall verification success.',
          'Independent code checks below do not establish meaning, period interpretation, or definition.',
          '| Code check | Report line | Result | Evidence |','|---|---|---|---|']
    for check in result.get('deterministic_checks',[]):
        evidence=(f"{check.get('reported','')} vs {check.get('source_value',check.get('calculated',''))}; "
                  f"{check.get('tag',check.get('source_id',check.get('expression','')))}; "
                  f"{check.get('start','')} through {check.get('end','')}; {check.get('accession','')}; "
                  f"{check.get('url','')}; {check.get('actual_quote','')}")
        rows.append('| '+' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in
                    [check['check'],check['report_line'],check['status'],evidence])+' |')
    marks = result.get('marks', [])
    if marks:
        rows += ['', 'Final deterministic filing-conflict marks remain valid while semantic review is incomplete.',
                 '| Report line | Reported | Mark | Corrected value | Filing citation |',
                 '|---|---|---|---|---|']
        for mark in marks:
            rows.append('| '+' | '.join(str(value).replace('|', '\\|').replace('\n', ' ') for value in
                        [mark['report_line'], mark['original'], mark['mark'], mark['correction'],
                         mark.get('citation', '')])+' |')
    return first+'\n'+'\n'.join(rows)+'\n\n'+rest
