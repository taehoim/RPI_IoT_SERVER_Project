/**
 * platform_r1124.c — Seeed reComputer R1124-10 backend (Phase 1+ STUB)
 *
 * Phase 0에서는 ABI 컴파일 검증용 stub.
 * Phase 1 도착 시 carrier board의 GPIO expander (예: MCP23017) + onboard
 * RS485 chip 매핑으로 구현 예정.
 */

#include "gw_hal.h"

int gw_gpio_init(void) {
    return GW_ERR_NOT_INIT;  /* Phase 1+ */
}

int gw_gpio_request_output(int pin, int initial_value) {
    (void)pin; (void)initial_value;
    return GW_ERR_NOT_INIT;
}

int gw_gpio_request_input(int pin, int pull) {
    (void)pin; (void)pull;
    return GW_ERR_NOT_INIT;
}

int gw_gpio_set(int pin, int value) {
    (void)pin; (void)value;
    return GW_ERR_NOT_INIT;
}

int gw_gpio_get(int pin, int* value_out) {
    (void)pin; (void)value_out;
    return GW_ERR_NOT_INIT;
}

int gw_gpio_assert_safe_state(void) {
    return GW_OK;  /* best-effort, R1124 미구현 시 noop */
}

int gw_gpio_cleanup(void) {
    return GW_OK;  /* R1124 stub — Phase 1+에서 expander handle release */
}
