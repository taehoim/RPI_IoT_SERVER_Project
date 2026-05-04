/**
 * rs485.c — RS-485 시리얼 + Modbus RTU 공통 구현
 *
 * Linux termios + select() 기반.
 * USB-RS485 어댑터 (FT232/CH340 + MAX485)는 자동 DE/RE 토글.
 * 자체 GPIO DE/RE 제어가 필요한 경우는 platform_*.c 에서 추가.
 *
 * Modbus RTU CRC-16 (polynomial 0xA001, init 0xFFFF) 자동 검증.
 */

#include "gw_hal.h"
#include <termios.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/select.h>
#include <stdio.h>

/* ----- CRC-16 Modbus ----- */

static uint16_t crc16_modbus(const uint8_t* buf, int len) {
    uint16_t crc = 0xFFFF;
    for (int i = 0; i < len; i++) {
        crc ^= (uint16_t)buf[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 1) crc = (crc >> 1) ^ 0xA001;
            else         crc >>= 1;
        }
    }
    return crc;
}

static speed_t baud_to_speed(int baud) {
    switch (baud) {
        case 9600:   return B9600;
        case 19200:  return B19200;
        case 38400:  return B38400;
        case 57600:  return B57600;
        case 115200: return B115200;
        default:     return 0;
    }
}

/* ----- public API ----- */

int gw_rs485_open(const char* dev, int baud, char parity, int data_bits, int stop_bits) {
    if (!dev) return GW_ERR_INVALID;
    speed_t speed = baud_to_speed(baud);
    if (speed == 0) return GW_ERR_INVALID;
    if (parity != 'N' && parity != 'E' && parity != 'O') return GW_ERR_INVALID;
    if (data_bits != 7 && data_bits != 8) return GW_ERR_INVALID;
    if (stop_bits != 1 && stop_bits != 2) return GW_ERR_INVALID;

    int fd = open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        return (errno == EACCES) ? GW_ERR_PERM : GW_ERR_IO;
    }

    struct termios tio;
    if (tcgetattr(fd, &tio) < 0) {
        close(fd);
        return GW_ERR_IO;
    }

    cfmakeraw(&tio);
    cfsetispeed(&tio, speed);
    cfsetospeed(&tio, speed);

    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= (data_bits == 7) ? CS7 : CS8;

    if (parity == 'N') {
        tio.c_cflag &= ~PARENB;
    } else {
        tio.c_cflag |= PARENB;
        if (parity == 'O') tio.c_cflag |= PARODD;
        else               tio.c_cflag &= ~PARODD;
    }

    if (stop_bits == 2) tio.c_cflag |= CSTOPB;
    else                tio.c_cflag &= ~CSTOPB;

    tio.c_cflag |= (CLOCAL | CREAD);
    tio.c_cflag &= ~CRTSCTS;

    /* read returns immediately when bytes available */
    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 0;

    if (tcsetattr(fd, TCSANOW, &tio) < 0) {
        close(fd);
        return GW_ERR_IO;
    }

    /* drain stale bytes */
    tcflush(fd, TCIOFLUSH);
    return fd;
}

static int read_with_timeout(int fd, uint8_t* buf, int want, int timeout_ms) {
    int got = 0;
    while (got < want) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(fd, &rfds);
        struct timeval tv;
        tv.tv_sec = timeout_ms / 1000;
        tv.tv_usec = (timeout_ms % 1000) * 1000;
        int r = select(fd + 1, &rfds, NULL, NULL, &tv);
        if (r < 0) {
            if (errno == EINTR) continue;
            return GW_ERR_IO;
        }
        if (r == 0) return GW_ERR_TIMEOUT;
        ssize_t n = read(fd, buf + got, want - got);
        if (n < 0) {
            if (errno == EINTR || errno == EAGAIN) continue;
            return GW_ERR_IO;
        }
        if (n == 0) return GW_ERR_IO;
        got += (int)n;
    }
    return got;
}

int gw_rs485_modbus_read(int fd, uint8_t slave, uint8_t function_code,
                         uint16_t register_addr, uint16_t length,
                         uint16_t* out, int timeout_ms) {
    if (fd < 0 || !out || length == 0 || length > 125) return GW_ERR_INVALID;
    if (function_code != 0x03 && function_code != 0x04) return GW_ERR_INVALID;

    /* request: slave(1) fn(1) reg_hi(1) reg_lo(1) len_hi(1) len_lo(1) crc(2) = 8 bytes */
    uint8_t req[8];
    req[0] = slave;
    req[1] = function_code;
    req[2] = (uint8_t)(register_addr >> 8);
    req[3] = (uint8_t)(register_addr & 0xFF);
    req[4] = (uint8_t)(length >> 8);
    req[5] = (uint8_t)(length & 0xFF);
    uint16_t crc = crc16_modbus(req, 6);
    req[6] = (uint8_t)(crc & 0xFF);
    req[7] = (uint8_t)(crc >> 8);

    tcflush(fd, TCIFLUSH);
    if (write(fd, req, 8) != 8) return GW_ERR_IO;

    /* normal response: slave(1) fn(1) byte_count(1) data(2*length) crc(2) = 5 + 2*length
     * exception response: slave(1) fn|0x80(1) exception_code(1) crc(2) = 5
     *
     * 헤더 2바이트(slave + fn)를 먼저 읽고 fn의 0x80 비트로 분기해야 함.
     * 한꺼번에 expected = 5 + 2*length를 기다리면 exception 응답(5바이트)이 와도
     * 추가 데이터를 무한 대기 → GW_ERR_IO 대신 GW_ERR_TIMEOUT만 반환되는 unreachable 버그.
     */
    uint8_t resp[256];
    int rc = read_with_timeout(fd, resp, 2, timeout_ms);
    if (rc < 0) return rc;

    if ((resp[1] & 0x80) != 0) {
        /* exception 응답 5바이트 = 헤더 2 + exc_code(1) + crc(2) = 추가 3바이트 */
        rc = read_with_timeout(fd, resp + 2, 3, timeout_ms);
        if (rc < 0) return rc;
        uint16_t got_crc_e = resp[3] | ((uint16_t)resp[4] << 8);
        uint16_t calc_crc_e = crc16_modbus(resp, 3);
        if (got_crc_e != calc_crc_e) return GW_ERR_CRC;
        return GW_ERR_IO;  /* slave 측 exception (illegal function/address/value 등) */
    }

    int expected = 5 + 2 * length;
    if (expected > (int)sizeof(resp)) return GW_ERR_INVALID;

    rc = read_with_timeout(fd, resp + 2, expected - 2, timeout_ms);
    if (rc < 0) return rc;

    if (resp[0] != slave || resp[1] != function_code || resp[2] != 2 * length) {
        return GW_ERR_CRC;
    }

    uint16_t got_crc = resp[expected - 2] | ((uint16_t)resp[expected - 1] << 8);
    uint16_t calc_crc = crc16_modbus(resp, expected - 2);
    if (got_crc != calc_crc) return GW_ERR_CRC;

    for (int i = 0; i < length; i++) {
        out[i] = ((uint16_t)resp[3 + 2 * i] << 8) | resp[4 + 2 * i];
    }
    return GW_OK;
}

int gw_rs485_modbus_write(int fd, uint8_t slave, uint16_t register_addr,
                          uint16_t value, int timeout_ms) {
    if (fd < 0) return GW_ERR_INVALID;

    uint8_t req[8];
    req[0] = slave;
    req[1] = 0x06;  /* write single register */
    req[2] = (uint8_t)(register_addr >> 8);
    req[3] = (uint8_t)(register_addr & 0xFF);
    req[4] = (uint8_t)(value >> 8);
    req[5] = (uint8_t)(value & 0xFF);
    uint16_t crc = crc16_modbus(req, 6);
    req[6] = (uint8_t)(crc & 0xFF);
    req[7] = (uint8_t)(crc >> 8);

    tcflush(fd, TCIFLUSH);
    if (write(fd, req, 8) != 8) return GW_ERR_IO;

    /* echo response: 8 bytes 동일 */
    uint8_t resp[8];
    int rc = read_with_timeout(fd, resp, 8, timeout_ms);
    if (rc < 0) return rc;

    if ((resp[1] & 0x80) != 0) return GW_ERR_IO;
    if (memcmp(req, resp, 6) != 0) return GW_ERR_CRC;

    uint16_t got_crc = resp[6] | ((uint16_t)resp[7] << 8);
    uint16_t calc_crc = crc16_modbus(resp, 6);
    if (got_crc != calc_crc) return GW_ERR_CRC;
    return GW_OK;
}

int gw_rs485_close(int fd) {
    if (fd < 0) return GW_ERR_INVALID;
    return close(fd) < 0 ? GW_ERR_IO : GW_OK;
}
