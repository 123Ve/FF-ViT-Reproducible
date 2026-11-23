# 0 "/home/user/Desktop/ff_vit_re/Cloud_test/e07/build/e06_net_workspace/e06_net_platform/psu_cortexa53_0/standalone_psu_cortexa53_0/bsp/lop-config.dts"
# 0 "<built-in>"
# 0 "<command-line>"
# 1 "/home/user/Desktop/ff_vit_re/Cloud_test/e07/build/e06_net_workspace/e06_net_platform/psu_cortexa53_0/standalone_psu_cortexa53_0/bsp/lop-config.dts"

/dts-v1/;
/ {
        compatible = "system-device-tree-v1,lop";
        lops {
                lop_0 {
                        compatible = "system-device-tree-v1,lop,load";
                        load = "assists/baremetal_validate_comp_xlnx.py";
                };

                lop_1 {
                    compatible = "system-device-tree-v1,lop,assist-v1";
                    node = "/";
                    outdir = "/home/user/Desktop/ff_vit_re/Cloud_test/e07/build/e06_net_workspace/e06_net_platform/psu_cortexa53_0/standalone_psu_cortexa53_0/bsp";
                    id = "module,baremetal_validate_comp_xlnx";
                    options = "psu_cortexa53_0 /opt/vivado/2025.1/Vitis/data/embeddedsw/ThirdParty/sw_services/lwip220_v1_2/src /home/user/Desktop/ff_vit_re/Cloud_test/e07/build/e06_net_workspace/_ide/.wsdata/.repo.yaml";
                };

        };
    };
