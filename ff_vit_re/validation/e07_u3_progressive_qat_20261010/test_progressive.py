import unittest
import torch
from torch import nn
from progressive import active_blocks, U3AttentionController,read_ranges,sources,u,epoch_loader,dependency_hashes

class DummyAttention(nn.Module):
    def __init__(self):
        super().__init__(); self.fused_attn=True
        self.attn_drop=nn.Identity(); self.qkv=nn.Identity(); self.proj=nn.Identity()
        self.qkv.log_scale=nn.Parameter(torch.zeros(3)); self.proj.log_scale=nn.Parameter(torch.zeros(1))
class DummyBlock(nn.Module):
    def __init__(self):
        super().__init__(); self.attn=DummyAttention(); self.norm1=nn.Identity(); self.norm2=nn.Identity()
class DummyBackbone(nn.Module):
    def __init__(self):
        super().__init__(); self.vit=nn.Module(); self.vit.blocks=nn.ModuleList([DummyBlock() for _ in range(12)])

class ProgressiveTests(unittest.TestCase):
    def setUp(self):
        self.backbone=DummyBackbone()
        ranges={f'b{b}.{key}':{'abs_p999':3.} for b in range(12)
            for key in ('ln1_out','q_prequant','k_prequant','v_prequant','attn_A_pre_proj')}
        self.c=U3AttentionController(self.backbone,ranges,torch.ones(12),torch.full((12,),.05))
        self.c.install()
    def tearDown(self):self.c.remove()
    def test_progression(self):
        self.assertEqual(active_blocks(1),list(range(6,12)))
        self.assertEqual(active_blocks(2),list(range(3,12)))
        self.assertEqual(active_blocks(3),list(range(12)))
        self.assertEqual(active_blocks(10),list(range(12)))
    def test_actual_ranges_schema(self):
        for name in ('plantvillage','nwpu'):
            ranges=read_ranges(sources(u.dataset_spec(name))['ranges'])
            self.assertGreater(ranges['b0.ln2_out']['abs_p999'],0)
    def test_epoch_loader_reproducible_without_main_rng(self):
        ds=torch.utils.data.TensorDataset(torch.arange(20))
        first=[x[0].tolist() for x in epoch_loader(ds,4,0,123,2)]
        torch.manual_seed(76543);torch.rand(100)
        second=[x[0].tolist() for x in epoch_loader(ds,4,0,123,2)]
        third=[x[0].tolist() for x in epoch_loader(ds,4,0,123,3)]
        self.assertEqual(first,second);self.assertNotEqual(first,third)
    def test_actual_dependencies_pinned(self):
        spec=u.dataset_spec('plantvillage');hashes=dependency_hashes(spec)
        self.assertIn(str(spec['rom']),hashes)
        self.assertTrue(any(p.endswith('stage4j_attention_activation_qat.py') for p in hashes))
        self.assertTrue(any(p.endswith('arrays.npz') for p in hashes))
    def test_inactive_is_unchanged_and_fused_disabled(self):
        self.c.set_active([11]); x=torch.tensor([.073,.876])
        self.assertTrue(torch.equal(self.backbone.vit.blocks[0].attn.attn_drop(x),x))
        self.assertTrue(all(not b.attn.fused_attn for b in self.backbone.vit.blocks))
    def test_u3_clamp_and_gradient(self):
        self.c.set_active([11]); x=torch.tensor([.073,.876],requires_grad=True)
        y=self.backbone.vit.blocks[11].attn.attn_drop(x)
        self.assertTrue(torch.allclose(y.detach()/self.c.softmax_scale(11).detach(),torch.tensor([1.,7.])))
        y.sum().backward()
        self.assertTrue(torch.isfinite(self.c.log_softmax_scale.grad).all())
        self.assertNotEqual(float(self.c.log_softmax_scale.grad[11]),0)
        self.assertEqual(float(x.grad[0]),1.)
    def test_raw_qkv_before_requant(self):
        self.c.set_active([11]); block=self.backbone.vit.blocks[11]
        raw=torch.full((1,1,576),3000.)
        y=block.attn.qkv(raw)
        self.assertEqual(tuple(y.shape),(1,1,576))
        self.assertTrue(bool((y<=3).all()))
    def test_residual_uses_physical_o_domain(self):
        self.c.set_active([11]); self.c.log_a_scale.data[11]=torch.log(torch.tensor(.5))
        x=torch.tensor([.26]); y=self.backbone.vit.blocks[11].norm2(x)
        self.assertTrue(torch.allclose(y,torch.tensor([.5])))

if __name__=='__main__':unittest.main()
