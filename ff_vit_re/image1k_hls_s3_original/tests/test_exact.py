"""Hand-computed vectors for original HLS casts and operator ordering."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
import torch


def kernel():
    assert importlib.util.find_spec('src.exact'), 'exact implementation is required'
    from src import exact
    return exact


def test_wrap_is_not_saturation_and_shift_rounds_negative_ties_up():
    e = kernel()
    assert e.wrap(torch.tensor([-5, -4, 3, 4, 7, 8]), 3).tolist() == [3, -4, 3, -4, -1, 0]
    assert e.requant(torch.tensor([-3, -1, 1, 3]), 1, 1, 3).tolist() == [-1, 0, 1, 2]


def test_lut_cast_precedes_clamp():
    e = kernel()
    table = torch.arange(64)
    assert e.address_lut(torch.tensor([-1, 255, 256, 511, 512]), [0, 0, 63, 0], table, 9).tolist() == [0, 63, 0, 0, 0]
    assert e.address_lut(torch.tensor([-5, -1, 0, 2]), [2, 1, 3, 0], torch.tensor([0, 2, 5, 7]), 32).tolist() == [0, 0, 2, 5]


def test_residual_cast_wraps_before_and_after_addition():
    e = kernel()
    assert e.residual(torch.tensor([7, -8]), torch.tensor([3, -3]), [2, 0], 4).tolist() == [1, -3]


def test_ln_centred_difference_wrap_and_affine_clamp():
    e = kernel()
    p = dict(scalars=[1, 1, 0, 0, 0, 0, 3], lnw=[1, 1], lnb=[0, 0], rsqrt_table=[1])
    # Mean(-4, 3) rounds -0.5 to 0; identity affine then clamps to s3.
    assert e.layernorm(torch.tensor([[-4, 3]]), p, input_bits=3).tolist() == [[-4, 3]]


def test_softmax_uses_unsigned_cast_then_clamp_then_u3_output():
    e = kernel()
    # Equal exp=4, reciprocal=2 => product8, shift1 =>4 each.
    scalars = [0, 0, 0, 0, 0, 63, 0, 1, 0, 0, 63, 0, 1, 3]
    assert e.softmax(torch.tensor([[0, 0]]), scalars, [4], [2]*64, [2]*64).tolist() == [[4, 4]]
    # A clamp8 scalar is legal in the original ABI: 8 becomes 0 on final u3 cast.
    scalars[7] = 0; scalars[13] = 8
    assert e.softmax(torch.tensor([[0, 0]]), scalars, [4], [2]*64, [2]*64).tolist() == [[0, 0]]


def test_pack3_little_endian_and_padding():
    e = kernel()
    values = np.zeros((1, 32), dtype=np.int8)
    values[0, :4] = [-4, -1, 0, 3]
    packed = e.pack3(values)
    assert packed == bytes([60, 6]) + bytes(14)
    np.testing.assert_array_equal(e.unpack3(packed, (1, 32)), values)
    with pytest.raises(ValueError):
        e.pack3(np.full((1, 32), 4))


def test_source_binding_detects_mutation(tmp_path):
    e = kernel()
    source = tmp_path / 'source.h'; source.write_text('original')
    record = e.bind_sources([source])
    source.write_text('changed')
    with pytest.raises(ValueError, match='hash'):
        e.verify_sources(record)


def test_head_has_narrow_signed_mean_and_unsigned_variance():
    e = kernel()
    p = dict(scalars=[1, 1, 0, 0, 0, 0, 8], lnw=[1, 1], lnb=[0, 0], rsqrt_table=[1])
    # Rounded mean100 casts to signed7=-28, diff128 clamps to signed8=127.
    assert e.layernorm(torch.tensor([[100, 100]]), p, input_bits=13, head=True).tolist() == [[127, 127]]


def test_histogram_lut_and_ln_fit_replay_original_contract():
    e = kernel()
    assert hasattr(e, 'fitters'), 'original HLS fitters required'
    f = e.fitters()
    x = torch.tensor([[-2, -1, 0, 1]*48, [-1, 0, 1, 2]*48])
    y = torch.tensor([[-1, 0, 0, 1]*48]*2)
    fitted = f['fit_layernorm_codes'](x, y, input_scale=.1, eps=1e-6, output_bits=3)
    assert e.layernorm(x, fitted, input_bits=13).tolist() == y.tolist()
    counts = np.zeros(2048, dtype=np.int64); counts[1024:1032] = 10
    lut = f['lut'].fit_gelu_u3_lut(counts, input_scale=1., output_scale=1.)
    actual = e.address_lut(torch.arange(8), [lut.bias, lut.shift, lut.bound], lut.table, 32)
    assert actual.tolist() == [0, 1, 2, 3, 4, 5, 6, 7]


def test_fused_softmax_does_not_apply_unused_typedef_casts():
    e = kernel()
    assert hasattr(e, 'fused_softmax')
    scalars = [0, 0, 1, 0, 0, 63, 0, 0, 0, 0, 63, 0, 0, 8]
    # fused rq is int, so8 survives. Standalone Softmax converts to u3 and returns0.
    assert e.fused_softmax(torch.tensor([[0, 0]]), scalars, [4, 1], [2]*64, [2]*64).tolist() == [[8, 8]]


def test_integer_gemm_patch_trace_and_model_dimensions():
    e = kernel()
    assert hasattr(e, 'matmul')
    assert e.matmul(torch.tensor([[3, -4]]), torch.tensor([[3], [-4]])).tolist() == [[25]]
    with pytest.raises(ValueError, match='exact'):
        e.matmul(torch.tensor([[1 << 50]]), torch.tensor([[1 << 10]]))


def test_fitted_fused_softmax_matches_uniform_u3_target():
    from src import exact
    assert hasattr(exact, 'fit_softmax')
    x = torch.zeros(16, 4, dtype=torch.int64)
    p = exact.fit_softmax(x, score_scale=.1, output_scale=.125)
    result = exact.fused_softmax(x, p['scalars'], p['exp'], p['recip1'], p['recip2'])
    assert result.tolist() == [[2]*4]*16
    assert p['scalars'][13] == 3


def test_exp_fit_avoids_denominator_overflow_for_full_token_row():
    from src import exact
    p=exact.fit_softmax(torch.zeros(2,196,dtype=torch.int64),score_scale=.1,output_scale=1/196)
    assert int(p['exp'].max())*196 < 1 << 23


def test_block_replay_obeys_mac_and_residual_wrap():
    from src import exact
    assert hasattr(exact, 'block_forward')
    ln = dict(scalars=[1, 1, 0, 0, 0, 0, 3], lnw=[0]*192, lnb=[0]*192, rsqrt_table=[1])
    p = {'ln1': ln, 'ln2': ln, 'attn_residual': [1, 0], 'mlp_residual': [1, 0]}
    for name, shape in [('q', (192,192)), ('k', (192,192)), ('v', (192,192)), ('o', (192,192)), ('m1', (768,192)), ('m2', (192,768))]:
        p[name+'_w'] = torch.zeros(shape, dtype=torch.int64)
        p[name+'_b'] = torch.zeros(shape[0], dtype=torch.int64)
    for name in ['q', 'k', 'v', 'a', 'gelu']:
        p[name+'_lut'] = dict(scalars=[0,0,0], table=[0])
    p['softmax'] = dict(scalars=[0,0,0,0,0,63,0,1,0,0,63,0,1,3], exp=[1], recip1=[1]*64, recip2=[1]*64)
    p['o_b'][0] = 1; p['m2_b'][0] = 1
    x = torch.zeros(1,196,192, dtype=torch.int64); x[:,:,0] = 4095
    y, trace = exact.block_forward(x, p, trace=True)
    assert y[0,0,0] == -4095
    assert trace['attention_residual'][0,0,0] == 4096


def test_artifact_rebuild_is_deterministic_and_tamper_fails(tmp_path):
    from src import exact
    assert hasattr(exact, 'save_artifact')
    value = {'blocks':[{'weight':np.array([-4,3],np.int8)}], 'scale': .1}
    exact.save_artifact(tmp_path/'one', value, {'checkpoint':exact.CHECKPOINT_SHA256})
    exact.save_artifact(tmp_path/'two', value, {'checkpoint':exact.CHECKPOINT_SHA256})
    assert (tmp_path/'one/arrays.npz').read_bytes() == (tmp_path/'two/arrays.npz').read_bytes()
    result, _ = exact.load_artifact(tmp_path/'one')
    assert result['blocks'][0]['weight'].tolist() == [-4,3]
    (tmp_path/'one/arrays.npz').write_bytes(b'broken')
    with pytest.raises(ValueError, match='hash'):
        exact.load_artifact(tmp_path/'one')


def test_original_block_fit_uses_physical_mac_scale_not_surrogate_fc_scale():
    from src import exact
    assert hasattr(exact, 'fit_block')
    state = {}; weights = {}
    prefix = 'vit.blocks.0.'
    for name in ['norm1','norm2']:
        state[prefix+name+'.weight'] = torch.ones(192)
        state[prefix+name+'.bias'] = torch.zeros(192)
    for name, shape, segments in [('attn.qkv',(576,192),3),('attn.proj',(192,192),1),('mlp.fc1',(768,192),1),('mlp.fc2',(192,768),1)]:
        state[prefix+name+'.bias'] = torch.zeros(shape[0])
        weights[prefix+name] = {'code':torch.zeros(shape,dtype=torch.int8),'scales':torch.full((segments,),.25)}
    scales = {name:[.5]*12 for name in ['ln1','q','k','v','a','softmax','ln2','gelu','fc1','fc2','o','attention_residual','mlp_residual']}
    scales['fc1'][0]=100.; scales['fc2'][0]=200.
    p, report = exact.fit_block(0,torch.zeros(1,196,192,dtype=torch.int64),.1,state,weights,scales,fit_tokens=196)
    assert report['physical_m1_scale'] == .125
    assert report['physical_m2_scale'] == .125
    y,_ = exact.block_forward(torch.zeros(1,196,192,dtype=torch.int64),p)
    assert int(y.abs().max()) == 0


def test_head_fitter_replays_same_narrow_statistics():
    assert importlib.util.find_spec('src.exact_head_fit'), 'head fitter required'
    from src import exact_head_fit, exact
    x = torch.arange(192).reshape(1,-1).repeat(4,1)-96
    stats = exact_head_fit.signed_head_stats(x)
    assert stats['acc15'].tolist() == [-96]*4
    assert stats['mean7'].tolist() == [-1]*4
    assert stats['diff13'][0,:4].tolist() == [-95,-94,-93,-92]


def test_patch_replaces_first_patch_with_cls_and_wraps_s13():
    from src import exact
    assert hasattr(exact,'patch_forward')
    p={'weight_code':np.zeros((192,768),np.int8),'bias_raw':np.zeros((196,192),np.int64),
       'cls_raw':np.full(192,256*4096,np.int64),'shift':8}
    p['bias_raw'][1]=256*3
    x=exact.patch_forward(torch.zeros(1,3,224,224),p)
    assert x.shape==(1,196,192)
    assert x[0,0,0]==-4096 and x[0,1,0]==3


def test_evaluation_resume_rechecks_predictions_and_labels():
    from scripts import evaluate_exact
    assert hasattr(evaluate_exact,'validate_shard')
    row=dict(ids=['a'],labels=[4],top5=[[4,0,1,2,3]],correct1=1,correct5=1)
    assert evaluate_exact.validate_shard(row,['a'],torch.tensor([4]))==(1,1)
    row['correct1']=0
    with pytest.raises(ValueError,match='count'):
        evaluate_exact.validate_shard(row,['a'],torch.tensor([4]))


def test_integer_logit_ties_choose_lowest_class_id():
    from scripts import evaluate_exact
    assert hasattr(evaluate_exact,'rank_logits')
    assert evaluate_exact.rank_logits(torch.tensor([[7,7,7,6,6,6]])).tolist()==[[0,1,2,3,4]]
