"""Read-only source inventory. Historical evidence never grants a new PASS."""
import argparse
import json
from pathlib import Path
import re
from capture_ln import ROOT, HERE, file_identity
from run_validation import write_json

HLS=Path('/home/user/Desktop/FF_Vit/E04_weight_schedule/E07_timing_300mhz/src')


def lines(path, pattern):
    return [dict(line=i,text=text) for i,text in enumerate(Path(path).read_bytes().decode('utf8',errors='replace').splitlines(),1)
            if re.search(pattern,text)]


def audit():
    sources=[HLS/name for name in ('layernorm.h','attn.h','mlp.h','block0.cpp','head.h','common.h','utils.h','adapter.h')]
    inventory=[]
    extras=[('python_quan/qat/hls_lut_qat.py', 'hls_integer_layernorm|bridge|quantile', 'manifest standalone integer LN; FP32 bridge uses unpaired quantiles, not paired hardware scale proof'),
            ('python_quan/qat/mixed_model.py', 'layernorm|LayerNorm', 'calls standalone FP32 bridge; not the three dataset capture routes'),
            ('image_lianghu/src/hls_exact_ste.py', 'def hls_layernorm_codes|def ', 'device-resident S3 LN with validation; inventory only'),
            ('image_lianghu/src/s3_layernorm_opt.py', '^def ', 'alternate fitted S3 LUT optimization; not executed'),
            ('image_lianghu/src/s8_exact_runtime.py', 'layernorm|LayerNorm', 'EXCLUDED S8 branch; source inventory only'),
            ('quantization_final/scripts/stage4h_exact_layernorm_roundfix.py', '^def ', 'historical fitter/arithmetic helper; provisional LN2 parameters not selected'),
            ('quantization_final/scripts/stage4k_exact_attention_outer.py', 'def install_exact_ln1|wrap_signed|var =', 'actual Plant LN1 replacement'),
            ('quantization_final/scripts/stage4m_exact_encoder_backbone.py', 'def install_exact_ln2|wrap_signed|var =', 'actual Plant LN2 replacement'),
            ('quantization_final/scripts/stage4n_head_integer_audit.py', 'def install_stage4m|install_exact_ln', 'actual Plant final encoder installation'),
            ('image1k_hls_s3_original/src/exact.py', '^def layernorm|^def block_forward|^def patch_forward', 'actual ImageNet final strict S3 integer replay'),
            ('quantization_final/scripts/stage4o_exact_head_signedfix.py', 'def apply_head_ln|wrap_signed', 'signed-corrected export Head semantics differs from E07 unsigned Head'),
            ('quantization_final/scripts/stage4p_prepare_hls_deployment_v2.py', '^def build_attn_struct|^def build_mlp_struct', 'canonical binary ABI packer')]
    for relative,pattern,note in extras:
        path=ROOT/relative
        inventory.append(dict(path=str(path),note=note,executed_for_24=('actual ' in note),callsites=lines(path,pattern)))
        sources.append(path)
    # Hash all Python sources that can be imported in the frozen reconstruction routes.
    for directory in [ROOT/'quantization_final/scripts',ROOT/'archive/nwpu_resisc45_ffvit/src',
                      ROOT/'archive/nwpu_resisc45_ffvit/scripts/quant',ROOT/'image1k_hls_s3_original/src',ROOT/'image_lianghu/src']:
        sources += sorted(directory.rglob('*.py'))
    historical=[]
    for relative in ['quantization_final/validation/reconstruction_report.json','quantization_final/audit/bitexact/full_verification.json',
                     'archive/nwpu_resisc45_ffvit/validation/hls_csim.json']:
        path=ROOT/relative
        historical.append(dict(**file_identity([path])[0],classification='HISTORICAL ONLY; original coverage retained; no new PASS assigned',
            content=json.loads(path.read_text())))
    return dict(schema='ln.source_audit.v1',scope='Only dataset final exports; no board parameter files parsed or executed',
        execution=dict(instances=24,blocks=12,physical_engines='one static attention engine and one static MLP engine, temporally reused',
                       method='do_layernorm_inter_token for both LN1 and LN2',template='deployed T196 TP2 C192 CP1'),
        callsites=dict(attn=lines(HLS/'attn.h','do_layernorm_inter_token'),mlp=lines(HLS/'mlp.h','do_layernorm_inter_token'),
                       static_engines=lines(HLS/'block0.cpp',r'static (AttnCoreType|MlpCoreType)'),
                       temporal_loop=lines(HLS/'block0.cpp','layer_loop:|ext_weights, l, num_layers'),
                       width_contract=lines(HLS/'block0.cpp','typedef .*__ln_|typedef .*__attn_if_t|typedef .*__mlp_if_t'),
                       arithmetic=lines(HLS/'layernorm.h',r'long long var_wide|sum_sq.*-|long long\)C|__divc_t tmp|__if_t diff|__affine_t val|__cursor_t cursor')),
        head=dict(included_in_24=False,status='NOT_MEASURED',types=lines(HLS/'block0.cpp','typedef .*__head_ln_'),
                  actual='unsigned sum15/div30/mean7/variance24/cursor6/rsqrt11; signed affine36/shift9',
                  context_correction='ADAPTER_CONTEXT historical note cursor7/rsqrt18 is incorrect for the current inspected E07 file',
                  fixed_callsites=lines(HLS/'block0.cpp',r'fixed_head_layernorm|diff_pow2|__head_ln_var_t\(sum'),
                  generic_callsites=lines(HLS/'head.h','Layernorm|do_layernorm'),
                  caveat='signed-corrected canonical export head passes cannot establish actual unsigned E07 head equivalence'),
        other_ln_inventory=inventory,historical_evidence=historical,sources=file_identity(sources),
        statuses=dict(source_inspection='MEASURED',VITIS_CSIM='NOT_MEASURED',RTL_COSIM='NOT_MEASURED',FPGA='NOT_MEASURED'),
        excludes=['third-party board weights and traces','S8 execution','accuracy evaluation','provisional Stage4H LN2 parameters'])


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=HERE/'outputs/source_audit.json')
    args=p.parse_args(); result=audit(); write_json(args.output,result)
    print(json.dumps(dict(output=str(args.output),hashed_sources=len(result['sources']),status='MEASURED')))
