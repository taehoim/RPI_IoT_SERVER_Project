#!/usr/bin/env python3
"""
modbus_simulator.py — pymodbus 기반 RS485 슬레이브 시뮬레이터

실 가스 센서 없을 때 USB-RS485 두 개 (또는 PTY pair)로 connect 후
가스 센서 흉내. NH3 (register 0), H2S (register 1), CO2 (register 2)
주기적 변동 값 반환.

사용:
    pip install pymodbus pyserial
    python3 modbus_simulator.py --port /dev/ttyUSB1 --slave-id 1

또는 PTY pair 모드:
    socat -d -d pty,raw,echo=0 pty,raw,echo=0
    # 출력된 두 PTY 중 하나는 simulator에, 다른 하나는 gateway interface에 사용
"""

import argparse
import asyncio
import math
import random
import time

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server import StartAsyncSerialServer


def make_context(reg_count: int) -> ModbusServerContext:
    """초기 holding registers 데이터 블록"""
    block = ModbusSequentialDataBlock(0, [0] * reg_count)
    slave = ModbusSlaveContext(hr=block)
    return ModbusServerContext(slaves=slave, single=True)


async def update_loop(ctx: ModbusServerContext, interval: float):
    """주기적으로 register 값 갱신 (사인파 + 노이즈)"""
    start = time.time()
    while True:
        t = time.time() - start
        # NH3: 200~300 (×0.1 = 20~30 ppm)
        nh3 = int(250 + 50 * math.sin(t / 60) + random.randint(-5, 5))
        # H2S: 50~150 (×0.1 = 5~15 ppm)
        h2s = int(100 + 50 * math.sin(t / 90) + random.randint(-3, 3))
        # CO2: 800~1500 ppm (직접 값)
        co2 = int(1150 + 350 * math.sin(t / 120) + random.randint(-10, 10))

        slave = ctx[0]
        # function code 0x03 = holding registers (fx=3)
        slave.setValues(3, 0, [nh3, h2s, co2])
        await asyncio.sleep(interval)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", required=True, help="serial device (예: /dev/ttyUSB1)")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--slave-id", type=int, default=1)
    p.add_argument("--update-interval", type=float, default=2.0)
    p.add_argument("--reg-count", type=int, default=10)
    args = p.parse_args()

    ctx = make_context(args.reg_count)
    print(f"[sim] starting Modbus RTU slave on {args.port} @ {args.baud} 8N1, slave_id={args.slave_id}")
    print(f"[sim] simulating registers: NH3=[0], H2S=[1], CO2=[2] (updated every {args.update_interval}s)")

    asyncio.create_task(update_loop(ctx, args.update_interval))

    await StartAsyncSerialServer(
        context=ctx,
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=1,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[sim] stopped")
