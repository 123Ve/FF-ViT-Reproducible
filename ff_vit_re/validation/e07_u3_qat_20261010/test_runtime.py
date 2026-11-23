import copy
import importlib.util
import sys
import unittest
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

class RuntimeTests(unittest.TestCase):
    def runtime(self):
        self.assertIsNotNone(importlib.util.find_spec('runtime'),'strict E07 runtime is missing')
        import runtime
        return runtime

    def test_unsigned_head_negative_sum_does_not_use_signed_fix(self):
        r=self.runtime()
        p=dict(scalars=np.array([683,17,0,14,63,0,8]),lnw=np.ones(192,dtype=np.int32),
               lnb=np.zeros(192,dtype=np.int64),rsqrt_table=np.ones(128,dtype=np.int64))
        x=torch.full((1,192),-1,dtype=torch.int64)
        d=r.head_intermediates(x,p)
        self.assertEqual(d['sum'].item(),32576)
        self.assertEqual(d['mean'].item(),42)
        self.assertEqual(d['variance'].item(),355008)
        self.assertTrue(torch.equal(r.head_layernorm(x,p),torch.full_like(x,-43)))

    def test_exact_ste_has_exact_forward_without_float_cancellation(self):
        r=self.runtime()
        proxy=torch.tensor([1e15,-1e15],requires_grad=True)
        actual=torch.tensor([3,-4])
        output=r.ste(proxy,actual)
        self.assertEqual(output.tolist(),[3.,-4.])
        output.sum().backward()
        self.assertEqual(proxy.grad.tolist(),[1.,1.])

    def test_softmax_u3_is_clamp_not_modulo(self):
        r=self.runtime()
        s=np.array([0,0,31,0,0,63,0,0,0,0,63,0,0,3])
        p=dict(scalars=s,exp=np.ones(32,dtype=np.uint16)*4096,
               recip1=np.ones(64,dtype=np.uint8)*255,recip2=np.ones(64,dtype=np.uint8)*255)
        y=r.exact.fused_softmax(torch.zeros((1,196,196),dtype=torch.int64),s,p['exp'],p['recip1'],p['recip2'])
        self.assertTrue(torch.equal(y,torch.full_like(y,7)))

    def test_trained_export_matches_forward_and_weight_gradients_exist(self):
        r=self.runtime()
        self.assertTrue(hasattr(r,'StrictQAT'),'differentiable strict runtime missing')
        spec=r.u.dataset_spec('plantvillage')
        a=r.u.load_native_artifact(spec)
        for p in a['blocks']:
            p['softmax']['scalars'][13]=3
            p['softmax']['scalars'][7]+=5
            p['softmax']['scalars'][12]+=5
        state=torch.load(spec['checkpoint'],weights_only=True,map_location='cpu')['student_state']
        import json
        ref=r.u.reference_parameters(spec)
        sm=json.loads((spec['reports']/'stage4l_exact_softmax_aq/report.json').read_text())['blocks']
        hs=json.loads((spec['reports']/'stage4o2_head_safe/report.json').read_text())
        for b,p in enumerate(ref):
            p['q_scale']=sm[str(b)]['q_scale'];p['k_scale']=sm[str(b)]['k_scale']
        model=r.StrictQAT(a,state,ref,38,dict(ln=hs['selected_logit_scale']/hs['selected_weight_scale'],weight=hs['selected_weight_scale']))
        torch.manual_seed(17)
        image=torch.randn(1,3,224,224)
        torch.set_num_threads(2)
        output=model(image)
        wanted,_=r.integer_forward(image,model.export())
        self.assertTrue(torch.equal(output.detach().long(),wanted))
        loss=F.cross_entropy(output[:,:38]*model.logit_scale,torch.tensor([3]))
        loss.backward()
        grad=model.blocks[-1].linears['m2'].master.grad
        self.assertIsNotNone(grad)
        self.assertTrue(torch.isfinite(grad).all())
        self.assertGreater(float(grad.abs().sum()),0)
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-5)
        optimizer.step()
        next_output=model(image)
        after,_=r.integer_forward(image,model.export())
        self.assertTrue(torch.equal(next_output.detach().long(),after))
        self.assertFalse(torch.equal(model.head_bias.detach(),model.initial_head_bias))

if __name__=='__main__':unittest.main()
