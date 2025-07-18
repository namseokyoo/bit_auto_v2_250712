// 대시보드 JavaScript 함수들

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
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('danger', data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('danger', '자동거래 토글 중 오류가 발생했습니다.');
    });
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
    
    switch(action) {
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
            // 잔고 정보 새로고침
            setTimeout(() => location.reload(), 2000);
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

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', function() {
    // 백테스트 히스토리 로드
    loadBacktestHistory();
    
    // 전략 링크 클릭 이벤트 처리
    document.addEventListener('click', function(e) {
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