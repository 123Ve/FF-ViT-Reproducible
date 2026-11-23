import copy
import hashlib
import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ROOT=Path(__file__).resolve().parents[1]

class PublicationBindingTests(unittest.TestCase):
    def test_final_elf_has_stack_margin_for_fatfs_and_summary(self):
        tool='/opt/vivado/2025.1/Vitis/gnu/aarch64/lin/aarch64-none/bin/aarch64-none-elf-nm'
        for name in ('plantvillage','nwpu'):
            raw=subprocess.check_output([tool,'-n',str(ROOT/'outputs'/name/'firmware/u3_accuracy.elf')],text=True)
            symbols={p[2]:int(p[0],16) for line in raw.splitlines() if len(p:=line.split())==3}
            self.assertGreaterEqual(symbols['__el3_stack']-symbols['_el3_stack_end'],65536)

    def test_compiled_bsp_binding_is_rechecked(self):
        from publish import verify_bsp_binding
        record=json.loads((ROOT/'outputs/plantvillage/firmware/identity.json').read_text())
        verify_bsp_binding(record)
        for key in ('bsp_libraries','bsp_headers'):
            wrong=copy.deepcopy(record);path=next(iter(wrong[key]));wrong[key][path]='0'*64
            with self.assertRaises(ValueError): verify_bsp_binding(wrong)
        for key in ('xparameters_sha256','board_abi_sha256'):
            wrong=copy.deepcopy(record);wrong[key]='0'*64
            with self.assertRaises(ValueError): verify_bsp_binding(wrong)

    def test_every_compiled_model_constant_is_checked(self):
        from publish import verify_firmware_config
        for name in ('plantvillage','nwpu'):
            out=ROOT/'outputs'/name
            record=json.loads((out/'firmware/identity.json').read_text())
            verify_firmware_config(out,record)
            for key in record['config']:
                wrong=copy.deepcopy(record);wrong['config'][key]+='WRONG'
                with self.assertRaises(ValueError,msg=key): verify_firmware_config(out,wrong)

    def test_returned_metadata_cannot_redefine_golden_hash_authority(self):
        from summarize_board import summarize
        with tempfile.TemporaryDirectory(prefix='u3_returned_metadata_') as tmp:
            folder=Path(tmp);payload=b'{"dataset":"plantvillage"}\n'
            (folder/'dataset.json').write_bytes(payload)
            binding={'status':'READY_FOR_FULL_BOARD_TEST_NOT_BOARD_MEASURED',
                'files':{'dataset.json':{'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}}}
            (folder/'identity.json').write_text(json.dumps(binding))
            # Even a length-preserving metadata change must be rejected before
            # any output is interpreted (no board outputs exist in this test).
            (folder/'dataset.json').write_bytes(payload.replace(b'plantvillage',b'PLANTVILLAGE'))
            with self.assertRaisesRegex(ValueError,'published file hash differs: dataset.json'):
                summarize(folder)

if __name__=='__main__':unittest.main()
