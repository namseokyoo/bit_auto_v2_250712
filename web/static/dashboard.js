// 대시보드 JavaScript 함수들

// 실시간 차트 열기
function openRealtimeChart() {
    // 새 창에서 실시간 차트 열기
    const chartWindow = window.open('', 'realtimeChart', 'width=1200,height=800,scrollbars=yes,resizable=yes');
    
    if (chartWindow) {
        chartWindow.document.write(`
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>비트코인 실시간 차트</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
                <style>
                    body { margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f8f9fa; }
                    .chart-container { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                    .header { text-align: center; margin-bottom: 20px; }
                    .price-info { display: flex; justify-content: space-around; margin-bottom: 20px; }
                    .price-item { text-align: center; }
                    .price-value { font-size: 24px; font-weight: bold; color: #007bff; }
                    .price-label { color: #6c757d; font-size: 14px; }
                    .loading { text-align: center; padding: 50px; color: #6c757d; }
                </style>
            </head>
            <body>
                <div class="chart-container">
                    <div class="header">
                        <h1>비트코인 실시간 차트</h1>
                        <p>업비트 KRW-BTC 실시간 가격 차트</p>
                    </div>
                    
                    <div class="price-info">
                        <div class="price-item">
                            <div class="price-value" id="current-price">로딩중...</div>
                            <div class="price-label">현재 가격</div>
                        </div>
                        <div class="price-item">
                            <div class="price-value" id="price-change">로딩중...</div>
                            <div class="price-label">24시간 변동률</div>
                        </div>
                        <div class="price-item">
                            <div class="price-value" id="volume">로딩중...</div>
                            <div class="price-label">24시간 거래량</div>
                        </div>
                    </div>
                    
                    <div style="position: relative; height: 400px;">
                        <canvas id="priceChart"></canvas>
                    </div>
                    
                    <div class="loading" id="loading">
                        <p>차트 데이터를 불러오는 중...</p>
                    </div>
                </div>
                
                <script>
                    let chart;
                    let priceData = [];
                    let maxDataPoints = 100;
                    
                    // 차트 초기화
                    function initChart() {
                        const ctx = document.getElementById('priceChart').getContext('2d');
                        chart = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'BTC 가격 (KRW)',
                                    data: [],
                                    borderColor: '#007bff',
                                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                                    borderWidth: 2,
                                    fill: true,
                                    tension: 0.4
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {
                                    x: {
                                        type: 'time',
                                        time: {
                                            displayFormats: {
                                                minute: 'HH:mm',
                                                hour: 'MM-dd HH:mm'
                                            }
                                        }
                                    },
                                    y: {
                                        beginAtZero: false,
                                        ticks: {
                                            callback: function(value) {
                                                return '₩' + value.toLocaleString();
                                            }
                                        }
                                    }
                                },
                                plugins: {
                                    legend: {
                                        display: true
                                    },
                                    tooltip: {
                                        callbacks: {
                                            label: function(context) {
                                                return '가격: ₩' + context.parsed.y.toLocaleString();
                                            }
                                        }
                                    }
                                }
                            }
                        });
                    }
                    
                    // 가격 데이터 업데이트
                    function updatePriceData() {
                        fetch('/api/current_price')
                            .then(response => response.json())
                            .then(data => {
                                if (data.success && data.price) {
                                    const now = new Date();
                                    const price = data.price;
                                    
                                    // 가격 데이터 추가
                                    priceData.push({
                                        x: now,
                                        y: price
                                    });
                                    
                                    // 최대 데이터 포인트 수 제한
                                    if (priceData.length > maxDataPoints) {
                                        priceData.shift();
                                    }
                                    
                                    // 차트 업데이트
                                    chart.data.labels = priceData.map(d => d.x);
                                    chart.data.datasets[0].data = priceData.map(d => d.y);
                                    chart.update('none');
                                    
                                    // 가격 정보 업데이트
                                    document.getElementById('current-price').textContent = '₩' + price.toLocaleString();
                                    
                                    // 로딩 숨기기
                                    document.getElementById('loading').style.display = 'none';
                                }
                            })
                            .catch(error => {
                                console.error('가격 데이터 로드 오류:', error);
                                document.getElementById('loading').innerHTML = '<p style="color: red;">데이터 로드 오류</p>';
                            });
                    }
                    
                    // 초기화
                    document.addEventListener('DOMContentLoaded', function() {
                        initChart();
                        updatePriceData();
                        
                        // 5초마다 데이터 업데이트
                        setInterval(updatePriceData, 5000);
                    });
                </script>
            </body>
            </html>
        `);
        chartWindow.document.close();
    } else {
        alert('팝업이 차단되었습니다. 팝업 차단을 해제하고 다시 시도해주세요.');
    }
}

// 자동 거래 토글 (새로운 버전)
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
                // UI 업데이트
                updateAutoTradingUI(enable);
                // 상태 업데이트
                updateAutoTradingStatus();
                // 대시보드 데이터 새로고침
                updateDashboardData();
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
                showAlert('danger', '긴급 정지가 실행되었습니다. 모든 자동 거래가 중단되었습니다.');
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

// 자동 거래 UI 업데이트
function updateAutoTradingUI(enabled) {
    const container = document.getElementById('trading-status-container');
    if (container) {
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
}

// 자동 거래 상태 업데이트 (시스템 상태 포함)
async function updateAutoTradingStatus() {
    try {
        // 시스템 상태와 자동거래 상태를 모두 가져오기
        const [autoResponse, systemResponse] = await Promise.all([
            fetch('/api/auto_trading_status'),
            fetch('/api/system/status')
        ]);

        const autoData = await autoResponse.json();
        const systemData = await systemResponse.json();

        if (autoData.success && autoData.status) {
            // 자동거래 UI 업데이트
            updateAutoTradingUI(autoData.status.auto_trading_enabled);

            // 다음 실행 시간 업데이트
            if (autoData.status.next_execution) {
                document.getElementById('next-trade-time').textContent = autoData.status.next_execution;
            }

            // 마지막 실행 시간 업데이트
            if (autoData.status.last_execution) {
                document.getElementById('last-trade-time').textContent = autoData.status.last_execution;
            }
        }

        // 시스템 상태 업데이트
        if (systemData && systemData.system_enabled !== undefined) {
            const systemBadges = document.querySelectorAll('.card-body .row .col-6:first-child .badge');
            systemBadges.forEach(badge => {
                const label = badge.closest('.col-6').querySelector('label');
                if (label && label.textContent.includes('시스템')) {
                    if (systemData.system_enabled) {
                        badge.className = 'badge bg-success';
                        badge.textContent = '활성화';
                    } else {
                        badge.className = 'badge bg-secondary';
                        badge.textContent = '비활성화';
                    }
                }
            });
        }

    } catch (error) {
        console.error('Error updating auto trading status:', error);
    }
}

// 대시보드 데이터 업데이트
async function updateDashboardData() {
    try {
        const response = await fetch('/api/dashboard_data');
        const data = await response.json();

        if (data.success) {
            // 통계 카드 업데이트
            const totalTradesEl = document.querySelector('.row.mb-4:nth-of-type(2) .col-md-3:nth-child(1) h2');
            const todayTradesEl = document.querySelector('.row.mb-4:nth-of-type(2) .col-md-3:nth-child(2) h2');
            const totalPnlEl = document.querySelector('.row.mb-4:nth-of-type(2) .col-md-3:nth-child(3) h2');
            const winRateEl = document.querySelector('.row.mb-4:nth-of-type(2) .col-md-3:nth-child(4) h2');

            if (totalTradesEl) totalTradesEl.textContent = data.data.total_trades || 0;
            if (todayTradesEl) todayTradesEl.textContent = data.data.today_trades || 0;
            if (totalPnlEl) totalPnlEl.textContent = `${data.data.total_pnl || 0} KRW`;
            if (winRateEl) winRateEl.textContent = `${(data.data.win_rate || 0).toFixed(1)}%`;

            // 최근 거래 내역 업데이트
            updateRecentTrades(data.data.recent_trades || []);
        }

        // 잔고 정보도 업데이트
        await updateBalanceInfo();

    } catch (error) {
        console.error('Error updating dashboard data:', error);
    }
}

// 잔고 정보 업데이트
async function updateBalanceInfo() {
    try {
        const response = await fetch('/api/balance');
        const data = await response.json();

        if (data.balances) {
            const krwEl = document.querySelector('.card-body .row .col-6:first-child .fw-bold');
            const btcEl = document.querySelector('.card-body .row .col-6:last-child .fw-bold');
            const btcValueEl = document.querySelector('.card-body .row .col-6:last-child .text-muted');
            const totalValueEl = document.querySelector('.card-body .row:last-child .col-6:last-child .fw-bold');

            if (krwEl) krwEl.textContent = `₩ ${data.balances.KRW.toLocaleString()}`;
            if (btcEl) btcEl.textContent = data.balances.BTC.toFixed(8);
            if (btcValueEl) btcValueEl.textContent = `≈ ₩ ${data.btc_value.toLocaleString()}`;
            if (totalValueEl) totalValueEl.textContent = `₩ ${data.total_value.toLocaleString()}`;
        }
    } catch (error) {
        console.error('Error updating balance:', error);
    }
}

// 최근 거래 내역 업데이트
function updateRecentTrades(trades) {
    const container = document.querySelector('.card-body .list-group, .card-body .alert');
    if (!container) return;

    if (trades.length === 0) {
        container.innerHTML = '<div class="alert alert-info"><i class="fas fa-info-circle"></i> 거래 내역이 없습니다.</div>';
    } else {
        const tradesHTML = trades.map(trade => `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <span class="badge ${trade.side === 'buy' ? 'bg-success' : 'bg-danger'} me-2">
                        ${trade.side === 'buy' ? '매수' : '매도'}
                    </span>
                    <small class="text-muted">${trade.strategy_id}</small>
                    <div class="small text-muted">${new Date(trade.entry_time).toLocaleString()}</div>
                </div>
                <div class="text-end">
                    <div class="fw-bold">₩ ${parseFloat(trade.entry_price).toLocaleString()}</div>
                    <div class="small ${trade.pnl > 0 ? 'text-success' : trade.pnl < 0 ? 'text-danger' : 'text-muted'}">
                        ${trade.pnl ? `${trade.pnl > 0 ? '+' : ''}${parseFloat(trade.pnl).toLocaleString()} KRW` : '-'}
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = `<div class="list-group">${tradesHTML}</div>`;
    }
}

// 시스템 토글
function toggleSystem(action) {
    if (!confirm(`정말로 시스템을 ${action === 'enable' ? '활성화' : '비활성화'}하시겠습니까?`)) {
        return;
    }

    fetch('/api/system/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: action })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('success', data.message);
                setTimeout(() => location.reload(), 1000);
            } else {
                showAlert('danger', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('danger', '시스템 토글 중 오류가 발생했습니다.');
        });
}

// 자동거래 토글
function toggleTrading(action) {
    if (!confirm(`정말로 자동거래를 ${action === 'enable' ? '활성화' : '비활성화'}하시겠습니까?`)) {
        return;
    }

    fetch('/api/trading/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: action })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('success', data.message);
                // 토글 상태만 업데이트하고 페이지는 새로고침하지 않음
                updateTradingToggleUI(action === 'enable');
            } else {
                showAlert('danger', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('danger', '자동거래 토글 중 오류가 발생했습니다.');
        });
}

// 자동거래 토글 UI 업데이트
function updateTradingToggleUI(enabled) {
    const tradingStatusElement = document.getElementById('trading-status-container');
    const timerElement = document.getElementById('next-trade-timer');

    if (tradingStatusElement) {
        if (enabled) {
            tradingStatusElement.innerHTML = `
                <span class="badge bg-success">활성화</span>
                <button class="btn btn-sm btn-outline-danger ms-2" onclick="toggleTrading('disable')">
                    비활성화
                </button>
            `;
            // 타이머 시작
            if (timerElement) {
                timerElement.style.display = 'block';
                startTradingCountdown();
            }
        } else {
            tradingStatusElement.innerHTML = `
                <span class="badge bg-secondary">비활성화</span>
                <button class="btn btn-sm btn-outline-success ms-2" onclick="toggleTrading('enable')">
                    활성화
                </button>
            `;
            // 타이머 중지
            if (timerElement) {
                timerElement.style.display = 'none';
                stopTradingCountdown();
            }
        }
    }
}

// 카운트다운 관련 변수
let countdownInterval = null;
let nextTradeTime = null;
let tradeIntervalMinutes = 10; // 기본값, API에서 가져옴
let autoTradingStatus = null; // 서버 자동 거래 상태
let statusUpdateInterval = null; // 상태 업데이트 인터벌

// 자동 거래 상태 가져오기
async function fetchAutoTradingStatus() {
    try {
        const response = await fetch('/api/auto_trading_status');
        const data = await response.json();

        if (data.success && data.status) {
            autoTradingStatus = data.status;

            // 서버에서 받은 다음 실행 시간 업데이트
            if (autoTradingStatus.next_execution) {
                // KST 시간 문자열을 올바르게 파싱
                // "2025-08-18 22:30:00 KST" 형식을 Date 객체로 변환
                const nextExecStr = autoTradingStatus.next_execution.replace(' KST', '');
                // 명시적으로 시간대 정보 추가 (KST = UTC+9)
                nextTradeTime = new Date(nextExecStr + '+09:00');
                console.log('서버 다음 실행 시간 (원본):', autoTradingStatus.next_execution);
                console.log('서버 다음 실행 시간 (파싱):', nextTradeTime);
                console.log('현재 시간:', new Date());
            }

            // 마지막 실행 시간도 localStorage에 저장
            if (autoTradingStatus.last_execution) {
                const lastExecStr = autoTradingStatus.last_execution.replace(' KST', '');
                const lastExecTime = new Date(lastExecStr);
                localStorage.setItem('lastTradeExecution', lastExecTime.getTime().toString());
            }
        }
    } catch (error) {
        console.error('자동 거래 상태 로드 오류:', error);
    }
}

// 거래 설정 가져오기
async function fetchTradingConfig() {
    try {
        const response = await fetch('/api/trading_config');
        const data = await response.json();
        if (data.success) {
            tradeIntervalMinutes = data.trade_interval_minutes;
            // 거래 간격 표시 업데이트
            const intervalElement = document.getElementById('trading-interval');
            if (intervalElement) {
                intervalElement.textContent = `${tradeIntervalMinutes}분마다 분석`;
            }
        }
    } catch (error) {
        console.error('거래 설정 로드 오류:', error);
    }
}

// 다음 거래 시간 계산
function calculateNextTradeTime() {
    // 서버에서 받은 시간이 있고 유효하면 우선 사용
    if (nextTradeTime && nextTradeTime > new Date()) {
        console.log('서버 시간 사용:', nextTradeTime);
        return nextTradeTime;
    }

    // 폴백: 로컬 계산
    const now = new Date();
    const lastExecutionTime = localStorage.getItem('lastTradeExecution');

    let nextTime = new Date(now);

    if (lastExecutionTime) {
        // 마지막 실행 시간이 있으면 그 시간부터 계산
        const lastTime = new Date(parseInt(lastExecutionTime));
        nextTime = new Date(lastTime.getTime() + tradeIntervalMinutes * 60 * 1000);

        // 이미 지난 시간이면 다음 주기로
        while (nextTime <= now) {
            nextTime = new Date(nextTime.getTime() + tradeIntervalMinutes * 60 * 1000);
        }
    } else {
        // 처음이면 현재 시간부터 다음 주기
        nextTime = new Date(now.getTime() + tradeIntervalMinutes * 60 * 1000);
    }

    console.log('로컬 계산 시간:', nextTime);
    return nextTime;
}

// 카운트다운 시작
function startTradingCountdown() {
    // 기존 인터벌 정리
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
    }

    // 서버 상태 가져오기 (이미 페이지 로드 시 가져왔으므로 calculateNextTradeTime만 호출)
    // 다음 거래 시간 계산
    nextTradeTime = calculateNextTradeTime();

    // 1초마다 카운트다운 업데이트
    countdownInterval = setInterval(updateCountdown, 1000);
    updateCountdown(); // 즉시 첫 업데이트

    // 10초마다 서버 상태 업데이트
    statusUpdateInterval = setInterval(() => {
        fetchAutoTradingStatus();
    }, 10000);
}

// 카운트다운 중지
function stopTradingCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
    if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
        statusUpdateInterval = null;
    }
}

// 카운트다운 업데이트
function updateCountdown() {
    if (!nextTradeTime) {
        nextTradeTime = calculateNextTradeTime();
    }

    // 서버 시간 표시 업데이트
    const nextTradeTimeElement = document.getElementById('next-trade-time');
    const lastTradeTimeElement = document.getElementById('last-trade-time');

    if (nextTradeTimeElement && nextTradeTime) {
        // KST 시간으로 표시
        const options = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Asia/Seoul'
        };
        nextTradeTimeElement.textContent = nextTradeTime.toLocaleString('ko-KR', options) + ' KST';
    }

    if (lastTradeTimeElement && autoTradingStatus && autoTradingStatus.last_execution) {
        lastTradeTimeElement.textContent = autoTradingStatus.last_execution;
    }

    const now = new Date();
    const diff = nextTradeTime - now;

    if (diff <= 0) {
        // 시간이 지났으면 서버 상태 업데이트 후 다시 계산
        const countdownDisplay = document.getElementById('countdown-display');
        if (countdownDisplay) {
            countdownDisplay.textContent = '분석 중...';
            countdownDisplay.className = 'text-warning animate-pulse';
        }

        // 서버 상태 업데이트
        setTimeout(() => {
            fetchAutoTradingStatus().then(() => {
                nextTradeTime = calculateNextTradeTime();
            });
        }, 3000);
        return;
    }

    // 시간 계산
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    // 표시 형식 결정
    let displayText = '';
    if (hours > 0) {
        displayText = `${hours}시간 ${minutes}분 ${seconds}초 남음`;
    } else if (minutes > 0) {
        displayText = `${minutes}분 ${seconds}초 남음`;
    } else {
        displayText = `${seconds}초 남음`;
    }

    // 카운트다운 표시
    const countdownDisplay = document.getElementById('countdown-display');
    if (countdownDisplay) {
        countdownDisplay.textContent = displayText;
        if (diff <= 10000) {
            countdownDisplay.className = 'text-danger animate-pulse';
        } else if (diff <= 60000) {
            countdownDisplay.className = 'text-warning';
        } else {
            countdownDisplay.className = 'text-primary';
        }
    }
}

// 수동 전략 분석
function manualAnalyze() {
    // 분석 버튼 비활성화
    const analyzeBtn = event.target;
    const originalText = analyzeBtn.innerHTML;
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 분석 중...';

    fetch('/api/manual_trading/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayAnalysisResults(data.data);
                showAlert('success', '전략 분석이 완료되었습니다.');
            } else {
                showAlert('danger', `분석 실패: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('danger', '분석 중 오류가 발생했습니다.');
        })
        .finally(() => {
            // 버튼 복원
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = originalText;
        });
}

// 수동 거래 실행
function manualExecute(action) {
    let confirmMessage = '';

    switch (action) {
        case 'analyze_and_execute':
            confirmMessage = '전략 분석 후 결과에 따라 자동으로 거래를 실행하시겠습니까?';
            break;
        case 'buy':
            confirmMessage = '강제 매수를 실행하시겠습니까? (기본 5만원)';
            break;
        case 'sell':
            confirmMessage = '보유 중인 BTC를 전량 매도하시겠습니까?';
            break;
        default:
            showAlert('danger', '지원하지 않는 액션입니다.');
            return;
    }

    if (!confirm(confirmMessage)) {
        return;
    }

    // 실행 버튼 비활성화
    const executeBtn = event.target;
    const originalText = executeBtn.innerHTML;
    executeBtn.disabled = true;
    executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 실행 중...';

    fetch('/api/manual_trading/execute', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: action })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayExecutionResults(data.message, 'success');
                showAlert('success', data.message);
                // 대시보드 데이터 즉시 새로고침 (페이지 리로드 대신)
                setTimeout(async () => {
                    await updateDashboardData();
                    await updateAutoTradingStatus();
                }, 1000);
            } else {
                displayExecutionResults(data.message, 'danger');
                showAlert('danger', `실행 실패: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            const errorMsg = '거래 실행 중 오류가 발생했습니다.';
            displayExecutionResults(errorMsg, 'danger');
            showAlert('danger', errorMsg);
        })
        .finally(() => {
            // 버튼 복원
            executeBtn.disabled = false;
            executeBtn.innerHTML = originalText;
        });
}

// 분석 결과 표시
function displayAnalysisResults(data) {
    const resultsDiv = document.getElementById('analysis-results');
    const contentDiv = document.getElementById('analysis-content');

    // API 상태 표시
    const apiStatusBadge = data.api_status === 'REAL_API' ?
        '<span class="badge bg-success ms-2"><i class="fas fa-wifi"></i> 실제 API</span>' :
        '<span class="badge bg-warning ms-2"><i class="fas fa-exclamation-triangle"></i> 시뮬레이션</span>';

    const marketDataBadge = data.market_data_available === false ?
        '<span class="badge bg-secondary ms-1">모의 데이터</span>' :
        '<span class="badge bg-info ms-1">실시간 데이터</span>';

    let html = `
        <div class="mb-3">
            <div class="row">
                <div class="col-md-6">
                    <strong>분석 시간:</strong> ${new Date(data.timestamp).toLocaleString()}
                </div>
                <div class="col-md-6">
                    <strong>활성 전략 수:</strong> <span class="badge bg-primary">${data.active_strategies_count || 0}</span>
                    ${apiStatusBadge}
                    ${marketDataBadge}
                </div>
            </div>
            ${data.api_status === 'SIMULATION' ?
            '<div class="alert alert-warning alert-sm mt-2 mb-0"><i class="fas fa-info-circle"></i> <strong>시뮬레이션 모드:</strong> API 키가 설정되지 않았거나 연결에 실패했습니다. 모의 데이터로 분석을 진행합니다.</div>' :
            '<div class="alert alert-success alert-sm mt-2 mb-0"><i class="fas fa-check-circle"></i> <strong>실시간 모드:</strong> 업비트 API를 통해 실제 시장 데이터로 분석을 진행합니다.</div>'
        }
        </div>
    `;

    // 개별 전략 신호 - 테이블 형태
    if (data.individual_signals && data.individual_signals.length > 0) {
        html += '<h6><i class="fas fa-chart-line"></i> 개별 전략 분석 결과</h6>';
        html += `
            <div class="table-responsive">
                <table class="table table-hover table-bordered strategy-analysis-table">
                    <thead>
                        <tr>
                            <th style="width: 18%">전략</th>
                            <th style="width: 12%">신호</th>
                            <th style="width: 10%">신뢰도</th>
                            <th style="width: 12%">제안금액</th>
                            <th style="width: 48%">분석 근거</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // 전략 이름 매핑 (고정)
        const strategyNames = {
            'ema_cross': 'EMA 골든크로스',
            'rsi_divergence': 'RSI 다이버전스',
            'pivot_points': '피봇 포인트',
            'vwap_pullback': 'VWAP 되돌림',
            'macd_zero_cross': 'MACD 제로크로스',
            'bollinger_band_strategy': '볼린저 밴드',
            'open_interest': '미체결 약정',
            'flag_pennant': '깃발/페넌트'
        };

        data.individual_signals.forEach(signal => {
            const actionClass = signal.action === 'buy' ? 'success' :
                signal.action === 'sell' ? 'danger' : 'secondary';
            const actionText = signal.action === 'buy' ? '매수' :
                signal.action === 'sell' ? '매도' : '홀드';
            const actionIcon = signal.action === 'buy' ? 'fa-arrow-up' :
                signal.action === 'sell' ? 'fa-arrow-down' : 'fa-minus';
            const strategyName = strategyNames[signal.strategy_id] || signal.strategy_id.toUpperCase();

            // 신뢰도에 따른 색상 클래스
            const confidence = signal.confidence * 100;
            let confidenceClass = 'confidence-low';
            if (confidence >= 70) confidenceClass = 'confidence-high';
            else if (confidence >= 50) confidenceClass = 'confidence-medium';

            html += `
                <tr class="table-row-${actionClass === 'secondary' ? 'light' : actionClass === 'success' ? 'success' : 'danger'}">
                    <td>
                        <div>
                            <strong class="text-primary">
                                <a href="#" class="strategy-link" data-strategy-id="${signal.strategy_id}" 
                                   style="text-decoration: none; color: inherit;">
                                    ${signal.strategy_id.toUpperCase()}
                                </a>
                            </strong>
                        </div>
                        <small class="text-muted">${strategyName}</small>
                    </td>
                    <td class="text-center">
                        <span class="badge bg-${actionClass}">
                            <i class="fas ${actionIcon}"></i> ${actionText}
                        </span>
                    </td>
                    <td class="text-center">
                        <span class="${confidenceClass}">${confidence.toFixed(1)}%</span>
                    </td>
                    <td class="text-end">
                        ${signal.suggested_amount > 0 ?
                    `<strong class="text-success">${signal.suggested_amount.toLocaleString()}원</strong>` :
                    '<span class="text-muted">-</span>'
                }
                    </td>
                    <td>
                        <div class="text-dark" style="font-size: 0.85rem; line-height: 1.3;">
                            ${signal.reasoning}
                        </div>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
    } else {
        html += `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i> 
                활성화된 전략이 없거나 신호를 생성할 수 없습니다.
                <br><small>설정에서 전략을 활성화하거나 시장 상황을 확인해주세요.</small>
            </div>
        `;
    }

    // 통합 신호
    if (data.consolidated_signal) {
        const signal = data.consolidated_signal;
        const actionClass = signal.action === 'buy' ? 'success' :
            signal.action === 'sell' ? 'danger' : 'warning';
        const actionText = signal.action === 'buy' ? '매수' :
            signal.action === 'sell' ? '매도' : '홀드';
        const actionIcon = signal.action === 'buy' ? 'fa-arrow-up' :
            signal.action === 'sell' ? 'fa-arrow-down' : 'fa-pause';

        html += `
            <hr>
            <h6><i class="fas fa-magic"></i> 최종 통합 결정</h6>
            <div class="alert alert-${actionClass}">
                <div class="row">
                    <div class="col-md-8">
                        <h5><i class="fas ${actionIcon}"></i> <strong>${actionText}</strong></h5>
                        <div class="mb-2">
                            <span class="badge bg-light text-dark">신뢰도: ${(signal.confidence * 100).toFixed(1)}%</span>
                            ${signal.suggested_amount > 0 ? `<span class="badge bg-light text-dark ms-2">제안 금액: ${signal.suggested_amount.toLocaleString()}원</span>` : ''}
                        </div>
                        <p class="mb-2">${signal.reasoning}</p>
                        <div class="small">
                            <strong>기여 전략:</strong> ${signal.contributing_strategies.map(s => s.toUpperCase()).join(', ')}<br>
                            <strong>시장 상황:</strong> ${signal.market_condition}<br>
                            ${signal.buy_count !== undefined ? `
                            <strong>신호 분포:</strong> 매수 ${signal.buy_count}개, 매도 ${signal.sell_count}개, 홀드 ${signal.hold_count}개<br>
                            <strong>평균 신뢰도:</strong> 매수 ${signal.buy_avg_confidence || 0}, 매도 ${signal.sell_avg_confidence || 0}, 홀드 ${signal.hold_avg_confidence || 0}<br>
                            <strong>최종 점수:</strong> 매수 ${signal.final_buy_score || 0}, 매도 ${signal.final_sell_score || 0}, 홀드 ${signal.final_hold_score || 0}
                            ` : ''}
                        </div>
                    </div>
                    <div class="col-md-4 text-center">
                        <div class="mt-2">
                            ${signal.action !== 'hold' ?
                `<button class="btn btn-${actionClass} btn-sm" onclick="manualExecute('analyze_and_execute')">
                                    <i class="fas fa-bolt"></i> 즉시 실행
                                </button>` :
                '<span class="text-muted"><i class="fas fa-pause"></i> 실행 권장하지 않음</span>'
            }
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    contentDiv.innerHTML = html;
    resultsDiv.style.display = 'block';

    // 스크롤을 분석 결과로 이동
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 실행 결과 표시
function displayExecutionResults(message, type) {
    const resultsDiv = document.getElementById('execution-results');
    const messageDiv = document.getElementById('execution-message');

    messageDiv.className = `alert alert-${type}`;
    messageDiv.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'}"></i>
        ${message}
    `;

    resultsDiv.style.display = 'block';

    // 5초 후 자동 숨김
    setTimeout(() => {
        resultsDiv.style.display = 'none';
    }, 5000);
}

// 알림 표시
function showAlert(type, message) {
    // 기존 알림 제거
    const existingAlert = document.querySelector('.alert-floating');
    if (existingAlert) {
        existingAlert.remove();
    }

    // 새 알림 생성
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-floating`;
    alertDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
    `;
    alertDiv.innerHTML = `
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        ${message}
    `;

    document.body.appendChild(alertDiv);

    // 5초 후 자동 제거
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// 페이지 로드 시 초기화 (아래 DOMContentLoaded에서 처리)

// 백테스팅 실행
function runBacktest() {
    const period = document.getElementById('backtest-period').value;
    const btn = event.target;
    const originalText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 실행 중...';

    fetch('/api/backtesting/run', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            mode: 'basic',
            days: parseInt(period)
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayBacktestResults(data);
                loadBacktestHistory(); // 히스토리 새로고침
                showAlert('success', `백테스트 완료: 수익률 ${data.metrics.total_return}`);
            } else {
                showAlert('danger', `백테스트 실패: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('danger', '백테스트 중 오류가 발생했습니다.');
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
}

// 백테스트 결과 표시
function displayBacktestResults(data) {
    const resultsDiv = document.getElementById('backtest-results');
    const contentDiv = document.getElementById('backtest-content');

    // 성과 등급별 색상
    const gradeClass = data.metrics.performance_grade === 'A' ? 'success' :
        data.metrics.performance_grade === 'B' ? 'warning' : 'danger';

    const html = `
        <div class="row">
            <div class="col-md-6">
                <h6><i class="fas fa-calendar-alt"></i> 백테스트 정보</h6>
                <div class="mb-3">
                    <div><strong>기간:</strong> ${data.start_date} ~ ${data.end_date} (${data.period_days}일)</div>
                    <div><strong>모드:</strong> <span class="badge bg-info">${data.mode}</span></div>
                    <div><strong>성과 등급:</strong> <span class="badge bg-${gradeClass}">${data.metrics.performance_grade}</span></div>
                </div>
            </div>
            <div class="col-md-6">
                <h6><i class="fas fa-chart-line"></i> 핵심 지표</h6>
                <div class="row">
                    <div class="col-6">
                        <div class="text-center p-2 border rounded mb-2">
                            <small class="text-muted">총 수익률</small>
                            <div class="h5 ${data.metrics.total_return.startsWith('-') ? 'text-danger' : 'text-success'} mb-0">
                                ${data.metrics.total_return}
                            </div>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="text-center p-2 border rounded mb-2">
                            <small class="text-muted">샤프 비율</small>
                            <div class="h5 text-info mb-0">${data.metrics.sharpe_ratio}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-3">
            <div class="col-md-12">
                <h6><i class="fas fa-list"></i> 상세 성과</h6>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <tbody>
                            <tr>
                                <td><strong>연환산 수익률</strong></td>
                                <td>${data.metrics.annualized_return}</td>
                                <td><strong>최대 낙폭</strong></td>
                                <td class="text-danger">${data.metrics.max_drawdown}</td>
                            </tr>
                            <tr>
                                <td><strong>승률</strong></td>
                                <td>${data.metrics.win_rate}</td>
                                <td><strong>총 거래 수</strong></td>
                                <td>${data.metrics.total_trades}</td>
                            </tr>
                            <tr>
                                <td><strong>Buy & Hold 수익률</strong></td>
                                <td>${data.metrics.buy_and_hold_return}</td>
                                <td><strong>알파 (초과수익)</strong></td>
                                <td class="${data.metrics.alpha.startsWith('-') ? 'text-danger' : 'text-success'}">${data.metrics.alpha}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="text-center mt-3">
            <small class="text-muted">
                <i class="fas fa-info-circle"></i> 
                결과 파일: ${data.output_file}<br>
                실행 시간: ${new Date(data.execution_time).toLocaleString()}
            </small>
        </div>
    `;

    contentDiv.innerHTML = html;
    resultsDiv.style.display = 'block';

    // 스크롤을 결과로 이동
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 백테스트 히스토리 로드
function loadBacktestHistory() {
    fetch('/api/backtesting/history')
        .then(response => response.json())
        .then(data => {
            const historyDiv = document.getElementById('backtest-history');

            if (data.results && data.results.length > 0) {
                let html = '<div class="list-group list-group-flush">';

                data.results.slice(0, 5).forEach(result => {
                    const returnClass = result.total_return >= 0 ? 'text-success' : 'text-danger';
                    const returnText = (result.total_return * 100).toFixed(2) + '%';

                    html += `
                    <div class="list-group-item list-group-item-action p-2">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <small class="text-muted">${result.date.substring(0, 8)}</small>
                                <div class="small">
                                    <span class="${returnClass}">${returnText}</span>
                                    <span class="text-muted ms-1">SR: ${result.sharpe_ratio.toFixed(2)}</span>
                                </div>
                            </div>
                            <div class="text-end">
                                <small class="text-muted">${result.total_trades}회</small>
                            </div>
                        </div>
                    </div>
                `;
                });

                html += '</div>';
                historyDiv.innerHTML = html;
            } else {
                historyDiv.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-chart-line"></i><br>
                    백테스트 기록이 없습니다
                </div>
            `;
            }
        })
        .catch(error => {
            console.error('Error loading backtest history:', error);
            document.getElementById('backtest-history').innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="fas fa-exclamation-triangle"></i><br>
                히스토리 로드 실패
            </div>
        `;
        });
}

// 전략 세부 정보 표시
function showStrategyDetails(strategyId) {
    fetch(`/api/strategy/${strategyId}/details`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayStrategyDetails(data.details);
            } else {
                showAlert('danger', `전략 정보 조회 실패: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('danger', '전략 정보 조회 중 오류가 발생했습니다.');
        });
}

// 전략 세부 정보 모달 표시
function displayStrategyDetails(details) {
    // 기존 모달 제거
    const existingModal = document.getElementById('strategy-details-modal');
    if (existingModal) {
        existingModal.remove();
    }

    // 현재 값들 표시
    let currentValuesHtml = '<div class="row">';
    const values = details.current_values || {};
    let colCount = 0;

    for (const [key, value] of Object.entries(values)) {
        if (colCount % 2 === 0 && colCount > 0) {
            currentValuesHtml += '</div><div class="row">';
        }
        currentValuesHtml += `
            <div class="col-md-6 mb-2">
                <div class="border rounded p-2 bg-light">
                    <small class="text-muted">${key}</small>
                    <div class="fw-bold">${typeof value === 'number' ? value.toLocaleString() : value}</div>
                </div>
            </div>
        `;
        colCount++;
    }
    currentValuesHtml += '</div>';

    // 계산 방법 표시
    let calculationHtml = '';
    if (details.calculation_method) {
        calculationHtml = '<div class="mb-3">';
        for (const [key, value] of Object.entries(details.calculation_method)) {
            calculationHtml += `
                <div class="mb-2">
                    <strong>${key}:</strong> <code>${value}</code>
                </div>
            `;
        }
        calculationHtml += '</div>';
    }

    // 추가 필터 표시
    let filtersHtml = '';
    if (details.additional_filters) {
        filtersHtml = '<div class="mb-3">';
        for (const [key, value] of Object.entries(details.additional_filters)) {
            filtersHtml += `
                <div class="mb-2">
                    <strong>${key}:</strong> ${value}
                </div>
            `;
        }
        filtersHtml += '</div>';
    }

    // 임계값 표시
    let thresholdsHtml = '';
    if (details.thresholds) {
        thresholdsHtml = '<div class="mb-3">';
        for (const [key, value] of Object.entries(details.thresholds)) {
            thresholdsHtml += `
                <div class="mb-2">
                    <strong>${key}:</strong> <span class="badge bg-info">${value}</span>
                </div>
            `;
        }
        thresholdsHtml += '</div>';
    }

    // 모달 HTML
    const modalHtml = `
        <div class="modal fade" id="strategy-details-modal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-chart-line"></i> ${details.strategy_name}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <p class="text-muted">${details.description}</p>
                        </div>
                        
                        <div class="card mb-3">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="fas fa-chart-bar"></i> 현재 값</h6>
                            </div>
                            <div class="card-body">
                                ${currentValuesHtml}
                            </div>
                        </div>
                        
                        <div class="card mb-3">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="fas fa-calculator"></i> 계산 방법</h6>
                            </div>
                            <div class="card-body">
                                ${calculationHtml}
                            </div>
                        </div>
                        
                        ${details.additional_filters ? `
                        <div class="card mb-3">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="fas fa-filter"></i> 추가 필터</h6>
                            </div>
                            <div class="card-body">
                                ${filtersHtml}
                            </div>
                        </div>
                        ` : ''}
                        
                        ${details.thresholds ? `
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="fas fa-sliders-h"></i> 임계값</h6>
                            </div>
                            <div class="card-body">
                                ${thresholdsHtml}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 모달을 body에 추가
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 모달 표시
    const modal = new bootstrap.Modal(document.getElementById('strategy-details-modal'));
    modal.show();

    // 모달이 완전히 숨겨진 후 DOM에서 제거
    document.getElementById('strategy-details-modal').addEventListener('hidden.bs.modal', function () {
        this.remove();
    });
}

// 자동 분석 이력 로드
function loadAnalysisHistory() {
    fetch('/api/analysis/latest?limit=5')
        .then(response => response.json())
        .then(data => {
            const historyDiv = document.getElementById('analysis-history');

            if (data.success && data.analyses && data.analyses.length > 0) {
                let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
                html += '<thead><tr><th>시간</th><th>액션</th><th>신뢰도</th><th>이유</th></tr></thead><tbody>';

                data.analyses.forEach(analysis => {
                    const timestamp = new Date(analysis.timestamp);
                    const action = analysis.action || 'hold';
                    const confidence = (analysis.confidence || 0) * 100;
                    const reasoning = analysis.reasoning || '분석 중...';

                    const actionClass = action === 'buy' ? 'success' :
                        action === 'sell' ? 'danger' : 'secondary';
                    const actionText = action === 'buy' ? '매수' :
                        action === 'sell' ? '매도' : '홀드';

                    html += `
                    <tr>
                        <td>${timestamp.toLocaleString('ko-KR', {
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    })}</td>
                        <td><span class="badge bg-${actionClass}">${actionText}</span></td>
                        <td>${confidence.toFixed(1)}%</td>
                        <td><small>${reasoning}</small></td>
                    </tr>
                `;
                });

                html += '</tbody></table></div>';
                historyDiv.innerHTML = html;
            } else {
                historyDiv.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-robot"></i><br>
                    자동 분석 기록이 없습니다
                </div>
            `;
            }
        })
        .catch(error => {
            console.error('Error loading analysis history:', error);
            document.getElementById('analysis-history').innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="fas fa-exclamation-triangle"></i><br>
                분석 이력 로드 실패
            </div>
        `;
        });
}

// 분석 이력 새로고침
function refreshAnalysisHistory() {
    const historyDiv = document.getElementById('analysis-history');
    historyDiv.innerHTML = '<div class="text-center text-muted"><i class="fas fa-spinner fa-spin"></i> 로딩 중...</div>';
    loadAnalysisHistory();
}

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', async function () {
    console.log('페이지 로드 시작');

    // 백테스트 히스토리 로드
    loadBacktestHistory();

    // 자동 분석 이력 로드
    loadAnalysisHistory();

    // 거래 설정 가져오기
    await fetchTradingConfig();
    console.log('거래 설정 로드 완료:', tradeIntervalMinutes);

    // 서버 자동 거래 상태 가져오기 및 UI 업데이트
    await updateAutoTradingStatus();
    console.log('자동 거래 상태 업데이트 완료');

    // 10초마다 자동 거래 상태 업데이트
    setInterval(updateAutoTradingStatus, 10000);

    // 자동거래 상태 확인 및 타이머 시작
    checkTradingStatusAndStartTimer();

    // 주기적으로 분석 이력 업데이트 (1분마다)
    setInterval(loadAnalysisHistory, 60000);

    // 전략 링크 클릭 이벤트 처리
    document.addEventListener('click', function (e) {
        if (e.target.closest('.strategy-link')) {
            e.preventDefault();
            const strategyId = e.target.closest('.strategy-link').dataset.strategyId;
            showStrategyDetails(strategyId);
        }
    });

    // 자동 새로고침 (30초마다)
    setInterval(() => {
        // 분석 결과나 실행 결과가 표시 중이면 새로고침 건너뛰기
        const analysisVisible = document.getElementById('analysis-results').style.display !== 'none';
        const executionVisible = document.getElementById('execution-results').style.display !== 'none';
        const backtestVisible = document.getElementById('backtest-results').style.display !== 'none';

        if (!analysisVisible && !executionVisible && !backtestVisible) {
            // 백그라운드에서 데이터만 업데이트
            updateDashboardData();
        }
    }, 30000);
});

// 자동거래 상태 확인 및 타이머 시작
function checkTradingStatusAndStartTimer() {
    const tradingStatusElement = document.querySelector('#trading-status-container .badge');
    const timerElement = document.getElementById('next-trade-timer');

    if (tradingStatusElement && tradingStatusElement.classList.contains('bg-success')) {
        // 자동거래가 활성화 상태면 타이머 시작
        if (timerElement) {
            timerElement.style.display = 'block';
            startTradingCountdown();
        }
    }
}

// 대시보드 데이터 업데이트 (페이지 새로고침 없이)
function updateDashboardData() {
    fetch('/api/dashboard_data')
        .then(response => response.json())
        .then(data => {
            // 통계 업데이트
            if (data.total_trades !== undefined) {
                document.getElementById('total-trades').textContent = data.total_trades;
            }
            if (data.today_trades !== undefined) {
                document.getElementById('today-trades').textContent = data.today_trades;
            }
            if (data.total_pnl !== undefined) {
                const pnlElement = document.getElementById('total-pnl');
                pnlElement.textContent = data.total_pnl.toLocaleString() + ' KRW';
                pnlElement.className = data.total_pnl >= 0 ? 'profit' : 'loss';
            }
            if (data.win_rate !== undefined) {
                document.getElementById('win-rate').textContent = data.win_rate.toFixed(1) + '%';
            }
        })
        .catch(error => {
            console.error('Dashboard data update error:', error);
        });
}