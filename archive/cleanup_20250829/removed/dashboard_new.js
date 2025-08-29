// 대시보드 JavaScript - 서버 상태만 표시하는 단순한 모니터

// 전역 변수
let statusUpdateInterval = null;
let countdownInterval = null;
let serverStatus = null;

// 자동 거래 토글
function toggleAutoTrading(enable) {
    const action = enable ? '활성화' : '비활성화';
    if (!confirm(`자동 거래를 ${action}하시겠습니까?`)) {
        return;
    }
    
    fetch('/api/trading/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: enable ? 'enable' : 'disable' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('success', `자동 거래가 ${action}되었습니다.`);
            // 즉시 상태 업데이트
            updateServerStatus();
        } else {
            showAlert('danger', data.message || '오류가 발생했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('danger', '자동 거래 토글 중 오류가 발생했습니다.');
    });
}

// 긴급 정지
function emergencyStop() {
    if (!confirm('긴급 정지하시겠습니까? 모든 자동 거래가 즉시 중단됩니다.')) {
        return;
    }
    
    fetch('/api/emergency_stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('danger', '긴급 정지가 실행되었습니다.');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('danger', data.message || '긴급 정지 실행 중 오류가 발생했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('danger', '긴급 정지 실행 중 오류가 발생했습니다.');
    });
}

// 서버 상태 업데이트 (파일 기반)
async function updateServerStatus() {
    try {
        const response = await fetch('/api/auto_trading_status');
        const data = await response.json();
        
        if (data.success && data.status) {
            serverStatus = data.status;
            
            // UI 업데이트
            updateUI();
        }
    } catch (error) {
        console.error('Error updating server status:', error);
    }
}

// UI 업데이트
function updateUI() {
    if (!serverStatus) return;
    
    // 자동 거래 상태 업데이트
    const container = document.getElementById('trading-status-container');
    if (container) {
        const enabled = serverStatus.auto_trading_enabled;
        container.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                ${enabled ? 
                    `<span class="badge bg-success">활성화</span>
                     <button class="btn btn-sm btn-warning" onclick="toggleAutoTrading(false)">
                         <i class="fas fa-pause"></i> 일시정지
                     </button>` :
                    `<span class="badge bg-secondary">비활성화</span>
                     <button class="btn btn-sm btn-success" onclick="toggleAutoTrading(true)">
                         <i class="fas fa-play"></i> 시작
                     </button>`
                }
                <button class="btn btn-sm btn-danger" onclick="emergencyStop()">
                    <i class="fas fa-stop"></i> 긴급정지
                </button>
            </div>
        `;
    }
    
    // 다음 실행 시간 표시 (서버 시간 그대로)
    const nextTradeElement = document.getElementById('next-trade-time');
    if (nextTradeElement && serverStatus.next_execution) {
        // ISO 형식을 읽기 쉬운 형식으로 변환
        const nextTime = new Date(serverStatus.next_execution);
        const timeStr = nextTime.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
        nextTradeElement.textContent = timeStr;
        
        // 카운트다운 업데이트
        updateCountdown(nextTime);
    }
    
    // 마지막 실행 시간 표시
    const lastTradeElement = document.getElementById('last-trade-time');
    if (lastTradeElement && serverStatus.last_execution) {
        const lastTime = new Date(serverStatus.last_execution);
        const timeStr = lastTime.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
        lastTradeElement.textContent = timeStr;
    }
}

// 카운트다운 업데이트
function updateCountdown(nextTime) {
    if (!nextTime) return;
    
    const now = new Date();
    const diff = nextTime - now;
    
    if (diff <= 0) {
        document.getElementById('countdown-display').textContent = '분석 중...';
        // 곧 실행될 예정이므로 더 자주 상태 체크
        setTimeout(updateServerStatus, 2000);
    } else {
        const minutes = Math.floor(diff / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        document.getElementById('countdown-display').textContent = 
            `${minutes}분 ${seconds}초 남음`;
    }
}

// 분석 이력 로드
async function loadAnalysisHistory() {
    try {
        const response = await fetch('/api/analysis/latest?limit=10');
        const data = await response.json();
        
        if (data.success && data.analyses) {
            displayAnalysisHistory(data.analyses);
        }
    } catch (error) {
        console.error('Error loading analysis history:', error);
    }
}

// 분석 이력 표시
function displayAnalysisHistory(analyses) {
    const container = document.getElementById('analysis-history');
    if (!container) return;
    
    if (analyses.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="fas fa-robot"></i><br>
                분석 기록이 없습니다
            </div>
        `;
        return;
    }
    
    let html = '<div class="list-group">';
    analyses.forEach(analysis => {
        const time = new Date(analysis.timestamp).toLocaleString('ko-KR');
        const actionClass = analysis.action === 'buy' ? 'text-success' : 
                           analysis.action === 'sell' ? 'text-danger' : 'text-secondary';
        
        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <small class="text-muted">${time}</small>
                        <div>
                            <span class="${actionClass} fw-bold">
                                ${analysis.action.toUpperCase()}
                            </span>
                            <span class="ms-2">신뢰도: ${(analysis.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <small class="text-muted">${analysis.reasoning || ''}</small>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

// 알림 표시
function showAlert(type, message) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) {
        // 알림 컨테이너가 없으면 생성
        const container = document.createElement('div');
        container.id = 'alert-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.getElementById('alert-container').appendChild(alert);
    
    // 5초 후 자동 제거
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initialized - Server monitoring mode');
    
    // 초기 상태 로드
    updateServerStatus();
    loadAnalysisHistory();
    
    // 5초마다 상태 업데이트
    statusUpdateInterval = setInterval(updateServerStatus, 5000);
    
    // 1초마다 카운트다운 업데이트 (로컬에서만)
    countdownInterval = setInterval(() => {
        if (serverStatus && serverStatus.next_execution) {
            updateCountdown(new Date(serverStatus.next_execution));
        }
    }, 1000);
    
    // 30초마다 분석 이력 업데이트
    setInterval(loadAnalysisHistory, 30000);
});

// 나머지 기존 함수들 (수동 거래, 백테스팅 등)은 그대로 유지...