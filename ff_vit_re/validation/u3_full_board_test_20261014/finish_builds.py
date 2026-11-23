"""Continue already-started isolated builds; publication remains fail-closed."""
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from prepare import HERE, save_json

PYTHON='/home/user/anaconda3/envs/vlm_token/bin/python'
VIVADO='/opt/vivado/2025.1/Vivado/bin/vivado'

def wait_json(path):
    while not path.exists(): time.sleep(5)
    item=json.loads(path.read_text())
    if 'exit_code' in item and item['exit_code']!=0: raise RuntimeError('failed stage: '+str(path))
    return item

def status(name,stage,**extra):
    record=dict(dataset=name,stage=stage,updated_unix=time.time(),**extra)
    save_json(HERE/'outputs'/name/'build_status.json',record)
    print(json.dumps(record),flush=True)

def main_dataset(name):
        out=HERE/'outputs'/name;hw=out/'hardware'
        status(name,'WAITING_HLS_SYNTHESIS')
        wait_json(hw/'hls_synthesis_exit.json');wait_json(hw/'package_exit.json')
        status(name,'SOC_SYNTHESIS_AND_IMPLEMENTATION')
        subprocess.run([PYTHON,'-B',str(HERE/'build_hardware.py'),'--dataset',name,'--stage','route'],cwd=HERE,check=True)
        status(name,'WAITING_FULL_CSIM_AND_REVIEW')
        wait_json(hw/'csim_verified.json')
        review=wait_json(HERE/'review_approved.json')
        if review['status']!='READ_ONLY_REVIEW_APPROVED_WITH_FIXES_VERIFIED' or review['critical_issues_open']!=0 or review['important_issues_open']!=0 or review['unit_tests_passed']<20:
            raise RuntimeError('review/test gate is not approved')
        status(name,'HARDWARE_QUALIFICATION')
        subprocess.run([PYTHON,'-B',str(HERE/'qualify.py'),'--dataset',name],cwd=HERE,check=True)
        status(name,'BITSTREAM_AND_XSA_EXPORT')
        with (hw/'export.console.log').open('x') as log:
            subprocess.run([VIVADO,'-mode','batch','-notrace','-source',str(HERE/'export.tcl'),
                '-log',str(hw/'export.log'),'-journal',str(hw/'export.jou'),'-tclargs',str(hw),name],
                cwd=hw,stdout=log,stderr=subprocess.STDOUT,check=True)
        status(name,'PS_PLATFORM_IDENTITY_AND_SD_PUBLICATION')
        subprocess.run([PYTHON,'-B',str(HERE/'publish.py'),'--dataset',name],cwd=HERE,check=True)
        status(name,'READY_FOR_BOARD_TEST_NOT_BOARD_MEASURED',published=json.loads((out/'published.json').read_text()))

def main():
    # Independent output trees; the matching existing SoC flow peaked at ~8 GB
    # per route. Each instance stays capped at 4 threads / 2 launch jobs.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(main_dataset,name) for name in ('plantvillage','nwpu')]
        failures=[]
        for future in futures:
            try: future.result()
            except Exception as e: failures.append(str(e))
        if failures: raise RuntimeError('; '.join(failures))

if __name__=='__main__':
    try: main()
    except Exception as e:
        save_json(HERE/'workflow_failure.json',dict(error=str(e),updated_unix=time.time(),boot_publication_blocked=True))
        raise
