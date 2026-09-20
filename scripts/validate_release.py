#!/usr/bin/env python3
"""Static source/configuration checks, not a production deployment certification."""
from pathlib import Path
import json,sys,re
import yaml
ROOT=Path(__file__).resolve().parents[1];errors=[];counts={}
excluded={'node_modules','.next','.venv','coverage_html','coverage','site-packages','__pycache__'}
for pattern in ['*.py','*.json']:
 files=[p for p in ROOT.rglob(pattern) if not any(x in excluded for x in p.parts)];counts[pattern]=len(files)
 for p in files:
  try:
   if pattern=='*.py':compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
   else:json.loads(p.read_text(encoding='utf-8-sig'))
  except Exception as exc:errors.append(f'{p.relative_to(ROOT)}: {exc}')
for file in ['docker-compose.yml','docker-compose.production.yml']:
 d=yaml.safe_load((ROOT/file).read_text());counts[file]=len(d['services'])
 for name,svc in d['services'].items():
  b=svc.get('build')
  if b:
   context=ROOT/(b.get('context','.') if isinstance(b,dict) else b)
   dockerfile=context/(b.get('dockerfile','Dockerfile') if isinstance(b,dict) else 'Dockerfile')
   if not dockerfile.is_file():errors.append(f'{file}: missing Dockerfile: {name}')
  for dep in svc.get('depends_on',[]):
   if dep not in d['services']:errors.append(f'{file}: missing dependency: {dep}')
  for mount in svc.get('volumes',[]):
   if isinstance(mount,str):
    expanded=re.sub(r'\$\{[^}:]+:-([^}]+)\}',r'\1',mount)
    if '${' in expanded:continue
    source=expanded.split(':')[0]
    if source.startswith('.') and not (ROOT/source).exists():errors.append(f'{file}: missing bind: {source}')
    elif '/' not in source and source not in d.get('volumes',{}):errors.append(f'{file}: missing volume: {source}')
resources=list(yaml.safe_load_all((ROOT/'infrastructure/kubernetes/base/release.yaml').read_text()));ids=set();deps={}
for r in resources:
 key=(r['kind'],r['metadata']['name'])
 if key in ids:errors.append(f'Duplicate resource: {key}')
 ids.add(key)
 if r['kind']=='Deployment':deps[key[1]]=r
for r in resources:
 if r['kind']=='Service':
  name=r['metadata']['name'];dep=deps.get(name)
  if not dep:errors.append('Missing deployment: '+name)
  elif r['spec']['ports'][0]['port']!=dep['spec']['template']['spec']['containers'][0]['ports'][0]['containerPort']:errors.append('Port mismatch: '+name)
counts['kubernetes_resources']=len(resources)
print(json.dumps({'status':'failed' if errors else 'passed','scope':'static only','counts':counts,'errors':errors},indent=2));sys.exit(bool(errors))
