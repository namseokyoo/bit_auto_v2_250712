"""
Enhanced Quantum Trading Dashboard with AI Analysis and Multi-Coin Control
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
from functools import wraps
from dotenv import load_dotenv
import pyupbit
import yaml
import subprocess
import pytz
import psutil

# KST 타임존 설정
KST = pytz.timezone('Asia/Seoul')

# 환경 변수 로드
load_dotenv('config/.env')

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 앱
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'quantum-trading-secret')

# Redis 연결 (옵션)
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected for dashboard")
except:
    redis_client = None
    logger.warning("Redis not available for dashboard")

# 대시보드 HTML 템플릿
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>퀀텀 트레이딩 대시보드 v3.0</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #4ade80 0%, #22d3ee 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            color: #94a3b8;
            font-size: 1.1em;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab {
            padding: 10px 20px;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 5px;
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.3s;
        }
        .tab.active {
            background: #4ade80;
            color: #000;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h3 {
            color: #4ade80;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-label {
            color: #94a3b8;
        }
        .metric-value {
            font-weight: bold;
            font-size: 1.1em;
        }
        .positive {
            color: #4ade80;
        }
        .negative {
            color: #ef4444;
        }
        .neutral {
            color: #fbbf24;
        }
        table {
            width: 100%;
            margin-top: 10px;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(255,255,255,0.1);
            color: #4ade80;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
            margin: 5px;
        }
        .btn-primary {
            background: #4ade80;
            color: #000;
        }
        .btn-danger {
            background: #ef4444;
            color: #fff;
        }
        .btn-warning {
            background: #fbbf24;
            color: #000;
        }
        .btn:hover {
            opacity: 0.8;
            transform: scale(1.05);
        }
        .loading {
            text-align: center;
            color: #94a3b8;
            padding: 20px;
        }
        .analysis-item {
            background: rgba(255,255,255,0.05);
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .analysis-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .analysis-date {
            color: #94a3b8;
            font-size: 0.9em;
        }
        .analysis-type {
            color: #4ade80;
            font-weight: bold;
        }
        .analysis-content {
            color: #e2e8f0;
            line-height: 1.5;
        }
        .coin-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        .coin-card {
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .coin-symbol {
            font-size: 1.5em;
            font-weight: bold;
            color: #4ade80;
            margin-bottom: 10px;
        }
        .coin-price {
            font-size: 0.9em;
            color: #94a3b8;
            margin-bottom: 5px;
        }
        .coin-pnl {
            font-size: 1.1em;
            font-weight: bold;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-running {
            background: #4ade80;
            animation: pulse 2s infinite;
        }
        .status-stopped {
            background: #ef4444;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .log-viewer {
            background: #000;
            color: #0f0;
            font-family: 'Courier New', monospace;
            padding: 15px;
            border-radius: 5px;
            height: 400px;
            overflow-y: auto;
            font-size: 12px;
            line-height: 1.4;
        }
        .control-panel {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        .status-message {
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            display: none;
        }
        .status-success {
            background: rgba(74, 222, 128, 0.2);
            color: #4ade80;
            border: 1px solid #4ade80;
        }
        .status-error {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid #ef4444;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>퀀텀 트레이딩 대시보드 v3.0</h1>
            <div class="subtitle">AI-Powered Multi-Coin Trading System with DeepSeek Analysis</div>
        </div>
        
        <div class="tabs">
            <button class="tab active" data-tab="overview">📊 개요</button>
            <button class="tab" data-tab="ai">🤖 AI 분석</button>
            <button class="tab" data-tab="multi-coin">💰 멀티코인</button>
            <button class="tab" data-tab="backtest">🧪 백테스트</button>
            <button class="tab" data-tab="optimization">🎯 최적화</button>
            <button class="tab" data-tab="control">🎮 제어판</button>
            <button class="tab" data-tab="trades">📈 거래내역</button>
            <button class="tab" data-tab="settings">⚙️ 설정</button>
            <button class="tab" data-tab="logs">📝 로그</button>
        </div>
        
        <!-- Overview Tab -->
        <div class="tab-content active" id="overview-content">
            <div class="grid">
                <div class="card">
                    <h3>📊 시스템 상태</h3>
                    <div id="system-status">
                        <div class="loading">시스템 상태 로딩중...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>💵 포트폴리오 요약</h3>
                    <div id="portfolio-summary">
                        <div class="loading">포트폴리오 로딩중...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📈 오늘의 성과</h3>
                    <div id="today-performance">
                        <div class="loading">성과 로딩중...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>🎯 활성 전략</h3>
                    <div id="active-strategies">
                        <div class="loading">전략 로딩중...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- AI Analysis Tab -->
        <div class="tab-content" id="ai-content">
            <div class="card">
                <h3>🤖 DeepSeek AI 분석</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="refreshAIAnalysis()">새로고침</button>
                    <button class="btn btn-warning" onclick="triggerAnalysis()">지금 분석 실행</button>
                </div>
                <div id="ai-analysis-list">
                    <div class="loading">AI 분석 로딩중...</div>
                </div>
            </div>
        </div>
        
        <!-- Multi-Coin Tab -->
        <div class="tab-content" id="multi-coin-content">
            <div class="card">
                <h3>💰 멀티코인 거래 상태</h3>
                <div style="text-align: center; padding: 50px; color: #94a3b8;">
                    <h2 style="margin-bottom: 20px;">🚧 준비중입니다 🚧</h2>
                    <p style="font-size: 1.1em; line-height: 1.6;">
                        멀티코인 거래 기능은 현재 개발 중입니다.<br/>
                        곧 BTC, ETH, XRP 등 여러 코인을 동시에 거래할 수 있습니다.<br/>
                        <br/>
                        <span style="color: #4ade80;">현재는 BTC 단일 거래만 지원됩니다.</span>
                    </p>
                </div>
            </div>
        </div>
        
        <!-- Optimization Tab -->
        <div class="tab-content" id="optimization-content">
            <div class="card">
                <h3>⚙️ 파라미터 최적화</h3>
                <div class="optimization-controls">
                    <div class="form-group">
                        <label>전략 선택:</label>
                        <select id="opt-strategy">
                            <option value="momentum_scalping">모멘텀 스캘핑</option>
                            <option value="mean_reversion">평균 회귀</option>
                            <option value="trend_following">추세 추종</option>
                            <option value="ml_prediction">ML 예측</option>
                            <option value="statistical_arbitrage">통계적 차익거래</option>
                            <option value="orderbook_imbalance">오더북 불균형</option>
                            <option value="vwap_trading">VWAP 트레이딩</option>
                            <option value="ichimoku_cloud">일목균형표</option>
                            <option value="combined_signal">복합 신호</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>최적화 방법:</label>
                        <select id="opt-method">
                            <option value="grid_search">Grid Search</option>
                            <option value="random_search">Random Search</option>
                            <option value="genetic_algorithm">Genetic Algorithm</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>심볼:</label>
                        <select id="opt-symbol">
                            <option value="KRW-BTC">BTC</option>
                            <option value="KRW-ETH">ETH</option>
                            <option value="KRW-XRP">XRP</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>테스트 기간 (일):</label>
                        <input type="number" id="opt-days" value="30" min="7" max="90">
                    </div>
                    <button class="btn btn-primary" onclick="runOptimization()">🚀 최적화 시작</button>
                </div>
                <div id="opt-status" class="status-message"></div>
            </div>
            
            <div class="card" id="opt-progress" style="display: none;">
                <h3>⏳ 최적화 진행 상황</h3>
                <div class="progress-bar">
                    <div id="opt-progress-fill" style="width: 0%; background: #4ade80; height: 30px; transition: width 0.5s;"></div>
                </div>
                <div id="opt-progress-text" style="text-align: center; margin-top: 10px;">준비중...</div>
            </div>
            
            <div class="card" id="opt-results" style="display: none;">
                <h3>📊 최적화 결과</h3>
                <div id="opt-best-params" class="analysis-item">
                    <h4>최적 파라미터</h4>
                    <div id="best-params-content"></div>
                </div>
                <div id="opt-comparison" style="margin-top: 20px;">
                    <h4>파라미터 성능 비교</h4>
                    <table id="opt-comparison-table">
                        <thead>
                            <tr>
                                <th>파라미터</th>
                                <th>ROI (%)</th>
                                <th>Sharpe</th>
                                <th>Max DD (%)</th>
                                <th>승률 (%)</th>
                                <th>거래수</th>
                                <th>Fitness</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr><td colspan="7">최적화를 실행하세요</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="card">
                <h3>📚 최적화 히스토리</h3>
                <div id="opt-history">
                    <table>
                        <thead>
                            <tr>
                                <th>시간</th>
                                <th>전략</th>
                                <th>방법</th>
                                <th>심볼</th>
                                <th>최적 ROI</th>
                                <th>Fitness</th>
                                <th>상세</th>
                            </tr>
                        </thead>
                        <tbody id="opt-history-tbody">
                            <tr>
                                <td colspan="7" style="text-align: center;">히스토리가 없습니다</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- Backtest Tab -->
        <div class="tab-content" id="backtest-content">
            <div class="card">
                <h3>📊 백테스트 설정</h3>
                <div class="backtest-controls">
                    <div class="form-group">
                        <label>전략 선택:</label>
                        <select id="backtest-strategy">
                            <option value="momentum_scalping">모멘텀 스캘핑</option>
                            <option value="mean_reversion">평균 회귀</option>
                            <option value="trend_following">추세 추종</option>
                            <option value="all">모든 전략 비교</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>심볼:</label>
                        <select id="backtest-symbol">
                            <option value="KRW-BTC">BTC</option>
                            <option value="KRW-ETH">ETH</option>
                            <option value="KRW-XRP">XRP</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>기간 (일):</label>
                        <input type="number" id="backtest-days" value="30" min="1" max="365">
                    </div>
                    <div class="form-group">
                        <label>초기 자본:</label>
                        <input type="number" id="backtest-capital" value="1000000" step="100000">
                    </div>
                    <button class="btn btn-primary" onclick="runBacktest()">🚀 백테스트 실행</button>
                </div>
                <div id="backtest-status" class="status-message"></div>
            </div>
            
            <div class="card" id="backtest-progress" style="display: none;">
                <h3>⏳ 진행 상황</h3>
                <div class="progress-bar">
                    <div id="progress-fill" style="width: 0%; background: #4CAF50; height: 30px; transition: width 0.5s;"></div>
                </div>
                <div id="progress-text" style="text-align: center; margin-top: 10px;">준비중...</div>
            </div>
            
            <div class="card" id="backtest-results" style="display: none;">
                <h3>📈 백테스트 결과</h3>
                <div class="grid">
                    <div class="metric-card">
                        <h4>총 수익</h4>
                        <div id="result-pnl" class="metric-value">-</div>
                    </div>
                    <div class="metric-card">
                        <h4>수익률 (ROI)</h4>
                        <div id="result-roi" class="metric-value">-</div>
                    </div>
                    <div class="metric-card">
                        <h4>승률</h4>
                        <div id="result-winrate" class="metric-value">-</div>
                    </div>
                    <div class="metric-card">
                        <h4>최대 낙폭</h4>
                        <div id="result-mdd" class="metric-value">-</div>
                    </div>
                    <div class="metric-card">
                        <h4>Sharpe Ratio</h4>
                        <div id="result-sharpe" class="metric-value">-</div>
                    </div>
                    <div class="metric-card">
                        <h4>총 거래</h4>
                        <div id="result-trades" class="metric-value">-</div>
                    </div>
                </div>
                
                <div id="equity-chart" style="margin-top: 20px;">
                    <h4>자산 곡선</h4>
                    <canvas id="equity-canvas" width="800" height="300"></canvas>
                </div>
                
                <div id="ai-analysis" style="margin-top: 20px; display: none;">
                    <h4>🤖 AI 분석 (DeepSeek)</h4>
                    <div id="ai-analysis-text" style="padding: 15px; background: #f5f5f5; border-radius: 5px;"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>📚 백테스트 히스토리</h3>
                <div id="backtest-history">
                    <table>
                        <thead>
                            <tr>
                                <th>시간</th>
                                <th>전략</th>
                                <th>심볼</th>
                                <th>기간</th>
                                <th>ROI</th>
                                <th>승률</th>
                                <th>상세</th>
                            </tr>
                        </thead>
                        <tbody id="history-tbody">
                            <tr>
                                <td colspan="7" style="text-align: center;">히스토리가 없습니다</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- Control Tab -->
        <div class="tab-content" id="control-content">
            <div class="card">
                <h3>💱 거래 모드 설정</h3>
                <div class="control-panel">
                    <div style="margin-bottom: 20px;">
                        <span>현재 모드: </span>
                        <span id="current-mode" style="font-weight: bold; color: #4CAF50;">로딩중...</span>
                    </div>
                    <button class="btn btn-success" onclick="setTradingMode('live')">💰 실거래 모드</button>
                    <button class="btn btn-warning" onclick="setTradingMode('dry_run')">🧪 드라이런 모드</button>
                    <button class="btn btn-info" onclick="setTradingMode('paper')">📝 페이퍼 모드</button>
                </div>
                <div id="mode-status" class="status-message"></div>
            </div>
            
            <div class="card">
                <h3>🎮 시스템 제어</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="controlSystem('start')">▶️ 거래 시작</button>
                    <button class="btn btn-danger" onclick="controlSystem('stop')">⏹️ 거래 중지</button>
                    <button class="btn btn-warning" onclick="controlSystem('restart')">🔄 시스템 재시작</button>
                </div>
                <div id="control-status" class="status-message"></div>
            </div>
            
            <div class="card">
                <h3>🛠️ 빠른 작업</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="emergencyStop()">🚨 긴급 중지</button>
                    <button class="btn btn-warning" onclick="closeAllPositions()">💸 모든 포지션 청산</button>
                    <button class="btn btn-primary" onclick="runBacktest()">📊 백테스트 실행</button>
                </div>
            </div>
            
            <div class="card">
                <h3>📊 프로세스 모니터</h3>
                <div id="process-monitor">
                    <div class="loading">프로세스 상태 로딩중...</div>
                </div>
            </div>
        </div>
        
        <!-- Trades Tab -->
        <div class="tab-content" id="trades-content">
            <div class="card">
                <h3>📈 최근 거래</h3>
                <p style="color: #94a3b8; margin-bottom: 10px;">거래를 클릭하면 상세 정보를 볼 수 있습니다</p>
                <table id="trades-table">
                    <thead>
                        <tr>
                            <th>시간</th>
                            <th>코인</th>
                            <th>전략</th>
                            <th>매수/매도</th>
                            <th>단가</th>
                            <th>수량</th>
                            <th>거래금액</th>
                            <th>손익</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="8" class="loading">Loading trades...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Trade Detail Popup -->
        <div id="trade-detail-popup"></div>
        
        <!-- Settings Tab -->
        <div class="tab-content" id="settings-content">
            <div class="card">
                <h3>⚙️ 거래 설정</h3>
                <div id="trading-config">
                    <div class="loading">설정 로딩중...</div>
                </div>
            </div>
            
            <div class="card">
                <h3>🔑 API Configuration</h3>
                <div id="api-config">
                    <div class="metric">
                        <span class="metric-label">DeepSeek API:</span>
                        <span class="metric-value positive">Configured ✓</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Upbit API:</span>
                        <span class="metric-value" id="upbit-api-status">Checking...</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Logs Tab -->
        <div class="tab-content" id="logs-content">
            <div class="card">
                <h3>📝 시스템 로그</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="refreshLogs()">새로고침</button>
                    <select id="log-filter" onchange="filterLogs()">
                        <option value="all">전체 로그</option>
                        <option value="error">에러만</option>
                        <option value="trade">Trades Only</option>
                        <option value="ai">AI Analysis</option>
                    </select>
                </div>
                <div class="log-viewer" id="log-viewer">
                    Loading logs...
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Load System Status
        async function loadSystemStatus() {
            try {
                const response = await fetch('/api/system-status');
                const data = await response.json();
                
                let html = '';
                html += `<div class="metric">
                    <span class="metric-label">Status:</span>
                    <span class="metric-value ${data.is_running ? 'positive' : 'negative'}">
                        <span class="status-indicator ${data.is_running ? 'status-running' : 'status-stopped'}"></span>
                        ${data.is_running ? '실행중' : '중지됨'}
                    </span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Uptime:</span>
                    <span class="metric-value">${data.uptime || 'N/A'}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">CPU Usage:</span>
                    <span class="metric-value">${data.cpu_usage || 0}%</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Memory:</span>
                    <span class="metric-value">${data.memory_usage || 0}%</span>
                </div>`;
                
                document.getElementById('system-status').innerHTML = html;
            } catch (error) {
                document.getElementById('system-status').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load system status</div>';
            }
        }
        
        // Load Portfolio Summary
        async function loadPortfolioSummary() {
            try {
                const response = await fetch('/api/portfolio');
                const data = await response.json();
                
                let html = '';
                html += `<div class="metric">
                    <span class="metric-label">Total Value:</span>
                    <span class="metric-value">₩${(data.total_value || 0).toLocaleString()}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Available KRW:</span>
                    <span class="metric-value">₩${(data.krw_balance || 0).toLocaleString()}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Invested:</span>
                    <span class="metric-value">₩${(data.invested || 0).toLocaleString()}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Total PnL:</span>
                    <span class="metric-value ${data.total_pnl >= 0 ? 'positive' : 'negative'}">
                        ₩${(data.total_pnl || 0).toLocaleString()}
                    </span>
                </div>`;
                
                document.getElementById('portfolio-summary').innerHTML = html;
            } catch (error) {
                document.getElementById('portfolio-summary').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load portfolio</div>';
            }
        }
        
        // Load Today's Performance
        async function loadTodayPerformance() {
            try {
                const response = await fetch('/api/performance/today');
                const data = await response.json();
                
                let html = '';
                html += `<div class="metric">
                    <span class="metric-label">Trades:</span>
                    <span class="metric-value">${data.trade_count || 0}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Win Rate:</span>
                    <span class="metric-value ${data.win_rate >= 50 ? 'positive' : 'negative'}">
                        ${(data.win_rate || 0).toFixed(1)}%
                    </span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Today's PnL:</span>
                    <span class="metric-value ${data.daily_pnl >= 0 ? 'positive' : 'negative'}">
                        ₩${(data.daily_pnl || 0).toLocaleString()}
                    </span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Return:</span>
                    <span class="metric-value ${data.return_rate >= 0 ? 'positive' : 'negative'}">
                        ${(data.return_rate || 0).toFixed(2)}%
                    </span>
                </div>`;
                
                document.getElementById('today-performance').innerHTML = html;
            } catch (error) {
                document.getElementById('today-performance').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load performance</div>';
            }
        }
        
        // Load Active Strategies
        async function loadActiveStrategies() {
            try {
                const response = await fetch('/api/strategies');
                const data = await response.json();
                
                let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';
                const strategies = data.strategies || [];
                
                strategies.forEach(strategy => {
                    const statusColor = strategy.active ? 'positive' : 'neutral';
                    html += `
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span>${strategy.name}</span>
                            <span class="${statusColor}" style="font-size: 0.9em;">
                                ${strategy.active ? '● Active' : '○ Inactive'}
                            </span>
                        </div>
                    `;
                });
                
                if (strategies.length === 0) {
                    html += '<div style="color: #94a3b8;">No strategies configured</div>';
                }
                
                html += '</div>';
                document.getElementById('active-strategies').innerHTML = html;
            } catch (error) {
                document.getElementById('active-strategies').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load strategies</div>';
            }
        }
        
        // Load AI Analysis
        async function loadAIAnalysis() {
            try {
                const response = await fetch('/api/ai-analysis');
                const data = await response.json();
                
                let html = '';
                const analyses = data.analyses || [];
                
                if (analyses.length > 0) {
                    analyses.forEach(analysis => {
                        const date = new Date(analysis.timestamp).toLocaleString();
                        const implemented = analysis.implemented ? '✅' : '⏳';
                        
                        html += `
                            <div class="analysis-item">
                                <div class="analysis-header">
                                    <span class="analysis-type">${analysis.type}</span>
                                    <span class="analysis-date">${date} ${implemented}</span>
                                </div>
                                <div class="analysis-content">${analysis.analysis}</div>
                            </div>
                        `;
                    });
                } else {
                    html = '<div style="color: #94a3b8; text-align: center; padding: 20px;">No AI analysis available yet</div>';
                }
                
                document.getElementById('ai-analysis-list').innerHTML = html;
            } catch (error) {
                document.getElementById('ai-analysis-list').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load AI analysis</div>';
            }
        }
        
        // Load Multi-Coin Status
        async function loadMultiCoinStatus() {
            try {
                const response = await fetch('/api/multi-coin-status');
                const data = await response.json();
                
                // Coin grid
                let gridHtml = '';
                const coins = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE'];
                
                coins.forEach(coin => {
                    const position = data.positions?.find(p => p.coin?.includes(coin)) || {};
                    const pnl = position.unrealized_pnl || 0;
                    const pnlColor = pnl >= 0 ? 'positive' : 'negative';
                    
                    gridHtml += `
                        <div class="coin-card">
                            <div class="coin-symbol">${coin}</div>
                            <div class="coin-price">₩${(position.current_value || 0).toLocaleString()}</div>
                            <div class="coin-pnl ${pnlColor}">${pnl >= 0 ? '+' : ''}${pnl.toLocaleString()}</div>
                        </div>
                    `;
                });
                
                document.getElementById('coin-status-grid').innerHTML = gridHtml;
                
                // Performance table
                let tableHtml = '';
                if (data.positions && data.positions.length > 0) {
                    data.positions.forEach(pos => {
                        const pnlPercent = pos.avg_price > 0 ? 
                            ((pos.current_value / (pos.quantity * pos.avg_price) - 1) * 100) : 0;
                        const pnlColor = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
                        
                        tableHtml += `
                            <tr>
                                <td>${pos.coin}</td>
                                <td>${Number(pos.quantity).toFixed(8)}</td>
                                <td>₩${Number(pos.avg_price).toLocaleString()}</td>
                                <td>₩${Number(pos.current_value / pos.quantity || 0).toLocaleString()}</td>
                                <td class="${pnlColor}">₩${Number(pos.unrealized_pnl).toLocaleString()}</td>
                                <td class="${pnlColor}">${pnlPercent.toFixed(2)}%</td>
                            </tr>
                        `;
                    });
                } else {
                    tableHtml = '<tr><td colspan="6" style="text-align: center; color: #94a3b8;">No positions</td></tr>';
                }
                
                document.querySelector('#coin-performance-table tbody').innerHTML = tableHtml;
            } catch (error) {
                document.getElementById('coin-status-grid').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load coin status</div>';
            }
        }
        
        // System Control
        async function controlSystem(action) {
            const statusDiv = document.getElementById('control-status');
            statusDiv.style.display = 'block';
            statusDiv.className = 'status-message';
            statusDiv.innerHTML = `Executing ${action}...`;
            
            try {
                const response = await fetch(`/api/control/${action}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await response.json();
                
                if (data.status) {
                    statusDiv.className = 'status-message status-success';
                    statusDiv.innerHTML = `✅ System ${data.status}`;
                    setTimeout(() => {
                        loadSystemStatus();
                        loadProcessMonitor();
                    }, 2000);
                } else {
                    statusDiv.className = 'status-message status-error';
                    statusDiv.innerHTML = `❌ Error: ${data.error}`;
                }
            } catch (error) {
                statusDiv.className = 'status-message status-error';
                statusDiv.innerHTML = `❌ Failed to ${action}`;
            }
        }
        
        // Trading Mode Functions
        async function getCurrentMode() {
            try {
                const response = await fetch('/api/trading-mode');
                const data = await response.json();
                const modeSpan = document.getElementById('current-mode');
                if (modeSpan) {
                    modeSpan.textContent = data.mode.toUpperCase();
                    if (data.mode === 'live') {
                        modeSpan.style.color = '#f44336';  // Red for live
                    } else if (data.mode === 'dry_run') {
                        modeSpan.style.color = '#ff9800';  // Orange for dry_run
                    } else {
                        modeSpan.style.color = '#2196F3';  // Blue for paper
                    }
                }
            } catch (error) {
                console.error('Error fetching trading mode:', error);
            }
        }
        
        async function setTradingMode(mode) {
            const statusDiv = document.getElementById('mode-status');
            statusDiv.style.display = 'block';
            statusDiv.className = 'status-message';
            statusDiv.innerHTML = `모드 변경 중...`;
            
            try {
                const response = await fetch('/api/trading-mode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: mode})
                });
                const data = await response.json();
                
                if (data.status === 'success') {
                    statusDiv.className = 'status-message status-success';
                    statusDiv.innerHTML = `✅ ${data.message}`;
                    getCurrentMode();  // Update display
                    
                    // Show restart reminder
                    setTimeout(() => {
                        if (confirm('모드가 변경되었습니다. 시스템을 재시작하시겠습니까?')) {
                            controlSystem('restart');
                        }
                    }, 1000);
                } else {
                    statusDiv.className = 'status-message status-error';
                    statusDiv.innerHTML = `❌ Error: ${data.error}`;
                }
            } catch (error) {
                statusDiv.className = 'status-message status-error';
                statusDiv.innerHTML = `❌ Error: ${error.message}`;
            }
            
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 5000);
        }
        
        // Emergency Stop
        async function emergencyStop() {
            if (confirm('긴급 정지를 실행하시겠습니까? 모든 거래가 즉시 중단됩니다.')) {
                try {
                    const response = await fetch('/api/emergency-stop', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    alert(data.message || '긴급 정지 실행됨');
                } catch (error) {
                    alert('긴급 정지 실행 실패: ' + error.message);
                }
            }
        }
        
        // Close All Positions
        async function closeAllPositions() {
            if (confirm('모든 포지션을 청산하시겠습니까?')) {
                try {
                    const response = await fetch('/api/control/close-all', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'}
                    });
                    const data = await response.json();
                    alert(`Positions closed: ${data.message}`);
                } catch (error) {
                    alert('Failed to close positions');
                }
            }
        }
        
        // Run Backtest
        async function runBacktest() {
            const strategy = document.getElementById('backtest-strategy').value;
            const symbol = document.getElementById('backtest-symbol').value;
            const days = parseInt(document.getElementById('backtest-days').value);
            const capital = parseInt(document.getElementById('backtest-capital').value);
            
            // UI 초기화
            document.getElementById('backtest-status').style.display = 'none';
            document.getElementById('backtest-progress').style.display = 'block';
            document.getElementById('backtest-results').style.display = 'none';
            document.getElementById('progress-fill').style.width = '0%';
            document.getElementById('progress-text').textContent = '백테스트 시작 중...';
            
            try {
                // 진행 상황 업데이트
                let progress = 0;
                const progressInterval = setInterval(() => {
                    progress += 10;
                    if (progress <= 90) {
                        document.getElementById('progress-fill').style.width = progress + '%';
                        document.getElementById('progress-text').textContent = `처리 중... ${progress}%`;
                    }
                }, 500);
                
                // API 호출
                const response = await fetch('/api/backtest/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        strategy: strategy,
                        symbol: symbol,
                        days: days,
                        initial_capital: capital,
                        position_size: 0.1
                    })
                });
                
                clearInterval(progressInterval);
                document.getElementById('progress-fill').style.width = '100%';
                document.getElementById('progress-text').textContent = '완료!';
                
                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.error);
                }
                
                // 결과 표시
                setTimeout(() => {
                    displayBacktestResults(result);
                }, 500);
                
            } catch (error) {
                document.getElementById('backtest-progress').style.display = 'none';
                const statusDiv = document.getElementById('backtest-status');
                statusDiv.style.display = 'block';
                statusDiv.className = 'status-message status-error';
                statusDiv.innerHTML = `❌ 백테스트 실패: ${error.message}`;
            }
        }
        
        function displayBacktestResults(result) {
            document.getElementById('backtest-progress').style.display = 'none';
            document.getElementById('backtest-results').style.display = 'block';
            
            // 메트릭 표시
            document.getElementById('result-pnl').textContent = `₩${result.metrics.net_pnl.toLocaleString()}`;
            document.getElementById('result-roi').textContent = `${result.metrics.roi}%`;
            document.getElementById('result-winrate').textContent = `${result.metrics.win_rate}%`;
            document.getElementById('result-mdd').textContent = `${result.metrics.max_drawdown}%`;
            document.getElementById('result-sharpe').textContent = result.metrics.sharpe_ratio.toFixed(2);
            document.getElementById('result-trades').textContent = result.metrics.total_trades;
            
            // 색상 적용
            const roiElement = document.getElementById('result-roi');
            roiElement.style.color = result.metrics.roi >= 0 ? '#4CAF50' : '#f44336';
            
            const pnlElement = document.getElementById('result-pnl');
            pnlElement.style.color = result.metrics.net_pnl >= 0 ? '#4CAF50' : '#f44336';
            
            // 자산 곡선 그리기
            if (result.equity_curve && result.equity_curve.length > 0) {
                drawEquityChart(result.equity_curve);
            }
            
            // AI 분석 표시
            if (result.ai_analysis) {
                document.getElementById('ai-analysis').style.display = 'block';
                document.getElementById('ai-analysis-text').textContent = result.ai_analysis;
            }
            
            // 히스토리에 추가
            addToHistory(result);
        }
        
        function drawEquityChart(equityData) {
            const canvas = document.getElementById('equity-canvas');
            const ctx = canvas.getContext('2d');
            
            // 캔버스 클리어
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            if (equityData.length === 0) return;
            
            const padding = 40;
            const width = canvas.width - padding * 2;
            const height = canvas.height - padding * 2;
            
            // 최소/최대값 찾기
            const minValue = Math.min(...equityData);
            const maxValue = Math.max(...equityData);
            const range = maxValue - minValue || 1;
            
            // 축 그리기
            ctx.strokeStyle = '#ddd';
            ctx.beginPath();
            ctx.moveTo(padding, padding);
            ctx.lineTo(padding, canvas.height - padding);
            ctx.lineTo(canvas.width - padding, canvas.height - padding);
            ctx.stroke();
            
            // 자산 곡선 그리기
            ctx.strokeStyle = '#4CAF50';
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            equityData.forEach((value, index) => {
                const x = padding + (index / (equityData.length - 1)) * width;
                const y = padding + height - ((value - minValue) / range) * height;
                
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            
            ctx.stroke();
            
            // 초기 자본선 그리기
            const initialCapital = equityData[0];
            const initialY = padding + height - ((initialCapital - minValue) / range) * height;
            ctx.strokeStyle = '#999';
            ctx.lineWidth = 1;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(padding, initialY);
            ctx.lineTo(canvas.width - padding, initialY);
            ctx.stroke();
            ctx.setLineDash([]);
        }
        
        function addToHistory(result) {
            const tbody = document.getElementById('history-tbody');
            
            // 빈 메시지 제거
            if (tbody.querySelector('td[colspan="7"]')) {
                tbody.innerHTML = '';
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date().toLocaleString('ko-KR')}</td>
                <td>${result.strategy}</td>
                <td>${result.symbol}</td>
                <td>${result.period}</td>
                <td style="color: ${result.metrics.roi >= 0 ? '#4CAF50' : '#f44336'}">${result.metrics.roi}%</td>
                <td>${result.metrics.win_rate}%</td>
                <td><button class="btn btn-sm" onclick="viewBacktestDetail(${result.session_id})">상세</button></td>
            `;
            
            tbody.insertBefore(row, tbody.firstChild);
            
            // 최대 10개만 유지
            while (tbody.children.length > 10) {
                tbody.removeChild(tbody.lastChild);
            }
        }
        
        async function viewBacktestDetail(sessionId) {
            try {
                const response = await fetch(`/api/backtest/detail/${sessionId}`);
                const detail = await response.json();
                console.log('Backtest detail:', detail);
                alert('상세 정보는 콘솔에서 확인하세요.');
            } catch (error) {
                alert('상세 정보를 불러올 수 없습니다.');
            }
        }
        
        // Load Process Monitor
        async function loadProcessMonitor() {
            try {
                const response = await fetch('/api/processes');
                const data = await response.json();
                
                let html = '<table style="width: 100%;">';
                html += '<tr><th>Process</th><th>상태</th><th>PID</th></tr>';
                
                const processes = data.processes || [];
                processes.forEach(proc => {
                    const statusIcon = proc.running ? '🟢' : '🔴';
                    html += `
                        <tr>
                            <td>${proc.name}</td>
                            <td>${statusIcon} ${proc.running ? '실행중' : '중지됨'}</td>
                            <td>${proc.pid || 'N/A'}</td>
                        </tr>
                    `;
                });
                
                html += '</table>';
                document.getElementById('process-monitor').innerHTML = html;
            } catch (error) {
                document.getElementById('process-monitor').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load process monitor</div>';
            }
        }
        
        // Load Trades
        async function loadTrades() {
            try {
                const response = await fetch('/api/trades/recent');
                const data = await response.json();
                
                let html = '';
                const trades = data.trades || [];
                
                if (trades.length > 0) {
                    trades.forEach((trade, index) => {
                        const time = new Date(trade.timestamp).toLocaleString();
                        const pnlColor = trade.pnl >= 0 ? 'positive' : 'negative';
                        
                        // 매수/매도를 한글로 표시
                        let sideText = '';
                        let sideColor = '';
                        if (trade.side === 'bid' || trade.side === 'buy') {
                            sideText = '매수';
                            sideColor = 'positive';
                        } else if (trade.side === 'ask' || trade.side === 'sell') {
                            sideText = '매도';
                            sideColor = 'negative';
                        } else {
                            sideText = trade.side;
                            sideColor = 'neutral';
                        }
                        
                        // 거래금액 계산
                        const totalAmount = trade.price * trade.quantity;
                        
                        html += `
                            <tr style="cursor: pointer;" onclick="showTradeDetail(${index})" data-trade='${JSON.stringify(trade)}'>
                                <td>${time}</td>
                                <td>${trade.coin || trade.symbol}</td>
                                <td>${trade.strategy || 'Quantum'}</td>
                                <td class="${sideColor}" style="font-weight: bold;">${sideText}</td>
                                <td>₩${Number(trade.price).toLocaleString()}</td>
                                <td>${Number(trade.quantity).toFixed(8)}</td>
                                <td>₩${Number(totalAmount).toLocaleString()}</td>
                                <td class="${pnlColor}">₩${Number(trade.pnl || 0).toLocaleString()}</td>
                            </tr>
                        `;
                    });
                } else {
                    html = '<tr><td colspan="8" style="text-align: center; color: #94a3b8;">거래 없음</td></tr>';
                }
                
                document.querySelector('#trades-table tbody').innerHTML = html;
            } catch (error) {
                document.querySelector('#trades-table tbody').innerHTML = 
                    '<tr><td colspan="8" style="color: #ef4444;">Failed to load trades</td></tr>';
            }
        }
        
        // 거래 상세 정보 표시
        function showTradeDetail(index) {
            const tradeRow = document.querySelectorAll('#trades-table tbody tr')[index];
            const trade = JSON.parse(tradeRow.getAttribute('data-trade'));
            
            const detailHtml = `
                <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                     background: #1e293b; border: 1px solid #4ade80; border-radius: 10px; 
                     padding: 20px; max-width: 500px; z-index: 1000;">
                    <h3 style="margin-bottom: 15px; color: #4ade80;">거래 상세 정보</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div><strong>시간:</strong></div>
                        <div>${new Date(trade.timestamp).toLocaleString()}</div>
                        
                        <div><strong>심볼:</strong></div>
                        <div>${trade.symbol || trade.coin}</div>
                        
                        <div><strong>거래 유형:</strong></div>
                        <div class="${trade.side === 'bid' || trade.side === 'buy' ? 'positive' : 'negative'}">
                            ${trade.side === 'bid' || trade.side === 'buy' ? '매수' : '매도'}
                        </div>
                        
                        <div><strong>단가:</strong></div>
                        <div>₩${Number(trade.price).toLocaleString()}</div>
                        
                        <div><strong>수량:</strong></div>
                        <div>${Number(trade.quantity).toFixed(8)}</div>
                        
                        <div><strong>거래금액:</strong></div>
                        <div>₩${Number(trade.price * trade.quantity).toLocaleString()}</div>
                        
                        <div><strong>전략:</strong></div>
                        <div>${trade.strategy || 'Quantum Trading'}</div>
                        
                        <div><strong>손익:</strong></div>
                        <div class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                            ₩${Number(trade.pnl || 0).toLocaleString()}
                        </div>
                        
                        ${trade.signal_strength ? `
                        <div><strong>신호 강도:</strong></div>
                        <div>${(trade.signal_strength * 100).toFixed(1)}%</div>
                        ` : ''}
                        
                        ${trade.reason ? `
                        <div><strong>거래 사유:</strong></div>
                        <div style="grid-column: span 2;">${trade.reason}</div>
                        ` : ''}
                    </div>
                    <button onclick="closeTradeDetail()" style="margin-top: 20px; width: 100%; 
                            padding: 10px; background: #4ade80; color: #1e293b; 
                            border: none; border-radius: 5px; cursor: pointer;">
                        닫기
                    </button>
                </div>
                <div onclick="closeTradeDetail()" style="position: fixed; top: 0; left: 0; 
                     width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 999;"></div>
            `;
            
            document.getElementById('trade-detail-popup').innerHTML = detailHtml;
        }
        
        function closeTradeDetail() {
            document.getElementById('trade-detail-popup').innerHTML = '';
        }
        
        // Load Settings
        async function loadSettings() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                
                let html = '';
                html += `<div class="metric">
                    <span class="metric-label">거래 모드:</span>
                    <span class="metric-value ${data.trading_mode === 'live' ? 'positive' : 'neutral'}">
                        ${data.trading_mode === 'live' ? '🔴 실거래' : data.trading_mode === 'dry_run' || data.trading_mode === 'dry-run' ? '🟡 테스트' : data.trading_mode}
                    </span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">최대 포지션:</span>
                    <span class="metric-value">₩${(data.max_position || 0).toLocaleString()}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">일일 손실 한도:</span>
                    <span class="metric-value negative">${(data.daily_loss_limit || -5)}%</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">신호 임계값:</span>
                    <span class="metric-value">${data.signal_threshold || 0.03}</span>
                </div>`;
                
                document.getElementById('trading-config').innerHTML = html;
                
                // Check Upbit API
                checkUpbitAPI();
            } catch (error) {
                document.getElementById('trading-config').innerHTML = 
                    '<div style="color: #ef4444;">Failed to load configuration</div>';
            }
        }
        
        // Check Upbit API Status
        async function checkUpbitAPI() {
            try {
                const response = await fetch('/api/check-upbit');
                const data = await response.json();
                
                const statusElement = document.getElementById('upbit-api-status');
                if (data.connected) {
                    statusElement.className = 'metric-value positive';
                    statusElement.innerHTML = 'Connected ✓';
                } else {
                    statusElement.className = 'metric-value negative';
                    statusElement.innerHTML = 'Not Connected ✗';
                }
            } catch (error) {
                document.getElementById('upbit-api-status').innerHTML = 'Error checking';
            }
        }
        
        // Refresh AI Analysis
        async function refreshAIAnalysis() {
            await loadAIAnalysis();
        }
        
        // Trigger AI Analysis
        async function triggerAnalysis() {
            if (confirm('Trigger AI analysis now? This will run DeepSeek analysis immediately.')) {
                try {
                    const response = await fetch('/api/ai-analysis/trigger', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'}
                    });
                    const data = await response.json();
                    alert('AI analysis triggered successfully');
                    setTimeout(refreshAIAnalysis, 3000);
                } catch (error) {
                    alert('Failed to trigger AI analysis');
                }
            }
        }
        
        // Load Logs
        async function refreshLogs() {
            try {
                const filter = document.getElementById('log-filter')?.value || 'all';
                const response = await fetch(`/api/logs?filter=${filter}`);
                const data = await response.json();
                
                const logs = data.logs || [];
                let logHtml = logs.join('\\n');
                
                if (!logHtml) {
                    logHtml = '로그 없음';
                }
                
                document.getElementById('log-viewer').textContent = logHtml;
                // Auto-scroll to bottom
                const viewer = document.getElementById('log-viewer');
                viewer.scrollTop = viewer.scrollHeight;
            } catch (error) {
                document.getElementById('log-viewer').textContent = 'Failed to load logs';
            }
        }
        
        // Filter Logs
        function filterLogs() {
            refreshLogs();
        }
        
        // Tab switching functionality
        function switchTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            const selectedContent = document.getElementById(tabName + '-content');
            if (selectedContent) {
                selectedContent.classList.add('active');
            }
            
            // Add active class to selected tab
            const selectedTab = document.querySelector(`[data-tab="${tabName}"]`);
            if (selectedTab) {
                selectedTab.classList.add('active');
            }
            
            // Load data for selected tab
            loadTabData(tabName);
        }
        
        // Load data for specific tab
        function loadTabData(tabName) {
            switch(tabName) {
                case 'overview':
                    loadSystemStatus();
                    loadPortfolioSummary();
                    loadTodayPerformance();
                    loadActiveStrategies();
                    break;
                case 'ai':
                    loadAIAnalysis();
                    break;
                case 'multi-coin':
                    loadMultiCoinStatus();
                    break;
                case 'optimization':
                    loadOptimizationHistory();
                    break;
                case 'control':
                    loadProcessMonitor();
                    break;
                case 'trades':
                    loadTrades();
                    break;
                case 'settings':
                    loadSettings();
                    checkUpbitAPI();
                    break;
                case 'logs':
                    refreshLogs();
                    break;
            }
        }
        
        // Initialize Dashboard
        async function initDashboard() {
            try {
                console.log('Initializing dashboard...');
                
                // Get current trading mode
                getCurrentMode();
                
                // Add click event listeners to tabs
                const tabs = document.querySelectorAll('.tab');
                console.log('Found tabs:', tabs.length);
                
                tabs.forEach(tab => {
                    // Remove any existing listeners first
                    tab.replaceWith(tab.cloneNode(true));
                });
                
                // Re-select tabs after cloning
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.addEventListener('click', function(e) {
                        e.preventDefault();
                        const tabName = this.getAttribute('data-tab');
                        console.log('Tab clicked:', tabName);
                        if (tabName) {
                            switchTab(tabName);
                        }
                    });
                });
                
                // Load initial data with error handling
                try {
                    await loadSystemStatus();
                } catch(e) {
                    console.error('Error loading system status:', e);
                }
                
                try {
                    await loadPortfolioSummary();
                } catch(e) {
                    console.error('Error loading portfolio:', e);
                }
                
                try {
                    await loadTodayPerformance();
                } catch(e) {
                    console.error('Error loading performance:', e);
                }
                
                try {
                    await loadActiveStrategies();
                } catch(e) {
                    console.error('Error loading strategies:', e);
                }
                
                console.log('Dashboard initialization complete');
            } catch(error) {
                console.error('Dashboard initialization error:', error);
            }
        }
        
        // Wait for DOM to be ready and initialize only once
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOM loaded, initializing dashboard...');
                initDashboard();
            });
        } else {
            // DOM is already ready
            console.log('DOM ready, initializing dashboard...');
            setTimeout(initDashboard, 100);  // Small delay to ensure everything is ready
        }
        
        // Auto-refresh
        setInterval(() => {
            const activeTab = document.querySelector('.tab-content.active');
            if (activeTab) {
                const activeTabId = activeTab.id;
                
                if (activeTabId === 'overview-content') {
                    loadSystemStatus();
                    loadPortfolioSummary();
                    loadTodayPerformance();
                    loadActiveStrategies();
                } else if (activeTabId === 'multi-coin-content') {
                    loadMultiCoinStatus();
                } else if (activeTabId === 'trades-content') {
                    loadTrades();
                }
            }
        }, 5000); // Refresh every 5 seconds
        
        // Optimization Functions
        async function runOptimization() {
            const strategy = document.getElementById('opt-strategy').value;
            const method = document.getElementById('opt-method').value;
            const symbol = document.getElementById('opt-symbol').value;
            const days = parseInt(document.getElementById('opt-days').value);
            
            // UI 초기화
            document.getElementById('opt-status').style.display = 'none';
            document.getElementById('opt-progress').style.display = 'block';
            document.getElementById('opt-results').style.display = 'none';
            document.getElementById('opt-progress-fill').style.width = '0%';
            document.getElementById('opt-progress-text').textContent = '최적화 시작 중...';
            
            try {
                // 진행 상황 업데이트
                let progress = 0;
                const progressInterval = setInterval(() => {
                    progress += 5;
                    if (progress <= 90) {
                        document.getElementById('opt-progress-fill').style.width = progress + '%';
                        document.getElementById('opt-progress-text').textContent = `최적화 진행 중... ${progress}%`;
                    }
                }, 1000);
                
                // API 호출
                const response = await fetch('/api/optimization/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        strategy: strategy,
                        method: method,
                        symbol: symbol,
                        days: days
                    })
                });
                
                clearInterval(progressInterval);
                document.getElementById('opt-progress-fill').style.width = '100%';
                document.getElementById('opt-progress-text').textContent = '완료!';
                
                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.error);
                }
                
                // 결과 표시
                setTimeout(() => {
                    displayOptimizationResults(result);
                }, 500);
                
            } catch (error) {
                document.getElementById('opt-progress').style.display = 'none';
                const statusDiv = document.getElementById('opt-status');
                statusDiv.style.display = 'block';
                statusDiv.className = 'status-message status-error';
                statusDiv.innerHTML = `❌ 최적화 실패: ${error.message}`;
            }
        }
        
        function displayOptimizationResults(result) {
            document.getElementById('opt-progress').style.display = 'none';
            document.getElementById('opt-results').style.display = 'block';
            
            // 최적 파라미터 표시
            const bestParamsContent = document.getElementById('best-params-content');
            let paramsHtml = '<div style="font-family: monospace; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 5px;">';
            for (const [key, value] of Object.entries(result.best_params)) {
                paramsHtml += `<div><strong>${key}:</strong> ${value}</div>`;
            }
            paramsHtml += `<div style="margin-top: 10px; color: #4ade80;"><strong>Best ROI:</strong> ${result.best_roi}%</div>`;
            paramsHtml += `<div><strong>Fitness Score:</strong> ${result.best_fitness.toFixed(4)}</div>`;
            paramsHtml += '</div>';
            bestParamsContent.innerHTML = paramsHtml;
            
            // 비교 테이블 표시
            const tbody = document.querySelector('#opt-comparison-table tbody');
            let tableHtml = '';
            
            result.all_results.forEach((res, idx) => {
                const isBest = idx === 0;
                const rowClass = isBest ? 'style="background: rgba(74, 222, 128, 0.1);"' : '';
                tableHtml += `
                    <tr ${rowClass}>
                        <td><small>${JSON.stringify(res.params).substring(0, 30)}...</small></td>
                        <td style="color: ${res.roi >= 0 ? '#4ade80' : '#ef4444'}">${res.roi}%</td>
                        <td>${res.sharpe.toFixed(2)}</td>
                        <td style="color: #ef4444">${res.max_drawdown}%</td>
                        <td>${res.win_rate}%</td>
                        <td>${res.trades}</td>
                        <td><strong>${res.fitness.toFixed(4)}</strong></td>
                    </tr>
                `;
            });
            
            tbody.innerHTML = tableHtml;
            
            // 히스토리에 추가
            addToOptimizationHistory(result);
        }
        
        function addToOptimizationHistory(result) {
            const tbody = document.getElementById('opt-history-tbody');
            
            // 빈 메시지 제거
            if (tbody.querySelector('td[colspan="7"]')) {
                tbody.innerHTML = '';
            }
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date().toLocaleString('ko-KR')}</td>
                <td>${result.strategy}</td>
                <td>${result.method}</td>
                <td>${result.symbol}</td>
                <td style="color: ${result.best_roi >= 0 ? '#4ade80' : '#ef4444'}">${result.best_roi}%</td>
                <td>${result.best_fitness.toFixed(4)}</td>
                <td><button class="btn btn-sm" onclick="viewOptimizationDetail('${result.session_id}')">상세</button></td>
            `;
            
            tbody.insertBefore(row, tbody.firstChild);
            
            // 최대 10개만 유지
            while (tbody.children.length > 10) {
                tbody.removeChild(tbody.lastChild);
            }
        }
        
        async function loadOptimizationHistory() {
            try {
                const response = await fetch('/api/optimization/history');
                const data = await response.json();
                
                const tbody = document.getElementById('opt-history-tbody');
                
                if (data.history && data.history.length > 0) {
                    let html = '';
                    data.history.forEach(item => {
                        html += `
                            <tr>
                                <td>${item.timestamp}</td>
                                <td>${item.strategy}</td>
                                <td>${item.method}</td>
                                <td>${item.symbol}</td>
                                <td style="color: ${item.best_roi >= 0 ? '#4ade80' : '#ef4444'}">${item.best_roi}%</td>
                                <td>${item.fitness.toFixed(4)}</td>
                                <td><button class="btn btn-sm" onclick="viewOptimizationDetail('${item.id}')">상세</button></td>
                            </tr>
                        `;
                    });
                    tbody.innerHTML = html;
                }
            } catch (error) {
                console.error('Failed to load optimization history:', error);
            }
        }
        
        async function viewOptimizationDetail(sessionId) {
            try {
                const response = await fetch(`/api/optimization/detail/${sessionId}`);
                const detail = await response.json();
                console.log('Optimization detail:', detail);
                alert('최적화 상세 정보는 콘솔에서 확인하세요.');
            } catch (error) {
                alert('상세 정보를 불러올 수 없습니다.');
            }
        }
        
        // Start
        initDashboard();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """메인 대시보드 페이지"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/system-status')
def get_system_status():
    """시스템 상태 조회"""
    try:
        # Check if processes are running
        is_running = False
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'integrated_trading_system.py' in cmdline or 'quantum_trading.py' in cmdline:
                    is_running = True
                    processes.append(proc.info['pid'])
            except:
                pass
        
        # Get system metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Calculate uptime if running
        uptime = "N/A"
        if is_running and processes:
            try:
                proc = psutil.Process(processes[0])
                create_time = datetime.fromtimestamp(proc.create_time())
                uptime_delta = datetime.now() - create_time
                hours = int(uptime_delta.total_seconds() // 3600)
                minutes = int((uptime_delta.total_seconds() % 3600) // 60)
                uptime = f"{hours}h {minutes}m"
            except:
                pass
        
        return jsonify({
            'is_running': is_running,
            'uptime': uptime,
            'cpu_usage': round(cpu_usage, 1),
            'memory_usage': round(memory.percent, 1),
            'processes': processes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio')
def get_portfolio():
    """포트폴리오 정보 조회"""
    try:
        import pyupbit
        from dotenv import load_dotenv
        import os
        
        # 환경변수 로드
        load_dotenv('config/.env')
        
        total_value = 0
        krw_balance = 0
        invested = 0
        total_pnl = 0
        
        # Upbit API로 실제 잔고 조회
        access_key = os.getenv('UPBIT_ACCESS_KEY')
        secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if access_key and secret_key:
            try:
                upbit = pyupbit.Upbit(access_key, secret_key)
                balances = upbit.get_balances()
                
                for balance in balances:
                    currency = balance['currency']
                    if currency == 'KRW':
                        krw_balance = float(balance['balance'])
                        total_value += krw_balance
                    else:
                        # 코인 평가액 계산
                        symbol = f"KRW-{currency}"
                        try:
                            current_price = pyupbit.get_current_price(symbol)
                            if current_price:
                                coin_balance = float(balance['balance'])
                                coin_value = coin_balance * current_price
                                total_value += coin_value
                                
                                # 투자금액 계산 (평균매수가 * 수량)
                                avg_buy_price = float(balance.get('avg_buy_price', 0))
                                if avg_buy_price > 0:
                                    invested += avg_buy_price * coin_balance
                        except:
                            pass  # 일부 코인은 KRW 마켓이 없을 수 있음
                            
                # PnL 계산
                if invested > 0:
                    total_pnl = (total_value - krw_balance) - invested
                    
                # Redis에 저장
                if redis_client:
                    redis_client.hset('portfolio:summary', mapping={
                        'total_value': total_value,
                        'krw_balance': krw_balance,
                        'invested': invested,
                        'total_pnl': total_pnl,
                        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
            except Exception as e:
                logger.error(f"Upbit API error in portfolio: {e}")
                # API 실패시 Redis/DB에서 가져오기
                if redis_client:
                    portfolio = redis_client.hgetall('portfolio:summary')
                    if portfolio:
                        return jsonify({
                            'total_value': float(portfolio.get('total_value', 0)),
                            'krw_balance': float(portfolio.get('krw_balance', 0)),
                            'invested': float(portfolio.get('invested', 0)),
                            'total_pnl': float(portfolio.get('total_pnl', 0))
                        })
        
        return jsonify({
            'total_value': total_value,
            'krw_balance': krw_balance,
            'invested': invested,
            'total_pnl': total_pnl
        })
    except Exception as e:
        logger.error(f"Portfolio API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance/today')
def get_today_performance():
    """오늘의 성과 조회"""
    try:
        import pyupbit
        from dotenv import load_dotenv
        import os
        from datetime import datetime, time
        
        # 환경변수 로드
        load_dotenv('config/.env')
        
        trade_count = 0
        win_count = 0
        daily_pnl = 0
        total_volume = 0
        
        # Upbit API로 오늘 거래 내역 조회
        access_key = os.getenv('UPBIT_ACCESS_KEY')
        secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if access_key and secret_key:
            try:
                upbit = pyupbit.Upbit(access_key, secret_key)
                
                # 오늘 날짜 범위
                today = datetime.now()
                today_start = datetime.combine(today.date(), time.min)
                
                # 주요 코인들의 오늘 거래 내역 조회
                symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-ADA', 'KRW-SOL']
                
                for symbol in symbols:
                    try:
                        orders = upbit.get_order(symbol, state='done')
                        if orders:
                            for order in orders:
                                # 오늘 거래만 필터링
                                created_at = order.get('created_at', '')
                                if created_at and created_at[:10] == today.strftime('%Y-%m-%d'):
                                    trade_count += 1
                                    
                                    # 거래량 계산
                                    executed_volume = float(order.get('executed_volume', 0))
                                    price = float(order.get('price', 0))
                                    total_volume += executed_volume * price
                                    
                                    # PnL 계산 (단순화: 매수/매도 차이로 추정)
                                    side = order.get('side', '')
                                    if side == 'bid':  # 매수
                                        daily_pnl -= executed_volume * price
                                    else:  # 매도
                                        daily_pnl += executed_volume * price
                                        win_count += 1  # 매도는 일단 수익으로 가정
                    except:
                        continue
                
                # 승률 계산
                win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
                
                # 수익률 계산 (현재 포트폴리오 대비)
                return_rate = 0
                if total_volume > 0:
                    return_rate = (daily_pnl / total_volume * 100)
                    
            except Exception as e:
                logger.error(f"Upbit API error in performance: {e}")
        
        # DB에서 백업 데이터 조회
        if trade_count == 0:
            try:
                conn = sqlite3.connect('data/quantum.db')
                cursor = conn.cursor()
                
                today = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute("""
                    SELECT COUNT(*), 
                           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                           SUM(pnl)
                    FROM trades
                    WHERE DATE(timestamp) = ?
                """, (today,))
                
                result = cursor.fetchone()
                trade_count = result[0] or 0
                win_count = result[1] or 0
                daily_pnl = result[2] or 0
                
                win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
                return_rate = (daily_pnl / 10000000 * 100) if daily_pnl else 0
                
                conn.close()
            except:
                pass
        
        return jsonify({
            'trade_count': trade_count,
            'win_rate': round(win_rate, 2),
            'daily_pnl': round(daily_pnl, 2),
            'return_rate': round(return_rate, 2)
        })
    except Exception as e:
        logger.error(f"Performance API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies')
def get_strategies():
    """전략 목록 조회"""
    strategies = [
        {'name': '마켓 메이킹', 'active': True},
        {'name': '통계적 차익거래', 'active': True},
        {'name': '모멘텀 스캘핑', 'active': True},
        {'name': '평균 회귀', 'active': True},
        {'name': 'AI Prediction', 'active': True}
    ]
    return jsonify({'strategies': strategies})

@app.route('/api/ai-analysis')
def get_ai_analysis():
    """AI 분석 결과 조회"""
    try:
        conn = sqlite3.connect('data/ai_analysis.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, type, analysis, implemented
            FROM analyses
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        
        analyses = []
        for row in cursor.fetchall():
            analyses.append({
                'timestamp': row[0],
                'type': row[1],
                'analysis': row[2],
                'implemented': row[3]
            })
        
        conn.close()
        return jsonify({'analyses': analyses})
    except Exception as e:
        return jsonify({'analyses': []})

@app.route('/api/multi-coin-status')
def get_multi_coin_status():
    """멀티코인 거래 상태 조회"""
    try:
        conn = sqlite3.connect('data/multi_coin.db')
        cursor = conn.cursor()
        
        # Current positions
        cursor.execute("""
            SELECT coin, quantity, avg_price, current_value, unrealized_pnl, last_updated
            FROM positions
            ORDER BY coin
        """)
        
        positions = []
        for row in cursor.fetchall():
            positions.append({
                'coin': row[0],
                'quantity': row[1],
                'avg_price': row[2],
                'current_value': row[3],
                'unrealized_pnl': row[4],
                'last_updated': row[5]
            })
        
        # Recent trades
        cursor.execute("""
            SELECT timestamp, coin, strategy, side, price, quantity, pnl
            FROM trades
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'timestamp': row[0],
                'coin': row[1],
                'strategy': row[2],
                'side': row[3],
                'price': row[4],
                'quantity': row[5],
                'pnl': row[6]
            })
        
        conn.close()
        
        return jsonify({
            'positions': positions,
            'trades': trades
        })
    except Exception as e:
        return jsonify({'positions': [], 'trades': []})

@app.route('/api/control/<action>', methods=['POST'])
def control_system(action):
    """시스템 제어"""
    try:
        if action == 'start':
            subprocess.Popen(['python3', 'integrated_trading_system.py'])
            return jsonify({'status': 'started'})
        
        elif action == 'stop':
            subprocess.run(['pkill', '-f', 'integrated_trading_system.py'])
            subprocess.run(['pkill', '-f', 'quantum_trading.py'])
            subprocess.run(['pkill', '-f', 'multi_coin_trading.py'])
            return jsonify({'status': 'stopped'})
        
        elif action == 'restart':
            subprocess.run(['pkill', '-f', 'integrated_trading_system.py'])
            import time
            time.sleep(2)
            subprocess.Popen(['python3', 'integrated_trading_system.py'])
            return jsonify({'status': 'restarted'})
        
        elif action == 'emergency-stop':
            subprocess.run(['pkill', '-9', '-f', 'trading'])
            return jsonify({'status': 'emergency stopped'})
        
        else:
            return jsonify({'error': 'Unknown action'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading-mode', methods=['GET', 'POST'])
def trading_mode():
    """거래 모드 조회 및 변경"""
    try:
        config_path = 'config/config.yaml'
        
        if request.method == 'GET':
            # 현재 모드 조회
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            current_mode = config.get('trading', {}).get('mode', 'dry_run')
            return jsonify({'mode': current_mode})
        
        elif request.method == 'POST':
            # 모드 변경
            data = request.get_json()
            new_mode = data.get('mode')
            
            if new_mode not in ['dry_run', 'paper', 'live']:
                return jsonify({'error': 'Invalid mode'}), 400
            
            # config.yaml 업데이트
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            config['trading']['mode'] = new_mode
            
            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
            
            # Redis에 상태 저장
            if redis_client:
                redis_client.set('trading_mode', new_mode)
                redis_client.set('mode_changed_at', datetime.now(KST).isoformat())
            
            # 프로세스 재시작 필요 알림
            return jsonify({
                'status': 'success',
                'mode': new_mode,
                'message': '모드가 변경되었습니다. 시스템을 재시작하세요.'
            })
    
    except Exception as e:
        logger.error(f"Trading mode error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system-control', methods=['POST'])
def system_control():
    """시스템 제어 (시작/중지/재시작)"""
    try:
        data = request.get_json()
        action = data.get('action')
        
        if action == 'start':
            # 현재 모드 확인
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            mode = config.get('trading', {}).get('mode', 'dry_run')
            
            # 모드에 따라 다른 스크립트 실행
            if mode == 'dry_run':
                subprocess.Popen(['python3', 'quantum_trading.py', '--dry-run'])
            else:
                subprocess.Popen(['python3', 'quantum_trading.py'])
            
            return jsonify({
                'status': 'started',
                'mode': mode,
                'timestamp': datetime.now(KST).isoformat()
            })
        
        elif action == 'stop':
            subprocess.run(['pkill', '-f', 'quantum_trading.py'])
            subprocess.run(['pkill', '-f', 'enhanced_trading_system.py'])
            return jsonify({
                'status': 'stopped',
                'timestamp': datetime.now(KST).isoformat()
            })
        
        elif action == 'restart':
            # 중지
            subprocess.run(['pkill', '-f', 'quantum_trading.py'])
            subprocess.run(['pkill', '-f', 'enhanced_trading_system.py'])
            
            import time
            time.sleep(2)
            
            # 시작
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            mode = config.get('trading', {}).get('mode', 'dry_run')
            
            if mode == 'dry_run':
                subprocess.Popen(['python3', 'quantum_trading.py', '--dry-run'])
            else:
                subprocess.Popen(['python3', 'quantum_trading.py'])
            
            return jsonify({
                'status': 'restarted',
                'mode': mode,
                'timestamp': datetime.now(KST).isoformat()
            })
        
        else:
            return jsonify({'error': 'Invalid action'}), 400
    
    except Exception as e:
        logger.error(f"System control error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/emergency-stop', methods=['POST'])
def emergency_stop():
    """긴급 정지"""
    try:
        # 모든 거래 프로세스 강제 종료
        subprocess.run(['pkill', '-9', '-f', 'trading'])
        subprocess.run(['pkill', '-9', '-f', 'quantum'])
        
        # Redis에 긴급 정지 상태 저장
        if redis_client:
            redis_client.set('emergency_stop', 'true')
            redis_client.set('emergency_stop_at', datetime.now(KST).isoformat())
        
        logger.warning("EMERGENCY STOP ACTIVATED")
        
        return jsonify({
            'status': 'emergency_stopped',
            'timestamp': datetime.now(KST).isoformat(),
            'message': '모든 거래가 긴급 중지되었습니다.'
        })
    
    except Exception as e:
        logger.error(f"Emergency stop error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backtest/run', methods=['POST'])
def run_backtest_api():
    """백테스트 실행 API"""
    try:
        data = request.get_json()
        strategy = data.get('strategy', 'momentum_scalping')
        symbol = data.get('symbol', 'KRW-BTC')
        days = data.get('days', 30)
        initial_capital = data.get('initial_capital', 1_000_000)
        position_size = data.get('position_size', 0.1)
        
        logger.info(f"백테스트 요청: {strategy} / {symbol} / {days}일")
        
        # 백테스트 실행을 위한 서브프로세스 (비동기 처리를 위해)
        import sys
        sys.path.append('.')
        from backtest_runner import StrategyTester
        
        tester = StrategyTester()
        
        # 전략별 백테스트 또는 전체 비교
        if strategy == 'all':
            # 모든 전략 비교
            strategies = ['momentum_scalping', 'mean_reversion', 'trend_following']
            results = []
            
            for strat in strategies:
                result = tester.run_backtest(
                    strategy_name=strat,
                    symbol=symbol,
                    days=days,
                    initial_capital=initial_capital,
                    position_size=position_size
                )
                if 'error' not in result:
                    results.append(result)
            
            # 최고 성과 전략 선택
            if results:
                best_result = max(results, key=lambda x: x['metrics']['roi'])
                best_result['comparison'] = results
                return jsonify(best_result)
            else:
                return jsonify({'error': '모든 전략 실행 실패'}), 500
        else:
            # 단일 전략 백테스트
            result = tester.run_backtest(
                strategy_name=strategy,
                symbol=symbol,
                days=days,
                initial_capital=initial_capital,
                position_size=position_size
            )
            
            if 'error' in result:
                return jsonify(result), 400
                
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"백테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/backtest/detail/<int:session_id>')
def get_backtest_detail(session_id):
    """백테스트 상세 정보 조회"""
    try:
        import sqlite3
        conn = sqlite3.connect('data/backtest_results.db')
        cursor = conn.cursor()
        
        # 세션 정보 조회
        cursor.execute("""
            SELECT * FROM backtest_sessions WHERE id = ?
        """, (session_id,))
        
        session = cursor.fetchone()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
            
        # 거래 내역 조회
        cursor.execute("""
            SELECT * FROM backtest_trades 
            WHERE session_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 100
        """, (session_id,))
        
        trades = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'session': {
                'id': session[0],
                'timestamp': session[1],
                'strategy': session[2],
                'symbol': session[3],
                'period_start': session[4],
                'period_end': session[5],
                'initial_capital': session[6],
                'final_capital': session[7],
                'total_trades': session[8],
                'win_rate': session[9],
                'total_pnl': session[10],
                'max_drawdown': session[11],
                'sharpe_ratio': session[12]
            },
            'trades_count': len(trades),
            'recent_trades': trades[:10]
        })
        
    except Exception as e:
        logger.error(f"백테스트 상세 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backtest/history')
def get_backtest_history():
    """백테스트 히스토리 조회"""
    try:
        import sqlite3
        conn = sqlite3.connect('data/backtest_results.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, strategy, symbol, 
                   period_start, period_end, total_trades,
                   win_rate, total_pnl, sharpe_ratio
            FROM backtest_sessions
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        sessions = cursor.fetchall()
        conn.close()
        
        history = []
        for session in sessions:
            history.append({
                'id': session[0],
                'timestamp': session[1],
                'strategy': session[2],
                'symbol': session[3],
                'period': f"{session[4][:10]} ~ {session[5][:10]}",
                'trades': session[6],
                'win_rate': round(session[7], 1),
                'pnl': round(session[8], 0),
                'sharpe': round(session[9], 2)
            })
            
        return jsonify({'history': history})
        
    except Exception as e:
        logger.error(f"히스토리 조회 오류: {e}")
        return jsonify({'history': []})

@app.route('/api/statistics')
def get_statistics():
    """통계 정보 조회"""
    try:
        stats = {
            'total_trades': 0,
            'win_rate': 0.0,
            'average_profit': 0.0,
            'total_volume': 0.0
        }
        
        # Redis에서 통계 조회
        if redis_client:
            cached_stats = redis_client.get('statistics:summary')
            if cached_stats:
                return jsonify(json.loads(cached_stats))
        
        # DB에서 통계 계산
        conn = sqlite3.connect('data/quantum.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   AVG(pnl),
                   SUM(quantity * price)
            FROM trades
            WHERE DATE(timestamp) = DATE('now')
        """)
        
        result = cursor.fetchone()
        if result and result[0] and result[0] > 0:
            stats['total_trades'] = result[0]
            stats['win_rate'] = (result[1] / result[0]) * 100 if result[0] > 0 else 0
            stats['average_profit'] = result[2] or 0
            stats['total_volume'] = result[3] or 0
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Statistics API error: {e}")
        return jsonify({'total_trades': 0, 'win_rate': 0, 'average_profit': 0, 'total_volume': 0})

@app.route('/api/recent_trades')
@app.route('/api/trades/recent')  # 프론트엔드 호환성을 위한 추가 라우트
def get_recent_trades():
    """최근 거래 내역 조회"""
    try:
        import pyupbit
        from dotenv import load_dotenv
        import os
        from datetime import datetime, timedelta
        
        trades = []
        
        # 환경변수 로드
        load_dotenv('config/.env')
        
        # Upbit API로 실제 거래 내역 조회
        access_key = os.getenv('UPBIT_ACCESS_KEY')
        secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if access_key and secret_key:
            try:
                upbit = pyupbit.Upbit(access_key, secret_key)
                
                # 최근 거래 내역 조회 (모든 마켓)
                # Upbit API는 마켓별로 조회해야 하므로 주요 코인만 확인
                symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-ADA', 'KRW-SOL']
                
                # 먼저 전체 주문 내역을 조회 (마켓 구분 없이)
                try:
                    # 모든 마켓의 완료된 주문 조회
                    all_orders = upbit.get_order(state='done', limit=200)
                    
                    logger.info(f"Fetched {len(all_orders) if all_orders else 0} orders from Upbit")
                    
                    if all_orders and isinstance(all_orders, list):
                        # 매수/매도 카운트
                        bid_count = sum(1 for o in all_orders if o.get('side') == 'bid')
                        ask_count = sum(1 for o in all_orders if o.get('side') == 'ask')
                        logger.info(f"Orders breakdown - Bid: {bid_count}, Ask: {ask_count}")
                        for order in all_orders:
                            # 주문 정보에서 거래 데이터 추출
                            market = order.get('market', '')
                            side = order.get('side', '')
                            
                            # KRW 마켓만 필터링
                            if market.startswith('KRW-'):
                                # trades 필드가 있으면 실제 체결 내역 사용
                                if order.get('trades'):
                                    for trade in order['trades']:
                                        price = float(trade.get('price', 0))
                                        volume = float(trade.get('volume', 0))
                                        
                                        trades.append({
                                            'timestamp': trade.get('created_at', order.get('created_at', '')),
                                            'strategy': 'Quantum Trading',
                                            'symbol': market,
                                            'side': side,  # bid(매수) or ask(매도)
                                            'price': price,
                                            'quantity': volume,
                                            'total': price * volume,
                                            'pnl': 0,
                                            'signal_strength': 0.75,
                                            'reason': '시스템 거래'
                                        })
                                else:
                                    # trades가 없으면 주문 정보 사용
                                    price = float(order.get('price', 0) or order.get('avg_price', 0))
                                    volume = float(order.get('executed_volume', 0) or order.get('volume', 0))
                                    
                                    if price > 0 and volume > 0:
                                        trades.append({
                                            'timestamp': order.get('created_at', ''),
                                            'strategy': 'Quantum Trading',
                                            'symbol': market,
                                            'side': side,
                                            'price': price,
                                            'quantity': volume,
                                            'total': price * volume,
                                            'pnl': 0,
                                            'signal_strength': 0.75,
                                            'reason': '시스템 거래'
                                        })
                except Exception as e:
                    logger.error(f"Error fetching all orders: {e}")
                    
                    # 전체 조회 실패시 개별 마켓 조회 시도
                    for symbol in symbols:
                        try:
                            # 최근 30일간의 완료된 주문 내역 조회 (매수/매도 모두 포함)
                            # get_order는 기본적으로 모든 side(bid/ask)를 반환함
                            orders = upbit.get_order(symbol, state='done', limit=50)
                            
                            if orders and isinstance(orders, list):
                                for order in orders:
                                    # Upbit API 응답에서 정확한 필드명 사용
                                    # trades 필드가 있으면 실제 체결 내역 사용
                                    if order.get('trades'):
                                        for trade in order['trades']:
                                            price = float(trade.get('price', 0))
                                            volume = float(trade.get('volume', 0))
                                            
                                            trades.append({
                                                'timestamp': trade.get('created_at', order.get('created_at', '')),
                                                'strategy': 'Quantum Trading',
                                                'symbol': trade.get('market', order.get('market', '')),
                                                'side': order.get('side', ''),  # bid(매수) or ask(매도)
                                                'price': price,
                                                'quantity': volume,
                                                'total': price * volume,
                                                'pnl': 0,
                                                'signal_strength': 0.75,
                                                'reason': '시스템 거래'
                                            })
                                    else:
                                        # trades가 없으면 주문 정보 사용
                                        avg_price = float(order.get('price', 0) or order.get('avg_price', 0))
                                        executed_volume = float(order.get('executed_volume', 0) or order.get('volume', 0))
                                        
                                        if avg_price > 0 and executed_volume > 0:
                                            trades.append({
                                                'timestamp': order.get('created_at', ''),
                                                'strategy': 'Quantum Trading',
                                                'symbol': order.get('market', ''),
                                                'side': order.get('side', ''),
                                                'price': avg_price,
                                                'quantity': executed_volume,
                                                'total': avg_price * executed_volume,
                                                'pnl': 0,
                                                'signal_strength': 0.75,
                                                'reason': '시스템 거래'
                                            })
                        except Exception as symbol_error:
                            logger.debug(f"Error fetching orders for {symbol}: {symbol_error}")
                            continue
                
                # 시간순 정렬 (최신 먼저)
                trades.sort(key=lambda x: x['timestamp'], reverse=True)
                trades = trades[:20]  # 최근 20건만
                
            except Exception as e:
                logger.error(f"Upbit API error in trades: {e}")
        
        # DB에서도 거래 내역 조회 (백업)
        if len(trades) == 0:
            try:
                conn = sqlite3.connect('data/quantum.db')
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT timestamp, strategy, symbol, side, price, quantity, pnl
                    FROM trades
                    ORDER BY timestamp DESC
                    LIMIT 20
                """)
                
                for row in cursor.fetchall():
                    trades.append({
                        'timestamp': row[0],
                        'strategy': row[1],
                        'symbol': row[2],
                        'side': row[3],
                        'price': row[4],
                        'quantity': row[5],
                        'pnl': row[6]
                    })
                
                conn.close()
            except:
                pass
        
        return jsonify({'trades': trades})
        
    except Exception as e:
        logger.error(f"Recent trades API error: {e}")
        return jsonify({'trades': []})

@app.route('/api/system/status')
def get_detailed_system_status():
    """상세 시스템 상태"""
    return get_system_status()

@app.route('/api/trading_mode', methods=['GET', 'POST'])
def trading_mode_handler():
    """거래 모드 조회 및 변경"""
    try:
        import yaml
        
        if request.method == 'GET':
            # 현재 모드 조회
            mode = 'dry_run'  # 기본값
            if os.path.exists('config/config.yaml'):
                with open('config/config.yaml', 'r') as f:
                    config = yaml.safe_load(f)
                    mode = config.get('trading', {}).get('mode', 'dry_run')
            return jsonify({'mode': mode})
            
        elif request.method == 'POST':
            # 모드 변경
            data = request.get_json()
            new_mode = data.get('mode', 'dry_run')
            
            if new_mode not in ['live', 'dry_run']:
                return jsonify({'error': 'Invalid mode. Must be "live" or "dry_run"'}), 400
            
            # config.yaml 읽기
            config_path = 'config/config.yaml'
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # 모드 변경
                if 'trading' not in config:
                    config['trading'] = {}
                config['trading']['mode'] = new_mode
                
                # 파일 저장
                with open(config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                
                logger.info(f"Trading mode changed to: {new_mode}")
                
                # Quantum Trading 재시작 필요 플래그
                return jsonify({
                    'mode': new_mode, 
                    'message': f'Trading mode changed to {new_mode}. Please restart Quantum Trading.',
                    'restart_required': True
                })
            else:
                return jsonify({'error': 'Config file not found'}), 500
        
    except Exception as e:
        logger.error(f"Trading mode API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/processes')
def get_processes():
    """프로세스 모니터 정보"""
    processes = []
    
    process_names = [
        ('integrated_trading_system.py', 'Integrated System'),
        ('quantum_trading.py', 'Quantum Trading'),
        ('multi_coin_trading.py', 'Multi-Coin Trading'),
        ('feedback_scheduler.py', 'AI Feedback'),
        ('dashboard.py', 'Dashboard')
    ]
    
    for script, name in process_names:
        running = False
        pid = None
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if script in cmdline:
                    running = True
                    pid = proc.info['pid']
                    break
            except:
                pass
        
        processes.append({
            'name': name,
            'running': running,
            'pid': pid
        })
    
    return jsonify({'processes': processes})

@app.route('/api/config')
def get_config():
    """설정 정보 조회"""
    try:
        # Load from config.yaml first, fallback to environment
        config_data = {}
        try:
            with open('config/config.yaml', 'r') as f:
                config_yaml = yaml.safe_load(f)
                trading_mode = config_yaml.get('trading', {}).get('mode', 'dry-run')
                max_position = config_yaml.get('trading', {}).get('limits', {}).get('max_position', 10000000)
                daily_loss = config_yaml.get('risk_management', {}).get('limits', {}).get('max_daily_loss_percent', 5.0)
                signal_threshold = config_yaml.get('trading', {}).get('signal_threshold', 0.65)
                
                config_data = {
                    'trading_mode': trading_mode,
                    'max_position': max_position,
                    'daily_loss_limit': -abs(daily_loss),  # Ensure negative
                    'signal_threshold': signal_threshold
                }
        except:
            # Fallback to environment variables
            config_data = {
                'trading_mode': os.getenv('TRADING_MODE', 'dry-run'),
                'max_position': int(os.getenv('MAX_POSITION_SIZE', 10000000)),
                'daily_loss_limit': float(os.getenv('DAILY_LOSS_LIMIT', -0.03)) * 100,
                'signal_threshold': float(os.getenv('SIGNAL_THRESHOLD', 0.65))
            }
        
        return jsonify(config_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-upbit')
def check_upbit():
    """Upbit API 연결 확인"""
    try:
        access_key = os.getenv('UPBIT_ACCESS_KEY')
        secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if access_key and secret_key and len(access_key) > 10:
            # Try to connect
            upbit = pyupbit.Upbit(access_key, secret_key)
            balances = upbit.get_balances()
            if balances is not None:
                return jsonify({'connected': True})
        
        return jsonify({'connected': False})
    except:
        return jsonify({'connected': False})

@app.route('/api/ai-analysis/trigger', methods=['POST'])
def trigger_ai_analysis():
    """AI 분석 수동 트리거"""
    try:
        # Run AI analysis
        subprocess.Popen(['python3', '-c', '''
import asyncio
from ai_analyzer import FeedbackLoop

async def run():
    feedback = FeedbackLoop()
    await feedback.run_daily_analysis()
    await feedback.close()

asyncio.run(run())
'''])
        
        return jsonify({'status': 'triggered'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """로그 조회"""
    try:
        filter_type = request.args.get('filter', 'all')
        log_file = 'logs/integrated_system.log'
        
        if not os.path.exists(log_file):
            return jsonify({'logs': ['로그 없음']})
        
        with open(log_file, 'r') as f:
            lines = f.readlines()[-100:]  # Last 100 lines
        
        if filter_type == 'error':
            lines = [l for l in lines if 'ERROR' in l or 'error' in l]
        elif filter_type == 'trade':
            lines = [l for l in lines if 'trade' in l.lower() or 'order' in l.lower()]
        elif filter_type == 'ai':
            lines = [l for l in lines if 'AI' in l or 'analysis' in l.lower()]
        
        return jsonify({'logs': lines})
    except Exception as e:
        return jsonify({'logs': [f'Error loading logs: {str(e)}']})

@app.route('/api/optimization/run', methods=['POST'])
def run_optimization_api():
    """파라미터 최적화 실행 API"""
    try:
        data = request.get_json()
        strategy = data.get('strategy', 'momentum_scalping')
        method = data.get('method', 'grid_search')
        symbol = data.get('symbol', 'KRW-BTC')
        days = data.get('days', 30)
        
        logger.info(f"최적화 요청: {strategy} / {method} / {symbol} / {days}일")
        
        # 최적화 실행
        import sys
        sys.path.append('.')
        from parameter_optimizer import ParameterOptimizer
        
        optimizer = ParameterOptimizer()
        
        # 최적화 방법에 따른 실행
        if method == 'grid_search':
            result = optimizer.grid_search(
                strategy_name=strategy,
                symbol=symbol,
                days=days
            )
        elif method == 'random_search':
            result = optimizer.random_search(
                strategy_name=strategy,
                symbol=symbol,
                days=days,
                n_iterations=20
            )
        elif method == 'genetic_algorithm':
            result = optimizer.genetic_algorithm(
                strategy_name=strategy,
                symbol=symbol,
                days=days,
                population_size=20,
                generations=10
            )
        else:
            return jsonify({'error': 'Unknown optimization method'}), 400
            
        if result is None:
            return jsonify({'error': 'Optimization failed'}), 500
            
        # 결과 형식화
        response = {
            'strategy': strategy,
            'method': method,
            'symbol': symbol,
            'best_params': result['best_params'],
            'best_roi': round(result['best_metrics']['roi'], 2),
            'best_fitness': result['best_fitness'],
            'all_results': []
        }
        
        # 상위 10개 결과 정렬
        for params, metrics, fitness in result.get('all_results', [])[:10]:
            response['all_results'].append({
                'params': params,
                'roi': round(metrics['roi'], 2),
                'sharpe': metrics['sharpe_ratio'],
                'max_drawdown': round(metrics['max_drawdown'], 2),
                'win_rate': round(metrics['win_rate'], 1),
                'trades': metrics['total_trades'],
                'fitness': fitness
            })
        
        # 세션 ID 생성 (타임스탬프 기반)
        import time
        response['session_id'] = int(time.time())
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"최적화 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/optimization/history')
def get_optimization_history():
    """최적화 히스토리 조회"""
    try:
        import sqlite3
        conn = sqlite3.connect('data/optimization_results.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, strategy, method, symbol, 
                   best_roi, best_fitness, best_params
            FROM optimization_sessions
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'id': row[0],
                'timestamp': row[1],
                'strategy': row[2],
                'method': row[3],
                'symbol': row[4],
                'best_roi': round(row[5], 2),
                'fitness': row[6],
                'best_params': row[7]
            })
        
        conn.close()
        return jsonify({'history': history})
        
    except Exception as e:
        logger.error(f"히스토리 조회 오류: {e}")
        return jsonify({'history': []})

@app.route('/api/optimization/detail/<int:session_id>')
def get_optimization_detail(session_id):
    """최적화 상세 정보 조회"""
    try:
        import sqlite3
        conn = sqlite3.connect('data/optimization_results.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM optimization_sessions WHERE id = ?
        """, (session_id,))
        
        session = cursor.fetchone()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
            
        # 상세 결과 조회
        cursor.execute("""
            SELECT params, roi, sharpe_ratio, max_drawdown, 
                   win_rate, total_trades, fitness
            FROM optimization_results
            WHERE session_id = ?
            ORDER BY fitness DESC
            LIMIT 20
        """, (session_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'params': row[0],
                'roi': round(row[1], 2),
                'sharpe': round(row[2], 2),
                'max_drawdown': round(row[3], 2),
                'win_rate': round(row[4], 1),
                'trades': row[5],
                'fitness': round(row[6], 4)
            })
        
        conn.close()
        
        return jsonify({
            'session': {
                'id': session[0],
                'timestamp': session[1],
                'strategy': session[2],
                'method': session[3],
                'symbol': session[4],
                'days': session[5],
                'best_roi': round(session[6], 2),
                'best_fitness': round(session[7], 4),
                'best_params': session[8]
            },
            'results': results
        })
        
    except Exception as e:
        logger.error(f"상세 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """헬스 체크"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.getenv('DASHBOARD_PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)