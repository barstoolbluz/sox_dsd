import sys,json,collections,random
from pathlib import Path
sys.path.insert(0,'tests/dsd')
from p15_full_band_campaign import canonical_plan,receipt_path
base=Path('tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/receipts')
replay=Path('tests/dsd/results/P15_campaign_dispatch_corrective_2026-10-17/SCHEDULE_REPLAY.json')
master=json.loads(replay.read_text())['stationary_schedule_results']
jobs=canonical_plan(); by_identity={(j['cell_id'],j['mode'],j['lo'],j['hi']):i for i,j in enumerate(jobs)}
indices={};res=[]
def add(index,group):
 if index in indices:indices[index].append(group);return
 j=jobs[index];r=json.loads(receipt_path(base,j).read_text());idx=len(res)
 indices[index]=[group]
 res.append(dict(index=index,job=j,prior_status=r['certificate']['status'],prior_reason=r['certificate'].get('reason'),groups=indices[index]))
for row in master:
 key=(row['cell_id'],row['mode'],row['lo'],row['hi'])
 assert key in by_identity,key
 add(by_identity[key],'historical_43')
print('historical',len(res),collections.Counter(r['prior_status'] for r in res),collections.Counter(r['prior_reason'] for r in res))
# Select by independent reproducible grouping. Find earliest source job for each group.
categories={}
for idx,j in enumerate(jobs):
 if idx in indices:continue
 receipt=json.loads(receipt_path(base,j).read_text())['certificate']
 st=receipt['status']; reason=receipt.get('reason','')
 if st=='OPEN':
  kind='structural' if str(reason).startswith('operator_path') else 'timeout'
 elif st.startswith('PASS-LOCAL-'):kind='cheap'
 else:kind='other'
 rate='48' if j['output_hz'] in (48000,96000,192000,384000) else '44'
 dsd=j['cell_id'].split('.')[0]
 label=(kind,rate,dsd,j['mode'])
 categories.setdefault(label,idx)
for (kind,rate,dsd,mode),idx in sorted(categories.items()):
 add(idx,f'representative_{kind}_{rate}_{dsd}_{mode}')
# Archived 10x-budget sample, particularly useful for testing whether the
# new mathematical method converts real historical 60-second timeouts.
budget=Path('tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/budget-sample')
by_job_id={json.dumps(j,sort_keys=True):i for i,j in enumerate(jobs)}
for file in sorted(budget.glob('*.json')):
 r=json.loads(file.read_text())
 job=r['job']; idx=by_job_id[json.dumps(job,sort_keys=True)]
 add(idx,'600s_sample_'+r['certificate']['status'])
print('budget statuses',collections.Counter(r['certificate']['status'] for r in (json.loads(f.read_text()) for f in budget.glob('*.json'))))
print('full corpus',len(res),collections.Counter(x['prior_status'] for x in res))
output=Path('tests/dsd/results/P15_prover_optimization_2026-10-18/CORPUS.json')
output.write_text(json.dumps(dict(schema='P15/numerical-profiling-corpus/1',source='original-2026-10-18-11516-receipt-full-campaign',cases=res),indent=2,sort_keys=True)+'\n')
