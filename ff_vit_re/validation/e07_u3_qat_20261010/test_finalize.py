import importlib.util
import sys
import unittest
import tempfile
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

class FinalizeTests(unittest.TestCase):
    def test_existing_artifact_rejects_changed_checkpoint_or_parameters(self):
        import finalize
        from runtime import exact
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'artifact'
            a={'x':np.array([1,2],dtype=np.int64)}
            exact.save_artifact(path,a,{'checkpoint_sha256':'old'})
            finalize.persist_artifact(path,a,'old')
            with self.assertRaises(ValueError):finalize.persist_artifact(path,a,'new')
            with self.assertRaises(ValueError):finalize.persist_artifact(path,{'x':np.array([1,3],dtype=np.int64)},'old')
    def test_merge_weights_by_output_elements_not_blocks(self):
        self.assertIsNotNone(importlib.util.find_spec('finalize'),'final evidence module missing')
        import finalize
        self.assertEqual(finalize.weighted_mae([(2,1.),(1,4.)]),2.)
        with self.assertRaises(ValueError):finalize.weighted_mae([])

    def test_export_rejects_softmax_gain_narrowing_not_just_weights(self):
        import finalize
        from runtime import u
        a=u.load_native_artifact(u.dataset_spec('plantvillage'))
        for p in a['blocks']:p['softmax']['scalars'][13]=3
        a['blocks'][0]['softmax']['recip1']=a['blocks'][0]['softmax']['recip1'].astype('int64')
        a['blocks'][0]['softmax']['recip1'][0]=256
        with self.assertRaises(ValueError):finalize.verify_export(a)

if __name__=='__main__':unittest.main()
