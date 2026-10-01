// =============================================================================
// 전역 변수
// =============================================================================
let subscribers = [];
let currentDevices = [];
let selectedUserId = null;
let selectedDeviceId = null;
let usageChart = null;


// =============================================================================
// [요구사항 #3] 상태 기반 Badge 스타일
// =============================================================================
// TODO [요구사항 #3]: 상태 값(value)에 따라 적절한 CSS 클래스를 반환하세요.
//
function badgeClass(value) {
    const v = (value || "").toLowerCase();

    // 매핑 규칙:
    // Active, Online, Normal   → "badge status-active"   (초록)
    // Paused, Standby          → "badge status-paused"   (파랑)
    // Expired, Error, Warning  → "badge status-expired"  (빨강)
    // Offline                  → "badge status-offline"  (회색)
    // On, Cleaning             → "badge status-on"       (노랑)
    // Off                      → "badge status-off"      (연회색)
    // 그 외                     → "badge"
    return "badge";
}


// =============================================================================
// [요구사항 #1] 구독 사용자 조회 + 검색/필터
// =============================================================================

// TODO [요구사항 #1-A]: GET /api/subscribers 를 호출하여
//   subscribers 변수에 저장하고 renderSubscribers()를 호출하세요.
//
async function fetchSubscribers() {
    try {
        // 1. GET /api/subscribers 호출
        const res = await fetch("/api/subscribers");
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
 
        // 2. 응답을 subscribers 변수에 저장 (BE가 아직 null을 주는 경우 대비)
        const data = await res.json();
        subscribers = Array.isArray(data) ? data : [];
    } catch (err) {
        console.error("Failed to fetch subscribers:", err);
        subscribers = [];
    }
 
    // 3. renderSubscribers() 호출
    renderSubscribers();
}

// TODO [요구사항 #1-B]: subscribers 배열을 테이블에 렌더링하세요.
//
function renderSubscribers() {
    const tbody = document.getElementById("subscriber-body");
    const search = document.getElementById("subscriber-search").value.toLowerCase();
    const statusFilter = document.getElementById("subscriber-status-filter").value;
    
    // 1. 검색어와 상태 필터 값 가져오기
    // 2. subscribers 배열 필터링
    //    - 검색: name, plan, status, userId에 대해 부분 문자열 매칭
    //    - 필터: status가 선택된 값과 일치
    // 3. <tbody>에 <tr> 렌더링
    //    - 표시 컬럼: userId, name, plan, status, deviceCount
    //    - 각 행 클릭 시 selectSubscriber(userId) 호출
    //    - 선택된 행(selectedUserId)에 "selected" 클래스 추가
 
    // 2. 검색어(부분 문자열) + 상태 필터를 동시에 만족하는 사용자만 남김
    const filtered = subscribers.filter((u) => {
        const matchesSearch = [u.name, u.plan, u.status, u.userId]
            .some((field) => String(field ?? "").toLowerCase().includes(search));
        const matchesStatus = !statusFilter || u.status === statusFilter;
        return matchesSearch && matchesStatus;
    });
 
    // 3. 기존 행을 지우고 다시 렌더링
    tbody.innerHTML = "";
 
    if (filtered.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 5;
        td.className = "empty-msg";
        td.textContent = subscribers.length === 0
            ? "No subscribers found."
            : "No subscribers matched.";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }
 
    filtered.forEach((u) => {
        const tr = document.createElement("tr");
        tr.className = "clickable";
        if (u.userId === selectedUserId) {
            tr.classList.add("selected");
        }
 
        // 텍스트는 textContent로 넣어 HTML 주입을 방지
        [u.userId, u.name, u.plan].forEach((value) => {
            const td = document.createElement("td");
            td.textContent = value;
            tr.appendChild(td);
        });
 
        const statusTd = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = badgeClass(u.status);   // 요구사항 #3 완료 시 색상 자동 적용
        badge.textContent = u.status;
        statusTd.appendChild(badge);
        tr.appendChild(statusTd);
 
        const countTd = document.createElement("td");
        countTd.textContent = u.deviceCount;
        tr.appendChild(countTd);
 
        tr.addEventListener("click", () => selectSubscriber(u.userId));
        tbody.appendChild(tr);
    });
}


// =============================================================================
// [요구사항 #2] 사용자별 가전 목록 + 사용 현황 + 차트
// =============================================================================

// TODO [요구사항 #2-A]: 사용자 클릭 시 해당 사용자의 가전 목록을 조회하세요.
//
async function selectSubscriber(userId) {
    // 여기에 구현하세요
    // 1. selectedUserId 업데이트, selectedDeviceId = null
    // 2. renderSubscribers() 호출 (선택 상태 반영)
    // 3. 이전 사용 현황 초기화:
    //    - usage-empty 표시, usage-detail 숨기기
    //    - usage-info 내용 비우기
    // 4. GET /api/subscribers/{userId}/devices 호출
    // 5. currentDevices에 저장
    // 6. renderDevices() 호출
}

// TODO [요구사항 #2-B]: currentDevices 배열을 테이블에 렌더링하세요.
//
function renderDevices() {
    const emptyEl = document.getElementById("device-empty");
    const tableEl = document.getElementById("device-table");
    const tbody = document.getElementById("device-body");
    const search = document.getElementById("device-search").value.toLowerCase();
    const statusFilter = document.getElementById("device-status-filter").value;

    // 여기에 구현하세요
    // 1. 검색어, 상태 필터 값 가져오기
    // 2. currentDevices 배열 필터링
    //    - 검색: type, model, status, deviceId, location 부분 매칭
    //    - 필터: status 일치
    // 3. 가전이 없으면 → "No registered devices" 메시지 표시
    //    필터 결과가 없으면 → "No devices matched" 메시지 표시
    //    결과 있으면 → device-table 표시
    // 4. <tbody>에 deviceId, type, model, location, status(badge) 렌더링
    // 5. 각 행 클릭 시 selectDevice(deviceId) 호출
}

// TODO [요구사항 #2-C]: 가전 클릭 시 상세 사용 현황을 조회하세요.
//
async function selectDevice(deviceId) {
    // 여기에 구현하세요
    // 1. selectedDeviceId 업데이트
    // 2. renderDevices() 호출 (선택 상태 반영)
    // 3. GET /api/devices/{deviceId}/usage 호출
    // 4. usage-empty 숨기기, usage-detail 표시
    // 5. usage-info에 상세 정보 렌더링:
    //    - Device ID, Device Name
    //    - Power Status (badge 스타일 적용)
    //    - Last Used, Total Usage Hours, Weekly Usage Count
    //    - Health Status (badge 스타일 적용)
    //    - Remark
    // 6. renderUsageChart(data.weeklyUsageTrend) 호출
}

// TODO [요구사항 #2-D]: Chart.js를 사용하여 주간 사용량 Bar Chart를 그리세요.
//
function renderUsageChart(trend) {
    const ctx = document.getElementById("usageChart");
    // 여기에 구현하세요

    // 1. 기존 차트 있으면 destroy()
    // 2. new Chart() 생성
    //    - type: "bar"
    //    - labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    //    - data: trend 배열
    //    - options: responsive, beginAtZero
}


// =============================================================================
// 이벤트 바인딩 + 초기화
// =============================================================================
function bindEvents() {
    // [요구사항 #1] 완료 후 아래 주석을 해제하세요
    // document.getElementById("subscriber-search").addEventListener("input", renderSubscribers);
    // document.getElementById("subscriber-status-filter").addEventListener("change", renderSubscribers);

    // [요구사항 #2] 완료 후 아래 주석을 해제하세요
    // document.getElementById("device-search").addEventListener("input", renderDevices);
    // document.getElementById("device-status-filter").addEventListener("change", renderDevices);
}

bindEvents();

// [요구사항 #1] 완료 후 아래 주석을 해제하세요
// fetchSubscribers();
