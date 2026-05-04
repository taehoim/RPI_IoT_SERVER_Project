/**
 * watchdog.c — Linux /dev/watchdog ioctl 래퍼
 *
 * BCM2835 hardware WDT는 최대 timeout 약 15초.
 * Magic close (V) 전송으로 disable.
 *
 * 권장 패턴:
 *   gw_watchdog_open(15) → 5초마다 gw_watchdog_kick → cleanup 시 close
 *
 * close 시 magic char 안 쓰면 WDT가 그대로 reboot 트리거하니 close 호출 필수.
 */

#include "gw_hal.h"
#include <linux/watchdog.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

#define WDT_DEV "/dev/watchdog"

int gw_watchdog_open(int timeout_sec) {
    if (timeout_sec < 1 || timeout_sec > 60) return GW_ERR_INVALID;

    int fd = open(WDT_DEV, O_WRONLY);
    if (fd < 0) {
        return (errno == EACCES || errno == EPERM) ? GW_ERR_PERM : GW_ERR_IO;
    }

    int timeout = timeout_sec;
    if (ioctl(fd, WDIOC_SETTIMEOUT, &timeout) < 0) {
        close(fd);
        return GW_ERR_IO;
    }
    return fd;
}

int gw_watchdog_kick(int fd) {
    if (fd < 0) return GW_ERR_INVALID;
    int dummy = 0;
    if (ioctl(fd, WDIOC_KEEPALIVE, &dummy) < 0) {
        return GW_ERR_IO;
    }
    return GW_OK;
}

int gw_watchdog_close(int fd) {
    if (fd < 0) return GW_ERR_INVALID;
    /* magic close: write 'V' then close */
    const char magic = 'V';
    (void)write(fd, &magic, 1);  /* best-effort */
    return close(fd) < 0 ? GW_ERR_IO : GW_OK;
}
