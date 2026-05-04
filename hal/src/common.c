/**
 * common.c — 공통 유틸 + 라이브러리 lifecycle
 */

#include "gw_hal.h"
#include <string.h>
#include <stdio.h>
#include <stdatomic.h>

#define HAL_VERSION "0.1.0-pi4-phase0"

static atomic_int g_initialized = 0;

int gw_hal_init(void) {
    int expected = 0;
    if (atomic_compare_exchange_strong(&g_initialized, &expected, 1)) {
        /* 첫 호출, 추가 초기화 필요 시 여기에 */
    }
    return GW_OK;
}

int gw_hal_cleanup(void) {
    /* 안전 상태 강제 → GPIO line/chip release → 상태 리셋.
     * gw_gpio_cleanup 미호출 시 libgpiod fd 누수 + g_chip dangling pointer UB. */
    gw_gpio_assert_safe_state();
    gw_gpio_cleanup();
    atomic_store(&g_initialized, 0);
    return GW_OK;
}

int gw_hal_version(char* buf, size_t size) {
    if (!buf || size == 0) return GW_ERR_INVALID;
    int written = snprintf(buf, size, "libgw_hal %s (built %s %s)",
                           HAL_VERSION, __DATE__, __TIME__);
    return (written > 0 && (size_t)written < size) ? GW_OK : GW_ERR_INTERNAL;
}

/* 4G modem stubs (Phase 0) */
int gw_modem_at(const char* cmd, char* resp, size_t size, int timeout_ms) {
    (void)cmd; (void)resp; (void)size; (void)timeout_ms;
    return GW_ERR_NOT_INIT;
}

int gw_modem_reset_soft(void) {
    return GW_ERR_NOT_INIT;
}

int gw_modem_reset_hard(void) {
    return GW_ERR_NOT_INIT;
}
