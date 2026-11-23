import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from board_contract import FRAME_BYTES, LOGIT_BYTES

class FixtureBindingTests(unittest.TestCase):
    def test_fixture_reference_input_and_weights_bound_to_dataset(self):
        from qualify import verify_fixtures
        with tempfile.TemporaryDirectory(prefix='u3_fixture_binding_') as tmp:
            out=Path(tmp); data=out/'data';data.mkdir();hw=out/'hardware'
            inp=b'\x01'*FRAME_BYTES;gold=b'\x02'*LOGIT_BYTES;weights=b'weights'
            (data/'I000.BIN').write_bytes(inp);(data/'G000.BIN').write_bytes(gold)
            (data/'weights.bin').write_bytes(weights)
            fixture=hw/'fixtures/frame_00000';fixture.mkdir(parents=True)
            for name,value in [('input_dma.bin',inp),('expected.bin',gold),('weights.bin',weights),
                               ('csim_logits.bin',gold),('csim_repeat_logits.bin',gold)]:
                (fixture/name).write_bytes(value)
            meta={'csim_fixture_indices':[0],'count':1,'chunk_frames':1000}
            verify_fixtures(out,meta)
            for filename in ('input_dma.bin','expected.bin','weights.bin'):
                original=(fixture/filename).read_bytes();(fixture/filename).write_bytes(b'BAD'+original[3:])
                with self.assertRaises(ValueError): verify_fixtures(out,meta)
                (fixture/filename).write_bytes(original)

if __name__=='__main__':unittest.main()
