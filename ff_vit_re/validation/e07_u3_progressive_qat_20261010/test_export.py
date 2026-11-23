import unittest
import numpy as np
import torch
from exporter import unsigned_statistics,fit_unsigned_head,fit_classifier,validate_split_binding,fitter_hashes,aggregate_rsqrt
from runtime import head_intermediates,head_layernorm

class ExportTests(unittest.TestCase):
    def test_rsqrt_csv_without_count_uses_matching_ln_token_count(self):
        rows=[dict(instance='a',input_images='1',real_mae='1',real_rmse='1',real_max_ae='2'),
              dict(instance='b',input_images='2',real_mae='3',real_rmse='3',real_max_ae='4')]
        ln=[dict(instance='a',count='37632'),dict(instance='b',count='75264')]
        result=aggregate_rsqrt(rows,ln)
        self.assertEqual(result['count'],588)
        self.assertAlmostEqual(result['real_mae'],7/3)
        self.assertAlmostEqual(result['real_rmse'],(19/3)**.5)
        self.assertEqual(result['real_max_ae'],4)
        with self.assertRaises(ValueError):aggregate_rsqrt(rows,ln[:1])
        with self.assertRaises(ValueError):aggregate_rsqrt(rows,[ln[0],dict(instance='b',count='75265')])
    def test_export_rejects_changed_full_split(self):
        expected={'val':{'count':2,'ordered_membership_sha256':'a'},'test':{'count':3,'ordered_membership_sha256':'b'}}
        validate_split_binding(expected,expected)
        with self.assertRaises(ValueError):validate_split_binding(expected,{**expected,'test':{'count':3,'ordered_membership_sha256':'changed'}})
    def test_actual_fitter_dependencies_hashed(self):
        paths=fitter_hashes()
        self.assertTrue(any(p.endswith('/src/exact_fit.py') for p in paths))
        self.assertTrue(any(p.endswith('/src/legacy_s3_lut.py') for p in paths))
    def test_unsigned_stats_match_runtime(self):
        x=torch.tensor([[-1]*192,[3]*192,[-4096,4095]*96],dtype=torch.int64)
        p=dict(scalars=np.array([683,17,0,18,63,8,8]),rsqrt_table=np.ones(128,np.int32),
            lnw=np.ones(192,np.int32),lnb=np.zeros(192,np.int64))
        s=unsigned_statistics(x);r=head_intermediates(x,p)
        self.assertTrue(torch.equal(s['diff13'],r['diff']))
        self.assertTrue(torch.equal(s['var24'],r['variance']))
        self.assertTrue(torch.equal(s['mean7'],r['mean']))
        self.assertGreaterEqual(int(s['mean7'].min()),0)
    def test_refitted_unsigned_head_replays(self):
        gen=torch.Generator().manual_seed(12);x=torch.randint(-30,31,(20,192),generator=gen)
        target=torch.nn.functional.layer_norm(x.float()*.1,(192,)).double()
        fit=fit_unsigned_head(x,target,.1)
        q=head_layernorm(x,fit)
        self.assertEqual(tuple(q.shape),(20,192))
        self.assertTrue(bool(((q>=-128)&(q<=127)).all()))
        self.assertLessEqual(int(np.max(fit['rsqrt_table'])),2047)
        self.assertEqual(int(fit['scalars'][4]),63)
        self.assertLessEqual(fit['stats']['affine_wrap_rate'],0)
    def test_classifier_inactive_padding_and_widths(self):
        gen=torch.Generator().manual_seed(1);x=torch.randint(-10,11,(8,192),generator=gen)
        weights=torch.randn(3,192,generator=gen)*.02;bias=torch.randn(3,generator=gen)*.1
        f=fit_classifier(x,x.double()*.05,weights,bias,.05)
        self.assertEqual(tuple(f['qw'].shape),(1000,192))
        self.assertTrue(torch.equal(f['qw'][3:],torch.zeros_like(f['qw'][3:])))
        self.assertTrue(bool((f['qb'][3:]==-262143).all()))
        self.assertTrue(bool(((f['qb']>=-262144)&(f['qb']<=262143)).all()))

if __name__=='__main__':unittest.main()
