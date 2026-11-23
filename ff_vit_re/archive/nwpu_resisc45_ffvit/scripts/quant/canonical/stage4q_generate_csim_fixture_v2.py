"""Canonical semantic input conversion; no historical fixture loading."""
import torch
import torch.nn.functional as F
T = 196
PATCH_DIM = 768

def make_input_codes(img_chw: torch.Tensor) -> torch.Tensor:
    """
    img_chw is the normalized eval-transform tensor [3,224,224].

    Stage2 input rule:
        q = round(x_norm * 64)

    HLS testbench stores each stream value in an int32 input_data array,
    while the AXI packet element itself is ap_int<16>.
    """
    if tuple(img_chw.shape) != (3, 224, 224):
        raise RuntimeError(
            f"Expected normalized [3,224,224], got {tuple(img_chw.shape)}"
        )

    q = torch.round(
        img_chw * 64.0
    ).to(torch.int64)

    if bool(((q < -32768) | (q > 32767)).any()):
        raise RuntimeError("Input quantization overflowed signed int16")

    # Conv2d-compatible patch flattening:
    # [1,3,224,224] -> [1,768,196] -> [196,768].
    patches = F.unfold(
        q.unsqueeze(0).to(torch.float32),
        kernel_size=(16, 16),
        stride=(16, 16),
    )

    patches = (
        torch.round(patches)
        .to(torch.int64)
        .squeeze(0)
        .transpose(0, 1)
        .contiguous()
    )

    if tuple(patches.shape) != (T, PATCH_DIM):
        raise RuntimeError(
            f"Patchified input shape {tuple(patches.shape)} != {(T, PATCH_DIM)}"
        )

    return patches
