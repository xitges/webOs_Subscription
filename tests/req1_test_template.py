"""
requirement_1.md 검증 스크립트 (TE 완성본)

검증 대상
--------
요구사항 #1: 구독 사용자 조회 + 검색/필터
  - BE : app/api/subscribers.py  (GET /api/subscribers)
  - FE : app/static/app.js       (fetchSubscribers / renderSubscribers / 이벤트 바인딩)

실행 방법
--------
    # 프로젝트 루트(skeleton/)에서
    python tests/req1_test_template.py

결과
----
    tests/reports/req1_report_template.md   (검증 Report)
    모든 자동 테스트가 PASS 이면 종료 코드 0, 하나라도 FAIL 이면 1

필요 패키지: fastapi, uvicorn, jinja2 (requirements.txt 에 이미 포함)
             그 외에는 파이썬 표준 라이브러리만 사용합니다.

────────────────────────────────────────────────────────────────────────
검증 구성
  1) DEV : 개발자 테스트  - 문법, 함수 반환값, app.js 구현/주석 해제 여부(정적 검사)
  2) API : API 테스트     - 서버를 켜고 실제 HTTP 응답/스키마 확인
  3) TE  : TE 시나리오    - requirement_1 예시(TE-1~8) + 추가 시나리오(TE-9~17)
  4) MAN : 수동 확인 항목 - 브라우저에서 직접 확인 후 Report 에 결과 기입

판정 값
  True  → PASS
  False → FAIL
  None  → 확인 필요 (명세 미정의 관찰 항목 / 수동 확인 항목, Pass Rate 에서 제외)

주의
  TE 시나리오의 검색/필터는 app.js 의 규칙을 파이썬(filter_subscribers)으로 재현한
  시뮬레이션입니다. app.js 가 실제로 그렇게 동작하는지는 MAN 항목으로 브라우저에서 확인하세요.
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
REPORT_PATH = os.path.join(REPORT_DIR, "req1_report_template.md")

SUBSCRIBERS_PY = os.path.join("app", "api", "subscribers.py")
APP_JS = os.path.join("app", "static", "app.js")

REQUIRED_FIELDS = ["userId", "name", "plan", "status", "deviceCount"]
VALID_STATUSES = {"Active", "Paused", "Expired"}

os.chdir(PROJECT_ROOT)          # 상대경로(app/static 등)를 위해 루트로 이동
BASE_URL = None                 # 서버 기동 후 채워짐

# 검증 결과를 담는 리스트. 각 항목: (TC ID, 시나리오, 기대결과, 실제결과, 판정, 비고)
results = []


def check(tc_id, scenario, expected, actual, passed, note=""):
    """검증 결과 1건을 기록한다. passed: True / False / None(확인 필요)."""
    results.append((tc_id, scenario, expected, actual, passed, note))
    tag = {True: "PASS", False: "FAIL", None: "CHECK"}[passed]
    print(f"  [{tag:5}] {tc_id:7} {scenario}")


# =============================================================================
# HTTP 유틸
# =============================================================================
def http_get_raw(path, timeout=5):
    """(status_code, body_text) 반환. 연결 실패 시 (None, None)."""
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
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


# =============================================================================
# 검색/필터 로직 (app.js renderSubscribers 와 동일한 규칙을 파이썬으로 재현)
#   - 검색: name, plan, status, userId 에 대해 대소문자 무시 부분 문자열 매칭
#   - 필터: status 가 선택된 값과 정확히 일치 ("" 이면 전체)
# =============================================================================
def filter_subscribers(subs, search="", status=""):
    s = (search or "").lower()
    out = []
    for u in subs:
        matches_search = (
            s in u["name"].lower()
            or s in u["plan"].lower()
            or s in u["status"].lower()
            or s in u["userId"].lower()
        )
        matches_status = (not status) or u["status"] == status
        if matches_search and matches_status:
            out.append(u)
    return out


def ids_of(subs):
    return sorted(u["userId"] for u in subs)


def names_of(subs):
    return [u["name"] for u in subs]


def describe(subs):
    return f"{len(subs)}명: {names_of(subs)}"


# =============================================================================
# app.js 정적 검사 유틸
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


def load_app_js():
    try:
        with open(APP_JS, encoding="utf-8") as f:
            return strip_js_comments(f.read())
    except OSError:
        return ""


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
def run_dev_tests():
    print("\n[1] 개발자 테스트")

    # DEV-01 : subscribers.py 문법 검사
    try:
        py_compile.compile(SUBSCRIBERS_PY, doraise=True)
        passed, actual = True, "컴파일 성공"
    except py_compile.PyCompileError as e:
        passed, actual = False, f"컴파일 오류: {e.msg.strip().splitlines()[-1]}"
    check("DEV-01", "subscribers.py 문법 검사(py_compile)", "컴파일 오류 없음", actual, passed)

    # DEV-02 : get_subscribers() 직접 호출
    data = None
    try:
        from app.api.subscribers import get_subscribers
        data = get_subscribers()
        passed = isinstance(data, list) and len(data) == 5
        actual = f"{len(data)}명 반환" if isinstance(data, list) else f"{type(data).__name__} 반환"
    except Exception as e:
        passed, actual = False, f"예외: {e}"
    check("DEV-02", "get_subscribers() 함수 직접 호출", "길이 5인 list 반환", actual, passed)

    # DEV-03 : 반환 항목의 필수 필드
    if isinstance(data, list) and data:
        missing = [(u.get("userId", "?"), f) for u in data for f in REQUIRED_FIELDS
                   if not isinstance(u, dict) or f not in u]
        passed = not missing
        actual = "모든 항목에 필수 필드 존재" if passed else f"누락: {missing}"
    else:
        passed, actual = False, "반환 데이터 없음"
    check("DEV-03", "반환 항목의 필수 필드 검증", ", ".join(REQUIRED_FIELDS), actual, passed)

    js = load_app_js()

    # DEV-04 : fetchSubscribers() 가 /api/subscribers 를 호출하고 렌더링하는가
    body = js_function_body(js, "fetchSubscribers")
    has_fetch = re.search(r"fetch\(\s*[`'\"]/api/subscribers[`'\"]", body) is not None
    has_render = "renderSubscribers(" in body
    check("DEV-04", "fetchSubscribers() 구현 (정적 검사)",
          "/api/subscribers fetch + renderSubscribers() 호출",
          f"fetch={'O' if has_fetch else 'X'}, render={'O' if has_render else 'X'}",
          has_fetch and has_render)

    # DEV-05 : renderSubscribers() 에 필터링 + 행 렌더링 + selected 처리가 있는가
    body = js_function_body(js, "renderSubscribers")
    has_filter = ".filter(" in body
    has_row = re.search(r"createElement\(\s*[`'\"]tr[`'\"]\s*\)|<tr", body) is not None
    has_selected = "selected" in body and "selectSubscriber" in body
    check("DEV-05", "renderSubscribers() 구현 (정적 검사)",
          "filter + <tr> 렌더링 + 행 클릭/selected 처리",
          f"filter={'O' if has_filter else 'X'}, tr={'O' if has_row else 'X'}, "
          f"selected/click={'O' if has_selected else 'X'}",
          has_filter and has_row and has_selected)

    # DEV-06 : 이벤트 리스너 + 초기 fetchSubscribers() 호출이 주석 해제되었는가
    has_input = re.search(r"subscriber-search[`'\"]\s*\)\s*\.addEventListener\(\s*[`'\"]input", js) is not None
    has_change = re.search(r"subscriber-status-filter[`'\"]\s*\)\s*\.addEventListener\(\s*[`'\"]change", js) is not None
    has_init = len(re.findall(r"(?<!function )fetchSubscribers\(\s*\)", js)) >= 1
    check("DEV-06", "이벤트 리스너 + 초기 fetchSubscribers() 주석 해제",
          "input/change 리스너 + 초기 호출 활성화",
          f"input={'O' if has_input else 'X'}, change={'O' if has_change else 'X'}, "
          f"init={'O' if has_init else 'X'}",
          has_input and has_change and has_init)

    return has_init


# =============================================================================
# 2) API 테스트 (실행 검증)
# =============================================================================
def run_api_tests():
    print("\n[2] API 테스트")

    # API-01 : 헬스 체크
    status, body = http_get("/health")
    check("API-01", "GET /health 호출", "200 OK", f"status={status}", status == 200,
          json.dumps(body) if body else "")

    # API-02 : 구독자 목록 조회
    status, body = http_get("/api/subscribers")
    is_list = isinstance(body, list)
    check("API-02", "GET /api/subscribers 호출", "200 OK + JSON 배열",
          f"status={status}, type={type(body).__name__}", status == 200 and is_list)
    subscribers = body if is_list else []

    # API-03 : 필수 필드 포함
    if subscribers:
        missing = [(u.get("userId", "?") if isinstance(u, dict) else "?", f)
                   for u in subscribers for f in REQUIRED_FIELDS
                   if not isinstance(u, dict) or f not in u]
        passed = not missing
        actual = "모든 항목에 포함" if passed else f"누락: {missing}"
    else:
        passed, actual = False, "응답 데이터 없음"
    check("API-03", "각 항목에 필수 필드 포함", ", ".join(REQUIRED_FIELDS), actual, passed)

    # 이후 테스트는 필드가 온전한 항목만 사용 (KeyError 방지)
    subscribers = [u for u in subscribers
                   if isinstance(u, dict) and all(f in u for f in REQUIRED_FIELDS)]

    # API-04 : 값의 타입/범위
    problems = []
    for u in subscribers:
        if not isinstance(u["deviceCount"], int) or isinstance(u["deviceCount"], bool) or u["deviceCount"] < 0:
            problems.append(f'{u["userId"]}.deviceCount={u["deviceCount"]!r}')
        if u["status"] not in VALID_STATUSES:
            problems.append(f'{u["userId"]}.status={u["status"]!r}')
    user_ids = [u["userId"] for u in subscribers]
    if len(user_ids) != len(set(user_ids)):
        problems.append("userId 중복")
    passed = bool(subscribers) and not problems
    actual = "정상" if passed else (", ".join(problems) if problems else "응답 데이터 없음")
    check("API-04", "필드 타입/값 범위 검증",
          "deviceCount 0 이상 정수, status ∈ Active/Paused/Expired, userId 고유", actual, passed)

    # API-05 : 대시보드 페이지 제공
    status, html = http_get_raw("/")
    has_table = bool(html) and 'id="subscriber-body"' in html
    has_js = bool(html) and "app.js" in html
    check("API-05", "GET / (대시보드 페이지) 호출",
          "200 OK + 구독자 테이블 영역 + app.js 로드",
          f"status={status}, table={'O' if has_table else 'X'}, app.js={'O' if has_js else 'X'}",
          status == 200 and has_table and has_js)
    page_ok = status == 200 and has_table and has_js

    return subscribers, page_ok


# =============================================================================
# 3) TE 시나리오
# =============================================================================
def run_te_tests(subscribers, page_ok, init_call_active):
    print("\n[3] TE 시나리오")
    sim = "검색/필터 로직 시뮬레이션"

    # ---- requirement_1 예시 시나리오 (TE-1 ~ TE-8) -------------------------
    check("TE-1", "/api/subscribers 호출", "5명의 사용자 목록 JSON 반환",
          f"{len(subscribers)}명", len(subscribers) == 5)

    passed = len(subscribers) == 5 and page_ok and init_call_active
    check("TE-2", "대시보드 접속 시 Table 자동 표시", "5명 목록 표시",
          f"API {len(subscribers)}명 / 페이지 {'O' if page_ok else 'X'} / "
          f"초기 호출 {'O' if init_call_active else 'X'}",
          passed, "실제 화면 표시는 MAN-1 에서 확인")

    r = filter_subscribers(subscribers, search="Kim")
    check("TE-3", '검색창에 "Kim" 입력', "Kim Minsoo만 표시",
          describe(r), names_of(r) == ["Kim Minsoo"], sim)

    r = filter_subscribers(subscribers, search="Premium")
    check("TE-4", '검색창에 "Premium" 입력', "Premium 플랜 사용자만 표시 (U001, U004)",
          f"{len(r)}명: {ids_of(r)}", ids_of(r) == ["U001", "U004"], sim)

    r = filter_subscribers(subscribers, status="Active")
    check("TE-5", '상태 필터 "Active" 선택', "Active 사용자만 표시 (U001, U002, U004)",
          f"{len(r)}명: {ids_of(r)}", ids_of(r) == ["U001", "U002", "U004"], sim)

    r = filter_subscribers(subscribers, status="Expired")
    check("TE-6", '상태 필터 "Expired" 선택', "Jung Hyerin만 표시",
          describe(r), names_of(r) == ["Jung Hyerin"], sim)

    r = filter_subscribers(subscribers, search="Kim", status="Active")
    check("TE-7", '검색("Kim") + 필터("Active") 동시 적용', "두 조건 모두 만족 (U001)",
          f"{len(r)}명: {ids_of(r)}", ids_of(r) == ["U001"], sim)

    before = filter_subscribers(subscribers, search="Kim")
    r = filter_subscribers(subscribers, search="")
    check("TE-8", '검색어("Kim") 삭제 시', "전체 목록(5명) 복원",
          f"검색 중 {len(before)}명 → 삭제 후 {len(r)}명",
          len(before) == 1 and len(r) == 5, sim)

    # ---- 완료 조건 보완 시나리오 (TE-9 ~ TE-12) ----------------------------
    r = filter_subscribers(subscribers, search="U003")
    check("TE-9", '검색창에 ID "U003" 입력', "Park Junho만 표시",
          describe(r), names_of(r) == ["Park Junho"], "완료 조건: ID 기준 검색")

    r = filter_subscribers(subscribers, search="Paused")
    check("TE-10", '검색창에 상태 "Paused" 입력', "Park Junho만 표시",
          describe(r), names_of(r) == ["Park Junho"], "완료 조건: 상태 기준 검색")

    r = filter_subscribers(subscribers, status="Paused")
    check("TE-11", '상태 필터 "Paused" 선택', "Park Junho만 표시",
          describe(r), names_of(r) == ["Park Junho"], "완료 조건: Paused 필터")

    before = filter_subscribers(subscribers, status="Active")
    r = filter_subscribers(subscribers, status="")
    check("TE-12", '필터 "Active" → "All Status" 복귀', "전체 목록(5명) 복원",
          f"필터 중 {len(before)}명 → 복귀 후 {len(r)}명",
          len(before) == 3 and len(r) == 5, sim)

    # ---- 경계값 / 예외 시나리오 (TE-13 ~ TE-17) ----------------------------
    lower = ids_of(filter_subscribers(subscribers, search="kim"))
    upper = ids_of(filter_subscribers(subscribers, search="PREMIUM"))
    check("TE-13", '대소문자 변형 검색 ("kim", "PREMIUM")', "kim → U001 / PREMIUM → U001, U004",
          f"kim → {lower} / PREMIUM → {upper}",
          lower == ["U001"] and upper == ["U001", "U004"], "대소문자 무시 매칭")

    r = filter_subscribers(subscribers, search="min")
    check("TE-14", '부분 문자열 "min" 검색', "Kim Minsoo, Choi Sumin 표시",
          describe(r), sorted(names_of(r)) == ["Choi Sumin", "Kim Minsoo"], "부분 매칭")

    r = filter_subscribers(subscribers, search="xyz")
    check("TE-15", '존재하지 않는 값 "xyz" 검색', "0명 (빈 테이블, 오류 없음)",
          describe(r), bool(subscribers) and len(r) == 0, "빈 화면 표시는 MAN-2 에서 확인")

    r = filter_subscribers(subscribers, search="Premium", status="Expired")
    check("TE-16", '검색("Premium") + 필터("Expired") 교집합 없음', "0명",
          describe(r), bool(subscribers) and len(r) == 0, sim)

    r = filter_subscribers(subscribers, search=" Kim")
    check("TE-17", '앞 공백 포함 " Kim" 검색', "명세 미정의 (trim 여부)",
          describe(r), None,
          "공백 미제거 시 0명 — 의도된 동작인지 PM 확인 필요")


# =============================================================================
# 4) 수동 확인 항목 (브라우저에서 직접 확인 후 Report 의 결과 칸을 채우세요)
# =============================================================================
MANUAL_TESTS = [
    ("MAN-1", "브라우저로 http://localhost:8000 접속",
     "새로고침 없이 5명 목록 자동 표시"),
    ("MAN-2", '"xyz" 검색', "빈 테이블 표시, 콘솔(F12) 오류 없음"),
    ("MAN-3", "테이블 컬럼 확인", "ID / Name / Plan / Status / Devices 5개 (organization 미표시)"),
    ("MAN-4", "Enter 없이 검색어 타이핑", "입력할 때마다 결과 즉시 반영 (실시간)"),
    ("MAN-5", "상태 필터 드롭다운 변경", "선택 즉시 결과 반영"),
    ("MAN-6", "구독자 행 클릭", '클릭한 행에 "selected" 클래스(강조 표시) 적용'),
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

# requirement_1 완료 조건 → 관련 TC
REQUIREMENT_MAP = [
    ("GET /api/subscribers API 정상 동작", ["DEV-02", "API-02", "API-03", "API-04", "TE-1"]),
    ("대시보드 진입 시 구독자 목록 자동 표시", ["DEV-04", "DEV-06", "API-05", "TE-2", "MAN-1"]),
    ("이름/플랜/상태/ID 기준 검색 동작", ["DEV-05", "TE-3", "TE-4", "TE-9", "TE-10", "TE-13", "TE-14"]),
    ("Active/Paused/Expired 상태 필터 동작", ["TE-5", "TE-6", "TE-11", "TE-12"]),
    ("검색/필터 결과 실시간 반영", ["DEV-06", "TE-7", "TE-8", "TE-16", "MAN-4", "MAN-5"]),
]


def mark(passed):
    return {True: "✅ PASS", False: "❌ FAIL", None: "⬜ 확인 필요"}[passed]


def section_of(tc_id):
    return tc_id.split("-")[0]


def render_report():
    auto = [r for r in results if r[4] is not None]
    passed = sum(1 for r in auto if r[4])
    failed = len(auto) - passed
    pending = len(results) - len(auto)
    rate = (passed / len(auto) * 100) if auto else 0.0
    by_id = {r[0]: r[4] for r in results}

    lines = [
        "# requirement_1 검증 Report",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        "| **프로젝트** | webOS Subscription Management Dashboard |",
        "| **검증 대상** | requirement_1.md (구독 사용자 조회 + 검색/필터) |",
        f"| **검증 일시** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| **작성자** | {AUTHOR} |",
        "| **검증 도구** | tests/req1_test_template.py |",
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

    for prefix, title in SECTIONS:
        rows = [r for r in results if section_of(r[0]) == prefix]
        if not rows:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| TC ID | 테스트 시나리오 | 기대 결과 | 실제 결과 | 판정 | 비고 |")
        lines.append("|:-----:|----------------|-----------|-----------|:----:|------|")
        for tc_id, scenario, expected, actual, passed_, note in rows:
            lines.append(f"| {tc_id} | {scenario} | {expected} | {actual} | {mark(passed_)} | {note} |")
        lines.append("")

    lines.append("## requirement_1 완료 조건 매핑")
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
    lines.append("> 본 Report 는 `tests/req1_test_template.py` 로 생성되었습니다.")
    lines.append("> TE 시나리오의 검색/필터는 app.js 규칙을 파이썬으로 재현한 시뮬레이션이며, "
                 "실제 화면 동작은 MAN 항목(브라우저 수동 확인)으로 검증합니다.")
    lines.append("> MAN 항목은 확인 후 실제 결과와 판정 칸을 직접 수정하세요.")

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return passed, failed, len(auto), pending, rate


# =============================================================================
# main
# =============================================================================
def main():
    global BASE_URL
    print("=" * 60)
    print(" requirement_1 검증")
    print("=" * 60)

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    init_call_active = run_dev_tests()

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
        subscribers, page_ok = run_api_tests()
        run_te_tests(subscribers, page_ok, init_call_active)
    finally:
        stop_server(proc)

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
