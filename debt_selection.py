"""Keep debt scopes separate. Ratio basis: long-term borrowings, current plus
noncurrent, excluding finance/operating leases and standalone short-term debt.
"""
from decimal import Decimal, InvalidOperation
import re
from bs4 import BeautifulSoup

SCOPES = {
 'LongTermDebtNoncurrent': 'noncurrent long-term debt, excluding finance leases',
 'LongTermDebtCurrent': 'current portion of long-term debt, excluding finance leases',
 'LongTermDebt': 'long-term debt aggregate; classification requires filing evidence; never add current debt',
 'LongTermDebtAndCapitalLeaseObligations': 'noncurrent long-term debt including finance leases',
 'LongTermDebtAndCapitalLeaseObligationsCurrent': 'current long-term debt including finance leases',
 'FinanceLeaseLiability': 'total finance lease liabilities',
 'FinanceLeaseLiabilityCurrent': 'current finance lease liabilities',
 'FinanceLeaseLiabilityNoncurrent': 'noncurrent finance lease liabilities',
 'ShortTermBorrowings': 'standalone short-term borrowings; outside long-term-debt ratio basis',
}
RATIO_BASIS = 'Current plus noncurrent long-term borrowings, excluding finance leases, operating leases, and standalone short-term borrowings.'


def debt_evidence(html, url, accession):
    soup=BeautifulSoup(html,'html.parser')
    contexts={n.get('id'):n for n in soup.find_all(lambda n:n.name.lower().split(':')[-1]=='context')}
    units={n.get('id'):n.get_text(' ',strip=True) for n in soup.find_all(lambda n:n.name.lower().split(':')[-1]=='unit')}
    out=[]
    for n in soup.find_all('ix:nonfraction'):
        tag=n.get('name',''); local=tag.split(':')[-1]
        if local not in SCOPES and not (not tag.startswith('us-gaap:') and any(w in local.lower() for w in ['debt','borrow','lease','swap'])):
            continue
        ctx=contexts.get(n.get('contextref'))
        if ctx is None or ctx.find(lambda x:x.name.lower().split(':')[-1] in {'explicitmember','typedmember'}):continue
        instant=ctx.find(lambda x:x.name.lower().split(':')[-1]=='instant')
        if instant is None or units.get(n.get('unitref'),'').split(':')[-1]!='USD':continue
        row=n.find_parent('tr')
        if row is None:continue
        cells=row.find_all(['td','th'],recursive=False)
        if not cells:continue
        label=cells[0].get_text(' ',strip=True)
        try:
            val=Decimal(n.get_text('',strip=True).replace(',','').replace('$',''))*Decimal(10)**int(n.get('scale',0))
            if n.get('sign')=='-':val=-val
        except (InvalidOperation,ValueError):continue
        out.append({'tag':tag,'val':int(val),'end':instant.text.strip(),'unit':'USD','accn':accession,'source_url':url,'source_label':label,'source_row':' | '.join(c.get_text(' ',strip=True) for c in cells),'context_id':n.get('contextref'),'status':'reported','definition':SCOPES.get(local,'Custom concept; retained as evidence, not automatically classified.')})
    return out


def select_debt(raw, end, accession, evidence=None):
    reported={}; conflicts=[]
    for tag,definition in SCOPES.items():
        concept=raw.get('facts',{}).get('us-gaap',{}).get(tag,{})
        rows=[r for r in concept.get('units',{}).get('USD',[]) if r.get('end')==end and r.get('accn')==accession and not r.get('start') and r.get('form') in {'10-K','10-K/A'}]
        if len({r['val'] for r in rows})>1:
            conflicts.append(tag);continue
        if not rows:continue
        r=rows[-1]
        proofs=[p for p in evidence or [] if p['tag']=='us-gaap:'+tag and p['end']==end and p['accn']==accession and p['val']==r['val']]
        if evidence is not None and not proofs:continue
        reported[tag]={**r,'tag':'us-gaap:'+tag,'unit':'USD','definition':definition,'status':'reported','source_label':proofs[0]['source_label'] if proofs else concept.get('label',tag),'label_origin':'taxonomy label' if evidence is None else 'filing row','sources':proofs}
    custom=[p for p in evidence or [] if not p['tag'].startswith('us-gaap:') and p['end']==end and p['accn']==accession]
    def calculate(a,b,operator,definition):
        if a is None or b is None:return None
        val=a['val']+b['val'] if operator=='+' else a['val']-b['val']
        if val<0:return None
        return {'val':val,'tag':'calculated','unit':'USD','end':end,'accn':accession,'status':'calculated','definition':definition,'source_label':'Calculated: '+definition,'inputs':[a,b],'arithmetic':f"{a['val']} {operator} {b['val']} = {val}"}
    current=reported.get('LongTermDebtCurrent');noncurrent=reported.get('LongTermDebtNoncurrent')
    inclusive_current=reported.get('LongTermDebtAndCapitalLeaseObligationsCurrent')
    inclusive_noncurrent=reported.get('LongTermDebtAndCapitalLeaseObligations')
    derived_current=calculate(inclusive_current,reported.get('FinanceLeaseLiabilityCurrent'),'-',SCOPES['LongTermDebtCurrent'])
    derived_noncurrent=calculate(inclusive_noncurrent,reported.get('FinanceLeaseLiabilityNoncurrent'),'-',SCOPES['LongTermDebtNoncurrent'])
    for name,direct,derived in [('current',current,derived_current),('noncurrent',noncurrent,derived_noncurrent)]:
        if direct and derived and direct['val']!=derived['val']:conflicts.append(name+' direct/derived mismatch')
    excluded = []
    # A standard tag cannot override a filing label identifying standalone
    # short-term borrowing. Retain the reported fact, but exclude it from
    # the long-term-borrowings ratio; do not assume its replacement is zero.
    if current and any(re.search(r'\bshort[ -]term (?:debt|borrowings?)\b', p.get('source_label', ''), re.I)
                       and not re.search(r'current portion|current maturit', p.get('source_label', ''), re.I)
                       for p in current.get('sources', [])):
        current['taxonomy_definition'] = current['definition']
        current['definition'] = 'Filing identifies short-term debt/borrowings; not established as current long-term debt.'
        current['classification_warning'] = 'Source label conflicts with LongTermDebtCurrent classification.'
        excluded.append(current)
        current = None
        derived_current = None  # Do not silently resolve contradictory source evidence.
    current=current or derived_current;noncurrent=noncurrent or derived_noncurrent
    total=calculate(noncurrent,current,'+','Total current and noncurrent long-term borrowings, excluding finance leases')
    inclusive_total=calculate(inclusive_noncurrent,inclusive_current,'+','Total current and noncurrent long-term debt including finance leases')
    reason=None
    if conflicts:
        total=None;reason='Conflicting debt evidence: '+', '.join(conflicts)
    elif excluded:
        reason='The filing labels the tagged current amount as short-term debt/borrowings. It is excluded from the long-term-borrowings ratio. A comparable current portion of long-term debt has not been established; missing is not zero.'
    elif total is None:
        reason='Comparable debt-only current and noncurrent balances could not both be established for the same date, currency, and filing. Aggregate LongTermDebt is not a noncurrent substitute; missing leases are not zero.'
    return {'end':end,'accn':accession,'ratio_basis':RATIO_BASIS,'reported':reported,'custom_evidence':custom,'excluded_current_candidates':excluded,'current_debt_only':current,'noncurrent_debt_only':noncurrent,'total_debt_only':total,'total_debt_including_finance_leases':inclusive_total,'unavailable_reason':reason}
