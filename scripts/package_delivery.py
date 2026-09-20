#!/usr/bin/env python3
"""Package the source with an original-file preservation gate and SHA-256 manifest.
Never deletes workspace files and refuses to overwrite an existing ZIP.
"""
from pathlib import Path
import argparse,hashlib,json,zipfile,sys

ROOT=Path(__file__).resolve().parents[1]
EXCLUDE_PARTS={'node_modules','.next','.venv','venv','__pycache__','.pytest_cache','.ruff_cache','.mypy_cache','coverage_html','site-packages'}

def sha(data):return hashlib.sha256(data).hexdigest()
def archive_files(path):
    with zipfile.ZipFile(path) as archive:
        names=[n for n in archive.namelist() if not n.endswith('/')]
        prefix=names[0].split('/',1)[0]+'/'
        return {n[len(prefix):]:sha(archive.read(n)) for n in names}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--original',required=True);parser.add_argument('--checkpoint');parser.add_argument('--output',required=True);a=parser.parse_args()
    output=Path(a.output).resolve()
    if output.exists():parser.error('Output already exists; choose a new output to preserve it')
    original=archive_files(a.original);checkpoint=archive_files(a.checkpoint) if a.checkpoint else {}
    required=set(original)|set(checkpoint)
    missing=[name for name in required if not (ROOT/name).is_file()]
    if missing:raise RuntimeError('Missing prior files: '+repr(missing))
    included=[]
    for path in ROOT.rglob('*'):
        relative=path.relative_to(ROOT);name=relative.as_posix()
        if name in required:
            included.append(path);continue
        if any(part in EXCLUDE_PARTS for part in relative.parts):continue
        if not path.is_file() or path.is_symlink():continue
        if name.startswith(('docs/release/', 'docs/reports/', 'scripts/')):
            included.append(path);continue
        if path.suffix in {'.pyc','.pyo','.db','.sqlite','.sqlite3','.log','.tsbuildinfo'}:continue
        if name in {'.coverage','tests/coverage.xml'} or relative.parts[0] in {'data','backups','pytest-of-root'}:continue
        if name.startswith('services/data/') or name.startswith('tmp/'):continue
        if relative.parts[0].startswith(('pip-','tmp')):continue
        if path.name.startswith('.env') and not (path.name.endswith('.example') or 'example' in path.name):continue
        included.append(path)
    manifest=ROOT/'docs/release/SOURCE_CHANGES.json';manifest.parent.mkdir(parents=True,exist_ok=True)
    current={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in included}
    result={'original_archive_sha256':sha(Path(a.original).read_bytes()),'original_file_count':len(original),'original_files_missing':[],
            'original_files_unchanged':[n for n,h in original.items() if current.get(n)==h],
            'original_files_modified':[n for n,h in original.items() if current.get(n)!=h],
            'added_files':sorted(set(current)-set(original)),
            'original_files':original,'checkpoint_file_count':len(checkpoint),'checkpoint_files_missing':[],
            'changes_since_checkpoint':[n for n,h in checkpoint.items() if current.get(n)!=h],
            'packaging_policy':'All original and checkpoint files retained. Only new dependency/build caches, runtime test data and generated private configuration are excluded.'}
    manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if manifest not in included:included.append(manifest)
    sums=ROOT/'SHA256SUMS.txt';included=[p for p in included if p!=sums]
    sums.write_text(''.join(sha(p.read_bytes())+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in sorted(included)))
    included.append(sums);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(included):archive.write(p,'HSAAI/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None,'ZIP CRC failure'
        for line in archive.read('HSAAI/SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1)
            assert sha(archive.read('HSAAI/'+name))==digest,'Hash mismatch: '+name
        assert all('HSAAI/'+name in archive.namelist() for name in required)
    report={'file':str(output),'size_bytes':output.stat().st_size,'sha256':sha(output.read_bytes()),'files':len(included),'original_files_preserved':len(original),'checkpoint_files_preserved':len(checkpoint),'zip_crc':'passed','file_hashes':'passed'}
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
