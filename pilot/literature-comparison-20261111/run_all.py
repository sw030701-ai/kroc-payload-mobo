"""Reproduce into a fresh directory without changing the published results."""
import argparse,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path

root=Path(__file__).resolve().parent
a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);v=a.parse_args()
target=v.output.resolve()
if target.exists():raise SystemExit('Choose a new output directory; published results are never overwritten')
target.mkdir(parents=True)
for name in ('experiment.py','validate.py','analyze.py','PROTOCOL_KO.md'):
    shutil.copy2(root/name,target/name)
(target/'fingerprint.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()},indent=2))
with (target/'validation.log').open('w') as f:
    subprocess.run([sys.executable,str(target/'validate.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
for e in range(1,5):
    with (target/f'E{e}_execution.log').open('w') as f:
        subprocess.run([sys.executable,'-u',str(target/'experiment.py'),'--experiment',str(e)],stdout=f,stderr=subprocess.STDOUT,check=True)
with (target/'analysis.log').open('w') as f:
    subprocess.run([sys.executable,str(target/'analyze.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
print('All four experiments and audit completed:',target)
