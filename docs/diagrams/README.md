# 시스템 다이어그램

| 파일 | 형태 | 설명 |
|---|---|---|
| `01_system_concept.md` | Markdown ASCII | 6-layer top-down 개념도, 흐름 시나리오 4종, watchdog 3-layer |
| `01_system_concept.excalidraw` | Excalidraw JSON | 시각화 버전 (75 elements: 41 text, 29 rectangle, 5 arrow) |

## Excalidraw 파일 열기

### 옵션 1: 웹 (가장 쉬움)

1. https://excalidraw.com/ 접속
2. 좌상단 햄버거 메뉴 → **Open** 클릭
3. `docs/diagrams/01_system_concept.excalidraw` 선택
4. 자유롭게 편집·내보내기 (PNG/SVG)

### 옵션 2: VS Code Extension

1. VS Code에 [Excalidraw extension](https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor) 설치
2. `.excalidraw` 파일 더블클릭 → 자동 렌더링
3. 편집 후 저장 시 JSON으로 자동 저장

### 옵션 3: 데스크톱 앱

[Excalidraw+ Desktop](https://plus.excalidraw.com/desktop) — 오프라인 편집 지원.

### 옵션 4: PNG export (CLI)

skill 내장 render 스크립트:

```bash
cd .claude/skills/excalidraw-diagram/references
uv run python render_excalidraw.py \
  /path/to/IoT_Gateway_Server/docs/diagrams/01_system_concept.excalidraw
```

WSL/제한 네트워크 환경에서 esm.sh 모듈 로드가 느려 timeout 가능. 그 경우 옵션 1 (웹) 권장.

## 다이어그램 구조

`01_system_concept.excalidraw` 의 6 layer (top → down):

```
y=0~100      Title + Subtitle
y=130~190    ① USER LAYER          5명 역할
y=240~310    ② WEB PORTAL          4 메인 화면
y=395~935    ③ SELF-HOSTED SERVER  Nginx + Keycloak + Backend + Worker + PostgreSQL + VerneMQ + Storage
y=1015~1235  ④ MQTT TOPIC PATTERN  publish 7 + subscribe 3 + telemetry payload 예시
y=1325~1685  ⑤ GATEWAY LAYER       Go Agent + cgo + libgw_hal.so + local mosquitto + GW-N
y=1770~2000  ⑥ FIELD I/O           6-in-1 센서 register 매핑 + 환기팬 + 살균기 + 로봇청소기
```

**6 layer + 5 계층간 화살표** = 시스템 전체가 한 화면에 응축.

## 색상 의미 (Color semantics)

| 색상 | Hex | 의미 |
|---|---|---|
| 🟧 주황 (`#fed7aa`) | start/trigger | User layer · MQTT broker · 액추에이터 |
| 🟦 파랑 (`#93c5fd`/`#60a5fa`) | primary/secondary | Web Portal · Backend · Worker · Go Agent |
| 🟪 보라 (`#ddd6fe`) | AI/특수 | Keycloak (인증·토큰) |
| 🟩 녹색 (`#a7f3d0`) | end/success | PostgreSQL · 6-in-1 센서 (data 저장/생성) |
| 🟨 노랑 (`#fef3c7`) | decision | C HAL (cgo 경계) |
| 🟥 빨강 (`#fee2e2`) | warning/reset | GW-N 다중 인스턴스 (확장 포인트) |
| ⬛ 검정 (`#1e293b`) | code/JSON evidence | MQTT topic 명세 + telemetry payload 예시 |
| ⬜ 흰색 dashed | container | Server frame · Gateway frame |

## 다이어그램 7종 (모두 작성 완료)

| 파일 | elements | 핵심 |
|---|---:|---|
| `01_system_concept.excalidraw` | 76 | 6-layer top-down 개념 (User→Web→Server→MQTT→Gateway→Field) |
| `02_detailed_architecture.excalidraw` | 45 | Server 7 모듈 + Gateway 내부 layered (Go/cgo/HAL/systemd/WDT 3-layer) zoom-in |
| `03_data_flow_telemetry.excalidraw` | 43 | Telemetry 8-step sequence (10초 주기, 7 actor lifeline) + payload JSON evidence |
| `04_data_flow_command.excalidraw` | 48 | Command 11-step sequence (User→Relay) + safety check + max_on_duration |
| `05_failure_modes.excalidraw` | 58 | 10 failure × 4열(Failure/Detection/Response/Test) 매트릭스 |
| `06_security_layers.excalidraw` | 22 | 8 layer 다중 방어선 (Network→TLS→Auth→RBAC→RLS→ACL→Cmd Safety→NC Wiring) |
| `07_phase_roadmap.excalidraw` | 38 | Phase 0-7 columnar timeline + 8 milestone gate 조건 |

**총 330 elements** · 모두 JSON valid + 색상 팔레트 일관 + `fontFamily 3` + `roughness 0`

## 일관 색상 의미

| 색 | Hex | 용도 |
|---|---|---|
| 🟧 | `#fed7aa` (start/trigger) | User · Gateway frame · MQTT broker · 액추에이터 · CRC retry |
| 🟦 진한 | `#3b82f6` (primary) | Nginx · Go agent main · 강조 |
| 🟦 중간 | `#60a5fa` (secondary) | Backend · Worker · Go module · 일반 컴포넌트 |
| 🟦 연한 | `#93c5fd` (tertiary) | Web Portal 화면 · Phase 1 |
| 🟪 | `#ddd6fe` (AI/특수) | Keycloak (인증·토큰) · Phase 3 |
| 🟩 | `#a7f3d0` (end/success) | PostgreSQL · 6-in-1 센서 · Phase 6 · 성공 path |
| 🟨 | `#fef3c7` (decision) | C HAL (cgo 경계) · systemd 정책 · Phase 5 · medium severity |
| 🟥 진한 | `#fecaca` (error) | 최후 방어선 (NC wiring + WDT) |
| 🟥 연한 | `#fee2e2` (warning) | CRITICAL 실패 모드 · GW-N (확장) · Phase 7 |
| ⬛ | `#1e293b` (code) | JSON payload · MQTT topic 명세 evidence artifact |
