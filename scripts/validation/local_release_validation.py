#!/usr/bin/env python3
"""Actual local validation; Docker/cluster gates remain independent.
Use a disposable copy of apps/web as --frontend-dir: npm ci changes its dependencies.
"""
import argparse,json,os,signal,subprocess,sys,time,urllib.request,statistics
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--frontend-dir',type=Path,required=True);p.add_argument('--browser',type=Path,required=True);p.add_argument('--port',type=int,default=13000);a=p.parse_args()
    root=Path(__file__).resolve().parents[2];e=root/'docs/reports/evidence';e.mkdir(exist_ok=True,parents=True);web=a.frontend_dir.resolve();url=f'http://127.0.0.1:{a.port}'
    env={**os.environ,'NEXT_TELEMETRY_DISABLED':'1','PYTHONPATH':f'{root}:{root}/services:{root}/packages','OTEL_ENABLED':'false','HSAAI_E2E_BASE_URL':url,'HSAAI_E2E_CHROMIUM_PATH':str(a.browser.resolve())};results=[]
    def run(name,args,cwd=root,timeout=300):
        start=time.monotonic()
        with (e/(name+'.log')).open('w') as out:
            try:code=subprocess.run(args,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124
            except FileNotFoundError:code=127
        row={'name':name,'command':args,'exit_code':code,'seconds':round(time.monotonic()-start,2)};results.append(row);(e/'final-validation.json').write_text(json.dumps(results,indent=2));print(json.dumps(row),flush=True);return code
    for name,args in [('frontend-install',['npm','ci']),('frontend-lint',['npm','run','lint']),('frontend-typecheck',['npm','run','type-check']),('frontend-tests',['npm','test','--','--reporter=json',f'--outputFile={e}/frontend-tests.json']),('frontend-build',['npm','run','build']),('frontend-audit',['npm','audit','--json'])]:
        result=run(name,args,web)
        if name in {'frontend-install','frontend-build'} and result:raise RuntimeError(name+' failed')
    log=(e/'frontend-runtime-final.log').open('w');server=subprocess.Popen(['npm','run','start','--','--port',str(a.port)],cwd=web,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        for _ in range(80):
            try:urllib.request.urlopen(url+'/api/health',timeout=1);break
            except Exception:time.sleep(.25)
        else:raise RuntimeError('Frontend did not start')
        run('backend-tests-final',[sys.executable,'-m','pytest','tests','-q','--cov-report=json:'+str(e/'coverage-final.json'),'--junitxml='+str(e/'backend-tests-final.xml')],timeout=360)
        from playwright.sync_api import sync_playwright
        pages=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=str(a.browser.resolve()),headless=True)
            for width,height in [(1440,960),(768,1024),(390,844)]:
                page=browser.new_page(viewport={'width':width,'height':height});errors=[];responses=[]
                page.on('pageerror',lambda error:errors.append(str(error)));page.on('response',lambda response:responses.append({'status':response.status,'url':response.url}) if response.status>=400 else None)
                response=page.goto(url+'/login');page.wait_for_load_state('networkidle');page.screenshot(path=str(e/f'login-{width}.png'),full_page=True)
                row=page.evaluate('({rtl:document.dir,overflow:document.documentElement.scrollWidth>innerWidth,fonts:document.fonts.status,title:document.title})');row.update(width=width,status=response.status,errors=errors,http_errors=responses);pages.append(row);page.close()
            browser.close()
        samples=[]
        for _ in range(30):
            start=time.perf_counter()
            with urllib.request.urlopen(url+'/api/health',timeout=5) as response:assert response.status==200
            samples.append((time.perf_counter()-start)*1000)
        (e/'browser-visual-validation.json').write_text(json.dumps({'pages':pages,'health_http_samples':len(samples),'health_mean_ms':statistics.mean(samples),'health_p95_ms':sorted(samples)[28],'scope':'Real Chromium + production Next.js; public UI only. Backend/identity requests remain unavailable; no full-stack claim.'},ensure_ascii=False,indent=2))
        assert all(x['status']==200 and not x['overflow'] and not x['errors'] and x['rtl']=='rtl' and x['fonts']=='loaded' for x in pages)
        print('Public browser visual checks PASS; backend/SSO dependency errors are retained',flush=True)
    finally:
        try:os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=10)
        except ProcessLookupError:pass
        log.close()
    run('static-release-final',[sys.executable,'scripts/validate_release.py'])
    run('python-critical-lint-final',[sys.executable,'-m','ruff','check','services','packages','--select','F821,F822,F823,E9'])
    print('Validation completed; assess coverage exit status and separate external production gates.',flush=True)

if __name__=='__main__':main()
