## Makefile — libgw_hal.so + 단위 테스트
## platform=pi4 (default, BCM2711 — Pi 4 microSD + CM4 eMMC 공통) | r1124 (Phase 1+ stub)
## targets: all | test | clean | install

PLATFORM ?= pi4
BUILD_DIR := build
LIB := $(BUILD_DIR)/libgw_hal.so
PREFIX ?= /usr/local

CC ?= gcc
CFLAGS := -Wall -Wextra -Werror -fPIC -O2 -std=c11 -Iinclude -pthread
LDFLAGS := -shared -lgpiod -lpthread

# platform별 backend 선택
COMMON_SRCS := src/common.c src/rs485.c src/watchdog.c
ifeq ($(PLATFORM),pi4)
    PLATFORM_SRC := src/platform_pi4.c
else ifeq ($(PLATFORM),r1124)
    PLATFORM_SRC := src/platform_r1124.c
else
    $(error Unknown PLATFORM=$(PLATFORM). Use pi4 or r1124)
endif

SRCS := $(COMMON_SRCS) $(PLATFORM_SRC)
OBJS := $(SRCS:src/%.c=$(BUILD_DIR)/%.o)

# Test binaries
TEST_BINS := $(BUILD_DIR)/test_rs485_pty $(BUILD_DIR)/test_gpio_mock $(BUILD_DIR)/test_safe_state
TEST_CFLAGS := -Wall -Wextra -O0 -g -std=c11 -Iinclude -pthread

.PHONY: all test clean install

all: $(LIB)

$(LIB): $(OBJS) | $(BUILD_DIR)
	$(CC) $(LDFLAGS) -o $@ $(OBJS)
	@echo "Built: $@ (platform=$(PLATFORM))"

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR):
	@mkdir -p $@

# ----- Tests -----
# 단위 테스트는 platform_pi4.c 미포함 (libgpiod 의존). RS485 PTY 테스트와 mock GPIO 테스트만.
TEST_RS485_OBJS := $(BUILD_DIR)/rs485_test.o $(BUILD_DIR)/common_test.o
TEST_GPIO_OBJS := $(BUILD_DIR)/common_test.o

test: $(TEST_BINS)
	@echo "----- Running C unit tests -----"
	@for t in $(TEST_BINS); do \
		echo "→ $$t"; \
		if ! $$t; then echo "FAIL: $$t"; exit 1; fi; \
	done
	@echo "All C unit tests PASSED"

$(BUILD_DIR)/test_rs485_pty: tests/test_rs485_pty.c $(BUILD_DIR)/rs485.o $(BUILD_DIR)/common.o | $(BUILD_DIR)
	$(CC) $(TEST_CFLAGS) -o $@ $^

$(BUILD_DIR)/test_gpio_mock: tests/test_gpio_mock.c | $(BUILD_DIR)
	$(CC) $(TEST_CFLAGS) -o $@ $<

$(BUILD_DIR)/test_safe_state: tests/test_safe_state.c | $(BUILD_DIR)
	$(CC) $(TEST_CFLAGS) -o $@ $<

install: $(LIB)
	install -d $(PREFIX)/lib $(PREFIX)/include
	install -m 755 $(LIB) $(PREFIX)/lib/
	install -m 644 include/gw_hal.h $(PREFIX)/include/
	ldconfig
	@echo "Installed to $(PREFIX)"

clean:
	rm -rf $(BUILD_DIR)
