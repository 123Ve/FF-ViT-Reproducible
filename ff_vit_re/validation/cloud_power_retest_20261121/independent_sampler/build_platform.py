"""Generate a new CPU-specific A53-1 BSP; run using Vitis 2025.1 -s.

Never opens or regenerates the historical workspace. Core 0 uses the immutable
audited network BSP; core 1 gets a domain derived from the frozen XSA.
"""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    import vitis
    xsa = ROOT / 'Cloud_test/e07/vendor/e07_base/e07_300mhz_wrapper.xsa'
    assert hashlib.sha256(xsa.read_bytes()).hexdigest() == 'b46ed4b26f11340c9eb9fed1a55822f4a30c7f81627287e9c556a0a5416a5df1'
    workspace = HERE / 'build/platform_workspace'
    if workspace.exists():
        raise FileExistsError('Fresh platform workspace required: ' + str(workspace))
    client = vitis.create_client()
    try:
        client.set_workspace(path=str(workspace))
        platform = client.create_platform_component(
            name='sampler_platform', hw_design=str(xsa), os='standalone',
            cpu='psu_cortexa53_1', domain_name='sampler_a53_1',
            no_boot_bsp=True, generate_dtb=False, architecture='64-bit', compiler='gcc',
            advanced_options=client.create_advanced_options_dict(dt_overlay='0'))
        domain = platform.get_domain(name='sampler_a53_1')
        # AMP suppresses global GIC initialization if a driver ever calls it.
        # The sampler application itself uses no IRQs and no global timer init.
        domain.set_config('proc', 'proc_extra_compiler_flags',
                          '-O2 -g -Wall -Wextra -fno-tree-loop-distribute-patterns -DUSE_AMP=1')
        platform.build()
        (HERE / 'build/platform_configuration.json').write_text(json.dumps({
            'cpu': 'psu_cortexa53_1', 'domain': 'sampler_a53_1',
            'os': 'standalone', 'architecture': '64-bit', 'exception_level': 'EL3',
            'USE_AMP': 1, 'workspace': str(workspace), 'physical_status': 'NOT_RUN'
        }, indent=2) + '\n')
    finally:
        vitis.dispose()


if __name__ == '__main__':
    main()
