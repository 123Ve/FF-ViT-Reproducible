import pytest
import torch
from torch import nn
from timm.models.vision_transformer import Block as TimmBlock

from src.quant import StrictS3Controller, fake_quantize, tensor_error_statistics


class TinyAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.num_heads = 1
        self.head_dim = 3
        self.scale = 3 ** -0.5
        self.fused_attn = False
        self.qkv = nn.Linear(3, 9, bias=False)
        self.q_norm = nn.Identity()
        self.k_norm = nn.Identity()
        self.attn_drop = nn.Dropout(0)
        self.norm = nn.Identity()
        self.proj = nn.Linear(3, 3, bias=False)
        self.proj_drop = nn.Identity()

    def forward(self, x, attn_mask=None):
        batch, tokens, channels = x.shape
        q, k, v = self.qkv(x).reshape(batch, tokens, 3, 1, 3).permute(2, 0, 3, 1, 4).unbind(0)
        a = (q * self.scale @ k.transpose(-2, -1)).softmax(-1)
        return self.proj((a @ v).transpose(1, 2).reshape(batch, tokens, channels))


class TinyBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.norm1 = nn.Identity()
        self.attn = TinyAttention()
        self.norm2 = nn.Identity()
        self.mlp = nn.Module()
        self.mlp.fc1 = nn.Linear(3, 3, bias=False)
        self.mlp.act = nn.GELU()
        self.mlp.fc2 = nn.Linear(3, 3, bias=False)

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        return x + self.mlp.fc2(self.mlp.act(self.mlp.fc1(self.norm2(x))))


class TinyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.vit = nn.Module()
        self.vit.blocks = nn.Sequential(TinyBlock(), TinyBlock())

    def forward(self, x):
        return self.vit.blocks(x)


class ToggleLinear(nn.Linear):
    def __init__(self, enabled=True):
        super().__init__(3, 3, bias=False)
        self.quant_enabled = enabled

    def set_quant_enabled(self, enabled):
        self.quant_enabled = bool(enabled)

    def forward(self, x):
        weight = self.weight.round() if self.quant_enabled else self.weight
        return nn.functional.linear(x, weight)


def test_signed_and_unsigned_domains_and_ties_to_even():
    values = torch.tensor([-10., -3.5, -2.5, -.5, .5, 1.5, 2.5, 3.5, 10.])
    assert fake_quantize(values, 1., signed=True, bits=3).tolist() == [-4., -4., -2., 0., 0., 2., 2., 3., 3.]
    assert fake_quantize(values, 1., signed=False, bits=3).tolist() == [0., 0., 0., 0., 0., 2., 2., 4., 7.]
    with pytest.raises(ValueError):
        fake_quantize(values, 0., signed=True, bits=3)


def test_qkv_independent_hooks_and_block_mask():
    model = TinyModel()
    controller = StrictS3Controller(model, scales={"q": [1., 1.], "k": [2., 2.], "v": [4., 4.]})
    values = torch.tensor([[[1.6, 1.6, 1.6]]])
    unquantized_first = model.vit.blocks[0].attn.qkv(values)
    controller.set_enabled({"q", "k", "v"}, blocks={0})
    controller.install()
    first = model.vit.blocks[0].attn.qkv(values)
    second = model.vit.blocks[1].attn.qkv(values)
    q, k, v = first.chunk(3, dim=-1)
    original_q, original_k, original_v = unquantized_first.chunk(3, dim=-1)
    assert torch.equal(q, fake_quantize(original_q, 1., signed=True, bits=3))
    assert torch.equal(k, fake_quantize(original_k, 2., signed=True, bits=3))
    assert torch.equal(v, fake_quantize(original_v, 4., signed=True, bits=3))
    assert torch.equal(second, model.vit.blocks[1].attn.qkv(values))
    controller.remove()
    assert torch.equal(model.vit.blocks[0].attn.qkv(values), unquantized_first)


def test_softmax_u3_only_when_enabled():
    model = TinyModel()
    controller = StrictS3Controller(model, scales={"softmax": [1 / 7, 1 / 7]})
    x = torch.randn(1, 3, 3)
    controller.install()
    base = model(x)
    controller.set_enabled({"softmax"}, blocks={0})
    altered = model(x)
    assert not torch.equal(base, altered)
    assert set(controller.observations) == {(0, "softmax")}
    assert controller.observations[(0, "softmax")]["after"].min() >= 0
    assert controller.observations[(0, "softmax")]["after"].max() <= 1
    controller.remove()
    assert torch.allclose(model(x), base)


def test_tensor_statistics_reports_error_and_clipping():
    stats = tensor_error_statistics(torch.tensor([0., 2., 4.]), torch.tensor([0., 2., 3.]), qmin=0, qmax=3, scale=1.)
    assert stats["mse"] == pytest.approx(1 / 3)
    assert stats["mae"] == pytest.approx(1 / 3)
    assert stats["clip_rate"] == pytest.approx(1 / 3)
    assert stats["zero_rate"] == pytest.approx(1 / 3)


def test_controller_scales_receive_gradients_without_registering_parent_weights():
    model = TinyModel()
    controller = StrictS3Controller(model, scales={"ln1": [0.3, 0.3]})
    controller.set_enabled({"ln1"}, blocks={0})
    controller.install()
    result = model(torch.tensor([[[0.2, 0.7, 1.1]]])).sum()
    result.backward()
    assert controller.scale("ln1", 0).requires_grad
    assert controller.log_scales["ln1"].grad is not None
    assert controller.log_scales["ln1"].grad[0].abs() > 0
    assert not any(name.startswith("model.") for name, _ in controller.named_parameters())
    controller.remove()


def test_operator_masks_can_target_different_blocks():
    model = TinyModel()
    controller = StrictS3Controller(model, scales={"q": [0.2, 0.2], "k": [0.3, 0.3]})
    values = torch.tensor([[[0.43, 0.79, 1.1]]])
    original = [block.attn.qkv(values) for block in model.vit.blocks]
    controller.set_masks({"q": {0}, "k": {1}})
    controller.install()
    altered = [block.attn.qkv(values) for block in model.vit.blocks]
    for index in range(2):
        q0, k0, v0 = original[index].chunk(3, dim=-1)
        q1, k1, v1 = altered[index].chunk(3, dim=-1)
        assert torch.allclose(q1, fake_quantize(q0, 0.2, signed=True, bits=3) if index == 0 else q0)
        assert torch.allclose(k1, fake_quantize(k0, 0.3, signed=True, bits=3) if index == 1 else k0)
        assert torch.equal(v1, v0)
    controller.remove()


def test_weight_mask_perturbs_only_selected_module_and_restores_parent_state():
    model = TinyModel()
    for block in model.vit.blocks:
        block.mlp.fc1 = ToggleLinear(enabled=True)
        block.mlp.fc2 = ToggleLinear(enabled=True)
    model.vit.blocks[1].mlp.fc2.set_quant_enabled(False)
    baseline = [(block.mlp.fc1.quant_enabled, block.mlp.fc2.quant_enabled) for block in model.vit.blocks]
    controller = StrictS3Controller(model, scales={})
    controller.set_masks({"fc1_weight": {0}})
    controller.install()
    assert [(block.mlp.fc1.quant_enabled, block.mlp.fc2.quant_enabled) for block in model.vit.blocks] == [(False, True), (True, False)]
    controller.set_masks({"fc2_weight": {0}})
    assert [(block.mlp.fc1.quant_enabled, block.mlp.fc2.quant_enabled) for block in model.vit.blocks] == [(True, False), (True, False)]
    controller.remove()
    assert [(block.mlp.fc1.quant_enabled, block.mlp.fc2.quant_enabled) for block in model.vit.blocks] == baseline


def test_unsupported_weight_mask_rejects_before_any_hook_is_installed():
    model = TinyModel()
    controller = StrictS3Controller(model, scales={})
    original_forward = model.vit.blocks[0].attn.forward
    with pytest.raises(TypeError, match="progressive W3"):
        controller.set_masks({"fc1_weight": {0}})
        controller.install()
    assert not controller._handles
    assert model.vit.blocks[0].attn.forward == original_forward
    assert not model.vit.blocks[0].attn.qkv._forward_hooks
    assert not model.vit.blocks[0].norm1._forward_hooks


def test_attention_residual_quantizes_the_mlp_skip_tensor():
    model = nn.Module()
    model.vit = nn.Module()
    model.vit.blocks = nn.Sequential(TimmBlock(12, 3, mlp_ratio=2.))
    for parameter in model.parameters():
        parameter.data.zero_()
    controller = StrictS3Controller(model, scales={"attention_residual": [1.]})
    controller.set_masks({"attention_residual": {0}})
    controller.install()
    try:
        output = model.vit.blocks(torch.full((1, 2, 12), .4))
        assert torch.equal(output, torch.zeros_like(output))
        assert torch.equal(controller.observations[(0, "attention_residual")]["after"], output)
    finally:
        controller.remove()
