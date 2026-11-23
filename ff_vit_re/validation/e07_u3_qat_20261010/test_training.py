import importlib.util
import sys
import unittest
import tempfile
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

class TrainingTests(unittest.TestCase):
    def test_resume_recipe_cannot_change_schedule_or_batch(self):
        t=self.training()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);recipe={'epochs':12,'micro_batch':64,'lr':1e-5}
            (out/'recipe.json').write_text(json.dumps(recipe))
            t.check_recipe(out,recipe,resume=True)
            with self.assertRaises(ValueError):t.check_recipe(out,dict(recipe,epochs=8),resume=True)
            self.assertEqual(json.loads((out/'recipe.json').read_text()),recipe)

    def test_initial_artifact_identity_is_immutable(self):
        t=self.training()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);artifact=out/'artifact';artifact.mkdir()
            (artifact/'manifest.json').write_text('{}');(artifact/'arrays.npz').write_bytes(b'original')
            identity=t.pin_initial(out,artifact,require_existing=False)
            self.assertEqual(t.pin_initial(out,artifact,require_existing=True),identity)
            (artifact/'manifest.json').write_text('{"modified":true}')
            with self.assertRaises(ValueError):t.pin_initial(out,artifact,require_existing=True)

    def test_resume_retains_superior_best_after_partial_checkpoint_save(self):
        t=self.training()
        recipe={'epochs':12}
        last={'best':50.,'recipe':recipe};best={'best':60.,'recipe':recipe}
        score=t.reconcile_best(last,best,recipe)
        self.assertEqual(score,60.)
        self.assertFalse(t.select_best('val',55.,score))
        with self.assertRaises(ValueError):t.reconcile_best(last,dict(best,recipe={'epochs':8}),recipe)

    def test_new_run_cannot_overwrite_orphaned_best_checkpoint(self):
        t=self.training()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'best.pth').write_bytes(b'preserve selected checkpoint')
            with self.assertRaises(ValueError):t.check_recipe(out,{'epochs':12},resume=False)
            self.assertEqual((out/'best.pth').read_bytes(),b'preserve selected checkpoint')
    def training(self):
        self.assertIsNotNone(importlib.util.find_spec('train'),'training runner missing')
        import train
        return train
    def test_test_labels_cannot_select_checkpoint(self):
        t=self.training()
        with self.assertRaises(ValueError):t.select_best('test',99.,1.)
        self.assertTrue(t.select_best('val',50.,49.))
        self.assertFalse(t.select_best('val',49.,50.))
    def test_nonfinite_validation_cannot_replace_best(self):
        t=self.training()
        with self.assertRaises(ValueError):t.select_best('val',float('nan'),50.)

if __name__=='__main__':unittest.main()
