"""Opt-in real-fixture CPU/CUDA equality before formal GPU integer evaluation."""
import os
from pathlib import Path
import pytest
import torch
from src import exact


@pytest.mark.skipif(os.environ.get('FFVIT_RUN_EXACT_CUDA_TEST')!='1',reason='GPU schedule controlled by parent')
def test_all_fixed_fixture_integer_boundaries_match_cpu_cuda():
    root=Path(__file__).resolve().parents[1]
    artifact,_=exact.load_artifact(root/'exact/main')
    fixture,_=exact.load_artifact(root/'reports/exact_probe128_shards/fixtures')
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False
    images=torch.from_numpy(fixture['images'])
    with torch.inference_mode():
        cpu,ct=exact.forward(images,artifact,trace=True)
        gpu,gt=exact.forward(images.cuda(),artifact,trace=True)
    assert torch.equal(cpu,gpu.cpu())
    assert ct.keys()==gt.keys()
    for name in ct:
        assert torch.equal(ct[name],gt[name].cpu()),name
