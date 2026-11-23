# Additional clean files
cmake_minimum_required(VERSION 3.16)

if("${CONFIG}" STREQUAL "" OR "${CONFIG}" STREQUAL "")
  file(REMOVE_RECURSE
  "/home/user/Desktop/ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/build/platform_workspace/sampler_platform/psu_cortexa53_1/sampler_a53_1/bsp/include/sleep.h"
  "/home/user/Desktop/ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/build/platform_workspace/sampler_platform/psu_cortexa53_1/sampler_a53_1/bsp/include/xiltimer.h"
  "/home/user/Desktop/ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/build/platform_workspace/sampler_platform/psu_cortexa53_1/sampler_a53_1/bsp/include/xtimer_config.h"
  "/home/user/Desktop/ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/build/platform_workspace/sampler_platform/psu_cortexa53_1/sampler_a53_1/bsp/lib/libxiltimer.a"
  )
endif()
