"""Sequential GPU jobs; durable status and automatic final error measurement."""
from pathlib import Path
import csv
import json
import os
import subprocess
import sys
import time
from runtime import HERE,u

def run_all():
    (HERE/'logs').mkdir(exist_ok=True)
    for dataset in ('plantvillage','nwpu'):
        out=HERE/'outputs'/dataset
        if (out/'final/summary.json').exists():continue
        command=[sys.executable,'-B',str(HERE/'train.py'),'--dataset',dataset,'--micro-batch','64','--epochs','12']
        if (out/'last.pth').exists():command.append('--resume')
        u.save_json(HERE/'status.json',dict(status='RUNNING',dataset=dataset,driver_pid=os.getpid(),command=command,
            started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
        with (HERE/'logs'/f'{dataset}_training.log').open('a') as stream:
            completed=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env=dict(os.environ,
                PYTHONDONTWRITEBYTECODE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8'))
        if completed.returncode:
            u.save_json(HERE/'status.json',dict(status='FAILED',dataset=dataset,exit_code=completed.returncode,
                log=str(HERE/'logs'/f'{dataset}_training.log')))
            raise SystemExit(completed.returncode)
    accuracy=[];errors=[]
    for name in ('plantvillage','nwpu'):
        final=HERE/'outputs'/name/'final'
        for filename,rows in (('accuracy.csv',accuracy),('nonlinear_error.csv',errors)):
            with (final/filename).open(newline='') as f:rows.extend(csv.DictReader(f))
    u.write_csv(HERE/'accuracy.csv',accuracy);u.write_csv(HERE/'nonlinear_error.csv',errors)
    u.save_json(HERE/'status.json',dict(status='COMPLETE',accuracy=accuracy,
        integer_software='MEASURED',HLS_full_C_sim='NOT_MEASURED',RTL='NOT_MEASURED',FPGA='NOT_MEASURED'))

if __name__=='__main__':run_all()
