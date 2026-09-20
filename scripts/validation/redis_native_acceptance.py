#!/usr/bin/env python3
"""Isolated native Redis TCP acceptance. Never touches production data or ports.
This is not Docker, Redis 7, ACL, Sentinel, or cluster certification.
"""
from pathlib import Path
import argparse,concurrent.futures,json,shutil,socket,subprocess,tempfile,time
import redis


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--redis-server',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    checks=[];processes=[];clients=[]
    def check(name,condition):
        checks.append({'name':name,'result':'PASS' if condition else 'FAIL'})
        if not condition:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='hsaai-redis-acceptance-') as location:
        base=Path(location)
        def start(directory):
            directory.mkdir(exist_ok=True);port=free_port();log=(directory/'server.log').open('w')
            process=subprocess.Popen([args.redis_server,'--bind','127.0.0.1','--port',str(port),'--daemonize','no','--dir',str(directory),'--dbfilename','test.rdb','--save','','--appendonly','no'],stdout=log,stderr=subprocess.STDOUT)
            processes.append((process,log));client=redis.Redis(host='127.0.0.1',port=port,socket_timeout=2,socket_connect_timeout=1,decode_responses=True);clients.append(client)
            for _ in range(100):
                try:client.ping();return client
                except redis.ConnectionError:time.sleep(.05)
            raise RuntimeError('Redis did not start')
        started=time.monotonic()
        result={'scope':'native isolated TCP, not production container'}
        try:
            directory=base/'original';client=start(directory);result['redis_version']=client.info()['redis_version']
            check('connect',client.ping());client.set('acceptance:key','preserved');check('read_write',client.get('acceptance:key')=='preserved')
            client.set('acceptance:ttl','value',ex=60);check('expiry',0<client.ttl('acceptance:ttl')<=60)
            pipe=client.pipeline();pipe.incrby('usage',7);pipe.incrby('usage',3);check('transaction',pipe.execute()==[7,10])
            before=time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:list(pool.map(lambda _:client.incr('parallel'),range(200)))
            result['concurrency_200_operations_seconds']=round(time.monotonic()-before,4);check('concurrent_increments',client.get('parallel')=='200')
            client.save();check('snapshot', (directory/'test.rdb').stat().st_size>0)
            backup=base/'backup.rdb';shutil.copy2(directory/'test.rdb',backup);client.shutdown(nosave=True)
            try:client.ping();unavailable=False
            except redis.ConnectionError:unavailable=True
            check('controlled_outage',unavailable)
            restarted=start(directory);check('restart_persistence',restarted.get('acceptance:key')=='preserved' and restarted.get('usage')=='10')
            restored_dir=base/'restored';restored_dir.mkdir();shutil.copy2(backup,restored_dir/'test.rdb');restored=start(restored_dir)
            check('backup_restore',restored.get('acceptance:key')=='preserved' and restored.get('parallel')=='200')
        except Exception as error:result['error']=f'{type(error).__name__}: {error}'
        finally:
            for process,log in processes:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                log.close()
            for client in clients:client.close()
            result.update(checks=checks,seconds=round(time.monotonic()-started,3),result='PASS' if len(checks)==9 and all(x['result']=='PASS' for x in checks) and 'error' not in result else 'FAIL')
            Path(args.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
            return 0 if result['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
