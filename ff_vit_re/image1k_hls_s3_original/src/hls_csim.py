"""Strict HLS fixture preparation and integer boundary comparison."""
import hashlib
from pathlib import Path
import numpy as np

BOUNDARIES = {'hls_patch_out.bin':'patch',
              **{f'hls_block{i}_out.bin':f'block{i:02d}.mlp_residual' for i in range(12)},
              'hls_logits.bin':'logits'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inventory(inventory):
    for name, digest in inventory.items():
        if sha256(name) != digest:
            raise ValueError(f'source changed: {name}')


def validate_input(path):
    if Path(path).stat().st_size != 196*768*2:
        raise ValueError('input must be logical little-endian int16[196,768]')


def validate_weights(path):
    if Path(path).stat().st_size != 12*231008:
        raise ValueError('weights must contain 12 native 231008-byte blocks')


def unpack_fm(values):
    values=np.asarray(values)
    if values.size != 196*192:
        raise ValueError('feature dump has wrong element count')
    return values.reshape(98,192,2).transpose(0,2,1).reshape(196,192)


def compare_boundaries(directory,traces):
    rows={}
    for filename,key in BOUNDARIES.items():
        actual=np.fromfile(Path(directory)/filename,dtype='<i4')
        expected=np.asarray(traces[key],dtype=np.int64)
        actual=unpack_fm(actual) if key!='logits' else actual
        if actual.shape != expected.shape:
            raise ValueError(f'{key}: shape mismatch {actual.shape} != {expected.shape}')
        error=actual.astype(np.int64)-expected
        rows[key]={'elements':int(error.size),'mismatch_count':int(np.count_nonzero(error)),
                   'max_abs_error':int(np.abs(error).max()),'output_sha256':sha256(Path(directory)/filename)}
    return {'passed':all(row['mismatch_count']==0 for row in rows.values()),'boundaries':rows}
