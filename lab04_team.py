"""Lab 04 LangGraph team. Code fixes routing; all Manager paths go to Verifier."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
import report_workflow as desk
from lab04_verifier import saved_evidence, verify, VERIFIER_SCHEMA

ROOT=Path(__file__).resolve().parent
ROLE_FILES={role:ROOT/'roles'/(role.lower().replace(' ','_')+'.md') for role in [*desk.ROLES,'Verifier']}
MANAGER_SCHEMA=deepcopy(desk.SCHEMAS['Strategy Manager'])
MANAGER_SCHEMA['properties']['revision_requests']=desk.arr(desk.obj({'role':{'type':'string','enum':desk.ROLES[:3]},'instructions':desk.STRING}))
MANAGER_SCHEMA['required'].append('revision_requests')
SCHEMAS={**desk.SCHEMAS,'Strategy Manager':MANAGER_SCHEMA,'Verifier':VERIFIER_SCHEMA}


class State(TypedDict, total=False):
    data: dict
    outputs: dict
    counts: dict
    errors: list
    pending: dict
    round: int
    report: str
    verification: dict
    verify_only: bool
    manager_approved: bool


def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')


def evidence_copy(source,dest):
    """Copy only public filing/fact inputs. Preserve original reports/audits in place."""
    names={'company.json','filings.json','facts.json','peers.json','calculations.json','release_lines.json',
           'companyfacts_raw.json','10-K.txt','10-Q.txt','8-K.txt','earnings_release_99_1.txt','earnings_release_99_1.html','user_inputs.json'}
    manifest={}
    for path in sorted(Path(source).iterdir()):
        if path.is_file() and not path.is_symlink() and (path.name in names or re.fullmatch(
                r'(annual_(revenue|debt)_(source|evidence)_\d+\.(html|json)|peer_\d+_companyfacts_raw\.json)',path.name)):
            shutil.copyfile(path,Path(dest)/path.name)
            manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            if re.fullmatch(r'annual_revenue_source_\d+\.html',path.name):
                from equity_desk import plain_text
                (Path(dest)/(path.stem+'.txt')).write_text(plain_text(path.read_text()))
    save(Path(dest)/'source_manifest.json',{'source_folder':str(Path(source).resolve()),'sha256':manifest})


def new_folder(company,root):
    name=re.sub(r'[^A-Za-z0-9_-]+','_',company)
    path=Path(root)/f'{name}_{datetime.now(timezone.utc):%Y-%m-%d_%H-%M-%S_%f_UTC}'
    path.mkdir(parents=True,exist_ok=False)
    return path


def choose_report(folder):
    if (folder/'report.md').exists():return folder/'report.md'
    choices=list(folder.glob('*fallback_report.md'))+list(folder.glob('lab03_*_report.md'))
    if len(choices)!=1:raise desk.ReportError('Saved run must have report.md or exactly one candidate report. Use a separate test copy.')
    return choices[0]


class Team:
    def __init__(self, folder, model, source=None, ticker=None, peers=None, price=None, verify_only=False):
        self.folder=Path(folder);self.model=model;self.source=Path(source) if source else None
        self.ticker=ticker;self.peers=peers or [];self.price=price;self.verify_only=verify_only
        self.events=[];self.instructions={r:p.read_text() for r,p in ROLE_FILES.items()}

    def event(self,node,inputs,output):
        entry={'node':node,'input':deepcopy(inputs),'output':deepcopy(output)}
        self.events.append(entry)
        save(self.folder/f'node_{len(self.events):02d}_{node.lower().replace(" ","_")}.json',entry)

    def generate(self,role,packet):
        # Single stateless SDK call. No graph state, client, credentials, or chat history in packet.
        if set(packet)!={'task','context','expected_output'}:raise desk.ReportError('Invalid handoff boundary')
        output=self.model.generate_structured(role,deepcopy(packet),packet['task'],packet['expected_output'])
        if desk.schema_check(output,packet['expected_output']):raise desk.ReportError(role+' schema validation failed')
        return output

    def steps(self,state):
        print('steps',flush=True)
        try:
            if self.source:
                evidence_copy(self.source,self.folder)
                data=desk.prepare(self.folder,self.price)
                if self.ticker and data['company']['ticker'].upper()!=self.ticker.upper():raise desk.ReportError('Saved ticker mismatch')
                supplied=set(data_key.upper() for data_key in desk.load(self.folder,'peers.json'))
                if self.peers and set(self.peers)!=supplied:raise desk.ReportError('Saved peer set does not match --peers')
                mode='seven saved data steps; no downloads'
            else:
                from dotenv import dotenv_values
                from equity_desk import Desk, SECClient
                import logging
                logging.getLogger('dotenv.main').disabled=True
                agent=dotenv_values(ROOT/'.env',interpolate=False).get('SEC_USER_AGENT')
                if not agent:raise desk.ReportError('SEC_USER_AGENT is missing')
                tool=Desk(SECClient(agent),self.ticker,self.peers,self.price,output_root=self.folder/'data_steps')
                for i in range(1,8):
                    print(f'Step {i}',flush=True);getattr(tool,f'step{i}')()
                evidence_copy(tool.folder,self.folder);data=desk.prepare(self.folder,self.price)
                mode='seven data steps executed'
            save(self.folder/'user_inputs.json',{'price':self.price,'source':'user-supplied --price; not a filing fact','price_date':None})
            result={'data':data,'outputs':{},'counts':{},'errors':[],'pending':{},'round':0}
            self.event('steps',{'ticker':self.ticker,'peers':self.peers,'price':self.price,'source':str(self.source)},
                       {'mode':mode,'data':data})
            desk.write_audit(self.folder/'human_audit.md',data['metrics'])
            return result
        except Exception as error:
            result={'outputs':{},'counts':{},'errors':['Data steps failed; evidence unavailable'],'pending':{},'round':0}
            self.event('steps',{}, {'error':'data_preparation_failed'})
            return result

    def role(self,role,state):
        print(role,flush=True)
        counts=dict(state.get('counts',{}));outputs=deepcopy(state.get('outputs',{}));errors=list(state.get('errors',[]))
        if errors or not state.get('data'):
            self.event(role,{}, {'status':'not called: upstream failure'});return {}
        if counts.get(role,0)>=2:
            self.event(role,{}, {'status':'call budget exhausted'});return {'errors':errors+[role+' call budget exhausted']}
        data=state['data'];context={}
        if role=='Research Analyst':context={'sources':data['sources']}
        elif role=='Financial Analyst':
            # Include ratio components, not just outputs, so Verifier has quoted inputs.
            context={'metrics':data['metrics'],'required_metric_ids':list(data['metrics'])}
        elif role=='Investment Advisor':context=desk.analyst_outputs(outputs['Research Analyst'],outputs['Financial Analyst'],data)
        else:
            context={'analyst_outputs':desk.analyst_outputs(outputs['Research Analyst'],outputs['Financial Analyst'],data),
                     'investment_advisor':outputs['Investment Advisor'],
                     'automated_errors':{r:desk.validate(r,outputs[r],data,outputs.get('Research Analyst'),outputs.get('Financial Analyst')) for r in desk.ROLES[:3]},
                     'required_sections':desk.SECTIONS,
                     'revision_eligible':[r for r in desk.ROLES[:3] if counts.get(r,0)<2] if state['round']==0 else [],
                     'can_revise':state['round']==0}
        if role in state.get('pending',{}):
            context['revision']={'instructions':state['pending'][role],'previous_output':outputs[role]}
        packet={'task':self.instructions[role],'context':context,'expected_output':SCHEMAS[role]}
        counts[role]=counts.get(role,0)+1
        try:
            output=self.generate(role,packet)
            outputs[role]=output;self.event(role,packet,output)
        except Exception as error:
            detail=error.details if isinstance(error,desk.ModelCallError) else {'category':'schema_or_local_error','role':role}
            self.event(role,packet,{'error':detail});errors.append(role+' failed: '+detail['category'])
            return {'counts':counts,'errors':errors}
        result={'outputs':outputs,'counts':counts}
        if role=='Strategy Manager':
            pending={}
            if output['decision']=='revise' and state['round']==0:
                for request in output['revision_requests']:
                    target=request['role']
                    if target in pending or counts.get(target,0)>=2:
                        errors.append('Invalid or duplicate revision request');break
                    pending[target]=request['instructions']
                # Support the old single-request fields, but never execute twice.
                if not pending and output['revision_role'] in desk.ROLES[:3]:pending[output['revision_role']]=output['instructions']
                if any(r in pending for r in desk.ROLES[:2]):
                    pending.setdefault('Investment Advisor','Refresh synthesis using the revised analyst outputs.')
                if not pending:errors.append('Manager requested revision without an eligible owner')
            elif output['decision']=='revise':errors.append('Revision budget exhausted; no third role call')
            elif output['decision']=='reject':errors.append('Manager rejected draft')
            checks=context['automated_errors']
            approved=output['decision']=='approve' and not any(checks.values()) and output['sections']==desk.SECTIONS
            if output['decision']=='approve' and not approved:errors.append('Manager approval cannot override automated checks')
            if output['sections']!=desk.SECTIONS:errors.append('Five-part template mismatch')
            # Build the draft even when rejected, so Verifier can inspect it independently.
            try:report=desk.render(data,outputs,datetime.now(timezone.utc).isoformat())
            except Exception:report='Filings read: unavailable\nRun time: '+datetime.now(timezone.utc).isoformat()+'\n\nReport compilation failed.\n'
            (self.folder/f'report_round_{state["round"]+1}.md').write_text(report)
            (self.folder/'report.md').write_text(report)
            result.update(pending=pending,report=report,errors=errors,manager_approved=approved)
        return result

    def verifier(self,state):
        print('Verifier',flush=True)
        report=state.get('report','')
        if not report:
            filings=state.get('data',{}).get('filings',{})
            header='Filings read: '+('; '.join(f"{form} {row['accessionNumber']} ({row['document_url']})" for form,row in filings.items()) or 'unavailable')
            report=header+'\nRun time: '+datetime.now(timezone.utc).isoformat()+'\n\nNo report: upstream failure.\n'
            (self.folder/'report.md').write_text(report)
        counts=dict(state.get('counts',{}));counts['Verifier']=counts.get('Verifier',0)+1
        completed={}
        def checkpoint(partial):
            completed.update(deepcopy(partial))
            save(self.folder/f'deterministic_round_{counts["Verifier"]}.json',partial)
        def batch_checkpoint(record, packet):
            save(self.folder / f'semantic_batch_{counts["Verifier"]}_{record["batch"]}.json',
                 {'input': packet, 'output': record})
        try:
            if not state.get('report'):raise desk.ReportError('No compiled report')
            bundle=saved_evidence(self.folder)
            captured=[]
            def generate(role,packet):
                captured.append(packet)
                return self.generate(role,packet)
            verified,result=verify(report,bundle,generate,checkpoint=checkpoint,
                                   batch_checkpoint=batch_checkpoint)
            result['mode']='mocked offline checks' if getattr(self.model,'is_mock',False) else ('live model and deterministic checks' if result['model_checks_completed'] else 'live model attempt incomplete; independent code checks retained')
            if getattr(self.model,'is_mock',False):verified=verified.replace('Automated verification —','MOCK RESPONSES — offline test only. Automated verification —',1)
            self.event('Verifier', {'batches': captured}, result)
        except Exception as error:
            detail=error.details if isinstance(error,desk.ModelCallError) else {'category':'verification_unavailable'}
            result={**completed,'model_checks_completed':False,'model_judgments':'incomplete',
                    'overall_verification_success':False,'status':'incomplete','error':detail,'marks':[]}
            first,_,rest=report.partition('\n')
            verified=first+'\n\nVerification unavailable; no correctness claim.\n\n'+rest
            self.event('Verifier', {'batches': captured} if 'captured' in locals() else {'report':report},result)
        n=counts['Verifier']
        (self.folder/f'verified_report_round_{n}.md').write_text(verified)
        (self.folder/'verified_report.md').write_text(verified)
        save(self.folder/f'verification_round_{n}.json',result)
        return {'verification':result,'counts':counts,'report':report}

    def graph(self):
        builder=StateGraph(State)
        builder.add_node('steps',self.steps)
        for role in desk.ROLES:builder.add_node(role,lambda state,r=role:self.role(r,state))
        builder.add_node('Verifier',self.verifier)
        def revision_start(state):
            print('revision_start',flush=True)
            self.event('revision_start',{'requested_roles':list(state['pending'])},{'round':1})
            return {'round':1}
        builder.add_node('revision_start',revision_start)
        # Fixed second sweep; only requested roles get a model call. No model controls edges.
        for role in desk.ROLES[:3]:
            def revise(state,r=role):
                if r in state['pending']:return self.role(r,state)
                print('revise_'+r+' (no call requested)',flush=True)
                self.event('revise_'+r,{'requested':False},{'status':'no model call'})
                return {}
            builder.add_node('revise_'+role,revise)
        builder.add_edge(START,'Verifier' if self.verify_only else 'steps')
        chain=['steps',*desk.ROLES,'Verifier']
        for a,b in zip(chain,chain[1:]):builder.add_edge(a,b)
        builder.add_conditional_edges('Verifier',lambda state:'revise' if not self.verify_only and state.get('pending') and state.get('round',0)==0 and not state.get('errors') and state['verification'].get('model_checks_completed') else 'done',{'revise':'revision_start','done':END})
        chain=['revision_start',*['revise_'+r for r in desk.ROLES[:3]],'Strategy Manager']
        for a,b in zip(chain,chain[1:]):builder.add_edge(a,b)
        return builder.compile()

    def run(self):
        initial={'verify_only':self.verify_only,'counts':{},'errors':[],'round':0}
        if self.verify_only:
            try:
                evidence_copy(self.source,self.folder)
                report=choose_report(self.source).read_text()
                (self.folder/'report.md').write_text(report)
                initial['report']=report
            except (OSError,desk.ReportError):
                initial['errors']=['Saved report unavailable or ambiguous; Verifier will record failure']
        # Disable optional external tracing even if it is configured in the shell.
        from langsmith import tracing_context
        with tracing_context(enabled=False):
            state=self.graph().invoke(initial,config={'recursion_limit':24})
        summary={'node_order':[x['node'] for x in self.events],'calls':state.get('counts',{}),
                 'errors':state.get('errors',[]),'manager_approved':state.get('manager_approved'),
                 'verification_completed':state.get('verification',{}).get('model_checks_completed',False),
                 'mode':'offline mock' if getattr(self.model,'is_mock',False) else 'live',
                 'human_verification':None,'partner_sign_off':None}
        save(self.folder/'run.json',summary)
        for error in summary['errors']:print(error)
        if not summary['verification_completed']:
            detail=state.get('verification',{}).get('error',{})
            print('Verifier unavailable: '+detail.get('category','unknown')+
                  (f" (HTTP {detail['http_status']})" if 'http_status' in detail else ''))
        print('Verified report: '+str(self.folder/'verified_report.md'))
        return summary


class LazyGoogle:
    """Load credentials only when a role call is actually needed."""
    def __init__(self,model):self.model=model;self.adapter=None
    def generate_structured(self,*args):
        if self.adapter is None:self.adapter=desk.GeminiModel.from_env(self.model,ROOT/'.env')
        return self.adapter.generate_structured(*args)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker',nargs='?')
    parser.add_argument('--peers',nargs='+',default=[])
    parser.add_argument('--price',type=float)
    parser.add_argument('--verify-only',type=Path,metavar='SAVED_RUN')
    parser.add_argument('--saved-run',type=Path,help='Reuse seven saved data steps; no SEC downloads')
    parser.add_argument('--model',default='gemini-2.5-flash')
    args=parser.parse_args(argv)
    if args.price is not None and (not math.isfinite(args.price) or args.price<=0):parser.error('--price must be finite and positive')
    if args.verify_only and (args.saved_run or args.peers or args.price is not None):parser.error('--verify-only cannot change peers, price, or source data')
    if not args.verify_only and not args.ticker:parser.error('ticker is required for a team run')
    source=args.verify_only or args.saved_run
    try:
        company=desk.load(source,'company.json') if source else {'name':args.ticker}
        if source and args.ticker and args.ticker.upper()!=company['ticker'].upper():raise desk.ReportError('Saved ticker mismatch')
        folder=new_folder(company.get('name') or company.get('title') or args.ticker or company['ticker'],ROOT/'lab04_runs')
        peers=list(dict.fromkeys(x.upper() for item in args.peers for x in item.split(',') if x))
        summary=Team(folder,LazyGoogle(args.model),source,args.ticker,peers,args.price,bool(args.verify_only)).run()
        return 0 if summary['verification_completed'] and not summary['errors'] else 1
    except desk.ReportError as error:
        print(str(error));return 1


if __name__=='__main__':raise SystemExit(main())
