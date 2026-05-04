# CM4 eMMC OS 굽기 (rpiboot 절차)

CM4의 eMMC는 onboard NAND라 직접 빼서 imager로 굽지 못합니다. 대신 **rpiboot**(Raspberry Pi 공식 도구)로 carrier board의 USB-C OTG 포트를 통해 eMMC를 PC의 USB mass storage로 노출시킨 뒤 imager로 굽습니다.

## 준비물

- CM4 모듈 (eMMC 16GB 이상 — Lite 아닌 모델)
- Carrier board — Waveshare CM4-IO-BASE-B 권장 (USB SLAVE 포트 + BOOT 점퍼 보유)
- USB-C **데이터** 케이블 (충전 전용 케이블 다수, 주의)
- PC (Linux 권장, Windows/Mac 가능)
- Pi OS Lite 64-bit 이미지 (.img 또는 imager 자체 다운로드)

## Step 1: PC에 rpiboot 설치 (Linux 기준)

```bash
sudo apt-get install -y git libusb-1.0-0-dev pkg-config build-essential
git clone --depth=1 https://github.com/raspberrypi/usbboot
cd usbboot
make
# 빌드 산출물: ./rpiboot
```

Windows: https://github.com/raspberrypi/usbboot/releases 에서 Windows 인스톨러 다운로드.
Mac: `brew install libusb` 후 위 git clone + make.

## Step 2: Carrier board를 rpiboot 모드로 진입

Waveshare CM4-IO-BASE-B 기준 (다른 carrier도 boot select 점퍼 위치만 다름):

```
1. carrier board 전원 어댑터 분리 (전원 OFF 상태)
2. BOOT 점퍼 핀을 GND 쪽으로 단락 (eMMC를 USB mass storage 모드로 진입시킴)
   ── Waveshare는 J2 헤더의 BOOT 핀 ── 점퍼 추가 또는 와이어로 연결
3. carrier board의 USB SLAVE 포트 (USB-C OTG)와 PC를 USB-C 데이터 케이블로 연결
4. carrier board에 5V 전원 연결 (DC jack 또는 GPIO 5V)
```

## Step 3: PC에서 rpiboot 실행

```bash
sudo ./rpiboot
# 출력 예:
#   Waiting for BCM2835/6/7/2711...
#   Loading: msd.elf
#   Second stage boot server
#   File read: msd.elf
#   File read: bootcode4.bin
#   ...
#   File read complete
```

위 메시지가 뜨면 eMMC가 PC에 USB mass storage로 노출됩니다.

## Step 4: 이미지 굽기

```bash
# lsblk으로 새로 노출된 디바이스 확인 (보통 16GB 또는 32GB)
lsblk
# NAME    SIZE  TYPE
# sda    14.6G  disk    ← 이게 CM4 eMMC

# 옵션 A: Pi Imager (GUI)
sudo rpi-imager
# Operating System → Raspberry Pi OS (Other) → Pi OS Lite 64-bit
# Storage → /dev/sda 선택
# 톱니바퀴 ⚙ → hostname/ssh/user/timezone 미리 설정
# Write

# 옵션 B: dd (CLI)
xz -d 2024-xx-xx-raspios-bookworm-arm64-lite.img.xz
sudo dd if=2024-xx-xx-raspios-bookworm-arm64-lite.img of=/dev/sda bs=4M status=progress conv=fsync
sync

# 옵션 C: balenaEtcher (GUI, 크로스플랫폼)
```

## Step 5: 부팅 모드 복귀 + 첫 부팅

```
1. 굽기 완료 후 PC에서 USB 안전 제거 (sync; sudo eject /dev/sda)
2. carrier board 전원 분리
3. BOOT 점퍼 제거 (또는 NORMAL 위치로 복귀)
4. USB-C 케이블 분리
5. ethernet 케이블 연결
6. 전원 재인가 → eMMC에서 부팅
```

부팅 시간: 약 8-12초 (microSD 12-18s 대비 빠름).

## Step 6: ssh 접속 + 세팅

```bash
# Imager에서 hostname 설정했으면 그 이름으로 ssh
ssh iot@cm4-iot-dev01.local
# 또는 공유기 DHCP 로그에서 IP 확인 후 ssh iot@<ip>

# 초기 설정
sudo timedatectl set-timezone Asia/Seoul
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git
git clone <YOUR_REPO_URL> ~/IoT_Gateway_Server
cd ~/IoT_Gateway_Server
sudo bash deploy/scripts/install-pi4.sh   # CM4도 같은 BCM2711 family라 그대로 동작
```

## eMMC 전용 운영 권장 사항

### A. fstab 최적화 (write 최소화)

`/etc/fstab` 의 root partition `/` 라인을 다음으로 수정:

```fstab
/dev/disk/by-label/rootfs  /  ext4  defaults,noatime,nodiratime,commit=60  0  1
```

- `noatime`: 파일 읽을 때마다 access time 업데이트 안 함 → 매 read마다 발생하는 metadata write 제거
- `commit=60`: filesystem journal flush를 60초마다 (기본 5초) → eMMC write cycle 12× 감소

### B. journald 메모리만 사용

`/etc/systemd/journald.conf`:

```ini
[Journal]
Storage=volatile
RuntimeMaxUse=100M
```

부팅마다 로그 사라지지만 telemetry/event는 SQLite + MQTT로 영구 저장하므로 OK. 개발 단계는 `Storage=auto + SystemMaxUse=200M` 절충도 가능.

### C. swap 비활성화

eMMC swap은 write 폭증 → 빠른 마모. CM4 4GB는 Phase 0 워크로드(Go agent ~50MB + mosquitto ~10MB)에 충분.

```bash
sudo systemctl disable --now dphys-swapfile
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
```

### D. log rotation 강제

```bash
sudo logrotate -f /etc/logrotate.conf
```

`/etc/logrotate.d/iot-gateway`:
```
/var/log/iot-gateway/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
```

## 재플래시 (OS 업데이트 / 초기화)

운영 중 eMMC 재굽기 절차는 Step 2-5 반복. 데이터 보존 필요 시:

```bash
# 1. 부팅 가능한 시점에 SQLite + config 백업 (PC로 scp)
ssh iot@cm4 "sudo sqlite3 /var/lib/iot-gateway/local.db .dump" > backup.sql
scp iot@cm4:/etc/iot-gateway/config.yaml ./

# 2. rpiboot 모드로 재진입 (Step 2-5)
# 3. 새 OS 부팅 후 install + 백업 복원
sudo bash deploy/scripts/install-pi4.sh
sudo cp config.yaml /etc/iot-gateway/
sudo sqlite3 /var/lib/iot-gateway/local.db < backup.sql
sudo systemctl restart iot-gateway
```

## 트러블슈팅 (rpiboot)

| 증상 | 원인 | 해결 |
|---|---|---|
| `Waiting for BCM...` 무한 대기 | USB-C 케이블이 충전 전용 | 데이터 케이블 (양 쪽 다 USB-C인 짧은 케이블이 보통 OK) |
| `lsblk`에 새 디바이스 안 뜸 | BOOT 점퍼 위치 오류 | carrier datasheet 재확인, 전원 OFF→점퍼→전원 ON |
| `Permission denied: /dev/sda` | sudo 없이 dd | `sudo dd` 또는 udev rule 추가 |
| 굽기는 됐는데 부팅 안 됨 | BOOT 점퍼 안 뺐음 | 굽기 완료 후 BOOT 점퍼 제거 후 재부팅 |
| 부팅 후 wifi 안 됨 (Lite 모델 아닌데) | wpa_supplicant 미설정 | rpi-imager 설정 시 WiFi 자격증명 미리 설정 권장 |
| 첫 ssh 시 hostname 못 찾음 | mDNS resolver 부재 | `avahi-daemon` 설치 또는 공유기 DHCP IP 직접 사용 |

## CM4 모델별 메모리 / eMMC 조합

| 모델 코드 | RAM | eMMC | WiFi |
|---|---|---|---|
| CM4001000 | 1GB | 없음 | 없음 |
| CM4001008 | 1GB | 8GB | 없음 |
| CM4001016 | 1GB | 16GB | 없음 |
| CM4001032 | 1GB | 32GB | 없음 |
| CM4002000 | 2GB | 없음 | 없음 |
| CM4002008 | 2GB | 8GB | 없음 |
| ...    | ... | ... | ... |
| **CM4104016** | **4GB** | **16GB** | **WiFi+BT** | ← Phase 0 권장 (저렴) |
| **CM4104032** | **4GB** | **32GB** | **WiFi+BT** | ← Phase 0 권장 (여유) |
| CM4108032 | 8GB | 32GB | WiFi+BT | overkill (Phase 0 워크로드) |

명명 규칙: CM4 + RAM(1/2/4/8 GB) + eMMC(00/08/16/32 GB) + WiFi(0=없음, 1=있음). 예: `CM4104016` = 1GB×... 아니, 4GB+16GB+WiFi. 정확한 룩업 표는 [공식 데이터시트](https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf) 참조.
