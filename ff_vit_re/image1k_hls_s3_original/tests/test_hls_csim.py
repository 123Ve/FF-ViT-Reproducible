import importlib.util
import numpy as np
import pytest


def harness():
    assert importlib.util.find_spec('src.hls_csim'), 'HLS comparison harness required'
    from src import hls_csim
    return hls_csim


def test_stream_dump_layout_preserves_both_tokens():
    h = harness()
    logical = np.arange(196*192, dtype=np.int32).reshape(196,192)
    stream = logical.reshape(98,2,192).transpose(0,2,1).reshape(-1)
    np.testing.assert_array_equal(h.unpack_fm(stream), logical)
    with pytest.raises(ValueError):
        h.unpack_fm(stream[:-1])


def test_boundary_comparison_fails_on_one_bit_and_missing_stage(tmp_path):
    h = harness()
    traces = {'patch':np.zeros((196,192),dtype=np.int32),
              **{f'block{i:02d}.mlp_residual':np.zeros((196,192),dtype=np.int32) for i in range(12)},
              'logits':np.zeros(1000,dtype=np.int32)}
    for filename,key in h.BOUNDARIES.items():
        traces[key].astype('<i4').tofile(tmp_path/filename)
    assert h.compare_boundaries(tmp_path,traces)['passed']
    data = np.zeros(196*192,dtype='<i4');data[3]=1
    data.tofile(tmp_path/'hls_block7_out.bin')
    result=h.compare_boundaries(tmp_path,traces)
    assert not result['passed']
    assert result['boundaries']['block07.mlp_residual']['mismatch_count']==1
    (tmp_path/'hls_logits.bin').unlink()
    with pytest.raises(FileNotFoundError):
        h.compare_boundaries(tmp_path,traces)


def test_input_rejects_truncation_and_weights_wrong_native_stride(tmp_path):
    h=harness()
    p=tmp_path/'input.bin';p.write_bytes(bytes(196*768*2))
    h.validate_input(p)
    p.write_bytes(bytes(196*768*2-2))
    with pytest.raises(ValueError):h.validate_input(p)
    w=tmp_path/'weights.bin';w.write_bytes(bytes(231008*12))
    h.validate_weights(w)
    w.write_bytes(bytes(231008*12-1))
    with pytest.raises(ValueError):h.validate_weights(w)


def test_source_inventory_detects_changed_original(tmp_path):
    h=harness()
    p=tmp_path/'original.h';p.write_text('original')
    inventory={str(p):h.sha256(p)}
    h.verify_inventory(inventory)
    p.write_text('changed')
    with pytest.raises(ValueError,match='changed'):h.verify_inventory(inventory)
