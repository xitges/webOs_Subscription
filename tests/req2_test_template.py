"""
requirement_2.md 검증 스크립트 (TE)

검증 대상
--------
요구사항 #2: 가전 목록 조회 + 사용 현황 + 차트
  - BE : app/api/subscribers.py  (GET /api/subscribers/{user_id}/devices)
         app/api/devices.py      (GET /api/devices/{device_id}/usage)
  - FE : app/static/app.js       (selectSubscriber / renderDevices / selectDevice /
                                  renderUsageChart / 이벤트 바인딩)

실행 방법
--------
    # 프로젝트 루트에서
    python tests/req2_test_template.py
    python tests/req2_test_template.py --skip-regression   # req1 회귀 테스트 생략

결과
----
    tests/reports/req2_report_template.md   (검증 Report)
    모든 자동 테스트가 PASS 이면 종료 코드 0, 하나라도 FAIL 이면 1

필요 패키지: fastapi, uvicorn, jinja2 (requirements.txt 에 이미 포함)
             그 외에는 파이썬 표준 라이브러리만 사용합니다.

────────────────────────────────────────────────────────────────────────
검증 구성
  1) DEV : 개발자 테스트  - 문법, 함수 반환값/예외, app.js 구현/주석 해제 여부(정적 검사)
  2) API : API 테스트     - 서버를 켜고 실제 HTTP 응답/스키마 확인
  3) TE  : TE 시나리오
           TE-1  ~ TE-12 : requirement_2 예시 시나리오
           TE-13 ~ TE-20 : [A] 완료 조건 보완 (검색 기준별 / 상태 필터 4종 / 0건)
           TE-21 ~ TE-26 : [B] 검색·필터 경계 조건
           TE-27 ~ TE-30 : [C] 상태 전환 (정적 검사)
           TE-31 ~ TE-34 : [D] 사용 현황 상세 + Badge
           TE-35 ~ TE-37 : [E] 차트
           TE-38 ~ TE-42 : [F] API·데이터 정합성
           TE-43         : [G] req1 회귀 테스트
  4) MAN : 수동 확인 항목 - 브라우저에서 직접 확인 후 Report 에 결과 기입

판정 값
  True  → PASS
  False → FAIL
  None  → 확인 필요 (명세 미정의 관찰 항목 / 수동 확인 항목, Pass Rate 에서 제외)

주의
  TE 시나리오의 검색/필터는 app.js renderDevices 의 규칙을 파이썬(filter_devices)으로
  재현한 시뮬레이션입니다. app.js 가 실제로 그렇게 동작하는지는 MAN 항목으로 확인하세요.
  TE-43(회귀)은 req1 스크립트를 실행하므로 req1 Report 파일이 새로 덮어써집니다.
────────────────────────────────────────────────────────────────────────
"""

import os
import re
import sys
import time
import json
import socket
import py_compile
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

# Windows 콘솔(cp949)에서도 한글/기호가 깨지지 않도록 출력 인코딩을 UTF-8 로 설정
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# =============================================================================
# 설정
# =============================================================================
AUTHOR = "(여기에 이름을 적으세요)"

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
REPORT_DIR = os.path.join(THIS_DIR, "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "req2_report_template.md")
REQ1_SCRIPT = os.path.join(THIS_DIR, "req1_test_template.py")

SUBSCRIBERS_PY = os.path.join("app", "api", "subscribers.py")
DEVICES_PY = os.path.join("app", "api", "devices.py")
APP_JS = os.path.join("app", "static", "app.js")
STYLE_CSS = os.path.join("app", "static", "style.css")
INDEX_HTML = os.path.join("app", "templates", "index.html")

DEVICE_FIELDS = ["deviceId", "type", "model", "location", "status", "lastSeen"]
VALID_DEVICE_STATUSES = {"Online", "Offline", "Standby", "Error"}
USAGE_FIELDS = ["deviceId", "deviceName", "powerStatus", "lastUsedAt", "totalUsageHours",
                "weeklyUsageCount", "healthStatus", "remark", "weeklyUsageTrend"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# app.js renderDevices 의 검색 대상 필드
DEVICE_SEARCH_FIELDS = ["type", "model", "status", "deviceId", "location"]

os.chdir(PROJECT_ROOT)          # 상대경로(app/static 등)를 위해 루트로 이동
BASE_URL = None                 # 서버 기동 후 채워짐

# 검증 결과를 담는 리스트. 각 항목: (TC ID, 시나리오, 기대결과, 실제결과, 판정, 비고)
results = []


def check(tc_id, scenario, expected, actual, passed, note=""):
    """검증 결과 1건을 기록한다. passed: True / False / None(확인 필요)."""
    results.append((tc_id, scenario, expected, actual, passed, note))
    tag = {True: "PASS", False: "FAIL", None: "CHECK"}[passed]
    print(f"  [{tag:5}] {tc_id:7} {scenario}")


def ox(flag):
    return "O" if flag else "X"


# =============================================================================
# HTTP 유틸
# =============================================================================
def http_get_raw(path, timeout=5):
    """(status_code, body_text) 반환. 4xx/5xx 도 본문을 읽는다. 연결 실패 시 (None, None)."""
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8")
        except Exception:
            return e.code, None
    except Exception:
        return None, None


def http_get(path, timeout=5):
    """(status_code, json_data) 반환. JSON 이 아니거나 실패 시 data 는 None."""
    status, body = http_get_raw(path, timeout)
    if body is None:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, None


def is_404_with_detail(status, body):
    return status == 404 and isinstance(body, dict) and "detail" in body


# =============================================================================
# 검색/필터 로직 (app.js renderDevices 와 동일한 규칙을 파이썬으로 재현)
#   - 검색: type, model, status, deviceId, location 에 대해 대소문자 무시 부분 매칭
#           (검색어 trim 없음 — app.js 와 동일)
#   - 필터: status 가 선택된 값과 정확히 일치 ("" 이면 전체)
#   - 표시: 가전 0개 → "No registered devices" / 필터 결과 0개 → "No devices matched"
# =============================================================================
def filter_devices(devs, search="", status=""):
    s = (search or "").lower()
    out = []
    for d in devs:
        matches_search = any(s in str(d.get(f) if d.get(f) is not None else "").lower()
                             for f in DEVICE_SEARCH_FIELDS)
        matches_status = (not status) or d.get("status") == status
        if matches_search and matches_status:
            out.append(d)
    return out


def device_view(devs, search="", status=""):
    """화면에 보일 결과: 안내 메시지(str) 또는 deviceId 정렬 리스트."""
    if not devs:
        return "No registered devices"
    r = filter_devices(devs, search, status)
    if not r:
        return "No devices matched"
    return sorted(d["deviceId"] for d in r)


def describe_view(view):
    return f'"{view}" 메시지' if isinstance(view, str) else f"{len(view)}개: {view}"


# =============================================================================
# 정적 검사 유틸 (app.js / style.css / index.html)
# =============================================================================
def strip_js_comments(src):
    """/* */ 블록 주석과 // 라인 주석을 제거한다. (http:// 같은 URL 은 보존)"""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?<![:\\])//.*", "", src)


def js_function_body(src, name):
    """function name(...) { ... } 의 본문을 중괄호 매칭으로 추출한다. 없으면 ""."""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(src) and depth:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[m.end():i - 1]


def js_expanded_body(src, name):
    """함수 본문 + 본문에서 호출하는 (app.js 에 정의된) 헬퍼 함수 본문을 1단계 펼쳐 붙인다.
    예) selectSubscriber 가 resetUsageDetail() 로 초기화를 위임해도 검사가 가능하도록."""
    body = js_function_body(src, name)
    defined = set(re.findall(r"function\s+(\w+)\s*\(", src)) - {name}
    called = {fn for fn in defined if re.search(r"\b" + re.escape(fn) + r"\s*\(", body)}
    return body + "\n".join(js_function_body(src, fn) for fn in sorted(called))


def read_text(path, strip_js=False):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    return strip_js_comments(text) if strip_js else text


# =============================================================================
# 서버 기동 유틸
# =============================================================================
def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server(port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if proc.poll() is not None:
            return proc, False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                if r.status == 200:
                    return proc, True
        except Exception:
            time.sleep(0.5)
    return proc, False


def stop_server(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# =============================================================================
# 1) 개발자 테스트 (코드/구현 검증)
# =============================================================================
def call_expect_404(func, arg):
    """func(arg) 가 HTTPException(404) 를 발생시키는지 확인. (passed, actual)"""
    from fastapi import HTTPException
    try:
        ret = func(arg)
    except HTTPException as e:
        return e.status_code == 404, f"HTTPException({e.status_code})"
    except Exception as e:
        return False, f"다른 예외: {type(e).__name__}: {e}"
    return False, f"예외 없음 ({type(ret).__name__} 반환)"


def run_dev_tests():
    """정적 검사 결과 플래그(dict)를 반환한다. TE 시나리오 판정에 재사용."""
    print("\n[1] 개발자 테스트")
    flags = {}

    # DEV-01 : subscribers.py / devices.py 문법 검사
    errors = []
    for path in (SUBSCRIBERS_PY, DEVICES_PY):
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"{os.path.basename(path)}: {e.msg.strip().splitlines()[-1]}")
    check("DEV-01", "subscribers.py / devices.py 문법 검사(py_compile)", "컴파일 오류 없음",
          "컴파일 성공" if not errors else "; ".join(errors), not errors)

    # DEV-02 : get_devices_by_user("U001") 직접 호출
    try:
        from app.api.subscribers import get_devices_by_user
        data = get_devices_by_user("U001")
        ids = sorted(d.get("deviceId") for d in data) if isinstance(data, list) else None
        passed = ids == ["D001", "D002"]
        actual = f"{ids}" if ids is not None else f"{type(data).__name__} 반환"
    except Exception as e:
        get_devices_by_user = None
        passed, actual = False, f"예외: {e}"
    check("DEV-02", 'get_devices_by_user("U001") 직접 호출', "D001, D002 list 반환", actual, passed)

    # DEV-03 : get_devices_by_user("U999") → 404
    if get_devices_by_user:
        passed, actual = call_expect_404(get_devices_by_user, "U999")
    else:
        passed, actual = False, "함수 import 실패"
    check("DEV-03", 'get_devices_by_user("U999") 직접 호출', "HTTPException(404) 발생", actual, passed)

    # DEV-04 : get_device_usage("D001") 직접 호출
    try:
        from app.api.devices import get_device_usage
        data = get_device_usage("D001")
        passed = isinstance(data, dict) and data.get("deviceId") == "D001"
        actual = (f"deviceId={data.get('deviceId')}" if isinstance(data, dict)
                  else f"{type(data).__name__} 반환")
    except Exception as e:
        get_device_usage = None
        passed, actual = False, f"예외: {e}"
    check("DEV-04", 'get_device_usage("D001") 직접 호출', "deviceId=D001 인 dict 반환", actual, passed)

    # DEV-05 : get_device_usage("D999") → 404
    if get_device_usage:
        passed, actual = call_expect_404(get_device_usage, "D999")
    else:
        passed, actual = False, "함수 import 실패"
    check("DEV-05", 'get_device_usage("D999") 직접 호출', "HTTPException(404) 발생", actual, passed)

    js = read_text(APP_JS, strip_js=True)

    # DEV-06 : selectSubscriber()
    body = js_function_body(js, "selectSubscriber")
    ext = js_expanded_body(js, "selectSubscriber")
    c = {
        "deviceId=null": re.search(r"selectedDeviceId\s*=\s*null", body) is not None,
        "renderSubscribers": "renderSubscribers(" in body,
        "usage 초기화": all(k in ext for k in ("usage-empty", "usage-detail", "usage-info")),
        "fetch": re.search(r"fetch\(\s*`/api/subscribers/\$\{[^}]+\}/devices`", body) is not None,
        "currentDevices": re.search(r"currentDevices\s*=", body) is not None,
        "renderDevices": "renderDevices(" in body,
    }
    flags["selectSubscriber"] = all(c.values())
    flags["usage_reset"] = c["usage 초기화"] and (".destroy(" in ext)
    check("DEV-06", "selectSubscriber() 구현 (정적 검사)",
          "선택 갱신 + renderSubscribers + 사용 현황 초기화 + devices fetch + renderDevices",
          ", ".join(f"{k}={ox(v)}" for k, v in c.items()), flags["selectSubscriber"])

    # DEV-07 : renderDevices()
    body = js_function_body(js, "renderDevices")
    c = {
        "filter": ".filter(" in body,
        "검색필드5": all(re.search(r"\b" + f + r"\b", body) for f in DEVICE_SEARCH_FIELDS),
        "No registered": "No registered devices" in body,
        "No matched": "No devices matched" in body,
        "tr": re.search(r"createElement\(\s*[`'\"]tr[`'\"]\s*\)|<tr", body) is not None,
        "selectDevice": "selectDevice(" in body,
    }
    flags["renderDevices"] = all(c.values())
    check("DEV-07", "renderDevices() 구현 (정적 검사)",
          "검색(5개 필드)/필터 + 안내 메시지 2종 + <tr> 렌더링 + 행 클릭 시 selectDevice",
          ", ".join(f"{k}={ox(v)}" for k, v in c.items()), flags["renderDevices"])

    # DEV-08 : selectDevice()
    body = js_function_body(js, "selectDevice")
    ext = js_expanded_body(js, "selectDevice")
    c = {
        "renderDevices": "renderDevices(" in body,
        "fetch": re.search(r"fetch\(\s*`/api/devices/\$\{[^}]+\}/usage`", body) is not None,
        "패널 전환": "usage-empty" in ext and "usage-detail" in ext,
        "상세 필드": all(f in body for f in USAGE_FIELDS[:-1]),
        "renderUsageChart": re.search(r"renderUsageChart\([^)]*weeklyUsageTrend", body) is not None,
    }
    flags["selectDevice"] = all(c.values())
    flags["usage_badges"] = (re.search(r"createBadge\(\s*data\.powerStatus", body) is not None
                             and re.search(r"createBadge\(\s*data\.healthStatus", body) is not None)
    flags["hrs_format"] = re.search(r"totalUsageHours\}?\s*hrs", body) is not None
    check("DEV-08", "selectDevice() 구현 (정적 검사)",
          "renderDevices + usage fetch + 패널 전환 + 상세 필드 렌더링 + renderUsageChart(weeklyUsageTrend)",
          ", ".join(f"{k}={ox(v)}" for k, v in c.items()), flags["selectDevice"])

    # DEV-09 : renderUsageChart()
    body = js_function_body(js, "renderUsageChart")
    days_re = r"\[\s*" + r"\s*,\s*".join(f"[`'\"]{d}[`'\"]" for d in DAYS) + r"\s*\]"
    c = {
        "destroy": ".destroy(" in body,
        "new Chart": "new Chart(" in body,
        "bar": re.search(r"type\s*:\s*[`'\"]bar[`'\"]", body) is not None,
        "Mon~Sun": re.search(days_re, body) is not None,
        "data=trend": re.search(r"data\s*:\s*trend\b", body) is not None,
        "beginAtZero": re.search(r"beginAtZero\s*:\s*true", body) is not None,
        "responsive": re.search(r"responsive\s*:\s*true", body) is not None,
    }
    flags["chart"] = all(c.values())
    flags["chart_destroy"] = c["destroy"]
    flags["chart_labels"] = c["Mon~Sun"]
    flags["chart_zero"] = c["beginAtZero"]
    check("DEV-09", "renderUsageChart() 구현 (정적 검사)",
          "기존 차트 destroy + bar 차트 + Mon~Sun 라벨 + data=trend + responsive/beginAtZero",
          ", ".join(f"{k}={ox(v)}" for k, v in c.items()), flags["chart"])

    # DEV-10 : 이벤트 리스너 주석 해제
    has_input = re.search(r"device-search[`'\"]\s*\)\s*\.addEventListener\(\s*[`'\"]input[`'\"]\s*,\s*renderDevices", js) is not None
    has_change = re.search(r"device-status-filter[`'\"]\s*\)\s*\.addEventListener\(\s*[`'\"]change[`'\"]\s*,\s*renderDevices", js) is not None
    flags["listeners"] = has_input and has_change
    check("DEV-10", "가전 검색/필터 이벤트 리스너 주석 해제",
          "device-search input + device-status-filter change → renderDevices",
          f"input={ox(has_input)}, change={ox(has_change)}", flags["listeners"])

    # 이후 TE 정적 검사에서 재사용
    flags["js"] = js
    return flags


# =============================================================================
# 2) API 테스트 (실행 검증)
# =============================================================================
def run_api_tests():
    print("\n[2] API 테스트")

    # API-01 : 헬스 체크
    status, body = http_get("/health")
    check("API-01", "GET /health 호출", "200 OK", f"status={status}", status == 200,
          json.dumps(body) if body else "")

    # API-02 : U001 가전 목록
    status, body = http_get("/api/subscribers/U001/devices")
    ids = sorted(d.get("deviceId") for d in body if isinstance(d, dict)) if isinstance(body, list) else None
    check("API-02", "GET /api/subscribers/U001/devices 호출", "200 OK + JSON 배열(D001, D002)",
          f"status={status}, ids={ids}", status == 200 and ids == ["D001", "D002"])

    # 전체 구독자의 가전 목록 수집 (이후 테스트에서 사용)
    _, subs = http_get("/api/subscribers")
    subs = [u for u in subs if isinstance(u, dict) and "userId" in u] if isinstance(subs, list) else []
    devices_by_user = {}
    for u in subs:
        st, devs = http_get(f"/api/subscribers/{u['userId']}/devices")
        devices_by_user[u["userId"]] = devs if st == 200 and isinstance(devs, list) else None

    # API-03 : 가전 스키마 (모든 사용자)
    problems = []
    for uid, devs in devices_by_user.items():
        if devs is None:
            problems.append(f"{uid}: 응답 오류")
            continue
        for d in devs:
            if not isinstance(d, dict):
                problems.append(f"{uid}: dict 아님")
                continue
            miss = [f for f in DEVICE_FIELDS if f not in d]
            if miss:
                problems.append(f"{d.get('deviceId', '?')} 누락 {miss}")
            elif d["status"] not in VALID_DEVICE_STATUSES:
                problems.append(f"{d['deviceId']}.status={d['status']!r}")
    passed = bool(devices_by_user) and not problems
    check("API-03", "가전 항목 스키마 검증 (전체 구독자)",
          f"필드 {', '.join(DEVICE_FIELDS)} + status ∈ Online/Offline/Standby/Error",
          "정상" if passed else ("; ".join(problems) if problems else "구독자 데이터 없음"), passed)

    # API-04 : 가전 없는 사용자
    status, body = http_get("/api/subscribers/U005/devices")
    check("API-04", "GET /api/subscribers/U005/devices 호출", "200 OK + 빈 배열 []",
          f"status={status}, body={json.dumps(body)}", status == 200 and body == [])

    # API-05 : 존재하지 않는 사용자
    status, body = http_get("/api/subscribers/U999/devices")
    check("API-05", "GET /api/subscribers/U999/devices 호출", '404 + {"detail": ...}',
          f"status={status}, body={json.dumps(body, ensure_ascii=False)}",
          is_404_with_detail(status, body))

    # API-06 : D001 사용 현황
    status, body = http_get("/api/devices/D001/usage")
    ok = status == 200 and isinstance(body, dict) and body.get("deviceId") == "D001"
    check("API-06", "GET /api/devices/D001/usage 호출", "200 OK + D001 사용 현황 JSON 객체",
          f"status={status}, type={type(body).__name__}", ok,
          "" if ok else f"body={json.dumps(body, ensure_ascii=False)}")

    # 모든 가전의 사용 현황 수집
    usage_by_device = {}
    for devs in devices_by_user.values():
        for d in devs or []:
            if isinstance(d, dict) and "deviceId" in d:
                st, u = http_get(f"/api/devices/{d['deviceId']}/usage")
                usage_by_device[d["deviceId"]] = (st, u)

    # API-07 : 사용 현황 스키마
    problems = []
    for did, (st, u) in usage_by_device.items():
        if st != 200 or not isinstance(u, dict):
            problems.append(f"{did}: status={st}, body={type(u).__name__}")
            continue
        miss = [f for f in USAGE_FIELDS if f not in u]
        if miss:
            problems.append(f"{did} 누락 {miss}")
            continue
        trend = u["weeklyUsageTrend"]
        if not (isinstance(trend, list) and len(trend) == 7
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0 for x in trend)):
            problems.append(f"{did}.weeklyUsageTrend={trend!r}")
    passed = bool(usage_by_device) and not problems
    check("API-07", "사용 현황 스키마 검증 (전체 가전)",
          f"필드 {len(USAGE_FIELDS)}개 + weeklyUsageTrend 길이 7, 0 이상 숫자",
          "정상" if passed else ("; ".join(problems[:4]) + (" ..." if len(problems) > 4 else "")
                               if problems else "가전 데이터 없음"), passed)

    # API-08 : 존재하지 않는 디바이스
    status, body = http_get("/api/devices/D999/usage")
    check("API-08", "GET /api/devices/D999/usage 호출", '404 + {"detail": ...}',
          f"status={status}, body={json.dumps(body, ensure_ascii=False)}",
          is_404_with_detail(status, body))

    # API-09 : 대시보드 페이지의 가전/사용 현황 영역
    status, html = http_get_raw("/")
    html = html or ""
    options = re.findall(r'<option value="(\w*)"', html.split('id="device-status-filter"')[-1].split("</select>")[0]) \
        if 'id="device-status-filter"' in html else []
    c = {
        "device-table": 'id="device-table"' in html,
        "device-search": 'id="device-search"' in html,
        "필터옵션4": set(options) >= VALID_DEVICE_STATUSES,
        "usage-info": 'id="usage-info"' in html,
        "usageChart": 'id="usageChart"' in html,
        "chart.js": re.search(r"<script[^>]+chart\.js", html, re.I) is not None,
    }
    check("API-09", "GET / 가전·사용 현황 영역 확인",
          "가전 테이블/검색/상태 필터(4종) + usage-info + usageChart canvas + Chart.js 로드",
          f"status={status}, " + ", ".join(f"{k}={ox(v)}" for k, v in c.items()),
          status == 200 and all(c.values()))

    return subs, devices_by_user, usage_by_device


# =============================================================================
# 3) TE 시나리오
# =============================================================================
def run_te_tests(flags, subs, devices_by_user, usage_by_device):
    print("\n[3] TE 시나리오")
    sim = "검색/필터 로직 시뮬레이션"
    js = flags["js"]

    def devs(uid):
        return devices_by_user.get(uid) or []

    def usage(did):
        st, u = usage_by_device.get(did, (None, None))
        if st is None:
            st, u = http_get(f"/api/devices/{did}/usage")
        return st, u if isinstance(u, dict) else None

    # ---- requirement_2 예시 시나리오 (TE-1 ~ TE-12) ------------------------
    ids = sorted(d["deviceId"] for d in devs("U001"))
    check("TE-1", "/api/subscribers/U001/devices 호출", "2개 가전 JSON 반환",
          f"{len(ids)}개: {ids}", ids == ["D001", "D002"])

    st, body = http_get("/api/subscribers/U005/devices")
    check("TE-2", "/api/subscribers/U005/devices 호출", "빈 배열 [] 반환",
          f"status={st}, body={json.dumps(body)}", st == 200 and body == [])

    st, body = http_get("/api/subscribers/U999/devices")
    check("TE-3", "/api/subscribers/U999/devices 호출", "404 에러 반환",
          f"status={st}", st == 404)

    view = device_view(devs("U001"))
    fe_ok = flags["selectSubscriber"] and flags["renderDevices"]
    check("TE-4", "U001 클릭 시 가전 Table 표시", "D001, D002 표시",
          f"{describe_view(view)} / FE 구현 {ox(fe_ok)}", view == ["D001", "D002"] and fe_ok,
          "실제 화면은 MAN-1 에서 확인")

    view = device_view(devs("U005")) if devices_by_user.get("U005") is not None else None
    check("TE-5", "U005 클릭 시 안내 메시지", '"No registered devices" 표시',
          describe_view(view) if view is not None else "U005 응답 오류",
          view == "No registered devices" and flags["renderDevices"], "실제 화면은 MAN-2 에서 확인")

    view = device_view(devs("U001"), search="TV")
    check("TE-6", 'U001 가전 검색 "TV" 입력', "TV 타입만 표시 (D001)",
          describe_view(view), view == ["D001"], sim)

    view = device_view(devs("U001"), status="Online")
    check("TE-7", 'U001 가전 상태 필터 "Online" 선택', "Online 가전만 표시 (D001)",
          describe_view(view), view == ["D001"], sim)

    st, u = usage("D001")
    check("TE-8", "/api/devices/D001/usage 호출", "사용 현황 JSON 반환",
          f"status={st}, deviceName={u.get('deviceName') if u else None}",
          st == 200 and u is not None and u.get("deviceId") == "D001")

    st, _ = http_get("/api/devices/D999/usage")
    check("TE-9", "/api/devices/D999/usage 호출", "404 에러 반환", f"status={st}", st == 404)

    has_fields = u is not None and all(f in u for f in USAGE_FIELDS)
    check("TE-10", "D001 클릭 시 사용 현황 표시", "전원상태, 누적시간 등 표시",
          f"API 필드 {ox(has_fields)} / FE 구현 {ox(flags['selectDevice'])}",
          has_fields and flags["selectDevice"], "실제 화면은 MAN-4 에서 확인")

    trend = u.get("weeklyUsageTrend") if u else None
    check("TE-11", "D001 클릭 시 Bar Chart 표시", "요일별(7일) 사용량 차트",
          f"trend={trend} / 차트 구현 {ox(flags['chart'])}",
          isinstance(trend, list) and len(trend) == 7 and flags["chart"],
          "실제 차트는 MAN-5 에서 확인")

    check("TE-12", "다른 가전 클릭 시 차트 갱신", "이전 차트 제거, 새 차트 표시",
          f"destroy() 호출 {ox(flags['chart_destroy'])}", flags["chart_destroy"],
          "실제 갱신은 MAN-6 에서 확인")

    # ---- [A] 완료 조건 보완 (TE-13 ~ TE-20) -------------------------------
    for tc, term, field in (("TE-13", "WashTower", "모델명"), ("TE-14", "Dormitory", "위치"),
                            ("TE-15", "Offline", "상태값"), ("TE-16", "D002", "deviceId")):
        expected = ["D001"] if term == "Dormitory" else ["D002"]
        view = device_view(devs("U001"), search=term)
        check(tc, f'U001 {field} 검색 "{term}"', f"{expected[0]}만 표시",
              describe_view(view), view == expected, f"[A] {field} 기준 검색")

    for tc, uid, st_, expected in (("TE-17", "U001", "Offline", ["D002"]),
                                   ("TE-18", "U004", "Standby", ["D008"]),
                                   ("TE-19", "U003", "Error", ["D006"])):
        view = device_view(devs(uid), status=st_)
        check(tc, f'{uid} 상태 필터 "{st_}" 선택', f"{expected[0]}만 표시",
              describe_view(view), view == expected, f"[A] {st_} 필터")

    view = device_view(devs("U002"), status="Error")
    check("TE-20", 'U002 상태 필터 "Error" 선택 (결과 0건)', '"No devices matched" 표시',
          describe_view(view), view == "No devices matched", "[A] 필터 결과 0건 안내")

    # ---- [B] 검색·필터 경계 조건 (TE-21 ~ TE-26) --------------------------
    lower = device_view(devs("U001"), search="tv")
    upper = device_view(devs("U003"), search="TV")
    check("TE-21", '대소문자 무시 ("tv" @U001, "TV" @U003)', "tv → D001 / TV → D004",
          f"tv → {lower} / TV → {upper}", lower == ["D001"] and upper == ["D004"],
          "[B] 대소문자 무시 매칭")

    view = device_view(devs("U003"), search="TV", status="Online")
    check("TE-22", 'U003 검색 "TV" + 필터 "Online"', "D004만 표시",
          describe_view(view), view == ["D004"], "[B] 검색+필터 조합")

    view = device_view(devs("U003"), search="TV", status="Error")
    check("TE-23", 'U003 검색 "TV" + 필터 "Error" (교집합 없음)', '"No devices matched" 표시',
          describe_view(view), view == "No devices matched", "[B] 검색+필터 조합")

    before = device_view(devs("U003"), search="TV", status="Online")
    after = device_view(devs("U003"))
    check("TE-24", "U003 검색어 삭제 + All Status 복귀", "전체 목록(D004, D005, D006) 복원",
          f"조건 적용 {before} → 해제 후 {after}",
          before == ["D004"] and after == ["D004", "D005", "D006"], "[B] " + sim)

    view = device_view(devs("U001"), search=" TV")
    check("TE-25", 'U001 앞 공백 포함 " TV" 검색', "명세 미정의 (trim 여부)",
          describe_view(view), None, "[B] 공백 미제거 시 0건 — 의도된 동작인지 PM 확인 필요")

    view = device_view(devs("U003"), search="Off")
    check("TE-26", 'U003 "Off" 검색 (부분 매칭 부작용)', "D005 표시 (location \"Office\" 부분 매칭)",
          describe_view(view), view == ["D005"],
          "[B] 명세상 정상. Offline 가전을 찾으려는 사용자에게 Online 가전이 보일 수 있음(관찰)")

    # ---- [C] 상태 전환 (TE-27 ~ TE-30, 정적 검사) -------------------------
    check("TE-27", "가전 선택 후 다른 구독자 클릭 시 초기화",
          "usage-empty 표시, usage-detail 숨김, usage-info 비움, 차트 제거",
          f"초기화+destroy {ox(flags['usage_reset'])}", flags["usage_reset"],
          "[C] 정적 검사, 실제 화면은 MAN-7")

    ext = js_expanded_body(js, "selectSubscriber")
    resets_search = re.search(r"device-search[^;]*\.value\s*=", ext) is not None
    check("TE-28", '"TV" 검색 상태에서 다른 구독자(U002) 클릭', "명세 미정의 (검색어 유지/초기화)",
          "검색어 초기화함" if resets_search
          else f'검색어 유지 → U002 에서 {describe_view(device_view(devs("U002"), search="TV"))}',
          None, "[C] 의도된 동작인지 PM 확인 필요 (MAN-8)")

    sub_guard = re.search(r"selectedUserId\s*!==?\s*userId", js_function_body(js, "selectSubscriber")) is not None
    dev_guard = re.search(r"selectedDeviceId\s*!==?\s*deviceId", js_function_body(js, "selectDevice")) is not None
    check("TE-29", "빠른 연속 클릭 시 늦게 온 응답 무시 (경쟁 상태)",
          "selectSubscriber / selectDevice 에 최신 선택 확인 로직",
          f"구독자 가드 {ox(sub_guard)}, 가전 가드 {ox(dev_guard)}", sub_guard and dev_guard,
          "[C] 정적 검사, 실제 동작은 MAN-10")

    b_sub, b_dev = js_function_body(js, "selectSubscriber"), js_function_body(js, "selectDevice")
    c = {
        "devices res.ok": "res.ok" in b_sub,
        "devices 실패 메시지": "Failed to load devices" in b_sub,
        "usage res.ok": "res.ok" in b_dev,
        "usage 실패 메시지": "Failed to load usage details" in b_dev,
    }
    check("TE-30", "API 실패(서버 다운/에러 응답) 시 처리",
          "res.ok 확인 + 실패 안내 메시지 표시",
          ", ".join(f"{k}={ox(v)}" for k, v in c.items()), all(c.values()),
          "[C] 정적 검사, 실제 동작은 MAN-11")

    # ---- [D] 사용 현황 상세 + Badge (TE-31 ~ TE-34) -----------------------
    check("TE-31", "Power Status / Health Status badge 렌더링", "두 값 모두 badge(span) 로 표시",
          f"createBadge(powerStatus/healthStatus) {ox(flags['usage_badges'])}", flags["usage_badges"],
          "[D] 정적 검사")

    css = read_text(STYLE_CSS)
    values = set()
    for _, (_, u_) in usage_by_device.items():
        if isinstance(u_, dict):
            values.update(str(u_.get(k)) for k in ("powerStatus", "healthStatus") if u_.get(k))
    missing = sorted(v for v in values if f".status-{v.lower()}" not in css)
    check("TE-32", "사용 현황의 모든 상태값에 대응하는 CSS 클래스 존재",
          "On/Off/Standby/Error/Cleaning/Normal/Warning → .status-* 정의",
          f"값 {sorted(values)} / 누락 {missing}" if values else "usage 응답에 상태값 없음 (API 확인 필요)",
          bool(values) and not missing, "[D] style.css 검사")

    badge_body = js_function_body(js, "badgeClass")
    implemented = "status-" in badge_body
    check("TE-33", "badge 색상 적용 (badgeClass 매핑)", "상태값별 status-* 클래스 반환",
          "badgeClass 구현됨" if implemented else 'badgeClass 가 항상 "badge" 만 반환 (미구현)',
          True if implemented else None,
          "[D] 요구사항 #3 범위 — req3 완료 후 MAN-12 에서 색상 확인")

    _, u1 = usage("D001")
    shown = {
        "Last Used": u1.get("lastUsedAt") if u1 else None,
        "Total Usage": f"{u1.get('totalUsageHours')} hrs" if u1 else None,
        "Weekly Count": u1.get("weeklyUsageCount") if u1 else None,
    }
    expected = {"Last Used": "2026-03-22 10:10:00", "Total Usage": "152 hrs", "Weekly Count": 18}
    check("TE-34", "D001 상세 값 표시 형식", "Last Used 2026-03-22 10:10:00 / Total 152 hrs / Weekly 18",
          f"{shown} / hrs 표기 {ox(flags['hrs_format'])}",
          shown == expected and flags["hrs_format"], "[D] API 값 + FE 표기 형식")

    # ---- [E] 차트 (TE-35 ~ TE-37) -----------------------------------------
    trend = u1.get("weeklyUsageTrend") if u1 else None
    check("TE-35", "D001 차트 데이터/라벨", "[2,3,1,4,2,3,3], 라벨 Mon~Sun",
          f"trend={trend}, 라벨 {ox(flags['chart_labels'])}",
          trend == [2, 3, 1, 4, 2, 3, 3] and flags["chart_labels"], "[E]")

    _, u2 = usage("D002")
    trend2 = u2.get("weeklyUsageTrend") if u2 else None
    check("TE-36", "D002 (작은 값, 0 포함) 차트 y축", "y축 0부터 시작 (beginAtZero)",
          f"trend={trend2}, beginAtZero {ox(flags['chart_zero'])}",
          isinstance(trend2, list) and min(trend2, default=-1) == 0 and flags["chart_zero"], "[E]")

    bad = [did for did, (st, u_) in usage_by_device.items()
           if not (isinstance(u_, dict) and isinstance(u_.get("weeklyUsageTrend"), list)
                   and len(u_["weeklyUsageTrend"]) == 7)]
    check("TE-37", "모든 가전의 주간 사용량 길이", "8개 가전 모두 7일치 데이터",
          f"{len(usage_by_device)}개 중 이상 {bad}", len(usage_by_device) == 8 and not bad, "[E]")

    # ---- [F] API·데이터 정합성 (TE-38 ~ TE-42) ----------------------------
    mismatch = [f"{u['userId']}: {u.get('deviceCount')}≠{len(devs(u['userId']))}"
                for u in subs if u.get("deviceCount") != len(devs(u["userId"]))]
    check("TE-38", "구독자 deviceCount 와 실제 가전 수 일치", "U001=2, U002=1, U003=3, U004=2, U005=0",
          "전원 일치" if subs and not mismatch else (", ".join(mismatch) or "구독자 데이터 없음"),
          bool(subs) and not mismatch, "[F]")

    not_ok = [f"{did}(status={st}, {type(u_).__name__})" for did, (st, u_) in usage_by_device.items()
              if st != 200 or not isinstance(u_, dict)]
    check("TE-39", "가전 목록의 모든 deviceId 로 usage 조회", "D001~D008 모두 200 + JSON 객체",
          f"{len(usage_by_device)}개 조회, 실패 {not_ok}", len(usage_by_device) == 8 and not not_ok, "[F]")

    model_of = {d["deviceId"]: d.get("model") for v in devices_by_user.values() for d in v or []}
    diffs = []
    for did, (st, u_) in usage_by_device.items():
        if not isinstance(u_, dict):
            diffs.append(f"{did}: 응답 없음")
        elif u_.get("deviceId") != did:
            diffs.append(f"{did}: deviceId={u_.get('deviceId')}")
        elif u_.get("deviceName") != model_of.get(did):
            diffs.append(f"{did}: deviceName={u_.get('deviceName')!r} vs model={model_of.get(did)!r}")
    check("TE-40", "usage 응답과 가전 목록의 일관성", "deviceId 일치, deviceName == 목록의 model",
          "전부 일치" if usage_by_device and not diffs else ("; ".join(diffs[:3]) or "데이터 없음"),
          bool(usage_by_device) and not diffs, "[F]")

    all_ids = [d["deviceId"] for v in devices_by_user.values() for d in v or []]
    dup = sorted({i for i in all_ids if all_ids.count(i) > 1})
    check("TE-41", "deviceId 전역 고유성", "사용자 간 중복 deviceId 없음",
          f"{len(all_ids)}개, 중복 {dup}", bool(all_ids) and not dup, "[F]")

    st_u, _ = http_get("/api/subscribers/u001/devices")
    st_d, _ = http_get("/api/devices/d001/usage")
    check("TE-42", '소문자 ID 요청 ("u001", "d001")', "명세 미정의 (대소문자 구분 여부)",
          f"u001 → {st_u}, d001 → {st_d}", None,
          "[F] 현재 대소문자를 구분함 — 의도된 동작인지 PM 확인 필요")


# =============================================================================
# [G] req1 회귀 테스트
# =============================================================================
def run_regression(skip):
    print("\n[3-G] 회귀 테스트")
    if skip:
        check("TE-43", "req1 회귀 테스트", "req1 자동 검증 전부 PASS", "--skip-regression 으로 생략",
              None, "[G] 생략됨")
        return
    if not os.path.exists(REQ1_SCRIPT):
        check("TE-43", "req1 회귀 테스트", "req1 자동 검증 전부 PASS", "req1 스크립트 없음", False, "[G]")
        return
    try:
        proc = subprocess.run([sys.executable, REQ1_SCRIPT], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, encoding="utf-8", timeout=180)
        summary = next((ln.strip() for ln in proc.stdout.splitlines() if "자동 검증:" in ln), "")
        actual = f"exit={proc.returncode} {summary}"
        passed = proc.returncode == 0
    except subprocess.TimeoutExpired:
        actual, passed = "시간 초과(180s)", False
    check("TE-43", "req1 회귀 테스트 (tests/req1_test_template.py)", "req1 자동 검증 전부 PASS",
          actual, passed, "[G] req1 Report 파일이 새로 생성됨")


# =============================================================================
# 4) 수동 확인 항목 (브라우저에서 직접 확인 후 Report 의 결과 칸을 채우세요)
# =============================================================================
MANUAL_TESTS = [
    ("MAN-1", "U001 행 클릭", "가전 Table 에 D001, D002 표시 + U001 행 강조(selected)"),
    ("MAN-2", "U005 행 클릭", '"No registered devices" 안내 메시지 표시'),
    ("MAN-3", "가전 검색어 타이핑 / 상태 필터 변경", "Enter 없이 즉시 결과 반영"),
    ("MAN-4", "D001 행 클릭", "Device ID ~ Remark 8개 항목 표시 + D001 행 강조"),
    ("MAN-5", "D001 Bar Chart 확인", "Mon~Sun 7개 막대, y축 0부터 시작"),
    ("MAN-6", "D001 → D002 클릭", "차트가 D002 데이터로 교체(겹침/깜빡임 없음), 콘솔(F12) 오류 없음"),
    ("MAN-7", "D001 선택 후 U002 클릭", "사용 현황 패널 초기화 + 차트 제거"),
    ("MAN-8", '"TV" 검색 상태에서 U002 클릭', "검색어 유지 여부 관찰 (TE-28 참고)"),
    ("MAN-9", 'D001 선택 후 상태 필터 "Offline" 선택', "D001 이 목록에서 사라질 때 사용 현황 패널 상태 관찰"),
    ("MAN-10", "D001 / D002 를 빠르게 번갈아 클릭", "마지막으로 클릭한 가전의 정보만 표시"),
    ("MAN-11", "서버 종료 후 구독자/가전 클릭", '"Failed to load devices." / "Failed to load usage details." 표시'),
    ("MAN-12", "Power/Health Status badge 색상", "상태별 색상 적용 (요구사항 #3 완료 후 확인)"),
]


def run_manual_tests():
    print("\n[4] 수동 확인 항목 (Report 에 결과 기입 필요)")
    for tc_id, scenario, expected in MANUAL_TESTS:
        check(tc_id, scenario, expected, "", None, "브라우저 수동 확인")


# =============================================================================
# Markdown Report 생성
# =============================================================================
SECTIONS = [
    ("DEV", "1. 개발자 테스트 (코드/구현 검증)"),
    ("API", "2. API 테스트 (실행 검증)"),
    ("TE", "3. TE 테스트 시나리오"),
    ("MAN", "4. 수동 확인 (브라우저)"),
]

# requirement_2 완료 조건 → 관련 TC
REQUIREMENT_MAP = [
    ("GET /api/subscribers/{userId}/devices API 정상 동작",
     ["DEV-02", "API-02", "API-03", "API-04", "TE-1", "TE-2", "TE-38"]),
    ("구독자 행 클릭 시 가전 목록 Table 표시", ["DEV-06", "DEV-07", "TE-4", "MAN-1"]),
    ("가전 없는 사용자 선택 시 안내 메시지", ["TE-5", "MAN-2"]),
    ("모델명/타입/상태/위치 기준 검색", ["TE-6", "TE-13", "TE-14", "TE-15", "TE-16", "TE-21"]),
    ("Online/Offline/Standby/Error 상태 필터", ["DEV-10", "TE-7", "TE-17", "TE-18", "TE-19", "TE-20"]),
    ("존재하지 않는 사용자 ID 404", ["DEV-03", "API-05", "TE-3"]),
    ("GET /api/devices/{deviceId}/usage API 정상 동작",
     ["DEV-04", "API-06", "API-07", "TE-8", "TE-39", "TE-40"]),
    ("가전 행 클릭 시 사용 현황 표시", ["DEV-08", "TE-10", "TE-31", "TE-34", "MAN-4"]),
    ("주간 사용량 Bar Chart(요일 기준) 표시", ["DEV-09", "TE-11", "TE-12", "TE-35", "TE-36", "MAN-5"]),
    ("존재하지 않는 디바이스 ID 404", ["DEV-05", "API-08", "TE-9"]),
]


def mark(passed):
    return {True: "✅ PASS", False: "❌ FAIL", None: "⬜ 확인 필요"}[passed]


def section_of(tc_id):
    return tc_id.split("-")[0]


def md_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report():
    auto = [r for r in results if r[4] is not None]
    passed = sum(1 for r in auto if r[4])
    failed = len(auto) - passed
    pending = len(results) - len(auto)
    rate = (passed / len(auto) * 100) if auto else 0.0
    by_id = {r[0]: r[4] for r in results}

    lines = [
        "# requirement_2 검증 Report",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        "| **프로젝트** | webOS Subscription Management Dashboard |",
        "| **검증 대상** | requirement_2.md (가전 목록 조회 + 사용 현황 + 차트) |",
        f"| **검증 일시** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| **작성자** | {AUTHOR} |",
        "| **검증 도구** | tests/req2_test_template.py |",
        "",
        "## 요약",
        "",
        "| 구분 | 전체 | PASS | FAIL | 확인 필요 |",
        "|:----:|:----:|:----:|:----:|:---------:|",
    ]
    for prefix, title in SECTIONS:
        rows = [r for r in results if section_of(r[0]) == prefix]
        lines.append(
            f"| {title} | {len(rows)} | {sum(1 for r in rows if r[4] is True)} | "
            f"{sum(1 for r in rows if r[4] is False)} | {sum(1 for r in rows if r[4] is None)} |")
    lines.append(f"| **합계** | **{len(results)}** | **{passed}** | **{failed}** | **{pending}** |")
    lines.append("")
    lines.append(f"**자동 검증 Pass Rate: {passed} / {len(auto)} = {rate:.1f}%** "
                 f"(확인 필요 {pending}건 제외)")
    lines.append("")
    verdict = "✅ 자동 검증 통과 — 수동 확인 항목 완료 후 PM 에게 전달" if failed == 0 \
        else f"❌ FAIL {failed}건 — 담당자(BE/FE) 수정 후 재검증 필요"
    lines.append(f"**종합 판정: {verdict}**")
    lines.append("")

    fails = [r for r in results if r[4] is False]
    if fails:
        lines.append("## 결함 목록 (FAIL)")
        lines.append("")
        lines.append("| TC ID | 시나리오 | 실제 결과 |")
        lines.append("|:-----:|----------|-----------|")
        for tc_id, scenario, _, actual, _, _ in fails:
            lines.append(f"| {tc_id} | {md_cell(scenario)} | {md_cell(actual)} |")
        lines.append("")

    for prefix, title in SECTIONS:
        rows = [r for r in results if section_of(r[0]) == prefix]
        if not rows:
            continue
        lines.append(f"## {title}")
        lines.append("")
        if prefix == "TE":
            lines.append("> [A] 완료 조건 보완 · [B] 검색·필터 경계 · [C] 상태 전환 · "
                         "[D] 상세/Badge · [E] 차트 · [F] 데이터 정합성 · [G] 회귀")
            lines.append("")
        lines.append("| TC ID | 테스트 시나리오 | 기대 결과 | 실제 결과 | 판정 | 비고 |")
        lines.append("|:-----:|----------------|-----------|-----------|:----:|------|")
        for tc_id, scenario, expected, actual, passed_, note in rows:
            lines.append(f"| {tc_id} | {md_cell(scenario)} | {md_cell(expected)} | "
                         f"{md_cell(actual)} | {mark(passed_)} | {md_cell(note)} |")
        lines.append("")

    lines.append("## requirement_2 완료 조건 매핑")
    lines.append("")
    lines.append("| 완료 조건 | 관련 TC | 자동 검증 판정 |")
    lines.append("|-----------|---------|:----:|")
    for cond, tcs in REQUIREMENT_MAP:
        auto_results = [by_id[t] for t in tcs if by_id.get(t) is not None]
        ok = bool(auto_results) and all(auto_results)
        lines.append(f"| {cond} | {', '.join(tcs)} | {'✅' if ok else '❌'} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> 본 Report 는 `tests/req2_test_template.py` 로 생성되었습니다.")
    lines.append("> TE 시나리오의 검색/필터는 app.js 규칙을 파이썬으로 재현한 시뮬레이션이며, "
                 "[C] 상태 전환은 app.js 정적 검사입니다. 실제 화면 동작은 MAN 항목으로 검증합니다.")
    lines.append("> '확인 필요' 항목은 명세 미정의 동작이므로 PM 에게 의도 여부를 확인받고, "
                 "MAN 항목은 확인 후 실제 결과와 판정 칸을 직접 수정하세요.")

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return passed, failed, len(auto), pending, rate


# =============================================================================
# main
# =============================================================================
def main():
    global BASE_URL
    skip_regression = "--skip-regression" in sys.argv[1:]

    print("=" * 60)
    print(" requirement_2 검증")
    print("=" * 60)

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    flags = run_dev_tests()

    port = find_free_port()
    print(f"\n[서버 기동] 127.0.0.1:{port} ...")
    proc, ok = start_server(port)
    if not ok:
        print("[오류] 서버 기동 실패. requirements 설치 및 app/main.py 를 확인하세요.")
        stop_server(proc)
        sys.exit(1)
    BASE_URL = f"http://127.0.0.1:{port}"
    print("[서버 기동] 성공")

    try:
        subs, devices_by_user, usage_by_device = run_api_tests()
        run_te_tests(flags, subs, devices_by_user, usage_by_device)
    finally:
        stop_server(proc)

    run_regression(skip_regression)
    run_manual_tests()

    passed, failed, total, pending, rate = render_report()
    print("\n" + "=" * 60)
    print(f" 자동 검증: PASS {passed} / FAIL {failed} (총 {total}) - {rate:.1f}%")
    print(f" 확인 필요: {pending}건 (수동 확인 / 명세 미정의)")
    print(f" Report 저장: {os.path.relpath(REPORT_PATH, PROJECT_ROOT)}")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
