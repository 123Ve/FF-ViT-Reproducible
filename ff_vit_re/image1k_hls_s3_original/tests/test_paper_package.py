import importlib.util
import pytest


def module():
    assert importlib.util.find_spec('src.paper_package'), 'paper package aggregation required'
    from src import paper_package
    return paper_package


def test_small_exact_probe_cannot_become_formal_accuracy():
    p=module()
    with pytest.raises(ValueError,match='50000'):
        p.formal_stage('exact',{'sample_count':128,'top1':.9,'top5':.99},'exact_integer_50k')
    row=p.formal_stage('exact',{'sample_count':50000,'top1':.6,'top5':.8},'exact_integer_50k')
    assert row['top1_percent']==60


def test_completeness_requires_corrected_sensitivity_and_real_hls():
    p=module()
    inputs={'operator':17,'layer':36,'cumulative':24,'sensitivity_version':1,
            'exact50k':True,'hls_passed':False,'hls_sample_count':4}
    result=p.completeness(inputs)
    assert not result['complete']
    assert set(result['missing'])=={'sensitivity_v2','hls_bit_exact'}
    inputs.update(sensitivity_version=2,hls_passed=True)
    assert p.completeness(inputs)['complete']
    inputs['hls_sample_count']=0
    assert not p.completeness(inputs)['complete']


def test_hls_pass_label_without_boundary_evidence_is_rejected():
    p=module()
    assert not p.hls_success({'passed':True,'status':'PASS','samples':[{}]*4})


def test_sensitivity_count_cannot_hide_duplicate_cases():
    p=module()
    with pytest.raises(ValueError,match='duplicate'):
        p.validate_sensitivity({'records':[{'experiment_id':'same','sample_count':50000}]*17},17)
