"""Prepare separate public-evidence fixtures. No network, models, or audit edits."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from lab04_team import evidence_copy, choose_report, save
from report_workflow import load, ReportError


def prepare_cases(seed_run,clean_run,output_root):
    seed_run,clean_run=Path(seed_run),Path(clean_run)
    seed_report=choose_report(seed_run);clean_report=choose_report(clean_run)
    audits=list(clean_run.glob('*fallback_audit.md'))
    if len(audits)!=1:raise ReportError('Clean candidate requires one saved human audit')
    marks={}
    for line in audits[0].read_text().splitlines():
        if line.startswith('| '):
            cells=line.split('|')
            if cells[1].strip().isdigit():marks[int(cells[1].strip())]=cells[5].strip()
    if any(marks.get(i)!='Correct' for i in range(1,12)):
        raise ReportError('Clean candidate does not have all eleven core human marks Correct')
    root=Path(output_root)/datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S_%f_UTC')
    root.mkdir(parents=True,exist_ok=False)
    for name,source,report in [('eps_error',seed_run,seed_report),('invented_growth',seed_run,seed_report),('clean_report',clean_run,clean_report)]:
        dest=root/name;dest.mkdir();evidence_copy(source,dest)
        original=report.read_text();text=original
        metadata={'test':name,'source_report':str(report.resolve()),'original_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),
                  'model_verification_performed':False,'human_audits_modified':False}
        if name=='eps_error':
            facts=load(source,'facts.json');eps=facts['concepts']['diluted_eps']['current']
            correct=Decimal(str(eps['val']));wrong=correct+1
            lines=text.splitlines(keepends=True);changed=False
            for i,line in enumerate(lines):
                if line.startswith('|') and re.search(r'GAAP diluted EPS',line,re.I):
                    cells=line.split('|')
                    if Decimal(cells[2].strip().replace(',',''))==correct:
                        cells[2]=' '+str(wrong)+' ';lines[i]='|'.join(cells);changed=True;break
            if not changed:raise ReportError('Cannot identify annual EPS table cell safely; original preserved')
            text=''.join(lines)
            source_lines=(source/'10-K.txt').read_text().splitlines()
            candidates=[(i+1,line) for i,line in enumerate(source_lines) if 'diluted' in line.lower() and re.search(r'(?<!\d)'+re.escape(str(correct))+r'(?!\d)',line)]
            if not candidates:raise ReportError('No exact diluted EPS source line found for seeded source quote')
            lineno,real=candidates[0]
            fabricated=re.sub(r'(?<!\d)'+re.escape(str(correct))+r'(?!\d)',str(wrong),real,count=1)
            # The copied report's source quotation is deliberately false; real saved filing untouched.
            anchor='\n## Market Positioning and Growth Outlook'
            added=f'\nPurported annual diluted EPS source, 10-K.txt:L{lineno}, {eps["tag"]}, period {eps.get("start")} through {eps["end"]}:\n> {fabricated}\n'
            text=text.replace(anchor,added+anchor,1)
            metadata.update(correct_eps=str(correct),seeded_eps=str(wrong),real_source_line=lineno,real_source_quote=real)
        elif name=='invented_growth':
            facts=load(source,'facts.json');pair=facts['concepts']['revenue']
            current,prior=pair['current'],pair['prior']
            a,b=Decimal(str(current['val'])),Decimal(str(prior['val']))
            actual=(a-b)/b*100;invented=actual+4
            sentence=(f'\nAnnual total revenue growth was {invented:.4f}%, calculated as '
                f'({a:,.0f} - {b:,.0f}) / {b:,.0f} × 100 from total revenue in USD. '
                f'Sources: {current["tag"]}, {current.get("start")} through {current["end"]}, '
                f'accession {current["accn"]}; {prior["tag"]}, {prior.get("start")} through {prior["end"]}, accession {prior["accn"]}.\n')
            text=text.replace('\n## Valuation Insights',sentence+'\n## Valuation Insights',1)
            metadata.update(correct_growth_percent=str(actual),seeded_growth_percent=f'{invented:.4f}')
        else:
            metadata['human_core_marks_source']=str(audits[0].resolve())
            metadata['scope']='Eleven core claims reviewed by human; supplemental claims are NOT certified clean.'
        assert text.splitlines()[0]==original.splitlines()[0]
        (dest/'report.md').write_text(text)
        save(dest/'test_case.json',metadata)
    return root


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed-run',type=Path,required=True);p.add_argument('--clean-run',type=Path,required=True)
    p.add_argument('--output-root',type=Path,default=Path('lab04_test_cases'))
    args=p.parse_args();print(prepare_cases(args.seed_run,args.clean_run,args.output_root))

if __name__=='__main__':main()
