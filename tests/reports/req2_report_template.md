# requirement_2 검증 Report

| 항목 | 내용 |
|------|------|
| **프로젝트** | webOS Subscription Management Dashboard |
| **검증 대상** | requirement_2.md (가전 목록 조회 + 사용 현황 + 차트) |
| **검증 일시** | 2026-10-01 17:34:15 |
| **작성자** | (여기에 이름을 적으세요) |
| **검증 도구** | tests/req2_test_template.py |

## 요약

| 구분 | 전체 | PASS | FAIL | 확인 필요 |
|:----:|:----:|:----:|:----:|:---------:|
| 1. 개발자 테스트 (코드/구현 검증) | 10 | 10 | 0 | 0 |
| 2. API 테스트 (실행 검증) | 9 | 9 | 0 | 0 |
| 3. TE 테스트 시나리오 | 43 | 40 | 0 | 3 |
| 4. 수동 확인 (브라우저) | 12 | 0 | 0 | 12 |
| **합계** | **74** | **59** | **0** | **15** |

**자동 검증 Pass Rate: 59 / 59 = 100.0%** (확인 필요 15건 제외)

**종합 판정: ✅ 자동 검증 통과 — 수동 확인 항목 완료 후 PM 에게 전달**

## 1. 개발자 테스트 (코드/구현 검증)

| TC ID | 테스트 시나리오 | 기대 결과 | 실제 결과 | 판정 | 비고 |
|:-----:|----------------|-----------|-----------|:----:|------|
| DEV-01 | subscribers.py / devices.py 문법 검사(py_compile) | 컴파일 오류 없음 | 컴파일 성공 | ✅ PASS |  |
| DEV-02 | get_devices_by_user("U001") 직접 호출 | D001, D002 list 반환 | ['D001', 'D002'] | ✅ PASS |  |
| DEV-03 | get_devices_by_user("U999") 직접 호출 | HTTPException(404) 발생 | HTTPException(404) | ✅ PASS |  |
| DEV-04 | get_device_usage("D001") 직접 호출 | deviceId=D001 인 dict 반환 | deviceId=D001 | ✅ PASS |  |
| DEV-05 | get_device_usage("D999") 직접 호출 | HTTPException(404) 발생 | HTTPException(404) | ✅ PASS |  |
| DEV-06 | selectSubscriber() 구현 (정적 검사) | 선택 갱신 + renderSubscribers + 사용 현황 초기화 + devices fetch + renderDevices | deviceId=null=O, renderSubscribers=O, usage 초기화=O, fetch=O, currentDevices=O, renderDevices=O | ✅ PASS |  |
| DEV-07 | renderDevices() 구현 (정적 검사) | 검색(5개 필드)/필터 + 안내 메시지 2종 + <tr> 렌더링 + 행 클릭 시 selectDevice | filter=O, 검색필드5=O, No registered=O, No matched=O, tr=O, selectDevice=O | ✅ PASS |  |
| DEV-08 | selectDevice() 구현 (정적 검사) | renderDevices + usage fetch + 패널 전환 + 상세 필드 렌더링 + renderUsageChart(weeklyUsageTrend) | renderDevices=O, fetch=O, 패널 전환=O, 상세 필드=O, renderUsageChart=O | ✅ PASS |  |
| DEV-09 | renderUsageChart() 구현 (정적 검사) | 기존 차트 destroy + bar 차트 + Mon~Sun 라벨 + data=trend + responsive/beginAtZero | destroy=O, new Chart=O, bar=O, Mon~Sun=O, data=trend=O, beginAtZero=O, responsive=O | ✅ PASS |  |
| DEV-10 | 가전 검색/필터 이벤트 리스너 주석 해제 | device-search input + device-status-filter change → renderDevices | input=O, change=O | ✅ PASS |  |

## 2. API 테스트 (실행 검증)

| TC ID | 테스트 시나리오 | 기대 결과 | 실제 결과 | 판정 | 비고 |
|:-----:|----------------|-----------|-----------|:----:|------|
| API-01 | GET /health 호출 | 200 OK | status=200 | ✅ PASS | {"status": "ok"} |
| API-02 | GET /api/subscribers/U001/devices 호출 | 200 OK + JSON 배열(D001, D002) | status=200, ids=['D001', 'D002'] | ✅ PASS |  |
| API-03 | 가전 항목 스키마 검증 (전체 구독자) | 필드 deviceId, type, model, location, status, lastSeen + status ∈ Online/Offline/Standby/Error | 정상 | ✅ PASS |  |
| API-04 | GET /api/subscribers/U005/devices 호출 | 200 OK + 빈 배열 [] | status=200, body=[] | ✅ PASS |  |
| API-05 | GET /api/subscribers/U999/devices 호출 | 404 + {"detail": ...} | status=404, body={"detail": "User 'U999' not found"} | ✅ PASS |  |
| API-06 | GET /api/devices/D001/usage 호출 | 200 OK + D001 사용 현황 JSON 객체 | status=200, type=dict | ✅ PASS |  |
| API-07 | 사용 현황 스키마 검증 (전체 가전) | 필드 9개 + weeklyUsageTrend 길이 7, 0 이상 숫자 | 정상 | ✅ PASS |  |
| API-08 | GET /api/devices/D999/usage 호출 | 404 + {"detail": ...} | status=404, body={"detail": "Device 'D999' not found"} | ✅ PASS |  |
| API-09 | GET / 가전·사용 현황 영역 확인 | 가전 테이블/검색/상태 필터(4종) + usage-info + usageChart canvas + Chart.js 로드 | status=200, device-table=O, device-search=O, 필터옵션4=O, usage-info=O, usageChart=O, chart.js=O | ✅ PASS |  |

## 3. TE 테스트 시나리오

> [A] 완료 조건 보완 · [B] 검색·필터 경계 · [C] 상태 전환 · [D] 상세/Badge · [E] 차트 · [F] 데이터 정합성 · [G] 회귀

| TC ID | 테스트 시나리오 | 기대 결과 | 실제 결과 | 판정 | 비고 |
|:-----:|----------------|-----------|-----------|:----:|------|
| TE-1 | /api/subscribers/U001/devices 호출 | 2개 가전 JSON 반환 | 2개: ['D001', 'D002'] | ✅ PASS |  |
| TE-2 | /api/subscribers/U005/devices 호출 | 빈 배열 [] 반환 | status=200, body=[] | ✅ PASS |  |
| TE-3 | /api/subscribers/U999/devices 호출 | 404 에러 반환 | status=404 | ✅ PASS |  |
| TE-4 | U001 클릭 시 가전 Table 표시 | D001, D002 표시 | 2개: ['D001', 'D002'] / FE 구현 O | ✅ PASS | 실제 화면은 MAN-1 에서 확인 |
| TE-5 | U005 클릭 시 안내 메시지 | "No registered devices" 표시 | "No registered devices" 메시지 | ✅ PASS | 실제 화면은 MAN-2 에서 확인 |
| TE-6 | U001 가전 검색 "TV" 입력 | TV 타입만 표시 (D001) | 1개: ['D001'] | ✅ PASS | 검색/필터 로직 시뮬레이션 |
| TE-7 | U001 가전 상태 필터 "Online" 선택 | Online 가전만 표시 (D001) | 1개: ['D001'] | ✅ PASS | 검색/필터 로직 시뮬레이션 |
| TE-8 | /api/devices/D001/usage 호출 | 사용 현황 JSON 반환 | status=200, deviceName=LG OLED evo C4 | ✅ PASS |  |
| TE-9 | /api/devices/D999/usage 호출 | 404 에러 반환 | status=404 | ✅ PASS |  |
| TE-10 | D001 클릭 시 사용 현황 표시 | 전원상태, 누적시간 등 표시 | API 필드 O / FE 구현 O | ✅ PASS | 실제 화면은 MAN-4 에서 확인 |
| TE-11 | D001 클릭 시 Bar Chart 표시 | 요일별(7일) 사용량 차트 | trend=[2, 3, 1, 4, 2, 3, 3] / 차트 구현 O | ✅ PASS | 실제 차트는 MAN-5 에서 확인 |
| TE-12 | 다른 가전 클릭 시 차트 갱신 | 이전 차트 제거, 새 차트 표시 | destroy() 호출 O | ✅ PASS | 실제 갱신은 MAN-6 에서 확인 |
| TE-13 | U001 모델명 검색 "WashTower" | D002만 표시 | 1개: ['D002'] | ✅ PASS | [A] 모델명 기준 검색 |
| TE-14 | U001 위치 검색 "Dormitory" | D001만 표시 | 1개: ['D001'] | ✅ PASS | [A] 위치 기준 검색 |
| TE-15 | U001 상태값 검색 "Offline" | D002만 표시 | 1개: ['D002'] | ✅ PASS | [A] 상태값 기준 검색 |
| TE-16 | U001 deviceId 검색 "D002" | D002만 표시 | 1개: ['D002'] | ✅ PASS | [A] deviceId 기준 검색 |
| TE-17 | U001 상태 필터 "Offline" 선택 | D002만 표시 | 1개: ['D002'] | ✅ PASS | [A] Offline 필터 |
| TE-18 | U004 상태 필터 "Standby" 선택 | D008만 표시 | 1개: ['D008'] | ✅ PASS | [A] Standby 필터 |
| TE-19 | U003 상태 필터 "Error" 선택 | D006만 표시 | 1개: ['D006'] | ✅ PASS | [A] Error 필터 |
| TE-20 | U002 상태 필터 "Error" 선택 (결과 0건) | "No devices matched" 표시 | "No devices matched" 메시지 | ✅ PASS | [A] 필터 결과 0건 안내 |
| TE-21 | 대소문자 무시 ("tv" @U001, "TV" @U003) | tv → D001 / TV → D004 | tv → ['D001'] / TV → ['D004'] | ✅ PASS | [B] 대소문자 무시 매칭 |
| TE-22 | U003 검색 "TV" + 필터 "Online" | D004만 표시 | 1개: ['D004'] | ✅ PASS | [B] 검색+필터 조합 |
| TE-23 | U003 검색 "TV" + 필터 "Error" (교집합 없음) | "No devices matched" 표시 | "No devices matched" 메시지 | ✅ PASS | [B] 검색+필터 조합 |
| TE-24 | U003 검색어 삭제 + All Status 복귀 | 전체 목록(D004, D005, D006) 복원 | 조건 적용 ['D004'] → 해제 후 ['D004', 'D005', 'D006'] | ✅ PASS | [B] 검색/필터 로직 시뮬레이션 |
| TE-25 | U001 앞 공백 포함 " TV" 검색 | 명세 미정의 (trim 여부) | "No devices matched" 메시지 | ⬜ 확인 필요 | [B] 공백 미제거 시 0건 — 의도된 동작인지 PM 확인 필요 |
| TE-26 | U003 "Off" 검색 (부분 매칭 부작용) | D005 표시 (location "Office" 부분 매칭) | 1개: ['D005'] | ✅ PASS | [B] 명세상 정상. Offline 가전을 찾으려는 사용자에게 Online 가전이 보일 수 있음(관찰) |
| TE-27 | 가전 선택 후 다른 구독자 클릭 시 초기화 | usage-empty 표시, usage-detail 숨김, usage-info 비움, 차트 제거 | 초기화+destroy O | ✅ PASS | [C] 정적 검사, 실제 화면은 MAN-7 |
| TE-28 | "TV" 검색 상태에서 다른 구독자(U002) 클릭 | 명세 미정의 (검색어 유지/초기화) | 검색어 유지 → U002 에서 "No devices matched" 메시지 | ⬜ 확인 필요 | [C] 의도된 동작인지 PM 확인 필요 (MAN-8) |
| TE-29 | 빠른 연속 클릭 시 늦게 온 응답 무시 (경쟁 상태) | selectSubscriber / selectDevice 에 최신 선택 확인 로직 | 구독자 가드 O, 가전 가드 O | ✅ PASS | [C] 정적 검사, 실제 동작은 MAN-10 |
| TE-30 | API 실패(서버 다운/에러 응답) 시 처리 | res.ok 확인 + 실패 안내 메시지 표시 | devices res.ok=O, devices 실패 메시지=O, usage res.ok=O, usage 실패 메시지=O | ✅ PASS | [C] 정적 검사, 실제 동작은 MAN-11 |
| TE-31 | Power Status / Health Status badge 렌더링 | 두 값 모두 badge(span) 로 표시 | createBadge(powerStatus/healthStatus) O | ✅ PASS | [D] 정적 검사 |
| TE-32 | 사용 현황의 모든 상태값에 대응하는 CSS 클래스 존재 | On/Off/Standby/Error/Cleaning/Normal/Warning → .status-* 정의 | 값 ['Cleaning', 'Error', 'Normal', 'Off', 'On', 'Standby', 'Warning'] / 누락 [] | ✅ PASS | [D] style.css 검사 |
| TE-33 | badge 색상 적용 (badgeClass 매핑) | 상태값별 status-* 클래스 반환 | badgeClass 구현됨 | ✅ PASS | [D] 요구사항 #3 범위 — req3 완료 후 MAN-12 에서 색상 확인 |
| TE-34 | D001 상세 값 표시 형식 | Last Used 2026-03-22 10:10:00 / Total 152 hrs / Weekly 18 | {'Last Used': '2026-03-22 10:10:00', 'Total Usage': '152 hrs', 'Weekly Count': 18} / hrs 표기 O | ✅ PASS | [D] API 값 + FE 표기 형식 |
| TE-35 | D001 차트 데이터/라벨 | [2,3,1,4,2,3,3], 라벨 Mon~Sun | trend=[2, 3, 1, 4, 2, 3, 3], 라벨 O | ✅ PASS | [E] |
| TE-36 | D002 (작은 값, 0 포함) 차트 y축 | y축 0부터 시작 (beginAtZero) | trend=[0, 1, 0, 1, 1, 0, 1], beginAtZero O | ✅ PASS | [E] |
| TE-37 | 모든 가전의 주간 사용량 길이 | 8개 가전 모두 7일치 데이터 | 8개 중 이상 [] | ✅ PASS | [E] |
| TE-38 | 구독자 deviceCount 와 실제 가전 수 일치 | U001=2, U002=1, U003=3, U004=2, U005=0 | 전원 일치 | ✅ PASS | [F] |
| TE-39 | 가전 목록의 모든 deviceId 로 usage 조회 | D001~D008 모두 200 + JSON 객체 | 8개 조회, 실패 [] | ✅ PASS | [F] |
| TE-40 | usage 응답과 가전 목록의 일관성 | deviceId 일치, deviceName == 목록의 model | 전부 일치 | ✅ PASS | [F] |
| TE-41 | deviceId 전역 고유성 | 사용자 간 중복 deviceId 없음 | 8개, 중복 [] | ✅ PASS | [F] |
| TE-42 | 소문자 ID 요청 ("u001", "d001") | 명세 미정의 (대소문자 구분 여부) | u001 → 404, d001 → 404 | ⬜ 확인 필요 | [F] 현재 대소문자를 구분함 — 의도된 동작인지 PM 확인 필요 |
| TE-43 | req1 회귀 테스트 (tests/req1_test_template.py) | req1 자동 검증 전부 PASS | exit=0 자동 검증: PASS 27 / FAIL 0 (총 27) - 100.0% | ✅ PASS | [G] req1 Report 파일이 새로 생성됨 |

## 4. 수동 확인 (브라우저)

| TC ID | 테스트 시나리오 | 기대 결과 | 실제 결과 | 판정 | 비고 |
|:-----:|----------------|-----------|-----------|:----:|------|
| MAN-1 | U001 행 클릭 | 가전 Table 에 D001, D002 표시 + U001 행 강조(selected) |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-2 | U005 행 클릭 | "No registered devices" 안내 메시지 표시 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-3 | 가전 검색어 타이핑 / 상태 필터 변경 | Enter 없이 즉시 결과 반영 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-4 | D001 행 클릭 | Device ID ~ Remark 8개 항목 표시 + D001 행 강조 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-5 | D001 Bar Chart 확인 | Mon~Sun 7개 막대, y축 0부터 시작 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-6 | D001 → D002 클릭 | 차트가 D002 데이터로 교체(겹침/깜빡임 없음), 콘솔(F12) 오류 없음 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-7 | D001 선택 후 U002 클릭 | 사용 현황 패널 초기화 + 차트 제거 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-8 | "TV" 검색 상태에서 U002 클릭 | 검색어 유지 여부 관찰 (TE-28 참고) |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-9 | D001 선택 후 상태 필터 "Offline" 선택 | D001 이 목록에서 사라질 때 사용 현황 패널 상태 관찰 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-10 | D001 / D002 를 빠르게 번갈아 클릭 | 마지막으로 클릭한 가전의 정보만 표시 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-11 | 서버 종료 후 구독자/가전 클릭 | "Failed to load devices." / "Failed to load usage details." 표시 |  | ⬜ 확인 필요 | 브라우저 수동 확인 |
| MAN-12 | Power/Health Status badge 색상 | 상태별 색상 적용 (요구사항 #3 완료 후 확인) |  | ⬜ 확인 필요 | 브라우저 수동 확인 |

## requirement_2 완료 조건 매핑

| 완료 조건 | 관련 TC | 자동 검증 판정 |
|-----------|---------|:----:|
| GET /api/subscribers/{userId}/devices API 정상 동작 | DEV-02, API-02, API-03, API-04, TE-1, TE-2, TE-38 | ✅ |
| 구독자 행 클릭 시 가전 목록 Table 표시 | DEV-06, DEV-07, TE-4, MAN-1 | ✅ |
| 가전 없는 사용자 선택 시 안내 메시지 | TE-5, MAN-2 | ✅ |
| 모델명/타입/상태/위치 기준 검색 | TE-6, TE-13, TE-14, TE-15, TE-16, TE-21 | ✅ |
| Online/Offline/Standby/Error 상태 필터 | DEV-10, TE-7, TE-17, TE-18, TE-19, TE-20 | ✅ |
| 존재하지 않는 사용자 ID 404 | DEV-03, API-05, TE-3 | ✅ |
| GET /api/devices/{deviceId}/usage API 정상 동작 | DEV-04, API-06, API-07, TE-8, TE-39, TE-40 | ✅ |
| 가전 행 클릭 시 사용 현황 표시 | DEV-08, TE-10, TE-31, TE-34, MAN-4 | ✅ |
| 주간 사용량 Bar Chart(요일 기준) 표시 | DEV-09, TE-11, TE-12, TE-35, TE-36, MAN-5 | ✅ |
| 존재하지 않는 디바이스 ID 404 | DEV-05, API-08, TE-9 | ✅ |

---

> 본 Report 는 `tests/req2_test_template.py` 로 생성되었습니다.
> TE 시나리오의 검색/필터는 app.js 규칙을 파이썬으로 재현한 시뮬레이션이며, [C] 상태 전환은 app.js 정적 검사입니다. 실제 화면 동작은 MAN 항목으로 검증합니다.
> '확인 필요' 항목은 명세 미정의 동작이므로 PM 에게 의도 여부를 확인받고, MAN 항목은 확인 후 실제 결과와 판정 칸을 직접 수정하세요.
