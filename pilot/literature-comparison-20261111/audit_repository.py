"""Read-only audit; run from any cwd with --repo path."""
import argparse,csv,gzip,hashlib,io,json,subprocess,zipfile
from pathlib import Path

def audit(repo,out):
    out.mkdir(exist_ok=True,parents=True)
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args])
    rows=[]
    for ref in git('for-each-ref','--format=%(refname:short)','refs/remotes/origin').decode().splitlines():
        if ref in ('origin','origin/HEAD') or 'literature-comparison' in ref:continue
        files=git('ls-tree','-r','--name-only',ref).decode().splitlines()
        rows.append(dict(ref=ref,sha=git('rev-parse',ref).decode().strip(),file_count=len(files),stage_matches=[x for x in files if any(k in x.lower() for k in ('20261111','stage2','stage3','stage4','stage5','final_verdict'))],zip_files=[x for x in files if x.endswith('.zip')]))
    (out/'branch_inventory.json').write_text(json.dumps(rows,indent=2))
    checks=[]
    for folder in ('objective-effort-20261110','objective-budget-torque-20261110','trajectory-generalization-20261110'):
        ref='origin/pilot/'+folder;base='pilot/'+folder+'/'
        files=git('ls-tree','-r','--name-only',ref,base).decode().splitlines();dest=out/folder;dest.mkdir(exist_ok=True)
        for p in files:
            if p.endswith('.md') or p.endswith('execution_summary.json') or p.endswith('execution.json'):
                (dest/p.replace(base,'').replace('/','__')).write_bytes(git('show',ref+':'+p))
        candidates=next(x for x in files if x.endswith('results/candidates.csv') or x.endswith('results/candidates.csv.gz'))
        data=git('show',ref+':'+candidates);raw=gzip.decompress(data) if candidates.endswith('.gz') else data
        reader=csv.DictReader(io.StringIO(raw.decode()));records=list(reader)
        seeds=sorted(set(str(x.get('seed',x.get('optimizer_seed'))) for x in records))
        manifest_path=base+'results/sha256.json';verified=[];mismatches=[]
        if manifest_path in files:
            manifest=json.loads(git('show',ref+':'+manifest_path))
            for path,expected in manifest.items():
                try:blob=git('show',ref+':'+base+('results/' if folder=='objective-effort-20261110' else '')+path)
                except subprocess.CalledProcessError:
                    mismatches.append(dict(path=path,status='missing'));continue
                actual=hashlib.sha256(blob).hexdigest()
                (verified if actual==expected else mismatches).append(path)
        checks.append(dict(ref=ref,path=candidates,sha256=hashlib.sha256(data).hexdigest(),rows=len(records),seeds=seeds,columns=reader.fieldnames,manifest_verified_count=len(verified),manifest_mismatches=mismatches))
    (out/'prior_candidate_audit.json').write_text(json.dumps(checks,indent=2))
    zips=[]
    for item in rows:
        for path in item['zip_files']:
            data=git('show',item['ref']+':'+path)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names=z.namelist();matches=[n for n in names if any(k in n.lower() for k in ('20261111','stage2','stage3','stage4','stage5','final_verdict'))]
                zips.append(dict(ref=item['ref'],path=path,sha256=hashlib.sha256(data).hexdigest(),entries=len(names),stage_matches=matches))
    (out/'zip_inventory.json').write_text(json.dumps(zips,indent=2))
    print(json.dumps(dict(branches=len(rows),prior_candidates=checks,zip_archives=len(zips),zip_stage_matches=sum(len(z['stage_matches']) for z in zips)),indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--repo',type=Path,required=True);v=a.parse_args();audit(v.repo,Path(__file__).resolve().parent/'audit')
