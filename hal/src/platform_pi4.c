/**
 * platform_pi4.c — BCM2711 SoC GPIO backend
 *
 * 호환 보드:
 *   - Raspberry Pi 4 Model B (microSD boot)
 *   - Raspberry Pi Compute Module 4 (eMMC boot, Lite도 SD 가능)
 *   - 같은 SoC라 동일 코드 경로. carrier board의 GPIO header pinout만
 *     동일해야 함 (Waveshare CM4-IO-BASE-B, 공식 CM4 IO Board 등).
 *
 * libgpiod v1.x API 사용 (Bookworm apt 기본). 이전 sysfs gpio는 deprecated.
 *
 * 안전 원칙:
 *   - 모든 reserve된 output line을 g_lines[] 에 추적
 *   - assert_safe_state는 g_lines 전체를 LOW로 강제 (NC 와이어링 가정)
 *   - libgpiod 호출 실패도 best-effort 무시 (panic 경로에서 fail-safe 우선)
 *
 * GPIO chip: /dev/gpiochip0 (BCM2711 default)
 * Pi 5는 BCM2712 + /dev/gpiochip4. 추후 platform_pi5.c에서 처리.
 * R1124-10은 같은 BCM2711이지만 carrier의 IO expander 매핑이 필요해
 * platform_r1124.c에서 별도 처리 (Phase 1+).
 */

#include "gw_hal.h"
#include <gpiod.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>

#define PI4_GPIO_CHIP "/dev/gpiochip0"
#define MAX_GPIO_LINES 32

typedef struct {
    int pin;                   /* BCM 번호, -1 = unused slot */
    int is_output;             /* 1 = output, 0 = input */
    struct gpiod_line* line;   /* libgpiod handle */
} pin_slot_t;

static struct gpiod_chip* g_chip = NULL;
static pin_slot_t g_lines[MAX_GPIO_LINES];
static pthread_mutex_t g_mu = PTHREAD_MUTEX_INITIALIZER;
static int g_gpio_initialized = 0;

/* ----- helpers ----- */

static pin_slot_t* find_slot(int pin) {
    for (int i = 0; i < MAX_GPIO_LINES; i++) {
        if (g_lines[i].pin == pin && g_lines[i].line != NULL) {
            return &g_lines[i];
        }
    }
    return NULL;
}

static pin_slot_t* alloc_slot(int pin) {
    for (int i = 0; i < MAX_GPIO_LINES; i++) {
        if (g_lines[i].line == NULL) {
            g_lines[i].pin = pin;
            return &g_lines[i];
        }
    }
    return NULL;
}

/* ----- public API ----- */

int gw_gpio_init(void) {
    pthread_mutex_lock(&g_mu);
    if (g_gpio_initialized) {
        pthread_mutex_unlock(&g_mu);
        return GW_OK;
    }

    g_chip = gpiod_chip_open(PI4_GPIO_CHIP);
    if (!g_chip) {
        pthread_mutex_unlock(&g_mu);
        /* errno 13 = EACCES → 'gpio' group missing */
        return GW_ERR_PERM;
    }

    memset(g_lines, 0, sizeof(g_lines));
    for (int i = 0; i < MAX_GPIO_LINES; i++) {
        g_lines[i].pin = -1;
    }
    g_gpio_initialized = 1;
    pthread_mutex_unlock(&g_mu);
    return GW_OK;
}

int gw_gpio_request_output(int pin, int initial_value) {
    if (!g_gpio_initialized) return GW_ERR_NOT_INIT;
    if (pin < 0 || pin > 53) return GW_ERR_INVALID;
    if (initial_value != 0 && initial_value != 1) return GW_ERR_INVALID;

    pthread_mutex_lock(&g_mu);
    if (find_slot(pin)) {
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_BUSY;
    }
    pin_slot_t* slot = alloc_slot(pin);
    if (!slot) {
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_BUSY;  /* slot 부족 */
    }

    struct gpiod_line* line = gpiod_chip_get_line(g_chip, pin);
    if (!line) {
        slot->pin = -1;
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_IO;
    }

    if (gpiod_line_request_output(line, "iot-gateway", initial_value) < 0) {
        slot->pin = -1;
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_IO;
    }

    slot->line = line;
    slot->is_output = 1;
    pthread_mutex_unlock(&g_mu);
    return GW_OK;
}

int gw_gpio_request_input(int pin, int pull) {
    if (!g_gpio_initialized) return GW_ERR_NOT_INIT;
    if (pin < 0 || pin > 53) return GW_ERR_INVALID;

    pthread_mutex_lock(&g_mu);
    if (find_slot(pin)) {
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_BUSY;
    }
    pin_slot_t* slot = alloc_slot(pin);
    if (!slot) {
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_BUSY;
    }

    struct gpiod_line* line = gpiod_chip_get_line(g_chip, pin);
    if (!line) {
        slot->pin = -1;
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_IO;
    }

    /* libgpiod v1 API는 bias 설정이 제한적 — pull은 향후 v2/v3로 확장 */
    (void)pull;
    if (gpiod_line_request_input(line, "iot-gateway") < 0) {
        slot->pin = -1;
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_IO;
    }

    slot->line = line;
    slot->is_output = 0;
    pthread_mutex_unlock(&g_mu);
    return GW_OK;
}

int gw_gpio_set(int pin, int value) {
    if (!g_gpio_initialized) return GW_ERR_NOT_INIT;
    if (value != 0 && value != 1) return GW_ERR_INVALID;

    pthread_mutex_lock(&g_mu);
    pin_slot_t* slot = find_slot(pin);
    if (!slot || !slot->is_output) {
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_INVALID;
    }
    int rc = gpiod_line_set_value(slot->line, value);
    pthread_mutex_unlock(&g_mu);
    return rc < 0 ? GW_ERR_IO : GW_OK;
}

int gw_gpio_get(int pin, int* value_out) {
    if (!g_gpio_initialized) return GW_ERR_NOT_INIT;
    if (!value_out) return GW_ERR_INVALID;

    pthread_mutex_lock(&g_mu);
    pin_slot_t* slot = find_slot(pin);
    if (!slot) {
        pthread_mutex_unlock(&g_mu);
        return GW_ERR_INVALID;
    }
    int v = gpiod_line_get_value(slot->line);
    pthread_mutex_unlock(&g_mu);
    if (v < 0) return GW_ERR_IO;
    *value_out = v;
    return GW_OK;
}

/**
 * gw_gpio_cleanup — 모든 line release + chip close + 상태 리셋.
 * gw_hal_cleanup에서 assert_safe_state 직후 호출. 멱등.
 *
 * 미호출 시: 재시작 반복 시 libgpiod fd 누수 + 다음 init 시 g_chip
 * dangling pointer 사용으로 UB.
 */
int gw_gpio_cleanup(void) {
    pthread_mutex_lock(&g_mu);
    for (int i = 0; i < MAX_GPIO_LINES; i++) {
        if (g_lines[i].line) {
            gpiod_line_release(g_lines[i].line);
            g_lines[i].line = NULL;
            g_lines[i].pin = -1;
        }
    }
    if (g_chip) {
        gpiod_chip_close(g_chip);
        g_chip = NULL;
    }
    g_gpio_initialized = 0;
    pthread_mutex_unlock(&g_mu);
    return GW_OK;
}

int gw_gpio_assert_safe_state(void) {
    /* best-effort: g_initialized 안 되어 있어도 무시.
     *
     * 시그널 핸들러(SIGTERM/SIGABRT)에서 호출될 수 있으므로 pthread_mutex_lock은
     * 데드락 위험이 있다 (signal handler에서 lock 시도 시 메인 스레드가 같은
     * mutex를 잡고 있으면 영구 정지 → relay ON 고정).
     *
     * trylock으로 시도하고 실패하면 mutex 없이 강제 진행. relay를 OFF로 만드는
     * 것이 mutex 일관성보다 우선 (NC wiring fail-safe 원칙).
     */
    int locked = (pthread_mutex_trylock(&g_mu) == 0);
    for (int i = 0; i < MAX_GPIO_LINES; i++) {
        if (g_lines[i].line && g_lines[i].is_output) {
            /* NC wiring 가정: 0 = open = safe */
            (void)gpiod_line_set_value(g_lines[i].line, 0);
        }
    }
    if (locked) {
        pthread_mutex_unlock(&g_mu);
    }
    return GW_OK;
}
