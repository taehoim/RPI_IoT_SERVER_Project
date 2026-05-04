#!/usr/bin/env python3
"""
CM4 IoT Gateway 자체 호스팅 플랫폼 — 상세 구현 계획서 (HWPX 개조식)
- 15개 장(章), 정부/공공기관 개조식 (1./가./1)/○/-) 계층
- report 템플릿 사용 (charPr/paraPr ID 매핑 활용)
"""

from html import escape

OUT_SECTION = "/tmp/iot_section0.xml"
TEMPLATE_HEADER = "/home/imth/.claude/skills/hwpxskill/templates/report/header.xml"

# 스타일 ID (report 템플릿 기준)
CHAR_BODY    = 0   # 10pt 기본
CHAR_TITLE_L = 12  # 16pt 볼드 (큰 제목)
CHAR_SECT    = 13  # 12pt 볼드 (섹션 헤더)
CHAR_SUBT    = 8   # 14pt 볼드 (소제목)
CHAR_BOLD    = 10  # 10pt 볼드+밑줄 (강조)
CHAR_TBL_HDR = 9   # 10pt 볼드 (표 헤더)
CHAR_SMALL   = 11  # 9pt (작은 글씨/각주)

PARA_DEFAULT = 0   # JUSTIFY 160%
PARA_CENTER  = 20  # CENTER 160%
PARA_TBL_C   = 21  # CENTER 130%
PARA_TBL_J   = 22  # JUSTIFY 130%
PARA_RIGHT   = 23  # RIGHT
PARA_L1      = 24  # left 600 (□)
PARA_L2      = 25  # left 1200 (○)
PARA_L3      = 26  # left 1800 (-)
PARA_SECT_HDR= 27  # 섹션 헤더 (상하단 테두리선)

BORDER_TBL   = 3
BORDER_HDR   = 4   # 표 헤더 셀 (배경색)

# A4 본문폭
TXT_WIDTH = 42520

# ---- ID 카운터 ----
class Counter:
    def __init__(self, start=1000000001):
        self.v = start
    def next(self):
        cur = self.v
        self.v += 1
        return cur
pid = Counter(1000000010)
tid = Counter(2000000001)

paragraphs = []  # XML 조각 리스트

# ---- secPr 첫 문단 ----
SEC_FIRST = """  <hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">
        <hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>
        <hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>
        <hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>
        <hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>
        <hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">
          <hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>
        </hp:pagePr>
        <hp:footNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="EACH_COLUMN" beneathText="0"/>
        </hp:footNotePr>
        <hp:endNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="END_OF_DOCUMENT" beneathText="0"/>
        </hp:endNotePr>
        <hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
      </hp:secPr>
      <hp:ctrl>
        <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>
      </hp:ctrl>
    </hp:run>
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
  </hp:p>
"""

# ---- 헬퍼 ----

def p(text, paraId=PARA_DEFAULT, charId=CHAR_BODY):
    """일반 문단."""
    pid_ = pid.next()
    safe = escape(text)
    paragraphs.append(
        f'  <hp:p id="{pid_}" paraPrIDRef="{paraId}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
        f'    <hp:run charPrIDRef="{charId}"><hp:t>{safe}</hp:t></hp:run>\n'
        f'  </hp:p>\n'
    )

def blank():
    """빈 줄."""
    pid_ = pid.next()
    paragraphs.append(
        f'  <hp:p id="{pid_}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
        f'    <hp:run charPrIDRef="0"><hp:t/></hp:run>\n'
        f'  </hp:p>\n'
    )

def title_main(text):
    """문서 메인 제목 (1줄, 16pt 볼드 가운데)."""
    p(text, paraId=PARA_CENTER, charId=CHAR_TITLE_L)

def chapter(text):
    """장 제목 (Ⅰ. Ⅱ. ...) — 상하단 테두리선 포함."""
    pid_ = pid.next()
    safe = escape(text)
    paragraphs.append(
        f'  <hp:p id="{pid_}" paraPrIDRef="{PARA_SECT_HDR}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
        f'    <hp:run charPrIDRef="{CHAR_SECT}"><hp:t>{safe}</hp:t></hp:run>\n'
        f'  </hp:p>\n'
    )

def section(num, text):
    """1. 가. 등 절 제목 (볼드)."""
    pid_ = pid.next()
    full = f"{num} {text}"
    safe = escape(full)
    # paraPr 24 (left 600), charPr 9 (10pt 볼드)
    paragraphs.append(
        f'  <hp:p id="{pid_}" paraPrIDRef="{PARA_L1}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
        f'    <hp:run charPrIDRef="{CHAR_TBL_HDR}"><hp:t>{safe}</hp:t></hp:run>\n'
        f'  </hp:p>\n'
    )

def L1(text, marker="□"):
    """1단계 항목 (□)."""
    p(f"{marker} {text}", paraId=PARA_L1, charId=CHAR_BODY)

def L2(text, marker="○"):
    """2단계 항목 (○)."""
    p(f"{marker} {text}", paraId=PARA_L2, charId=CHAR_BODY)

def L3(text, marker="-"):
    """3단계 항목 (-)."""
    p(f"{marker} {text}", paraId=PARA_L3, charId=CHAR_BODY)

def note(text):
    """※ 참고/주."""
    p(f"※ {text}", paraId=PARA_L1, charId=CHAR_SMALL)

def kv(key, value, level=2):
    """Key: Value 형태."""
    line = f"{key} : {value}"
    marker = {1: "□", 2: "○", 3: "-"}[level]
    paraId = {1: PARA_L1, 2: PARA_L2, 3: PARA_L3}[level]
    p(f"{marker} {line}", paraId=paraId, charId=CHAR_BODY)

def code_block(text):
    """코드/예시 블록 (들여쓰기 + 작은 글씨)."""
    for line in text.split("\n"):
        # 빈 라인은 그대로 출력
        if not line.strip():
            paragraphs.append(
                f'  <hp:p id="{pid.next()}" paraPrIDRef="{PARA_L2}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
                f'    <hp:run charPrIDRef="{CHAR_SMALL}"><hp:t/></hp:run>\n'
                f'  </hp:p>\n'
            )
        else:
            safe = escape(line)
            paragraphs.append(
                f'  <hp:p id="{pid.next()}" paraPrIDRef="{PARA_L2}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
                f'    <hp:run charPrIDRef="{CHAR_SMALL}"><hp:t>{safe}</hp:t></hp:run>\n'
                f'  </hp:p>\n'
            )

# ---- 표 빌더 ----

def table(headers, rows, col_widths_pct=None):
    """
    headers: [str, ...]
    rows: [[str, ...], ...]
    col_widths_pct: [pct, ...] (합 100). None이면 균등.
    표는 빈 wrapper 문단 안에 hp:tbl로 들어간다.
    """
    n_cols = len(headers)
    n_rows = len(rows) + 1
    if col_widths_pct is None:
        col_widths_pct = [100 / n_cols] * n_cols
    # 정확히 본문폭에 맞도록 정수 계산 + 마지막 보정
    col_widths = [int(TXT_WIDTH * w / 100) for w in col_widths_pct]
    diff = TXT_WIDTH - sum(col_widths)
    col_widths[-1] += diff

    row_h = 2400
    total_h = row_h * n_rows

    # 표 wrapper 문단
    wrap_id = pid.next()
    tbl_id = tid.next()
    cells_xml = []

    # 표 행 빌더
    def build_row(cells, row_addr, is_header):
        nonlocal n_cols
        out = ['      <hp:tr>']
        for col_addr, txt in enumerate(cells):
            cw = col_widths[col_addr]
            cell_p_id = pid.next()
            border_ref = BORDER_HDR if is_header else BORDER_TBL
            char_ref = CHAR_TBL_HDR if is_header else CHAR_BODY
            para_ref = PARA_TBL_C if is_header else PARA_TBL_J
            safe = escape(str(txt))
            out.append(
                f'        <hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="{border_ref}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'<hp:p paraPrIDRef="{para_ref}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{cell_p_id}">'
                f'<hp:run charPrIDRef="{char_ref}"><hp:t>{safe}</hp:t></hp:run>'
                f'</hp:p>'
                f'</hp:subList>'
                f'<hp:cellAddr colAddr="{col_addr}" rowAddr="{row_addr}"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{cw}" height="{row_h}"/>'
                f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
                f'</hp:tc>'
            )
        out.append('      </hp:tr>')
        return "\n".join(out)

    cells_xml.append(build_row(headers, 0, True))
    for ri, r in enumerate(rows, start=1):
        cells_xml.append(build_row(r, ri, False))

    rows_xml = "\n".join(cells_xml)

    paragraphs.append(
        f'  <hp:p id="{wrap_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
        f'    <hp:run charPrIDRef="0">\n'
        f'      <hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" '
        f'repeatHeader="1" rowCnt="{n_rows}" colCnt="{n_cols}" cellSpacing="0" '
        f'borderFillIDRef="{BORDER_TBL}" noAdjust="0">\n'
        f'        <hp:sz width="{TXT_WIDTH}" widthRelTo="ABSOLUTE" height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>\n'
        f'        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
        f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>\n'
        f'        <hp:outMargin left="0" right="0" top="0" bottom="0"/>\n'
        f'        <hp:inMargin left="141" right="141" top="141" bottom="141"/>\n'
        f'{rows_xml}\n'
        f'      </hp:tbl>\n'
        f'    </hp:run>\n'
        f'  </hp:p>\n'
    )

# ============================================================
#                      문서 본문 작성
# ============================================================

# ---- 표지 ----
title_main("산업용 CM4 기반 IoT Gateway 자체 호스팅 플랫폼")
title_main("상세 구현 계획서")
blank()
p("작성일 : 2026-05-03", paraId=PARA_CENTER)
p("구축 방식 : Docker 미사용 · systemd 기반 자체 호스팅", paraId=PARA_CENTER)
p("핵심 구성 : VerneMQ + PostgreSQL + Keycloak + FastAPI + React (Vite)", paraId=PARA_CENTER)
p("작성 주체 : Solo + Claude Code AI Pair", paraId=PARA_CENTER)
blank(); blank()

# ---- 목차 안내 ----
chapter("Ⅰ. 문서 개요")

section("1.", "작성 목적")
L1("본 계획서는 산업용 Raspberry Pi Compute Module 4(CM4) 기반 IoT Gateway 제품을 자체 호스팅 서버와 연동하여 상용화하기 위한 상세 구현 계획서이다.")
L1("여러 사용자가 각자 하나 이상의 IoT Gateway를 보유하고, Gateway마다 서로 다른 종류의 센서·제어 장치를 연결할 수 있다는 점을 기본 전제로 한다.")
L1("따라서 본 시스템은 단순 데이터 수집기가 아니라, IoT Gateway Fleet Management Platform으로 설계한다.")
blank()

section("2.", "10가지 핵심 요구사항")
L1("사용자별 여러 Gateway 관리")
L2("한 사용자가 N개의 Gateway를 보유 가능하며, 권한에 따라 조회·제어 범위가 달라진다.")
L1("Gateway별 서로 다른 센서 구성 관리")
L2("Gateway A는 온습도 센서 2개 + 수위 센서 1개, Gateway B는 기울기 센서 + GPS 등 자유 조합.")
L1("릴레이·밸브·펌프 등 제어 채널 관리")
L2("Gateway별 액추에이터 채널 수와 종류가 상이하며, 각각 안전 정책을 가진다.")
L1("센서 종류 추가 시 코드 수정 최소화")
L2("새 센서 모델은 Sensor Profile JSON 추가만으로 동작하도록 설계.")
L1("Gateway 설정 중앙 관리 및 원격 반영")
L2("desired/reported 패턴으로 서버에서 발행한 설정을 Gateway가 다운로드·적용·보고.")
L1("사용자·고객사·현장·장비 단위 권한")
L2("System Admin → 관리회사 → 고객사 → 현장 → 장비 5계층 + Maintenance Engineer 별도 축.")
L1("원격 제어 명령의 안전성 확보")
L2("8가지 안전 조건(idempotency, expires, timeout, ack, local safety, audit, fail-safe, override).")
L1("장비 상태·센서·알람·이력 통합 관리")
L2("Telemetry, command 이력, config 이력, audit 로그를 단일 DB에 통합.")
L1("Docker 없이 systemd 기반 운영")
L2("산업용 서버에서 컨테이너 의존성을 제거하고 OS 서비스 단위로 명확 관리.")
L1("무료 OSS 기반 상용화 가능 구조")
L2("AGPL/BSL/GPL 리스크가 없는 컴포넌트만 채택. OSS Notice·SBOM 발행.")
blank()

# ---- Ⅱ. 전제 조건 및 설계 철학 ----
chapter("Ⅱ. 전제 조건 및 설계 철학")

section("1.", "사업 및 운영 전제")
table(
    ["항목", "전제"],
    [
        ["서비스 운영", "자체 서버 운영 (퍼블릭 IoT 플랫폼 미사용)"],
        ["퍼블릭 IoT 플랫폼", "AWS IoT, Azure IoT, GCP IoT 미사용"],
        ["컨테이너", "Docker 미사용"],
        ["서버 OS", "Ubuntu Server 24.04 LTS · 사내 물리 머신"],
        ["사용자 구조", "한 사용자가 여러 Gateway 보유 가능"],
        ["센서 구성", "Gateway마다 종류·수량 상이"],
        ["제어 구성", "Gateway마다 릴레이·밸브·펌프 구성 상이"],
        ["관리회사", "전체 사용자·Gateway 통합 관리"],
        ["일반 사용자", "본인에게 할당된 Gateway만 접근"],
        ["라이선스", "무료 OSS 중심 (AGPL/BSL/GPL 리스크 최소화)"],
    ],
    col_widths_pct=[25, 75],
)
blank()

section("2.", "기술 스택 (확정)")
table(
    ["계층", "기술 / 버전", "비고"],
    [
        ["MQTT Broker", "VerneMQ", "Apache 2.0"],
        ["DB", "PostgreSQL 16", "Ubuntu apt 기본 제공"],
        ["인증", "Keycloak (latest stable)", "PostgreSQL backend 공유"],
        ["Backend", "FastAPI (Python 3.12)", "asyncio · pydantic v2"],
        ["Frontend", "React + Vite (SPA)", "TypeScript · MIT"],
        ["Chart", "Apache ECharts", "Apache 2.0"],
        ["Reverse Proxy", "Nginx + certbot", "Let's Encrypt 자동 발급"],
        ["서비스 관리", "systemd", "Restart=always"],
        ["Gateway OS", "Pi OS Lite / Ubuntu ARM64 (Phase 2 결정)", "Yocto는 옵션"],
        ["Gateway 통신", "MQTT (Phase 1: plain · Phase 7: TLS)", "QoS 1 권장"],
        ["Gateway 설정", "서버 desired/reported 구조", "config_version + hash"],
    ],
    col_widths_pct=[18, 42, 40],
)
blank()

section("3.", "핵심 설계 철학 4원칙")

L1("원칙 1 : Gateway 중심 엔티티")
L2("배경 : 한 사용자가 여러 Gateway를 보유하고, 하나의 Gateway가 특정 회사·현장에 배정될 수 있음.")
L2("적용 : 권한 판단을 User × Company × Gateway 3축으로 결합.")
L2("결과 : 사용자 변경/이전 시에도 Gateway 단위 권한·통계가 안정적으로 유지.")

L1("원칙 2 : 센서 종류는 코드가 아니라 Profile")
L2("배경 : 센서가 늘 때마다 schema·Gateway 코드를 수정하면 유지보수가 어렵다.")
L2("적용 : 센서 모델 정보는 Sensor Profile(JSON), Gateway 연결 인스턴스는 Sensor Channel로 분리.")
L2("결과 : 새 센서 추가 시 Backend·Gateway 코드 무수정 (Profile JSON만 추가).")

L1("원칙 3 : Gateway Config 중앙 버전 관리")
L2("배경 : Gateway마다 센서 구성이 달라 고정 설정으로 동작하면 안 됨.")
L2("적용 : 서버가 Gateway별 desired_config 발행 → Gateway가 reported_config로 보고.")
L2("결과 : 어떤 Gateway가 어떤 버전의 설정을 적용 중인지 100% 추적 가능, rollback 용이.")

L1("원칙 4 : Docker 대신 systemd")
L2("배경 : 산업용 서버 운영 환경에서 컨테이너 의존성 제거, OS 서비스 단위 관리 필요.")
L2("적용 : nginx, vernemq, postgresql, keycloak, iot-backend, iot-worker, iot-scheduler 7종 unit 등록.")
L2("결과 : 단일 OS 안에서 명확한 책임 분리·로그 위치·재시작 정책 일관 관리.")
blank()

# ---- Ⅲ. 시스템 아키텍처 ----
chapter("Ⅲ. 시스템 아키텍처")

section("1.", "전체 시스템 개념도 (Concept Architecture)")
L1("계층 구성 (Top-Down)")
L2("USER LAYER — 일반 사용자, 고객사 관리자, 관리회사 관리자")
L2("WEB PORTAL — React + Vite SPA + Apache ECharts (Nginx 정적 파일)")
L2("SELF-HOSTED SERVER — Ubuntu 24.04 LTS · systemd 기반 7종 서비스")
L3("Nginx (HTTPS reverse proxy)")
L3("Keycloak (OIDC/OAuth2)")
L3("Backend API (FastAPI)")
L3("Worker (MQTT 처리)")
L3("Scheduler (주기 작업)")
L3("PostgreSQL (관계형 DB)")
L3("VerneMQ (MQTT broker)")
L2("STORAGE — 펌웨어 저장소, Gateway 설정, 백업, 로그 번들")
L2("GATEWAY LAYER — N대의 CM4 Gateway + Safety MCU")

L1("주요 데이터 흐름")
L2("HTTPS : User ↔ Web Portal ↔ Backend API")
L2("MQTT : VerneMQ ↔ Gateway (telemetry · command · config · OTA)")
L2("내부 IPC : Backend ↔ PostgreSQL, Worker ↔ PostgreSQL, Backend ↔ VerneMQ")
blank()

section("2.", "상세 시스템 구성도 (Detailed Architecture)")

L1("서버 측 (Ubuntu 24.04 · systemd)")
L2("Nginx 443/80 — HTTPS reverse proxy + 정적 파일")
L3("/ → frontend 정적 파일")
L3("/api/ → 127.0.0.1:8000 (Backend)")
L3("/auth/ → 127.0.0.1:8080 (Keycloak)")
L2("Application Service 3종")
L3("iot-backend.service : FastAPI :8000 — REST API, 권한 검사, Command publish, Config 생성")
L3("iot-worker.service : Python — MQTT subscribe, telemetry 수신, latest upsert, alarm eval")
L3("iot-scheduler.service : Python — offline 판정, command timeout, partition 정리, report 생성")
L2("Infra Service 3종")
L3("Keycloak :8080 — OIDC/OAuth2, realm: iot-platform, role 7종")
L3("PostgreSQL :5432 — iot_platform DB + keycloak DB (RLS 검토)")
L3("VerneMQ :1883/:8883 — MQTT broker, password→X.509(Phase 7)")
L2("Storage 디렉터리")
L3("/var/lib/iot-platform/firmware/ — OTA 이미지")
L3("/var/lib/iot-platform/gateway-configs/ — desired/reported snapshot")
L3("/var/lib/iot-platform/backups/ — pg_dump 결과")
L3("/var/lib/iot-platform/log-bundles/ — 장비 로그 수집")

L1("Gateway 측 (CM4 Linux + Safety MCU)")
L2("CM4 Linux User Space (/opt/iot-gateway/)")
L3("gateway-agent — 메인 루프, 부팅 흐름")
L3("sensor-service — Modbus/AI/DI polling")
L3("actuator-service — GPIO/Relay 제어")
L3("rule-engine — Local Rule (오프라인에서도 동작)")
L3("mqtt-client — Telemetry/Command/Config publish·subscribe")
L3("local-db (SQLite) — telemetry queue, command log")
L3("ota-agent — 이미지 검증·적용")
L3("health-agent — CPU/MEM/Net heartbeat")
L2("STM32 / NXP Safety MCU")
L3("릴레이/밸브 직접 제어 (low-level)")
L3("Local Interlock — 센서 조건 위반 시 차단")
L3("Watchdog — Linux 행 시 자동 fail-safe")
L3("Fail-safe state 강제 전환")
L3("물리적 비상 정지 입력 처리")
L2("Field I/O — RS-485(Modbus RTU), GPIO Relay, Analog 0-10V/4-20mA, GPS, Digital Input")
blank()

section("3.", "서버 구성 — systemd 서비스 7+종")
table(
    ["서비스", "분류", "역할"],
    [
        ["nginx.service", "필수", "HTTPS reverse proxy, 정적 파일 제공"],
        ["vernemq.service", "필수", "MQTT Broker (Phase 1: 1883 plain, Phase 7: 8883 TLS)"],
        ["postgresql.service", "필수", "관계형 DB · 센서 데이터 · keycloak DB 공유"],
        ["keycloak.service", "필수", "사용자 인증 · OIDC/OAuth2 토큰 발급"],
        ["iot-backend.service", "필수", "REST API · 권한 검사 · Gateway 관리 · 명령 발행"],
        ["iot-worker.service", "필수", "MQTT subscribe · telemetry ingestion · alarm eval"],
        ["iot-scheduler.service", "필수", "offline 판단 · timeout 처리 · 백업 · OTA 상태 확인"],
        ["prometheus.service", "선택", "내부 metric 수집 (Phase 7+)"],
        ["opensearch.service", "선택", "로그 검색 (필요 시)"],
    ],
    col_widths_pct=[25, 12, 63],
)
note("모든 서비스는 EnvironmentFile=/etc/iot-platform/{name}.env 로 환경 변수 분리. Restart=always · After=network.target.")
blank()

section("4.", "권장 서버 디렉터리 구조")

L1("/opt/iot-platform/ — 애플리케이션 설치")
L2("backend/ : app/, venv/, migrations/, scripts/")
L2("worker/  : app/, venv/")
L2("scheduler/ : app/, venv/")
L2("frontend/ : current/, releases/")
L2("releases/ : backend-1.0.0/ … backend-1.0.x/")
L2("current → releases/backend-1.0.x (atomic switch via symlink)")

L1("/etc/iot-platform/ — 환경 변수 분리")
L2("backend.env (DATABASE_URL, KC_ISSUER, …)")
L2("worker.env (MQTT_HOST, MQTT_USER, …)")
L2("scheduler.env, mqtt.env, db.env, keycloak.env")

L1("/var/lib/iot-platform/ — 운영 데이터")
L2("firmware/ (OTA 이미지)")
L2("gateway-configs/ (desired/reported snapshots)")
L2("reports/ (정기 통계 리포트)")
L2("log-bundles/ (Gateway 진단 로그)")
L2("backups/ (pg_dump · realm export)")

L1("/var/log/iot-platform/ — 로그")
L2("backend.log, worker.log, scheduler.log, mqtt-ingestion.log")
blank()

section("5.", "Backend / Worker / Scheduler 역할 분담")

L1("Backend API")
L2("성격 : REST · 동기 요청 처리")
L2("주요 책임")
L3("사용자 인증 연동 (Keycloak JWT 검증)")
L3("User · Company · Site · Gateway 권한 검사")
L3("Gateway 등록 / Profile / Channel 관리")
L3("Gateway Config 생성 · 버전 관리")
L3("MQTT command publish (request 발행)")
L3("Telemetry 조회 API · latest 조회")
L3("Alarm Rule 관리 · Audit Log")

L1("Worker")
L2("성격 : MQTT subscribe · 비동기 이벤트 처리")
L2("주요 책임")
L3("MQTT subscribe (gw/+/telemetry, state, …)")
L3("Telemetry message 검증 (schema · timestamp)")
L3("Telemetry 저장 (월별 partition table)")
L3("telemetry_latest UPSERT")
L3("Heartbeat / state 처리")
L3("Command response 처리")
L3("Reported_config 처리 · Alarm evaluation")

L1("Scheduler")
L2("성격 : 주기 작업 · cron 대체")
L2("주요 책임")
L3("Gateway offline 판단 (heartbeat timeout)")
L3("미응답 command timeout 처리")
L3("오래된 telemetry partition drop")
L3("백업 실행 (pg_dump · realm export)")
L3("OTA job 상태 확인 · 재시도")
L3("알람 재전송")
L3("통계 / 리포트 생성")
blank()

# ---- Ⅳ. 사용자 및 권한 모델 ----
chapter("Ⅳ. 사용자 및 권한 모델")

section("1.", "권한 계층 (Top-Down)")
L1("System Admin — 시스템 전체 설정 · 모든 회사·Gateway 관리")
L1("Management Company Admin — 모든 고객사·전체 Gateway 관제·유지보수")
L1("Customer Company Admin — 본인 회사 사용자·현장·Gateway 관리")
L1("Site Manager — 특정 현장 Gateway 관리")
L1("Operator — 허용된 Gateway의 제어 채널 조작")
L1("Viewer — 센서 데이터·상태 조회만 가능")
L1("Maintenance Engineer (별도 축) — 진단·로그 수집·OTA·재부팅")
blank()

section("2.", "권한 테이블 3축")
table(
    ["테이블", "조합 키"],
    [
        ["user_company_roles", "user × company × role"],
        ["user_site_permissions", "user × site × permission"],
        ["user_gateway_permissions", "user × gateway × permission"],
    ],
    col_widths_pct=[35, 65],
)
L1("권한 종류 (permission)")
L2("view — 조회만 가능")
L2("control — 액추에이터 제어 가능")
L2("configure — 설정 변경 가능")
L2("maintain — 유지보수·OTA·재부팅")
L2("admin — 모든 권한 + 권한 위임")
blank()

section("3.", "Keycloak 구성")
L1("Realm : iot-platform")
L1("DB Backend : PostgreSQL 공유 인스턴스 안 별도 db (db=keycloak)")
L1("Groups (Company 매핑)")
L2("management-company")
L2("customer-company-a / customer-company-b / customer-company-c …")
L1("Roles (7종, Phase 1에서 모두 생성)")
L2("system_admin · management_admin · company_admin · site_manager · operator · viewer · maintenance_engineer")
blank()

section("4.", "Keycloak ↔ Backend 책임 분리")
L1("Keycloak 책임")
L2("사용자 인증, 비밀번호 정책, OTP/2FA, 비밀번호 reset")
L2("OIDC/OAuth2 토큰 발급, role claim 제공")
L1("Backend 책임")
L2("company_id · site_id · gateway_id 기반 실 접근 권한 판단")
L2("Keycloak claim만 신뢰하지 않고 DB 권한 매핑으로 최종 검증")
L1("토큰 검증 흐름")
L2("React → Keycloak OIDC 로그인 → Bearer token → /api/* 요청")
L2("Backend가 JWT 검증 → DB 권한 매핑 → 응답")
blank()

# ---- Ⅴ. 데이터 모델 (PostgreSQL) ----
chapter("Ⅴ. 데이터 모델 (PostgreSQL)")

section("1.", "핵심 ERD 요약")
L1("Identity / Auth : users, user_company_roles, user_site_permissions, user_gateway_permissions")
L1("Asset 계층 : companies → sites → gateways")
L1("Profile : gateway_profiles, sensor_profiles, actuator_profiles")
L1("Channel (인스턴스) : sensor_channels, actuator_channels (gateways에 종속)")
L1("Telemetry : telemetry (월별 partition), telemetry_latest")
L1("Config : gateway_configs, gateway_config_history")
L1("Operations : commands, alarm_rules, audit_logs, bulk_jobs")
blank()

section("2.", "핵심 테이블 DDL (Phase 2 우선)")

L1("companies")
code_block("""CREATE TABLE companies (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    company_type TEXT NOT NULL,      -- 'management' | 'customer'
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);""")

L1("sites")
code_block("""CREATE TABLE sites (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    address TEXT,
    latitude  DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now()
);""")

L1("users")
code_block("""CREATE TABLE users (
    id UUID PRIMARY KEY,
    keycloak_user_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);""")

L1("gateways")
code_block("""CREATE TABLE gateways (
    id UUID PRIMARY KEY,
    serial_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id),
    site_id UUID REFERENCES sites(id),
    gateway_profile_id UUID REFERENCES gateway_profiles(id),
    status TEXT NOT NULL DEFAULT 'offline',
    firmware_version TEXT,
    app_version TEXT,
    config_version INTEGER DEFAULT 0,
    last_seen_at TIMESTAMPTZ,
    registered_at TIMESTAMPTZ DEFAULT now()
);""")

L1("user_gateway_permissions")
code_block("""CREATE TABLE user_gateway_permissions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    gateway_id UUID NOT NULL,
    permission TEXT NOT NULL,
        -- view | control | configure | maintain | admin
    UNIQUE(user_id, gateway_id, permission)
);""")
blank()

section("3.", "Sensor Profile / Sensor Channel 분리")

L1("sensor_profiles : 센서 모델 정의 (재사용)")
L2("벤더 / 모델 / 통신 프로토콜 / interface_type")
L2("측정 항목 (key, display_name, unit, data_type)")
L2("scale / offset / min / max / quality")
L2("register map (Modbus function_code, register, length)")
L2("default_polling_interval_sec")
L2("visualization (line_chart / gauge / map)")

L1("예시 : RS485 Temperature Humidity Sensor")
code_block("""{
  "name": "RS485 Temperature Humidity Sensor",
  "vendor": "Generic", "model": "TH-RS485-01",
  "protocol": "modbus_rtu", "interface_type": "rs485",
  "default_polling_interval_sec": 10,
  "measurements": [
    {"key": "temperature", "unit": "degC",
     "modbus": {"function_code": 3, "register": 0, "length": 1},
     "scale": 0.1, "visualization": "line_chart"},
    {"key": "humidity", "unit": "%",
     "modbus": {"function_code": 3, "register": 1, "length": 1},
     "scale": 0.1, "visualization": "line_chart"}
  ]
}""")

L1("sensor_channels : Gateway에 실제 연결된 인스턴스")
L2("어떤 Gateway에 (gateway_id)")
L2("어떤 Sensor Profile을 (sensor_profile_id)")
L2("어떤 인터페이스/포트로 (interface_name)")
L2("Modbus slave_id / address")
L2("polling_interval_sec / enabled / display_name")
L2("override 가능한 config JSONB")

L1("예시 : GW-000001의 1번 RS-485에 슬레이브 1로 연결")
code_block("""{
  "gateway_id":         "GW-000001",
  "sensor_channel_id":  "sensor-01",
  "sensor_profile_id":  "profile-rs485-temp-humi-001",
  "display_name":       "1번 온습도 센서",
  "interface":          "rs485_1",
  "protocol":           "modbus_rtu",
  "slave_id":           1,
  "polling_interval_sec": 10,
  "enabled":            true
}""")
blank()

section("4.", "Telemetry 저장 모델")

L1("저장 전략")
L2("센서마다 컬럼이 다르므로 measurement_key + value_* 다중 컬럼 패턴")
L2("월별 partition으로 retention 정책 (drop partition으로 빠른 정리)")
L2("대시보드는 telemetry_latest 단일 테이블 → O(1) 조회")
L2("Worker에서 INSERT + UPSERT 동시 수행")

L1("DDL")
code_block("""CREATE TABLE telemetry (
    id BIGSERIAL,
    company_id UUID NOT NULL,
    site_id UUID,
    gateway_id UUID NOT NULL REFERENCES gateways(id),
    sensor_channel_id UUID NOT NULL REFERENCES sensor_channels(id),
    measurement_key TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    value_double DOUBLE PRECISION,
    value_text TEXT, value_bool BOOLEAN, value_json JSONB,
    unit TEXT, quality TEXT, raw JSONB,
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

CREATE TABLE telemetry_2026_05 PARTITION OF telemetry
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE telemetry_latest (
    gateway_id UUID, sensor_channel_id UUID,
    measurement_key TEXT, ts TIMESTAMPTZ,
    value_double DOUBLE PRECISION,
    value_text TEXT, value_bool BOOLEAN, value_json JSONB,
    unit TEXT, quality TEXT,
    PRIMARY KEY (gateway_id, sensor_channel_id, measurement_key)
);""")

L1("예시 데이터")
table(
    ["gateway_id", "sensor_channel_id", "measurement_key", "value_double", "unit"],
    [
        ["GW-001", "sensor-01", "temperature", "24.7", "degC"],
        ["GW-001", "sensor-01", "humidity",    "61.2", "%"],
        ["GW-002", "sensor-02", "tilt_x",       "3.2", "deg"],
    ],
    col_widths_pct=[18, 24, 25, 18, 15],
)
note("향후 TimescaleDB Community 기능 검토 가능. 단 Timescale License 혼재 주의.")
blank()

section("5.", "Gateway Config 버전 관리")

L1("처리 흐름 (6단계)")
L2("1) Web Portal에서 관리자 변경 → 2) Backend DB에 config 저장")
L2("3) Config Generator가 version + hash 생성")
L2("4) MQTT publish gw/{id}/config/desired → 5) Gateway 설정 적용")
L2("6) MQTT report gw/{id}/config/reported (적용 결과 보고)")

L1("DDL")
code_block("""CREATE TABLE gateway_configs (
    id UUID PRIMARY KEY,
    gateway_id UUID NOT NULL REFERENCES gateways(id),
    config_version INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    desired_config JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    applied_at TIMESTAMPTZ,
    UNIQUE(gateway_id, config_version)
);

CREATE TABLE gateway_config_history (
    id UUID PRIMARY KEY,
    gateway_id UUID NOT NULL REFERENCES gateways(id),
    config_version INTEGER NOT NULL,
    config_snapshot JSONB NOT NULL,
    change_reason TEXT,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMPTZ DEFAULT now()
);""")

L1("desired_config 예시 (서버)")
code_block("""{
  "gateway_id": "GW-000001",
  "config_version": 12,
  "config_hash": "a83f2e9d",
  "interfaces": [...],
  "sensors":    [...],
  "actuators":  [...],
  "rules":      [...]
}""")

L1("reported_config 예시 (Gateway)")
code_block("""{
  "gateway_id": "GW-000001",
  "applied_config_version": 12,
  "config_hash": "a83f2e9d",
  "status": "applied",
  "applied_at": "2026-05-02T12:00:00Z",
  "errors": []
}""")
blank()

# ---- Ⅵ. 통신 설계 (MQTT) ----
chapter("Ⅵ. 통신 설계 (MQTT)")

section("1.", "Topic 설계 원칙")
L1("비권장 (사용자 기준)")
L2("user/{userId}/gateway/{gatewayId}/telemetry → 사용자 변경/이전 시 topic 재구성 필요, ACL 복잡")
L1("권장 (Gateway 기준)")
L2("gw/{gatewayId}/telemetry → Gateway 단일 식별자 기준, ACL 단순, 사용자 매핑은 Backend DB")
blank()

section("2.", "Topic 권한 (publish / subscribe)")

L1("Gateway → Server (publish 권한)")
table(
    ["Topic", "용도"],
    [
        ["gw/{id}/telemetry",        "센서 측정값"],
        ["gw/{id}/state",            "전체 상태 (cpu·mem·net)"],
        ["gw/{id}/heartbeat",        "주기 alive 신호"],
        ["gw/{id}/event",            "에러·경보·이벤트"],
        ["gw/{id}/config/reported",  "현재 적용된 config"],
        ["gw/{id}/command/response", "명령 실행 결과"],
        ["gw/{id}/ota/status",       "OTA 진행 상황"],
    ],
    col_widths_pct=[40, 60],
)

L1("Server → Gateway (subscribe 권한)")
table(
    ["Topic", "용도"],
    [
        ["gw/{id}/config/desired",   "서버가 발행하는 설정"],
        ["gw/{id}/command/request",  "원격 제어 명령"],
        ["gw/{id}/ota/request",      "OTA 작업 지시"],
    ],
    col_widths_pct=[40, 60],
)

L1("VerneMQ ACL 정책 (Phase 7)")
L2("Gateway 계정은 자기 gw/{own_id}/* 만 publish/subscribe 가능")
L2("Backend 계정은 모든 topic publish/subscribe 가능")
L2("Phase 1 : password file (gateway / admin 계정 1개씩)")
L2("Phase 7 : X.509 client cert + serial → topic ACL 매핑")
blank()

section("3.", "Payload 예시")

L1("Telemetry Payload (gw/{id}/telemetry)")
code_block("""{
  "message_id": "msg-20260502-000001",
  "gateway_id": "GW-000001",
  "timestamp":  "2026-05-02T12:00:00Z",
  "values": [
    {
      "sensor_channel_id": "sensor-01",
      "measurement_key": "temperature",
      "value": 24.7, "unit": "degC", "quality": "good"
    },
    {
      "sensor_channel_id": "sensor-01",
      "measurement_key": "humidity",
      "value": 61.2, "unit": "%", "quality": "good"
    }
  ]
}""")

L1("Gateway State Payload (gw/{id}/state)")
code_block("""{
  "gateway_id": "GW-000001",
  "timestamp":  "2026-05-02T12:00:00Z",
  "status":     "online",
  "app_version":      "1.0.3",
  "firmware_version": "2026.05.02",
  "config_version":   12,
  "uptime_sec":       82344,
  "cpu_temp":         51.3,
  "memory_usage_percent": 38.7,
  "disk_usage_percent":   42.1,
  "network": {
    "ethernet": true,
    "ip":       "192.168.0.25",
    "rtt_ms":   34
  }
}""")
note("공통 envelope : message_id (idempotency) + gateway_id + timestamp(UTC ISO8601). 모든 메시지 QoS 1 권장.")
blank()

section("4.", "원격 제어 명령 흐름 (11 step)")
L1("1) User → Backend API : 릴레이 ON 요청 (POST /api/.../commands)")
L1("2) Backend → Backend : 사용자 권한 검사 (User × Gateway)")
L1("3) Backend → PostgreSQL : command 생성 (status=pending)")
L1("4) Backend → VerneMQ : MQTT publish gw/{id}/command/request")
L1("5) VerneMQ → Gateway : 명령 전달")
L1("6) Gateway → Gateway : Local Safety Rule 체크 (interlock, max_on)")
L1("7) Gateway → Relay/Valve : GPIO 제어")
L1("8) Relay/Valve → Gateway : 실행 결과 피드백")
L1("9) Gateway → VerneMQ : MQTT publish gw/{id}/command/response")
L1("10) Worker → PostgreSQL : 응답 수신, command status 업데이트")
L1("11) Backend → User : 결과 표시 (executed / failed / timeout)")
blank()

# ---- Ⅶ. 안전 및 자동화 ----
chapter("Ⅶ. 안전 및 자동화")

section("1.", "명령 안전 조건 (8가지)")
table(
    ["조건", "설명"],
    [
        ["command_id",          "중복 실행 방지 (idempotency key)"],
        ["expires_at",          "오래된 명령 자동 폐기"],
        ["timeout_ms",          "지연 명령 실패 처리"],
        ["require_ack",         "실행 결과 필수 확인"],
        ["local_safety_check",  "현장 조건 위반 시 거부"],
        ["audit_log",           "사용자·시간·대상·결과 보관"],
        ["fail_safe",           "장애 시 안전 상태로 전환"],
        ["manual_override",     "현장 수동 제어 우선"],
    ],
    col_widths_pct=[25, 75],
)
blank()

section("2.", "Alarm Rule 설계")
L1("alarm_rules 테이블")
code_block("""CREATE TABLE alarm_rules (
    id UUID PRIMARY KEY,
    gateway_id UUID NOT NULL REFERENCES gateways(id),
    sensor_channel_id UUID NOT NULL REFERENCES sensor_channels(id),
    measurement_key TEXT NOT NULL,
    condition TEXT NOT NULL,         -- '>', '<', '=', ...
    threshold DOUBLE PRECISION,
    duration_sec INTEGER DEFAULT 0,
    severity TEXT NOT NULL,          -- info | warning | critical
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);""")

L1("Alarm Rule 예시")
code_block("""{
  "gateway_id":  "GW-000001",
  "sensor_channel_id": "sensor-01",
  "measurement_key": "temperature",
  "condition": ">", "threshold": 35.0,
  "duration_sec": 60,
  "severity": "warning",
  "action": "notify"
}""")
blank()

section("3.", "자동 제어 Rule (서버 + Gateway 양쪽 배포)")
L1("배포 이유")
L2("통신 장애 시에도 동작해야 하므로 Gateway 로컬 Rule Engine에 함께 배포")
L1("자동 제어 Rule 예시")
code_block("""{
  "rule_id": "control-rule-001",
  "if": {
    "sensor_channel_id": "sensor-02",
    "measurement_key": "water_level",
    "condition": "<", "threshold": 20
  },
  "then": {
    "actuator_channel_id": "relay-01",
    "action": "ON"
  },
  "safety": { "max_on_duration_sec": 300 }
}""")
blank()

# ---- Ⅷ. Web Portal ----
chapter("Ⅷ. Web Portal")

section("1.", "권한별 화면 구성")
L1("일반 사용자 화면")
L2("내 Gateway 목록")
L3("이름 / 설치 위치")
L3("Online·Offline 상태")
L3("알람 상태")
L3("주요 센서 최신값")
L3("제어 가능 액추에이터")
L3("최근 이벤트")

L1("Gateway 상세 화면")
L2("기본 정보 / 네트워크 상태")
L2("센서 채널 목록")
L2("최신 센서값 (telemetry_latest)")
L2("시계열 그래프 (Apache ECharts)")
L2("제어 채널 (Toggle / Slider)")
L2("알람 이력 / 명령 이력")
L2("설정 버전 / 유지보수 로그")

L1("관리자 화면")
L2("사용자 · 고객사 · 현장 관리")
L2("Gateway 등록 / 소유권 할당")
L2("Gateway Profile 관리")
L2("Sensor Profile 관리")
L2("Sensor / Actuator Channel 설정")
L2("Gateway Template 관리")
L2("Bulk Operation / OTA")
L2("Audit Log 조회")
blank()

section("2.", "Sensor 추가 Wizard (8단계)")
table(
    ["단계", "이름", "설명"],
    [
        ["1", "Gateway 선택", "어떤 장비에 추가하나"],
        ["2", "인터페이스 선택", "RS-485 #1/2 · AI · DI · I2C · UART"],
        ["3", "Sensor Profile 선택", "온습도 · 미세먼지 · 기울기 · 수위 · pH ..."],
        ["4", "통신 설정", "Modbus slave_id · baudrate · parity"],
        ["5", "측정 주기", "polling_interval_sec"],
        ["6", "표시 이름", "사용자에게 보여줄 이름"],
        ["7", "저장", "sensor_channels 테이블에 INSERT"],
        ["8", "Config 배포", "config_version + 1, MQTT desired publish"],
    ],
    col_widths_pct=[8, 22, 70],
)
blank()

section("3.", "동적 Dashboard 자동 생성")
L1("측정 키 → Widget 매핑")
table(
    ["measurement_key", "Widget"],
    [
        ["temperature",     "Line Chart + Current Value Card"],
        ["humidity",        "Line Chart + Gauge"],
        ["pressure",        "Line Chart"],
        ["pm2_5",           "Gauge + Line Chart"],
        ["tilt_x, tilt_y",  "2-axis Tilt View + Line"],
        ["water_level",     "Gauge"],
        ["relay_state",     "Toggle + Status Card"],
        ["valve_state",     "Toggle + Status Card"],
        ["gps",             "Map"],
    ],
    col_widths_pct=[35, 65],
)
L1("Sensor Profile의 visualization 설정 예")
code_block("""{
  "key": "temperature",
  "display_name": "Temperature",
  "unit": "degC",
  "visualization": "line_chart",
  "display_group": "environment",
  "order": 1
}""")
L1("효과")
L2("새 센서 추가 시 frontend 수정 0줄")
L2("Gateway별 다른 대시보드 자동 생성")
L2("사용자별 widget 순서 커스텀 가능")
blank()

section("4.", "Bulk Operation")
L1("지원 작업 (8종)")
L2("Gateway 일괄 현장 배정 — company/site 매핑 변경")
L2("사용자 권한 일괄 부여 — 특정 group → 다수 Gateway")
L2("센서 polling 일괄 변경 — sensor_channels.polling_interval_sec")
L2("알람 기준 일괄 변경 — alarm_rules.threshold")
L2("OTA 일괄 업데이트 — 타겟 필터 + 점진 배포")
L2("Gateway 일괄 재시작 — command publish (reboot)")
L2("설정 일괄 배포 — Template 기반 desired_config 발행")
L2("로그 일괄 수집 — log/upload topic 트리거")

L1("bulk_jobs 테이블")
code_block("""CREATE TABLE bulk_jobs (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,
    target_filter JSONB NOT NULL,    -- {"company_id": "...", "site_id": "...", "tags": [...]}
    payload JSONB NOT NULL,          -- 작업별 파라미터
    status TEXT NOT NULL DEFAULT 'pending',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);""")
blank()

# ---- Ⅸ. Gateway Agent ----
chapter("Ⅸ. Gateway Agent")

section("1.", "내부 구성 (/opt/iot-gateway/)")
L1("gateway-agent — 메인 루프")
L1("sensor-service — Modbus / AI / DI polling")
L1("actuator-service — GPIO / Relay 제어")
L1("rule-engine — Local Rule (오프라인 가용)")
L1("mqtt-client — TLS pub/sub")
L1("local-db — SQLite (queue·log)")
L1("ota-agent — 이미지 검증·적용")
L1("health-agent — heartbeat 송신")
L1("config/ — 설정 파일")
L1("logs/ — 회전 로그")
blank()

section("2.", "부팅 흐름 (14단계)")
L1("01. Gateway ID 확인")
L1("02. 인증서·설정 파일 확인")
L1("03. 네트워크 확인")
L1("04. MQTT Broker 연결")
L1("05. 현재 config_version 보고")
L1("06. 서버 desired_config 확인")
L1("07. 버전이 다르면 다운로드")
L1("08. 설정 유효성 검사")
L1("09. Sensor driver 구성")
L1("10. Actuator driver 구성")
L1("11. Rule engine 구성")
L1("12. reported_config 전송")
L1("13. 센서 polling 시작")
L1("14. 주기 heartbeat 전송")
blank()

section("3.", "Local Buffer 정책 (SQLite)")
table(
    ["항목", "정책"],
    [
        ["저장 대상",   "telemetry · event · command response"],
        ["재전송 순서", "timestamp 오름차순"],
        ["중복 방지",   "message_id 기반"],
        ["보존 기간",   "7~30일 (정책 가능)"],
        ["저장공간 초과", "오래된 telemetry부터 삭제"],
        ["우선순위",   "event > command_response > telemetry"],
    ],
    col_widths_pct=[25, 75],
)
blank()

section("4.", "Safety MCU 설계 (CM4 + STM32 이중 구조)")
L1("CM4 Linux 책임")
L2("클라우드 통신 (MQTT TLS)")
L2("데이터 저장 (SQLite local buffer)")
L2("고수준 명령 처리 / Rule engine")
L2("OTA / 진단 / 로그 수집")

L1("STM32 / NXP Safety MCU 책임")
L2("릴레이 / 밸브 직접 제어 (low-level)")
L2("Local Interlock — 센서 조건 위반 시 차단")
L2("Watchdog — Linux 행 시 자동 fail-safe")
L2("Fail-safe state 강제 전환")
L2("물리적 비상 정지 입력 처리")

L1("필수 안전 기능 8가지")
table(
    ["기능", "설명"],
    [
        ["Fail-safe state",  "장애 시 릴레이/밸브 기본 안전 상태"],
        ["Max ON duration",  "릴레이가 너무 오래 켜지지 않도록 제한"],
        ["Command expiry",   "오래된 명령 실행 금지"],
        ["Manual override",  "현장 수동 제어 우선"],
        ["Interlock",        "센서 조건 위반 시 제어 차단"],
        ["Watchdog",         "프로세스 / OS 장애 감지"],
        ["Output feedback",  "실제 릴레이 상태 피드백"],
        ["Emergency stop",   "물리적 비상 정지"],
    ],
    col_widths_pct=[25, 75],
)
note("Safety MCU는 Phase 4-7에 점진 도입. Phase 1-3는 CM4 단독.")
blank()

# ---- Ⅹ. API 설계 (요약) ----
chapter("Ⅹ. API 설계 (요약)")

section("1.", "Gateway API")
code_block("""POST   /api/gateways
GET    /api/gateways
GET    /api/gateways/{id}
PATCH  /api/gateways/{id}
DELETE /api/gateways/{id}
GET    /api/gateways/{id}/state
GET    /api/gateways/{id}/telemetry
GET    /api/gateways/{id}/latest
GET    /api/gateways/{id}/events""")
blank()

section("2.", "Sensor API")
code_block("""POST   /api/sensor-profiles
GET    /api/sensor-profiles
PATCH  /api/sensor-profiles/{id}
POST   /api/gateways/{id}/sensor-channels
GET    /api/gateways/{id}/sensor-channels
PATCH  /api/sensor-channels/{id}
DELETE /api/sensor-channels/{id}""")
blank()

section("3.", "Actuator + Command API")
code_block("""POST   /api/actuator-profiles
GET    /api/actuator-profiles
POST   /api/gateways/{id}/actuator-channels
GET    /api/gateways/{id}/actuator-channels
PATCH  /api/actuator-channels/{id}
POST   /api/gateways/{id}/commands
GET    /api/commands/{cmd_id}""")
blank()

section("4.", "Config + Admin API")
code_block("""POST   /api/gateways/{id}/configs/generate
GET    /api/gateways/{id}/configs
GET    /api/gateways/{id}/configs/latest
POST   /api/gateways/{id}/configs/{ver}/deploy
POST   /api/gateways/{id}/configs/{ver}/rollback
POST   /api/companies   /api/sites
POST   /api/users/{id}/gateway-permissions
GET    /api/audit-logs   /api/bulk-jobs""")
blank()

# ---- Ⅺ. 보안 설계 ----
chapter("Ⅺ. 보안 설계")

section("1.", "장비 (Gateway) 보안")
table(
    ["항목", "정책"],
    [
        ["MQTT",          "TLS 필수 (Phase 7)"],
        ["Gateway 인증",  "Phase 1: ID/Password · Phase 7: X.509 인증서"],
        ["Topic ACL",     "Gateway는 자기 topic만 접근 가능"],
        ["Private Key",   "TPM / Secure Element 권장"],
        ["SSH",           "기본 비활성화"],
        ["OTA",           "서명 검증 필수"],
        ["Local Config",  "config_hash 검증"],
        ["로그",          "제어 명령·설정 변경·오류 이력 보관"],
    ],
    col_widths_pct=[25, 75],
)
blank()

section("2.", "서버 보안")
table(
    ["항목", "정책"],
    [
        ["인증",    "Keycloak OIDC / OAuth2"],
        ["API",     "JWT 검증 (Backend)"],
        ["권한",    "RBAC + ABAC"],
        ["DB 필터", "company_id · site_id · gateway_id 기반"],
        ["RLS",     "주요 테이블에 PostgreSQL Row Level Security 적용 검토"],
        ["TLS",     "Web · API · MQTT 전 구간"],
        ["Audit",   "사용자 명령 · 설정 변경 · 관리자 작업 기록"],
        ["Backup",  "정기 백업 + 복구 테스트"],
    ],
    col_widths_pct=[25, 75],
)
blank()

section("3.", "PostgreSQL Row Level Security 검토")
L1("적용 대상 테이블 (7종)")
L2("gateways, sensor_channels, actuator_channels")
L2("telemetry, telemetry_latest")
L2("commands, audit_logs")

L1("정책 예시")
code_block("""ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;

CREATE POLICY gateway_access_policy ON gateways
USING (
    id IN (
        SELECT gateway_id
          FROM user_gateway_permissions
         WHERE user_id = current_setting('app.current_user_id')::uuid
    )
);""")

L1("도입 시 고려사항")
L2("Backend connection pool에서 SET app.current_user_id 호출")
L2("service role 우회 정책 정의 필요 (worker, scheduler)")
L2("관리자 권한은 BYPASSRLS 별도 role")
L2("batch / migration 작업 시 일시 비활성화 고려")

L1("결론")
L2("Phase 1-5 동안은 application 레이어에서 권한 enforce")
L2("DB row-level 격리는 다중 테넌트가 본격화되는 Phase 6+에 도입")
blank()

# ---- Ⅻ. 운영 관리 ----
chapter("Ⅻ. 운영 관리")

section("1.", "백업 정책")
table(
    ["대상", "주기", "방식"],
    [
        ["PostgreSQL",     "매일",    "pg_dump / pg_basebackup"],
        ["Gateway Config", "매일",    "파일 / DB 백업"],
        ["펌웨어",         "변경 시", "rsync"],
        ["로그",           "정책 기반","압축 / 보관"],
        ["Keycloak realm", "변경 시", "kc.sh export"],
    ],
    col_widths_pct=[25, 20, 55],
)
blank()

section("2.", "모니터링 지표")
table(
    ["대상", "지표"],
    [
        ["Gateway",  "online · heartbeat · CPU · mem · disk · temperature"],
        ["VerneMQ",  "connected clients · message rate · dropped"],
        ["Backend",  "API latency · error rate"],
        ["DB",       "connections · slow query · disk usage"],
        ["Command",  "success · timeout · rejected rate"],
        ["Config",   "pending · applied · failed"],
        ["OTA",      "success · failed · rollback"],
    ],
    col_widths_pct=[20, 80],
)
blank()

section("3.", "장애 대응")
table(
    ["장애", "대응"],
    [
        ["Gateway offline",  "알람 발생 + 마지막 상태 표시"],
        ["센서 미수신",      "sensor_channel 상태 = degraded"],
        ["명령 timeout",     "command failed 처리"],
        ["config 적용 실패", "이전 config 유지 + 관리자 알림"],
        ["DB 용량 증가",     "partition retention 적용"],
        ["서버 장애",        "백업 복구 절차 실행"],
    ],
    col_widths_pct=[30, 70],
)
blank()

# ---- ⅩⅢ. 개발 로드맵 ----
chapter("ⅩⅢ. 개발 로드맵")

section("1.", "7단계 로드맵")
table(
    ["단계", "이름", "기간", "핵심 산출물"],
    [
        ["Phase 1", "서버 기본 구축",                   "1주",  "systemd 5종 · Keycloak realm · 코드 0줄"],
        ["Phase 2", "다중 Gateway 권한 모델",            "TBD", "companies/sites/users/gateways · Backend skeleton"],
        ["Phase 3", "Sensor Profile / Channel",          "TBD", "Sensor Wizard · Telemetry · 동적 Dashboard"],
        ["Phase 4", "Actuator + 원격 제어",              "TBD", "command 흐름 · 안전 조건 · 권한 분리"],
        ["Phase 5", "Gateway Config Versioning",         "TBD", "desired/reported · rollback"],
        ["Phase 6", "관리 편의성 (Template/Bulk/Alarm)", "TBD", "Template · Bulk · Alarm Rule"],
        ["Phase 7", "제품화",                            "TBD", "X.509 · ACL · OTA · Backup · Safety MCU · OSS Notice"],
    ],
    col_widths_pct=[10, 24, 8, 58],
)
blank()

section("2.", "Phase 1 상세 spec (1주 sprint, 코드 0줄)")

L1("환경")
L2("OS : Ubuntu Server 24.04 LTS")
L2("호스팅 : 사내 물리 머신")
L2("도메인 / SSL : 발급 가능 상태")
L2("패키지 정책 : Ubuntu apt 기본 (PostgreSQL 16) + 공식 릴리스 (Keycloak, VerneMQ)")
L2("팀 : Solo + Claude Code AI Pair")
L2("기간 : 1주 single sprint")
L2("Verification : 체크리스트 + scripts/phase1_smoke.sh")

L1("Scope (포함)")
L2("OS · 보안 hardening (ufw · ssh · iot 사용자)")
L2("PostgreSQL 16 (apt) · iot_platform DB · keycloak DB · iot_user role")
L2("VerneMQ 공식 .deb · systemd · password file 인증 · 1883 plain")
L2("Keycloak 공식 release · systemd · Postgres backend")
L3("realm: iot-platform · 7 roles · test user 1명")
L2("Nginx + certbot Let's Encrypt → HTTPS reverse proxy")
L3("/auth → Keycloak (placeholder /api · /)")
L2("/etc/iot-platform/ · .env 템플릿")
L2("운영 절차서 (markdown)")
L2("scripts/phase1_smoke.sh (자동 점검)")

L1("Non-goals (Phase 2+ 이연)")
L2("모든 application 코드 (FastAPI · React · Worker · Scheduler)")
L2("비즈니스 DB schema (companies · sites · users · gateways · …)")
L2("Gateway 연결 · telemetry · MQTT TLS · X.509")
L2("OTA · Safety MCU · Backup automation · Alarm · Bulk")

L1("Definition of Done")
L2("systemctl is-active → 4개 서비스 active")
L2("https://<도메인>/auth/realms/iot-platform/.well-known/openid-configuration → 200")
L2("Keycloak admin 로그인 성공 (test user)")
L2("mosquitto_pub/sub → password 인증 후 1883 publish/subscribe 성공")
L2("psql -U iot_user -d iot_platform -c \"SELECT 1\" → 성공")
L2("scripts/phase1_smoke.sh → 전체 PASS")
blank()

section("3.", "Phase 1 일정 분해 (Day 1-7)")

L1("Day 1 — OS 베이스 + 보안")
L2("Ubuntu 24.04 LTS 클린 설치")
L2("iot 시스템 사용자 생성 · sudo 정책")
L2("ufw 포트 정책 (22 · 80 · 443 · 1883)")
L2("ssh hardening (key only · port forward 차단)")
L2("/opt/iot-platform · /etc/iot-platform · /var/lib/iot-platform 디렉터리")

L1("Day 2 — PostgreSQL + VerneMQ")
L2("PostgreSQL 16 apt 설치 · 권한 설정")
L2("iot_platform DB + keycloak DB 생성")
L2("iot_user role + 권한 grant")
L2("VerneMQ .deb 설치 · systemd")
L2("vmq_passwd로 gateway/admin 계정 생성")

L1("Day 3 — Keycloak 설치 + realm")
L2("Keycloak release 다운로드 → /opt/iot-platform/keycloak")
L2("Postgres datasource 설정 (KEYCLOAK_DATABASE_*)")
L2("keycloak.service systemd unit 등록")
L2("iot-platform realm 생성")
L2("7 role + test user 1명 생성")

L1("Day 4 — Nginx + HTTPS")
L2("Nginx 설치 · iot-platform.conf 작성")
L2("/auth → 8080 reverse proxy")
L2("/api · / placeholder location 정의")
L2("certbot --nginx 으로 Let's Encrypt 발급")
L2("systemd timer로 인증서 자동 갱신 확인")

L1("Day 5 — 환경 분리 + 절차서")
L2("/etc/iot-platform/{backend,worker,scheduler,mqtt,db,keycloak}.env 템플릿")
L2("운영 절차서 (PHASE1_OPS.md) 작성 — 설치 명령 단계별")
L2("장애 대응 절차 (서비스 재시작 · 로그 위치)")

L1("Day 6 — smoke test 자동화")
L2("scripts/phase1_smoke.sh 작성")
L3("systemctl is-active 4개 확인")
L3("curl /auth/.well-known/openid-configuration")
L3("psql SELECT 1")
L3("mosquitto_pub/sub 인증 테스트")

L1("Day 7 — 검증 + 문서 정리")
L2("smoke test 전체 실행 → PASS 확인")
L2("체크리스트 마크다운 결과 commit")
L2("Phase 2 인터뷰 준비 (남은 트랙: Gateway OS · scale · PoC 산업 등)")
blank()

# ---- ⅩⅣ. 라이선스 및 우선순위 ----
chapter("ⅩⅣ. 라이선스 및 우선순위")

section("1.", "권장 OSS 컴포넌트")
table(
    ["컴포넌트", "라이선스", "판단"],
    [
        ["VerneMQ",         "Apache 2.0",         "권장"],
        ["PostgreSQL",      "PostgreSQL License", "권장"],
        ["Keycloak",        "Apache 2.0",         "권장"],
        ["Apache ECharts",  "Apache 2.0",         "권장"],
        ["Nginx",           "BSD-like",           "권장"],
        ["FastAPI",         "MIT",                "권장"],
        ["React + Vite",    "MIT",                "권장"],
        ["Prometheus",      "Apache 2.0",         "선택 사용 가능"],
        ["OpenSearch",      "Apache 2.0",         "선택 사용 가능"],
    ],
    col_widths_pct=[35, 35, 30],
)
blank()

section("2.", "피하거나 주의할 컴포넌트")
table(
    ["컴포넌트", "사유"],
    [
        ["EMQX 최신 버전",                "BSL 계열 이슈 가능"],
        ["MinIO",                         "AGPLv3"],
        ["Grafana 고객용 노출",           "AGPLv3"],
        ["Loki",                          "AGPL"],
        ["SWUpdate",                      "GPLv2"],
        ["TimescaleDB Community 일부",    "Timescale License 혼재 가능"],
        ["Docker Desktop",                "조직 규모/용도에 따라 구독 이슈"],
    ],
    col_widths_pct=[35, 65],
)
blank()

section("3.", "제품 출시 전 준비물")
L1("OSS Notice — 사용한 오픈소스 목록 + 라이선스 전문")
L1("SBOM — 소프트웨어 자재명세서")
L1("GPL/LGPL 구성요소 소스 제공 절차")
L1("Gateway 이미지 패키지 목록")
L1("수정한 오픈소스 코드 공개 여부 확인")
blank()

section("4.", "최종 구현 우선순위")

L1("최우선 (Phase 1-5 핵심)")
L2("사용자별 다중 Gateway 권한 모델")
L2("Gateway별 Sensor Profile / Channel 구조")
L2("MQTT topic + Gateway 인증 구조")
L2("Telemetry 저장 + latest 조회")
L2("Gateway Config Versioning")
L2("Command Request / Response 구조")

L1("중간 우선순위 (Phase 5-6)")
L2("Sensor 추가 Wizard")
L2("Dynamic Dashboard")
L2("Alarm Rule")
L2("Actuator Channel")
L2("Config Rollback")
L2("Audit Log")

L1("제품화 우선순위 (Phase 7)")
L2("Gateway별 X.509 인증서")
L2("VerneMQ ACL")
L2("OTA")
L2("Backup / Restore 자동화")
L2("Safety MCU 연동")
L2("OSS Notice / SBOM")
blank()

# ---- ⅩⅤ. 결론 및 Next Steps ----
chapter("ⅩⅤ. 결론 및 Next Steps")

section("1.", "최종 결론")
L1("Docker를 사용하지 않더라도 자체 호스팅 IoT Gateway 플랫폼 구축에는 문제가 없다.")
L1("산업용 서버 운영 환경에서는 systemd 기반으로 서비스 단위를 명확히 관리하는 방식이 오히려 안정적이다.")
L1("단, 다음 7가지 조건을 반드시 설계에 반영해야 한다.")
L2("한 사용자가 여러 IoT Gateway를 가질 수 있음")
L2("Gateway마다 연결된 센서 종류가 다를 수 있음")
L2("Gateway마다 릴레이·밸브·펌프 등 제어 구성이 다를 수 있음")
L2("관리회사는 전체 Gateway를 통합 관리해야 함")
L2("일반 사용자는 본인에게 할당된 Gateway만 접근")
L2("센서 종류 추가 시 코드 수정 최소화")
L2("Gateway 설정은 서버에서 중앙 관리하고 버전 관리되어야 함")
blank()

section("2.", "권장 최종 구조")
L1("VerneMQ + PostgreSQL + Keycloak + FastAPI Backend + React (Vite) Web Portal")
L1("systemd 기반 서비스 운영")
L1("Gateway Profile + Sensor Profile + Sensor Channel Mapping")
L1("Actuator Channel Mapping + Gateway Config Versioning")
L1("Dynamic Dashboard + RBAC / ABAC 권한 모델")
L1("CM4 Linux + Safety MCU 이중 구조 (Phase 4-7 도입)")
blank()

section("3.", "즉시 시작 가능한 4가지 (Next Steps)")

L1("01. Phase 1 sprint 시작")
L2("본 자료의 Day 1-7 일정대로 서버 인프라 1주 구축. 코드 0줄.")

L1("02. Phase 1 산출물 commit")
L2("운영 절차서(PHASE1_OPS.md) + scripts/phase1_smoke.sh를 git repo로 형상 관리.")

L1("03. Phase 2 인터뷰 준비")
L2("남은 미결정 트랙 결정 : Gateway OS · v1 운영 규모 · 첫 PoC 산업 · Safety MCU 시점.")

L1("04. Hardware lab 구성")
L2("보유 CM4 Gateway + RS-485 온습도 센서 1개로 Phase 3 telemetry 흐름 실측 가능.")
blank()

# ---- 문서 끝 ----
section("4.", "참고 출처")
L1("VerneMQ : https://github.com/vernemq/vernemq")
L1("PostgreSQL License : https://www.postgresql.org/about/licence/")
L1("PostgreSQL Row Level Security : https://www.postgresql.org/docs/current/ddl-rowsecurity.html")
L1("Keycloak Documentation : https://www.keycloak.org/documentation")
L1("Apache ECharts : https://echarts.apache.org/")
L1("FastAPI : https://fastapi.tiangolo.com/")
blank()
p("— 문서 끝 —", paraId=PARA_CENTER, charId=CHAR_SMALL)

# ============================================================
#                      XML 조립 + 저장
# ============================================================

XML_HEAD = """<?xml version='1.0' encoding='UTF-8'?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf/" xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" xmlns:epub="http://www.idpf.org/2007/ops" xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">
"""
XML_TAIL = "</hs:sec>\n"

with open(OUT_SECTION, "w", encoding="utf-8") as f:
    f.write(XML_HEAD)
    f.write(SEC_FIRST)
    for chunk in paragraphs:
        f.write(chunk)
    f.write(XML_TAIL)

print(f"✅ section0.xml 생성: {OUT_SECTION}")
print(f"   문단 수: {len(paragraphs)} + 1 (secPr 첫 문단)")
