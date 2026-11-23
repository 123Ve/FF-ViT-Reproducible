"""Serial long-running experiment supervisor. No second GPU training collector."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile

HERE=Path(__file__).resolve().parent
CURRENT=None

def status(**data):
    data=dict(updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),driver_pid=os.getpid(),**data)
    temporary=HERE/'status.tmp';temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(HERE/'status.json')
    print(json.dumps(data),flush=True)

def stop(signum,frame):
    if CURRENT is not None and CURRENT.poll() is None:CURRENT.terminate()
    status(status='INTERRUPTED',signal=signum,final_accuracy='NOT_MEASURED_UNTIL_FINAL_REPORT')
    raise SystemExit(128+signum)

def main():
    global CURRENT
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--resume',action='store_true')
    ap.add_argument('--background',action='store_true');args=ap.parse_args()
    if args.background:
        logs=HERE/'logs';logs.mkdir(exist_ok=True)
        command=[sys.executable,'-B',str(Path(__file__))]
        if args.resume:command.append('--resume')
        with (logs/'supervisor.log').open('a' if args.resume else 'x') as log:
            child=subprocess.Popen(command,cwd=HERE.parents[1],stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(json.dumps(dict(driver_pid=child.pid,status='LAUNCHED_CHECK_STATUS_JSON')),flush=True)
        return
    lock=(HERE/'driver.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    logs=HERE/'logs';logs.mkdir(exist_ok=True)
    environment=os.environ.copy();environment.update(PYTHONDONTWRITEBYTECODE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    for dataset in ('plantvillage','nwpu'):
        for stage in ('mlp','attention','integer_export_and_error'):
            if stage=='integer_export_and_error':
                command=[sys.executable,'-B',str(HERE/'exporter.py'),'--dataset',dataset]
            else:
                command=[sys.executable,'-B',str(HERE/'progressive.py'),'--dataset',dataset,'--stage',stage]
                if args.resume:command.append('--resume')
            path=logs/(dataset+'_'+stage+'.log')
            with path.open('a' if args.resume else 'x') as log:
                log.write('\nCOMMAND '+json.dumps(command)+'\n');log.flush()
                CURRENT=subprocess.Popen(command,cwd=HERE.parents[1],env=environment,stdout=log,stderr=subprocess.STDOUT)
                status(status='RUNNING',dataset=dataset,stage=stage,child_pid=CURRENT.pid,log=str(path),
                    final_accuracy='NOT_MEASURED_UNTIL_FINAL_REPORT',nonlinear_error='NOT_MEASURED_UNTIL_FINAL_REPORT')
                code=CURRENT.wait();CURRENT=None
            if code:
                status(status='FAILED',dataset=dataset,stage=stage,exit_code=code,log=str(path));raise SystemExit(code)
    archive=HERE/'e07_u3_progressive_qat_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in HERE.rglob('*'):
            if p.is_file() and (p.suffix in ('.py','.json','.csv','.txt','.tex','.jsonl','.log','.md') or '/final/artifact/' in str(p)):
                z.write(p,p.relative_to(HERE))
    status(status='COMPLETE_SOFTWARE_EXPERIMENT',archive=str(archive),HLS='NOT_MEASURED',RTL='NOT_MEASURED',FPGA='NOT_MEASURED')

if __name__=='__main__':main()
