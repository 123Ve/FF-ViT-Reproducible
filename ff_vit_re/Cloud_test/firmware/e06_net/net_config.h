#ifndef E06_NET_CONFIG_H
#define E06_NET_CONFIG_H

#define E06_BOARD_IP_A 192u
#define E06_BOARD_IP_B 168u
#define E06_BOARD_IP_C 10u
#define E06_BOARD_IP_D 2u
#define E06_GATEWAY_IP_A 192u
#define E06_GATEWAY_IP_B 168u
#define E06_GATEWAY_IP_C 10u
#define E06_GATEWAY_IP_D 1u
#define E06_NETMASK_A 255u
#define E06_NETMASK_B 255u
#define E06_NETMASK_C 255u
#define E06_NETMASK_D 0u
#define E06_TCP_PORT 5001u

#define E06_STAGE "E06_PHYSICAL"
#define E06_MODEL "E06"
#define E06_BOARD_IP_TEXT "192.168.10.2"

/* Host contract tests may override this; production receives the generated header. */
#ifndef E06_FIRMWARE_SHA256
#include "firmware_build_identity.h"
#endif
#ifndef E06_FIRMWARE_SHA256
#error "E06 firmware build identity was not generated"
#endif

#define E06_WEIGHTS_SHA256 \
    "0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7"
#define E06_INPUT_SHA256 \
    "f7fa33c31113271173effc4fb684c432378b85c2f15a6681aa682aacf2ba3a2c"
#define E06_OUTPUT_SHA256 \
    "f2da31d910ab48a49c5a803f836478e2b54e0cd9fdd1081cc2eabc1d36afe842"
#define E06_BITSTREAM_SHA256 \
    "fb64c88cdf155ed02d314703d7486b44338c4c25bceaa2c8caaeb279059f2f27"
#define E06_XSA_SHA256 \
    "9f41851e899418d63ae712930d10062744ffffa9a25763fa9a64b1043d6e7757"

#endif
