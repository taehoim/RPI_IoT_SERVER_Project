# 하드웨어 셋업 가이드 (Phase 0)

> 본 가이드는 **CM4 + eMMC + carrier board** 구성을 우선 권장합니다.
> Pi 4 + microSD 대안은 문서 하단 참조.

## A. CM4 + eMMC + Waveshare carrier board (권장)

같은 BCM2711 SoC + eMMC storage로, Phase 1의 R1124-10과 동일한 SoC·storage 클래스에서 검증할 수 있습니다. write endurance · power-loss tolerance 모두 microSD 대비 우월.

### 하드웨어 BOM (약 18-20만원)

| 항목 | 모델 / 사양 | 가격 |
|---|---|---|
| **CM4 4GB + eMMC 16-32GB Lite** | Raspberry Pi Compute Module 4 (Lite = WiFi only, eMMC 32GB) | 9-12만원 |
| **Carrier board** | Waveshare CM4-IO-BASE-B (RJ45, 2× USB, HDMI, GPIO header) | 3-4만원 |
| 5V 3A 어댑터 | 공식 USB-C PD 또는 동급 | 1만원 |
| USB-C 데이터 케이블 | rpiboot eMMC flashing 용 | 5천원 |
| USB-RS485 어댑터 | FT232 또는 CH340 + MAX485 | 1.5만원 |
| 릴레이 모듈 | 5V 1ch 또는 4ch | 5천원 |
| 6-in-1 환경 센서 | RS485 Modbus, NH3+CO2+PM10+PM2.5+T+H | 7-15만원 (또는 simulator로 0원) |
| 점퍼 와이어 | | 5천원 |

### CM4 Lite 모델 선택 가이드

| 모델 | RAM | eMMC | WiFi/BT | 권장 용도 |
|---|---|---|---|---|
| CM4002000 | 2GB | 없음 | 없음 | ❌ Phase 0 부적합 |
| CM4104016 | 4GB | 16GB | ✅ | 권장 (저렴) |
| CM4104032 | 4GB | 32GB | ✅ | 권장 (여유) |
| CM4108032 | 8GB | 32GB | ✅ | overkill (Phase 0) |

### eMMC OS 굽기 (rpiboot — PC에서 1회)

CM4의 eMMC는 USB OTG로 PC에 mass storage로 노출 후 Imager로 직접 굽습니다. microSD 굽는 것과 거의 동일한 흐름.

```bash
# 1. PC (Linux 권장 — Windows/Mac도 가능)에 rpiboot 설치
sudo apt install git libusb-1.0-0-dev pkg-config build-essential
git clone --depth=1 https://github.com/raspberrypi/usbboot
cd usbboot
make
sudo ./rpiboot &

# 2. Carrier board 준비
#    - SD/eMMC 부트 셀렉트 점퍼: eMMC boot 위치로 (Waveshare는 BOOT pin GND)
#    - 전원 어댑터는 아직 연결 안함
#    - USB-C OTG 포트 (carrier board의 'USB SLAVE' 또는 'OTG' 라벨)와 PC를 USB-C 케이블로 연결
#    - 이제 전원 연결

# 3. PC에서 lsblk 으로 새 USB mass storage 확인
lsblk
# 보통 /dev/sda 로 노출됨 (16GB 또는 32GB)

# 4. Pi Imager 또는 dd로 OS 굽기
#    Imager: "Choose Storage" 에서 새 디바이스 선택, Pi OS Lite 64-bit 굽기
#    또는 dd:
sudo dd if=raspios-lite-arm64.img of=/dev/sdX bs=4M status=progress conv=fsync

# 5. 완료 후 PC에서 USB 안전 제거 → 점퍼를 SD/eMMC boot 일반 위치로 → USB-C 분리 → 전원 재인가
```

### 첫 부팅 + ssh

```bash
# carrier board 후면 RJ45 ethernet 연결
# 공유기 DHCP 할당 IP를 hostname (raspberrypi 또는 설정한 hostname)으로 ssh
ssh iot@<cm4-ip>

# 시간/locale 확인
sudo timedatectl set-timezone Asia/Seoul
sudo apt-get update && sudo apt-get upgrade -y
```

### 결선 (Waveshare CM4-IO-BASE-B 기준)

```
Carrier board 40-pin GPIO header  →  주변
─────────────────────────────────────────────────────────────
Pin 1  (3.3V)                       →  RS485 어댑터 (옵션)
Pin 6  (GND)                        →  공통 GND
Pin 11 (BCM 17)                     →  Relay #1 IN (환기팬)
Pin 13 (BCM 27)                     →  Relay #2 IN (살균기)
USB Port (전면 USB-A)                →  USB-RS485 → /dev/ttyUSB0

릴레이 모듈은 NC 단자 + 외부 12V 전원 사용 (NC = relay open = safe)
```

### 부팅 시간 (참고)

| Storage | OS 부팅 (kernel + systemd target multi-user) | gateway-agent local-ready |
|---|---|---|
| **eMMC (CM4)** | 8-12초 | OS+1초 (총 9-13초) |
| microSD Class 10 (Pi 4) | 12-18초 | OS+1초 (총 13-19초) |
| microSD A2 high-end | 10-15초 | OS+1초 (총 11-16초) |

eMMC는 random IOPS 5-10×, write latency 안정성 우월. 추가로 power-loss 안전성도 ↑ (eMMC는 fail-safe write 내장).

---

## B. Pi 4 + microSD 대안 (저예산)

R1124-10과 SoC는 같지만 storage 매체와 form factor 다름. CM4 환경 차이는 코드 0줄, 절차 약간 (rpiboot 대신 microSD imager).

### 하드웨어 BOM (약 12만원)

| 항목 | 모델 | 가격 |
|---|---|---|
| Pi 4 4GB | Raspberry Pi 4 Model B 4GB | 6만원 |
| microSD 32GB | SanDisk Extreme A2 (Class 10) | 1.5만원 |
| 5V 3A 어댑터 | 공식 USB-C PD | 1만원 |
| USB-RS485 | FT232 / CH340 | 1.5만원 |
| 릴레이 모듈 | 5V 1ch | 5천원 |
| 환경 센서 | (위와 동일) | 7-15만원 |

### Pi 4 OS 굽기

```bash
# Raspberry Pi Imager 사용 (가장 단순)
# microSD를 PC에 → Imager → Pi OS Lite 64-bit → microSD 선택 → 굽기
# 옵션에서 hostname / ssh / user / WiFi 미리 설정 가능
```

### 결선 — CM4 carrier와 동일

(40-pin GPIO header 위치 동일, BCM 핀 번호 동일)

---

## A vs B 비교 결정 가이드

| 항목 | A (CM4 + eMMC) | B (Pi 4 + microSD) |
|---|---|---|
| BOM | 18-20만원 | 12만원 |
| Phase 1 (R1124-10)와의 일치도 | ★★★ (같은 SoC + eMMC) | ★★ (같은 SoC, 다른 storage) |
| 부팅 시간 | 8-12s | 12-18s |
| Storage 신뢰도 | 높음 (수천 P/E cycle) | 중간 (수백 P/E, sudden power loss 위험) |
| 첫 OS flash | rpiboot 필요 (PC) | microSD imager 단순 |
| 재플래시 | USB-C 연결 + rpiboot | microSD 빼서 PC에 |
| 24hr burn-in 신뢰도 | ↑ (write endurance) | △ (장시간 telemetry write로 SD 마모) |

**권장: A (CM4 + eMMC)** — Phase 1 진입 시점에 R1124-10과 동일한 storage class에서 검증된 stack을 그대로 가져갈 수 있음.

---

## 양쪽 공통 — install + 검증

OS가 부팅되면 이후 절차는 동일:

```bash
git clone <YOUR_REPO_URL> ~/IoT_Gateway_Server
cd ~/IoT_Gateway_Server
sudo bash deploy/scripts/install-pi4.sh   # CM4도 동일 (BCM2711 family)

# config 편집 + 시작
sudo nano /etc/iot-gateway/config.yaml
sudo systemctl start iot-gateway
sudo journalctl -fu iot-gateway

# smoke test
bash deploy/scripts/smoke_test.sh

# PC에서 telemetry monitor
mosquitto_sub -h <ip> -t 'gw/+/#' -v
```

## simulator 사용 (실 센서 없을 때)

```bash
pip3 install pymodbus pyserial
socat -d -d pty,raw,echo=0,link=/tmp/sim_a pty,raw,echo=0,link=/tmp/sim_b &
python3 deploy/scripts/modbus_simulator.py --port /tmp/sim_a --slave-id 1
# config.yaml의 sensors[].interface를 /tmp/sim_b 로 변경
```

USB-RS485 두 개 보유 시 cross-connect도 가능 (gateway = /dev/ttyUSB0, simulator = /dev/ttyUSB1, A↔A B↔B GND).

## 트러블슈팅

| 증상 | 원인 후보 | 해결 |
|---|---|---|
| **eMMC 부팅 실패** (CM4) | boot select 점퍼 위치 오류 | carrier board datasheet 확인, eMMC boot 모드 점퍼 (보통 BOOT pin = GND OFF) |
| **rpiboot 안 보임** (CM4) | USB-C 데이터 케이블이 아닌 충전 전용 | 데이터 가능 케이블로 교체 (충전만 되는 케이블 흔함) |
| **eMMC 안 보임** (lsblk) | rpiboot 시점에 전원 인가 순서 잘못 | rpiboot 먼저 실행 → carrier 전원 → 5초 대기 후 lsblk |
| `permission denied: /dev/gpiochip0` | iot 사용자 gpio group 미가입 | `sudo usermod -aG gpio iot && sudo reboot` |
| `permission denied: /dev/ttyUSB0` | dialout 미가입 | `sudo usermod -aG dialout iot && sudo reboot` |
| `kernel watchdog disabled: hal: permission denied` | iot가 /dev/watchdog 접근 불가 | `sudo chmod 660 /dev/watchdog && sudo chown root:iot /dev/watchdog` |
| systemd `WatchdogSec=30` 발동 → 부팅 직후 재시작 루프 | sd_notify 누락 | journalctl로 sd_notify_interval_sec 확인 |
| MQTT 연결 실패 | mosquitto 미기동 / firewall | `systemctl status mosquitto`, `ufw status` |
| Modbus 응답 없음 | DE/RE 핀 잘못, baudrate 불일치, slave_id 오류 | 가스 센서 datasheet 재확인, simulator로 link layer 검증 |
| **eMMC write 속도 느림** | filesystem mount 옵션 (noatime 미적용 등) | `/etc/fstab`에 `noatime,nodiratime` 추가 후 재부팅 |
