"""Deployment-only Stage4P/K/I quantization of the frozen Stage4J state.

Stage4P restores student, MLP controller, then attention controller. Each
controller includes the shared backbone, so the final attention-controller
backbone is authoritative. No model construction or training imports are needed.
"""

import numpy as np
import torch


def quantize_checkpoint(path):
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    attention = checkpoint["attention_controller_state"]
    mlp = checkpoint["mlp_controller_state"]
    state = attention
    if tuple(state["backbone.vit.pos_embed"].shape) != (1, 196, 192):
        raise ValueError("Expected frozen T=196, C=192 backbone")
    blocks = []
    for block in range(12):
        prefix = f"backbone.vit.blocks.{block}."

        def tensor(module, field):
            return state[prefix + module + "." + field].detach()

        def weight_scale(module):
            return torch.exp(tensor(module, "log_scale")).reshape(())

        def weight(module):
            # Preserve torch float32 division/rounding from Stage4I.
            return torch.clamp(torch.round(tensor(module, "weight") /
                                           weight_scale(module)), -4, 3).numpy().astype(np.int8)

        def bias(values, scale, bits):
            codes = torch.round(values / float(scale)).to(torch.int64)
            half = 1 << (bits - 1)
            return ((codes + half) % (1 << bits) - half).numpy().astype(np.int16)

        q = {}
        ln1 = float(torch.exp(attention["log_ln1_scale"][block]))
        scales = torch.exp(tensor("attn.qkv", "log_scale")).reshape(-1)
        if scales.numel() != 3:
            raise ValueError("Expected three independent Q/K/V scales")
        weights = torch.chunk(tensor("attn.qkv", "weight"), 3, dim=0)
        biases = torch.chunk(tensor("attn.qkv", "bias"), 3, dim=0)
        for name, w, b, scale, bits in zip("qkv", weights, biases, scales, (12, 11, 11)):
            q[name + "_w"] = torch.clamp(torch.round(w / float(scale)), -4, 3).numpy().astype(np.int8)
            q[name + "_b"] = bias(b, ln1 * float(scale), bits)

        # O uses a product of Python floats in Stage4P. MLP controller products
        # are evaluated as float32 tensors before conversion to Python floats.
        o_scale = float(torch.exp(attention["log_a_scale"][block])) * float(weight_scale("attn.proj"))
        m1_scale = float(torch.exp(mlp["log_ln2_scale"][block]) * weight_scale("mlp.fc1"))
        m2_scale = float(torch.exp(mlp["log_gelu_scale"][block]) * weight_scale("mlp.fc2"))
        for name, module, scale, bits, shape in (
            ("o", "attn.proj", o_scale, 13, (192, 192)),
            ("m1", "mlp.fc1", m1_scale, 11, (768, 192)),
            ("m2", "mlp.fc2", m2_scale, 13, (192, 768)),
        ):
            q[name + "_w"] = weight(module)
            q[name + "_b"] = bias(tensor(module, "bias"), scale, bits)
            if q[name + "_w"].shape != shape:
                raise ValueError(f"Invalid block {block} {name} weight shape")
        for name in "qkv":
            if q[name + "_w"].shape != (192, 192) or q[name + "_b"].shape != (192,):
                raise ValueError(f"Invalid block {block} {name} shape")
        blocks.append(q)
    return blocks
