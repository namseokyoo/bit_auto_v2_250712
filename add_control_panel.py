#!/usr/bin/env python3
"""제어판 UI 및 JavaScript 추가 스크립트"""

# 제어판 HTML 컨텐츠
CONTROL_PANEL_HTML = '''
        <!-- 제어판 탭 -->
        <div id="control" class="tab-content" style="display: none;">
            <div class="control-container" style="max-width: 800px; margin: 0 auto; padding: 20px;">
                <h2>⚙️ 시스템 제어판</h2>
                
                <!-- 거래 모드 전환 -->
                <div class="card">
                    <h3>거래 모드 설정</h3>
                    <div style="display: flex; gap: 20px; margin: 20px 0;">
                        <button id="mode-dryrun" class="btn" style="flex: 1; padding: 15px;" onclick="setTradingMode('dry-run')">
                            🟡 테스트 모드 (Dry-Run)
                        </button>
                        <button id="mode-live" class="btn btn-danger" style="flex: 1; padding: 15px;" onclick="setTradingMode('live')">
                            🔴 실거래 모드 (Live)
                        </button>
                    </div>
                    <div class="mode-info">
                        <p>현재 모드: <span id="current-mode" style="font-weight: bold;">확인중...</span></p>
                        <p id="live-warning" style="color: #dc3545; font-weight: bold; display: none;">
                            ⚠️ 실거래 모드에서는 실제 자금이 사용됩니다!
                        </p>
                    </div>
                </div>
                
                <!-- 시스템 제어 -->
                <div class="card">
                    <h3>시스템 제어</h3>
                    <div style="display: flex; gap: 15px; margin: 20px 0;">
                        <button class="btn btn-success" onclick="systemControl('start')">
                            ▶️ 거래 시작
                        </button>
                        <button class="btn btn-danger" onclick="systemControl('stop')">
                            ⏹️ 거래 중지
                        </button>
                        <button class="btn btn-primary" onclick="restartSystem()">
                            🔄 시스템 재시작
                        </button>
                    </div>
                </div>
                
                <!-- 긴급 제어 -->
                <div class="card" style="background: #fff5f5; border: 2px solid #dc3545;">
                    <h3>긴급 제어</h3>
                    <button class="btn btn-danger" style="margin: 10px;" onclick="emergencyStop()">
                        🚨 긴급 중지
                    </button>
                    <button class="btn btn-warning" style="margin: 10px;" onclick="closeAllPositions()">
                        💰 모든 포지션 청산
                    </button>
                </div>
                
                <!-- 시스템 상태 -->
                <div class="card">
                    <h3>시스템 상태</h3>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 6px;">
                        <p>프로세스: <span id="process-status" style="font-weight: bold;">확인중...</span></p>
                        <p>거래 횟수: <span id="trade-count" style="font-weight: bold;">0</span></p>
                        <p>오늘 수익: <span id="today-profit" style="font-weight: bold;">₩0</span></p>
                        <p>목표 달성률: <span id="target-progress-ctrl" style="font-weight: bold;">0%</span></p>
                    </div>
                </div>
            </div>
        </div>
'''

# JavaScript 함수들
CONTROL_PANEL_JS = '''
// === 제어판 JavaScript 함수 ===

// 거래 모드 전환
async function setTradingMode(mode) {
    if (mode === 'live') {
        if (!confirm('실거래 모드로 전환하시겠습니까?\\n\\n⚠️ 실제 자금이 사용됩니다!')) {
            return;
        }
    }
    
    try {
        const response = await fetch('/api/trading-mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mode: mode})
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            updateModeDisplay();
        } else {
            alert('모드 전환 실패: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (error) {
        alert('모드 전환 중 오류 발생: ' + error);
    }
}

// 시스템 제어
async function systemControl(action) {
    const confirmMsg = action === 'start' ? '거래를 시작하시겠습니까?' : '거래를 중지하시겠습니까?';
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    try {
        const response = await fetch('/api/system-control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: action})
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            updateSystemStatus();
        } else {
            alert('시스템 제어 실패: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (error) {
        alert('시스템 제어 중 오류 발생: ' + error);
    }
}

// 시스템 재시작
async function restartSystem() {
    if (!confirm('시스템을 재시작하시겠습니까?')) {
        return;
    }
    
    await systemControl('stop');
    setTimeout(() => {
        systemControl('start');
    }, 3000);
}

// 긴급 중지
async function emergencyStop() {
    if (!confirm('긴급 중지하시겠습니까?\\n\\n모든 거래가 즉시 중단됩니다!')) {
        return;
    }
    
    try {
        await fetch('/api/emergency-stop', {method: 'POST'});
        alert('긴급 중지 완료');
        updateSystemStatus();
    } catch (error) {
        alert('긴급 중지 실패: ' + error);
    }
}

// 모든 포지션 청산
async function closeAllPositions() {
    if (!confirm('모든 포지션을 청산하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/close-all-positions', {method: 'POST'});
        const data = await response.json();
        alert('포지션 청산 완료: ' + (data.message || '성공'));
    } catch (error) {
        alert('포지션 청산 실패: ' + error);
    }
}

// 모드 표시 업데이트
async function updateModeDisplay() {
    try {
        const response = await fetch('/api/trading-mode');
        const data = await response.json();
        
        const modeElement = document.getElementById('current-mode');
        const warningElement = document.getElementById('live-warning');
        
        if (data.current_mode === 'live') {
            modeElement.textContent = '🔴 실거래';
            modeElement.style.color = '#dc3545';
            warningElement.style.display = 'block';
            
            document.getElementById('mode-live')?.classList.add('active');
            document.getElementById('mode-dryrun')?.classList.remove('active');
        } else {
            modeElement.textContent = '🟡 테스트';
            modeElement.style.color = '#ffc107';
            warningElement.style.display = 'none';
            
            document.getElementById('mode-dryrun')?.classList.add('active');
            document.getElementById('mode-live')?.classList.remove('active');
        }
        
        document.getElementById('process-status').textContent = 
            data.process_running ? '✅ 실행중' : '⏹️ 중지됨';
            
    } catch (error) {
        console.error('모드 표시 업데이트 실패:', error);
    }
}

// 시스템 상태 업데이트
async function updateSystemStatus() {
    try {
        // Redis 통계 가져오기
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        document.getElementById('trade-count').textContent = stats.daily_trades || '0';
        document.getElementById('today-profit').textContent = '₩' + (stats.daily_profit || 0).toLocaleString();
        document.getElementById('target-progress-ctrl').textContent = (stats.target_progress || 0).toFixed(1) + '%';
        
    } catch (error) {
        console.error('시스템 상태 업데이트 실패:', error);
    }
}

// 제어판 초기화 함수
function initControlPanel() {
    // 제어판 탭 클릭시
    const controlTab = document.querySelector('[data-tab="control"]');
    if (controlTab) {
        controlTab.addEventListener('click', function() {
            updateModeDisplay();
            updateSystemStatus();
        });
    }
    
    // 주기적 업데이트
    setInterval(() => {
        const controlPanel = document.getElementById('control');
        if (controlPanel && controlPanel.style.display !== 'none') {
            updateSystemStatus();
        }
    }, 10000);
}

// DOM 로드 완료시 초기화
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initControlPanel);
} else {
    initControlPanel();
}
'''

print("제어판 UI 및 JavaScript 코드 생성 완료")
print("이 파일을 서버로 복사한 후 실행하세요:")