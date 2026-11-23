"""Integer replay of the original FF-ViT HLS ABI (no widened boundaries).

All operators consume integer codes. Float64 GEMM, when enabled, is permitted
only below its exact-integer mantissa bound; casts and LUTs remain integer.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import torch

HLS_ROOT = Path('/home/user/Desktop/FF_Vit/flash_vit_2/src')
CHECKPOINT_SHA256 = 'bf40fc4e40a27943f7b4e27b4b6e9dc9b45320c03b13ba181fb91fd81371fad3'


def fitters():
    from . import exact_fit
    from .model import legacy_module
    return {**vars(exact_fit), 'lut': legacy_module('legacy_s3_lut')}


def bind_sources(paths):
    return {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def verify_sources(records):
    for path, expected in records.items():
        if bind_sources([path])[path] != expected:
            raise ValueError(f'source hash mismatch: {path}')


def integer(value, device=None):
    value = torch.as_tensor(value, device=device)
    if value.is_floating_point() or value.is_complex():
        raise ValueError('integer codes required')
    return value.to(torch.int64)


def wrap(value, bits, signed=True):
    value = integer(value)
    if not 1 <= bits <= 62:
        raise ValueError('invalid integer width')
    half = (1 << (bits-1)) if signed else 0
    return (value + half).remainder(1 << bits) - half


def requant(value, multiplier, shift, bits):
    if not 0 <= shift <= 30:
        raise ValueError('invalid HLS residual shift')
    bias = (1 << (shift-1)) if shift else 0
    return wrap((integer(value)*int(multiplier)+bias) >> shift, bits)


def residual(skip, main, scalars, bits):
    return wrap(integer(main)+requant(skip, int(scalars[0]), int(scalars[1]), bits), bits)


def address_lut(value, scalars, table, cursor_bits, signed=True):
    bias, shift, bound = map(int, scalars[:3])
    cursor = wrap((integer(value)+bias) >> shift, cursor_bits, signed)
    return integer(table, cursor.device)[cursor.clamp(0, bound)]


def layernorm(value, params, *, input_bits, head=False):
    x = wrap(value, input_bits)
    m, shift, bias, address_shift, bound, affine_shift, bits = map(int, params['scalars'])
    acc = wrap(x.sum(-1), 15 if head else 32)
    mean = wrap((wrap(acc*m+(1 << (shift-1)), 30 if head else 32) >> shift), 7 if head else 32)
    diff = wrap(x-mean.unsqueeze(-1), input_bits)
    variance = wrap((diff*diff).sum(-1), 24, False) if head else wrap((x*x).sum(-1)-2*mean*acc+x.shape[-1]*mean*mean, 36)
    address = wrap((variance+bias) >> address_shift, 7 if head else 32, not head).clamp(0, bound)
    table = integer(params['rsqrt_table'], x.device)
    weight = integer(params['lnw'], x.device)
    bias = integer(params['lnb'], x.device)
    affine = wrap(diff*table[address].unsqueeze(-1)*weight+bias, 36 if head else 40)
    shifted = wrap(affine >> affine_shift, 9 if head else 32)
    return shifted.clamp(-(1 << (bits-1)), (1 << (bits-1))-1)


def softmax(scores, scalars, exp_table, reciprocal1, reciprocal2, *, fused=False):
    x = integer(scores) if fused else wrap(scores, 10)
    s = list(map(int, scalars))
    minus = wrap(x.max(-1, keepdim=True).values-x, 11)
    exp = address_lut(minus, s[:3], exp_table, 8, False)
    acc = wrap(exp.sum(-1), 23, False)
    one = wrap((acc+s[3]) >> s[4], 9, False)
    two = wrap((acc+s[8]) >> s[9], 7)
    use_two = one > s[5]
    recip = torch.where(use_two, wrap(integer(reciprocal2, x.device), 8, False)[two.clamp(0, s[10])],
                        wrap(integer(reciprocal1, x.device), 8, False)[one.clamp(0, s[5])])
    product = wrap(exp*recip.unsqueeze(-1), 23, False)
    bias = torch.where(use_two, s[11], s[6]).unsqueeze(-1)
    shift = torch.where(use_two, s[12], s[7]).unsqueeze(-1)
    cursor = (product+bias) >> shift
    if fused:
        return cursor.clamp(0, (1 << s[13])-1)
    return wrap(wrap(cursor, 8, False).clamp(0, (1 << s[13])-1), 3, False)


def fused_softmax(scores, scalars, exp_table, reciprocal1, reciprocal2):
    return softmax(scores, scalars, exp_table, reciprocal1, reciprocal2, fused=True)


def matmul(x, y):
    x, y = integer(x), integer(y)
    bound = int(x.abs().max())*int(y.abs().max())*x.shape[-1]
    if bound >= (1 << 53):
        raise ValueError('GEMM exceeds exact float64 integer mantissa')
    dtype = torch.float32 if bound < (1 << 24) else torch.float64
    # TF32 would truncate integer operands; an embedding caller must not enable it.
    if x.is_cuda and torch.backends.cuda.matmul.allow_tf32:
        raise ValueError('exact GEMM requires TF32 disabled')
    return torch.matmul(x.to(dtype), y.to(dtype)).to(torch.int64)


def fit_softmax(scores, *, score_scale, output_scale):
    """Histogram b/s search, then dual reciprocal tables; fixed original ABI."""
    x = integer(scores).cpu().reshape(-1, scores.shape[-1])
    if min(score_scale, output_scale) <= 0:
        raise ValueError('positive Softmax scales required')
    difference = x.max(-1, keepdim=True).values-x
    d = wrap(difference, 11).numpy().ravel()
    # PlantVillage EXP_SCALE=4096 bounds196-token sum below unsigned23.
    target = (torch.exp(-difference.double()*score_scale)*4096).round().numpy().ravel()
    counts = np.bincount(d+1024, minlength=2048).astype(np.float64)
    sums = np.bincount(d+1024, weights=target, minlength=2048)
    present = counts > 0
    values, count = np.arange(-1024, 1024)[present], counts[present]
    wanted = sums[present]/count
    best = None
    for shift in range(9):
        for bias in range(1 << shift):
            address = np.minimum(((values+bias) >> shift)%256, 31)
            c = np.bincount(address, weights=count, minlength=32)
            sm = np.bincount(address, weights=count*wanted, minlength=32)
            table = np.zeros(32, dtype=np.int64)
            used = np.where(c > 0)[0]
            table[used] = np.rint(sm[used]/c[used]).astype(np.int64).clip(0, 65535)
            for i in np.where(c == 0)[0]:
                table[i] = table[used[np.argmin(abs(used-i))]]
            error = float(np.average((table[address]-wanted)**2, weights=count))
            if best is None or error < best[0]:
                best = (error, bias, shift, table)
    _, bias, shift, table = best
    ex = address_lut(wrap(difference, 11), [bias, shift, 31], table, 8, False)
    acc = wrap(ex.sum(-1), 23, False)
    if bool((acc == 0).any()):
        raise ValueError('zero Softmax denominator')
    reference = (torch.softmax(x.double()*score_scale, -1)/output_scale).round().clamp(0, 7)
    # Spread fit rows across calibration instead of selecting a prefix class.
    idx = torch.linspace(0, len(x)-1, min(4096, len(x))).long()
    best_recip = None
    maximum = int(acc.max())
    start = max(0, maximum.bit_length()-6)
    for s2 in range(max(0, start-1), start+3):
        # Bank1 covers low sums at twice the address resolution of bank2.
        cursor1 = wrap(acc >> s2, 9, False)
        cursor2 = wrap(acc >> (s2+1), 7)
        region2 = cursor1 > 63
        for s3 in range(8, 25):
            desired = (float(1 << s3)/(acc.double()*output_scale)).round().clamp(0, 255)
            tables = []
            for cursor, mask in ((cursor1, ~region2), (cursor2, region2)):
                address = cursor.clamp(0, 63)
                sums = torch.bincount(address[mask], weights=desired[mask], minlength=64)
                counts = torch.bincount(address[mask], minlength=64)
                used = torch.where(counts > 0)[0]
                t = (sums/counts.clamp_min(1)).round().long()
                if len(used):
                    for i in torch.where(counts == 0)[0]:
                        t[i] = t[used[torch.argmin(abs(used-i))]]
                tables.append(t)
            scalars = [bias, shift, 31, 0, s2, 63, 1 << (s3-1), s3,
                       0, s2+1, 63, 1 << (s3-1), s3, 3]
            pred = fused_softmax(x[idx], scalars, table, *tables)
            error = float(((pred-reference[idx])**2).mean())
            if best_recip is None or error < best_recip[0]:
                best_recip = (error, scalars, tables)
    error, scalars, tables = best_recip
    return dict(scalars=np.array(scalars, np.int32), exp=table.astype(np.uint16),
                recip1=tables[0].numpy().astype(np.uint8), recip2=tables[1].numpy().astype(np.uint8).view(np.int8),
                mse=error, exp_mse=best[0], output_scale=output_scale)


def block_forward(x, params, *, trace=False):
    p = params
    records = {}
    def record(name, value):
        if trace:
            records[name] = value.detach().clone()
        return value
    def linear(value, name, bits):
        return record(name+'_raw', wrap(matmul(value, integer(p[name+'_w'], x.device).t())+integer(p[name+'_b'], x.device), bits))
    def lookup(value, name, bits):
        return record(name, address_lut(value, p[name+'_lut']['scalars'], p[name+'_lut']['table'], bits))
    ln = record('ln1', layernorm(x, p['ln1'], input_bits=13))
    q, k, v = [lookup(linear(ln, name, width), name, 9).reshape(-1,196,3,64).permute(0,2,1,3)
               for name, width in [('q',12), ('k',11), ('v',11)]]
    scores = record('scores', matmul(q,k.transpose(-1,-2)))
    sm = p['softmax']
    prob = record('softmax', fused_softmax(scores,sm['scalars'],sm['exp'],sm['recip1'],sm['recip2']))
    a = record('a_raw', wrap(matmul(prob, v), 11))
    a = lookup(a, 'a', 10).permute(0,2,1,3).reshape(-1,196,192)
    o = linear(a, 'o', 13)
    skip = record('attention_residual', residual(x,o,p['attn_residual'],15))
    ln2 = record('ln2', layernorm(skip,p['ln2'],input_bits=15))
    m1 = linear(ln2,'m1',11)
    gelu = lookup(m1,'gelu',32)
    m2 = linear(gelu,'m2',13)
    output = record('mlp_residual',residual(skip,m2,p['mlp_residual'],13))
    return output, records


def pack3(values):
    x = np.asarray(values)
    if x.ndim != 2 or x.shape[1] % 32 or x.dtype.kind not in 'iu' or np.any(x < -4) or np.any(x > 3):
        raise ValueError('pack3 requires s3 rows divisible by32')
    result = bytearray()
    for group in x.reshape(-1, 32):
        word = sum((int(v)&7) << (3*j) for j, v in enumerate(group))
        result.extend(word.to_bytes(16, 'little'))
    return bytes(result)


def unpack3(payload, shape):
    if len(payload)*2 != int(np.prod(shape)) or shape[1] % 32:
        raise ValueError('invalid packed matrix length')
    values = []
    for offset in range(0, len(payload), 16):
        word = int.from_bytes(payload[offset:offset+16], 'little')
        if word >> 96:
            raise ValueError('nonzero packed padding')
        values.extend((((word >> (j*3))&7)+4)%8-4 for j in range(32))
    return np.asarray(values, dtype=np.int8).reshape(shape)


def save_artifact(path, payload, metadata):
    root = Path(path)
    root.mkdir(parents=True, exist_ok=False)
    arrays = {}
    def encode(value):
        if torch.is_tensor(value):
            value = value.detach().cpu().numpy()
        if isinstance(value, np.ndarray):
            key = f'array_{len(arrays):05d}'
            arrays[key] = value
            return {'__array__':key}
        if isinstance(value, dict):
            return {k:encode(v) for k,v in sorted(value.items())}
        if isinstance(value, (tuple,list)):
            return [encode(v) for v in value]
        if isinstance(value, np.generic):
            return value.item()
        return value
    tree = encode(payload)
    with zipfile.ZipFile(root/'arrays.npz', 'w', compression=zipfile.ZIP_STORED) as archive:
        for key, value in arrays.items():
            stream = io.BytesIO(); np.save(stream,value,allow_pickle=False)
            archive.writestr(zipfile.ZipInfo(key+'.npy', date_time=(1980,1,1,0,0,0)),stream.getvalue())
    record = dict(schema='original_hls_s3.exact.v1',metadata=metadata,tree=tree,
                  arrays_sha256=hashlib.sha256((root/'arrays.npz').read_bytes()).hexdigest())
    (root/'manifest.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')


def load_artifact(path):
    root = Path(path)
    record = json.loads((root/'manifest.json').read_text())
    if record['schema'] != 'original_hls_s3.exact.v1':
        raise ValueError('exact schema mismatch')
    if hashlib.sha256((root/'arrays.npz').read_bytes()).hexdigest() != record['arrays_sha256']:
        raise ValueError('exact artifact hash mismatch')
    with np.load(root/'arrays.npz',allow_pickle=False) as arrays:
        def decode(value):
            if isinstance(value, dict):
                if set(value)=={'__array__'}:
                    return arrays[value['__array__']].copy()
                return {k:decode(v) for k,v in value.items()}
            if isinstance(value,list):
                return [decode(v) for v in value]
            return value
        return decode(record['tree']), record['metadata']


def fit_block(index, codes, input_scale, state, weights, scales, *, fit_tokens=4096):
    """Fit original LUTs from propagated exact input; no new MAC requantizers."""
    f = fitters(); lut = f['lut']
    prefix = f'vit.blocks.{index}.'
    def scale(name):
        return float(scales[name][index])
    # Whole images retain attention context. Spread over all calibration classes.
    chosen = torch.linspace(0,len(codes)-1,min(len(codes),max(1,fit_tokens//196))).long()
    x = integer(codes[chosen]).cpu()
    flat = x.reshape(-1,192)
    p = {}
    report = {'input_scale':input_scale, 'fit_images':len(x), 'fit_image_indices':chosen.tolist()}
    def fit_ln(value, name, input_bits, domain):
        source = value.reshape(-1,192)
        norm = 'norm1' if name=='ln1' else 'norm2'
        target = (torch.nn.functional.layer_norm(source.float()*domain,(192,),state[prefix+norm+'.weight'],
                  state[prefix+norm+'.bias'],1e-6)/scale(name)).round().clamp(-4,3).long()
        fitted = f['fit_layernorm_codes'](source,target,input_scale=domain,eps=1e-6,output_bits=3,input_bits=input_bits)
        p[name] = {key:fitted[key] for key in ['scalars','lnw','lnb','rsqrt_table']}
        report[name] = fitted['stats']
        return layernorm(value,p[name],input_bits=input_bits)
    def fit_lut(value,name,domain,outscale,bits,cursor):
        histogram = np.bincount(value.numpy().reshape(-1)+(1 << (bits-1)),minlength=1 << bits)
        fitted = (lut.fit_gelu_u3_lut(histogram,input_scale=domain,output_scale=outscale)
                  if name=='gelu' else lut.fit_signed_s3_requant_lut(histogram,accumulator_scale=domain,output_scale=outscale,cursor_bits=cursor))
        p[name+'_lut'] = dict(scalars=np.array([fitted.bias,fitted.shift,fitted.bound,0],np.int32),table=fitted.table)
        report[name+'_lut_mse'] = fitted.weighted_mse
        return address_lut(value,p[name+'_lut']['scalars'],fitted.table,cursor)
    ln1 = fit_ln(x,'ln1',13,input_scale)
    qkv = weights[prefix+'attn.qkv']
    qkv_values = []
    for part,(name,bits) in enumerate([('q',12),('k',11),('v',11)]):
        rows = slice(part*192,(part+1)*192)
        domain = scale('ln1')*float(qkv['scales'][part])
        p[name+'_w'] = qkv['code'][rows].cpu().numpy().astype(np.int8)
        p[name+'_b'] = wrap((state[prefix+'attn.qkv.bias'][rows]/domain).round().long(),bits).numpy().astype(np.int16)
        raw = wrap(matmul(ln1,integer(p[name+'_w']).t())+integer(p[name+'_b']),bits)
        quantized = fit_lut(raw,name,domain,scale(name),bits,9)
        qkv_values.append(quantized.reshape(-1,196,3,64).permute(0,2,1,3))
    q,k,v = qkv_values
    scores = matmul(q,k.transpose(-1,-2))
    sm = fit_softmax(scores,score_scale=scale('q')*scale('k')/8,output_scale=scale('softmax'))
    p['softmax'] = sm
    prob = fused_softmax(scores,sm['scalars'],sm['exp'],sm['recip1'],sm['recip2'])
    a_raw = wrap(matmul(prob,v),11)
    a = fit_lut(a_raw,'a',scale('softmax')*scale('v'),scale('a'),11,10)
    a = a.permute(0,2,1,3).reshape(-1,196,192)
    def linear(value, name, source, activation_scale, bits):
        exported = weights[prefix+source]
        domain = activation_scale*float(exported['scales'].reshape(-1)[0])
        p[name+'_w'] = exported['code'].cpu().numpy().astype(np.int8)
        p[name+'_b'] = wrap((state[prefix+source+'.bias']/domain).round().long(),bits).numpy().astype(np.int16)
        pre = matmul(value,integer(p[name+'_w']).t())+integer(p[name+'_b'])
        result = wrap(pre,bits)
        report[name+'_wrap_rate'] = float((pre != result).double().mean())
        report['physical_'+name+'_scale'] = domain
        return result,domain
    o,o_scale = linear(a,'o','attn.proj',scale('a'),13)
    fitted = f['_fit_rescale'](input_scale,o_scale,-4096,4095)
    p['attn_residual'] = np.array([fitted['RM'],fitted['RS'],0],np.int32)
    attention = residual(x,o,p['attn_residual'],15)
    ln2 = fit_ln(attention,'ln2',15,o_scale)
    m1,m1_scale = linear(ln2,'m1','mlp.fc1',scale('ln2'),11)
    gelu = fit_lut(m1,'gelu',m1_scale,scale('gelu'),11,32)
    m2,m2_scale = linear(gelu,'m2','mlp.fc2',scale('gelu'),13)
    fitted = f['_fit_rescale'](o_scale,m2_scale,-16384,16383)
    p['mlp_residual'] = np.array([fitted['RM'],fitted['RS']],np.int32)
    report.update(output_scale=m2_scale,softmax_mse=sm['mse'],
                  surrogate_m1_scale=scale('fc1'),surrogate_m2_scale=scale('fc2'))
    return p,report


def patch_forward(images, params):
    q = (images*64).round().clamp(-32768,32767)
    unfolded = torch.nn.functional.unfold(q,kernel_size=16,stride=16).transpose(1,2).long()
    raw = matmul(unfolded,integer(params['weight_code'],images.device).t())+integer(params['bias_raw'],images.device)
    raw[:,0] = integer(params['cls_raw'],images.device)
    shift=int(params['shift'])
    return wrap(wrap(raw+(1 << (shift-1)),32) >> shift,13)


def forward(images, artifact, *, trace=False):
    records={}
    x=patch_forward(images,artifact['patch'])
    if trace:
        records['patch']=x.detach().clone()
    for index,p in enumerate(artifact['blocks']):
        x,layer_trace=block_forward(x,p,trace=trace)
        records.update({f'block{index:02d}.{name}':value for name,value in layer_trace.items()})
    p=artifact['head']
    ln=dict(scalars=p['head_ln_scalars'][:7],lnw=p['head_lnw'],lnb=p['head_lnb'],rsqrt_table=p['head_rsqrt'])
    normalized=layernorm(x[:,0],ln,input_bits=13,head=True)
    logits=wrap(matmul(normalized,integer(p['head_weight'],x.device).t())+integer(p['head_bias'],x.device),19)
    if trace:
        records['head_ln']=normalized;records['logits']=logits
    return logits,records
