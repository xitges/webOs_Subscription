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
    const classes = {
        active: "status-active", online: "status-active", normal: "status-active",
        paused: "status-paused", standby: "status-paused",
        expired: "status-expired", error: "status-expired", warning: "status-expired",
        offline: "status-offline", on: "status-on", cleaning: "status-on", off: "status-off",
    };
    return Object.hasOwn(classes, v) ? `badge ${classes[v]}` : "badge";
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
    // 1. 선택 상태 갱신
    selectedUserId = userId;
    selectedDeviceId = null;
 
    // 2. 구독자 테이블에 선택 상태 반영
    renderSubscribers();
 
    // 3. 이전 사용 현황 초기화
    resetUsageDetail();
 
    // 4~5. 가전 목록 조회 (응답 오기 전 이전 사용자 목록이 보이지 않도록 먼저 비움)
    currentDevices = [];
    showDeviceMessage("Loading devices...");
 
    try {
        const res = await fetch(`/api/subscribers/${encodeURIComponent(userId)}/devices`);
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
 
        // 응답을 기다리는 동안 다른 사용자를 클릭했다면 이 응답은 버림
        if (selectedUserId !== userId) return;
 
        currentDevices = Array.isArray(data) ? data : [];
    } catch (err) {
        if (selectedUserId !== userId) return;
        console.error(`Failed to fetch devices for ${userId}:`, err);
        currentDevices = [];
        showDeviceMessage("Failed to load devices.");
        return;
    }
 
    // 6. 가전 테이블 렌더링
    renderDevices();
}
    // 가전 패널에 안내 메시지만 표시하고 테이블은 숨김
function showDeviceMessage(message) {
    const emptyEl = document.getElementById("device-empty");
    const tableEl = document.getElementById("device-table");
    emptyEl.textContent = message;
    emptyEl.classList.remove("hidden");
    tableEl.classList.add("hidden");
    document.getElementById("device-body").innerHTML = "";
}
 
// 사용 현황 패널을 초기 상태로 되돌림
function resetUsageDetail(message = "Select a device to view usage details.") {
    const usageEmpty = document.getElementById("usage-empty");
    usageEmpty.textContent = message;
    usageEmpty.classList.remove("hidden");
    document.getElementById("usage-detail").classList.add("hidden");
    document.getElementById("usage-info").innerHTML = "";
    if (usageChart) {
        usageChart.destroy();
        usageChart = null;
    }

}

// TODO [요구사항 #2-B]: currentDevices 배열을 테이블에 렌더링하세요.
//
function renderDevices() {
    const emptyEl = document.getElementById("device-empty");
    const tableEl = document.getElementById("device-table");
    const tbody = document.getElementById("device-body");
    const search = document.getElementById("device-search").value.toLowerCase();
    const statusFilter = document.getElementById("device-status-filter").value;

    // 아직 구독자를 선택하지 않은 상태에서 검색/필터를 건드린 경우
    if (!selectedUserId) {
        showDeviceMessage("Select a subscriber to view devices.");
        return;
    }
 
    // 2. 검색어(부분 문자열) + 상태 필터를 동시에 만족하는 가전만 남김
    const filtered = currentDevices.filter((d) => {
        const matchesSearch = [d.type, d.model, d.status, d.deviceId, d.location]
            .some((field) => String(field ?? "").toLowerCase().includes(search));
        const matchesStatus = !statusFilter || d.status === statusFilter;
        return matchesSearch && matchesStatus;
    });
 
    // 3. 안내 메시지 / 테이블 표시 전환
    if (currentDevices.length === 0) {
        showDeviceMessage("No registered devices");
        return;
    }
    if (filtered.length === 0) {
        showDeviceMessage("No devices matched");
        return;
    }
    emptyEl.classList.add("hidden");
    tableEl.classList.remove("hidden");
 
    // 4. 행 렌더링
    tbody.innerHTML = "";
    filtered.forEach((d) => {
        const tr = document.createElement("tr");
        tr.className = "clickable";
        if (d.deviceId === selectedDeviceId) {
            tr.classList.add("selected");
        }
 
        [d.deviceId, d.type, d.model, d.location].forEach((value) => {
            const td = document.createElement("td");
            td.textContent = value;
            tr.appendChild(td);
        });
 
        const statusTd = document.createElement("td");
        statusTd.appendChild(createBadge(d.status));
        tr.appendChild(statusTd);
 
        // 5. 행 클릭 시 사용 현황 조회
        tr.addEventListener("click", () => selectDevice(d.deviceId));
        tbody.appendChild(tr);
    });
}
 
function createBadge(value) {
    const badge = document.createElement("span");
    badge.className = badgeClass(value);   // 요구사항 #3 완료 시 색상 자동 적용
    badge.textContent = value;
    return badge;
}

// TODO [요구사항 #2-C]: 가전 클릭 시 상세 사용 현황을 조회하세요.
//
async function selectDevice(deviceId) {
   // 1~2. 선택 상태 갱신 + 테이블에 반영
    selectedDeviceId = deviceId;
    renderDevices();
 
    // 3. 사용 현황 조회
    let data;
    try {
        const res = await fetch(`/api/devices/${encodeURIComponent(deviceId)}/usage`);
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        data = await res.json();
    } catch (err) {
        if (selectedDeviceId !== deviceId) return;
        console.error(`Failed to fetch usage for ${deviceId}:`, err);
        resetUsageDetail("Failed to load usage details.");
        return;
    }
 
    // 응답을 기다리는 동안 다른 가전/사용자를 클릭했다면 이 응답은 버림
    if (selectedDeviceId !== deviceId || !data) return;
 
    // 4. 패널 전환
    document.getElementById("usage-empty").classList.add("hidden");
    document.getElementById("usage-detail").classList.remove("hidden");
 
    // 5. 상세 정보 렌더링 (label / value 2열 그리드)
    const info = document.getElementById("usage-info");
    info.innerHTML = "";
    const rows = [
        ["Device ID", data.deviceId],
        ["Device Name", data.deviceName],
        ["Power Status", createBadge(data.powerStatus)],
        ["Last Used", data.lastUsedAt],
        ["Total Usage", `${data.totalUsageHours} hrs`],
        ["Weekly Count", data.weeklyUsageCount],
        ["Health Status", createBadge(data.healthStatus)],
        ["Remark", data.remark],
    ];
    rows.forEach(([label, value]) => {
        const labelEl = document.createElement("div");
        labelEl.className = "label";
        labelEl.textContent = label;
 
        const valueEl = document.createElement("div");
        valueEl.className = "value";
        if (value instanceof Node) {
            valueEl.appendChild(value);
        } else {
            valueEl.textContent = value ?? "-";
        }
 
        info.append(labelEl, valueEl);
    });
 
    // 6. 주간 사용량 차트
    renderUsageChart(data.weeklyUsageTrend || []);
}

// TODO [요구사항 #2-D]: Chart.js를 사용하여 주간 사용량 Bar Chart를 그리세요.
//
function renderUsageChart(trend) {
    const ctx = document.getElementById("usageChart");
    // 1. 기존 차트 제거 (같은 canvas에 새 차트를 그리려면 반드시 필요)
    if (usageChart) {
        usageChart.destroy();
        usageChart = null;
    }
 
    // Chart.js CDN 로드에 실패한 경우 상세 정보는 그대로 두고 차트만 생략
    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded.");
        return;
    }
 
    // 2. Bar Chart 생성
    usageChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            datasets: [{
                label: "Weekly Usage Trend",
                data: trend,
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 } },
            },
        },
    });
}


// =============================================================================
// 이벤트 바인딩 + 초기화
// =============================================================================
function bindEvents() {
    // [요구사항 #1] 완료 후 아래 주석을 해제하세요
    document.getElementById("subscriber-search").addEventListener("input", renderSubscribers);
    document.getElementById("subscriber-status-filter").addEventListener("change", renderSubscribers);

    // [요구사항 #2] 완료 후 아래 주석을 해제하세요
    document.getElementById("device-search").addEventListener("input", renderDevices);
    document.getElementById("device-status-filter").addEventListener("change", renderDevices);
}

bindEvents();

// [요구사항 #1] 완료 후 아래 주석을 해제하세요
fetchSubscribers();
