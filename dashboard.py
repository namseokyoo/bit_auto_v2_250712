"""
Quantum Trading Dashboard with Settings and Trade Details
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

# 환경 변수 로드
load_dotenv()

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
    <title>Quantum Trading Dashboard</title>
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
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 30px;
            background: linear-gradient(135deg, #4ade80 0%, #22d3ee 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
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
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card h2 {
            color: #4ade80;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
        }
        .metric-label {
            font-weight: 500;
        }
        .metric-value {
            font-weight: bold;
        }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        .neutral { color: #fbbf24; }
        .btn {
            padding: 10px 20px;
            margin: 5px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s;
        }
        .btn-primary {
            background: #4ade80;
            color: #000;
        }
        .btn-danger {
            background: #f87171;
            color: #fff;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-running { background: #4ade80; }
        .status-stopped { background: #f87171; }
        .trade-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .trade-item {
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            cursor: pointer;
            transition: background 0.3s;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            font-size: 0.9em;
        }
        .trade-item:hover {
            background: rgba(255,255,255,0.05);
        }
        .trade-item.buy { border-left: 3px solid #4CAF50; }
        .trade-item.sell { border-left: 3px solid #f44336; }
        .trade-time { color: #94a3b8; }
        .trade-side { font-weight: bold; }
        .trade-side.buy { color: #4CAF50; }
        .trade-side.sell { color: #f44336; }
        .trade-price { color: #f59e0b; }
        .trade-signal { color: #8b5cf6; font-size: 0.85em; }
        .trade-pnl { font-weight: bold; }
        .trade-pnl.positive { color: #4CAF50; }
        .trade-pnl.negative { color: #f44336; }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
        }
        .modal-content {
            background: #1e293b;
            margin: 10% auto;
            padding: 30px;
            border-radius: 10px;
            width: 80%;
            max-width: 600px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .close {
            color: #94a3b8;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: #fff;
        }
        .setting-item {
            margin: 20px 0;
        }
        .setting-label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }
        .setting-input {
            width: 100%;
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 5px;
            color: #fff;
            font-size: 1em;
        }
        .setting-description {
            font-size: 0.9em;
            color: #94a3b8;
            margin-top: 5px;
        }
        .log-content {
            background: #000;
            color: #0f0;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            max-height: 500px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Quantum Trading Dashboard</h1>
        
        <!-- 탭 버튼 -->
        <div class="tabs">
            <button class="tab active" onclick="switchTab('dashboard', this)">대시보드</button>
            <button class="tab" onclick="switchTab('settings', this)">설정</button>
            <button class="tab" onclick="switchTab('logs', this)">로그</button>
        </div>
        
        <!-- 대시보드 탭 -->
        <div id="dashboard-tab" class="tab-content active">
            <div class="grid">
                <!-- 시스템 상태 -->
                <div class="card">
                    <h2>시스템 상태</h2>
                    <div class="metric">
                        <span class="metric-label">상태</span>
                        <span class="metric-value">
                            <span class="status-indicator" id="status-indicator"></span>
                            <span id="system-status">Loading...</span>
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">운영 시간</span>
                        <span class="metric-value" id="uptime">-</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">마지막 업데이트</span>
                        <span class="metric-value" id="last-update">-</span>
                    </div>
                    <div style="margin-top: 15px;">
                        <button class="btn btn-primary" onclick="startTrading()">시작</button>
                        <button class="btn btn-danger" onclick="stopTrading()">중지</button>
                    </div>
                </div>
                
                <!-- 계좌 정보 -->
                <div class="card">
                    <h2>계좌 정보</h2>
                    <div class="metric">
                        <span class="metric-label">총 자산</span>
                        <span class="metric-value" id="total-balance">₩0</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">KRW (예수금)</span>
                        <span class="metric-value" id="krw-balance">₩0</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">BTC 보유</span>
                        <span class="metric-value" id="btc-balance">0 BTC</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">BTC 평가금</span>
                        <span class="metric-value" id="position-value">₩0</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">BTC 손익</span>
                        <span class="metric-value" id="btc-pnl">₩0</span>
                    </div>
                </div>
                
                <!-- 오늘의 성과 -->
                <div class="card">
                    <h2>오늘의 성과</h2>
                    <div class="metric">
                        <span class="metric-label">일일 손익</span>
                        <span class="metric-value" id="daily-pnl">₩0</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">거래 횟수</span>
                        <span class="metric-value">
                            <span id="trade-count">0</span>회
                            (<span id="buy-count">0</span>매수/<span id="sell-count">0</span>매도)
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">승률</span>
                        <span class="metric-value" id="win-rate">0%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">평균 신호 강도</span>
                        <span class="metric-value" id="avg-signal">0.000</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">현재 임계값</span>
                        <span class="metric-value" id="current-threshold">0.25</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">오늘 최고/최저가</span>
                        <span class="metric-value" id="price-range">-</span>
                    </div>
                </div>
                
                <!-- 최근 거래 -->
                <div class="card">
                    <h2>최근 거래</h2>
                    <div class="trade-list" id="recent-trades">
                        <div class="trade-item">거래 내역이 없습니다</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 설정 탭 -->
        <div id="settings-tab" class="tab-content">
            <div class="card">
                <h2>거래 설정</h2>
                <div class="setting-item">
                    <label class="setting-label">신호 임계값 (Signal Threshold)</label>
                    <input type="number" id="signal-threshold" class="setting-input" 
                           min="0.05" max="0.5" step="0.05" value="0.25">
                    <div class="setting-description">
                        거래 신호 강도 임계값 (0.05~0.5)<br>
                        • 0.05~0.15: 매우 활발한 거래 (고위험)<br>
                        • 0.20~0.30: 보통 거래 빈도 <strong>(권장)</strong><br>
                        • 0.35~0.50: 보수적 거래 (저위험)
                    </div>
                </div>
                <div class="setting-item">
                    <label class="setting-label">최대 포지션 크기 (Max Position)</label>
                    <input type="number" id="max-position" class="setting-input" 
                           min="100000" max="10000000" step="100000" value="1000000">
                    <div class="setting-description">최대 포지션 크기 (원)</div>
                </div>
                <div class="setting-item">
                    <label class="setting-label">거래 간격 (Trading Interval)</label>
                    <input type="number" id="trading-interval" class="setting-input" 
                           min="30" max="300" step="10" value="60">
                    <div class="setting-description">거래 신호 생성 간격 (초)</div>
                </div>
                <div class="setting-item">
                    <label class="setting-label">일일 손실 한도 (Daily Loss Limit)</label>
                    <input type="number" id="daily-loss-limit" class="setting-input" 
                           min="1" max="10" step="0.5" value="5">
                    <div class="setting-description">일일 최대 손실 한도 (%)</div>
                </div>
                <button class="btn btn-primary" onclick="saveSettings()">설정 저장</button>
                <button class="btn" onclick="loadSettings()">현재 설정 불러오기</button>
            </div>
            
            <!-- 전략별 가중치 설정 -->
            <div class="card" style="margin-top: 20px;">
                <h2>전략별 가중치 설정</h2>
                <div class="setting-description" style="margin-bottom: 20px;">
                    전략별 가중치를 조절하여 신호 강도를 제어합니다. (합계: <span id="weight-total">100</span>%)
                </div>
                
                <div class="setting-item">
                    <label class="setting-label">Market Making (마켓 메이킹)</label>
                    <input type="number" id="weight-market-making" class="setting-input" 
                           min="0" max="100" step="5" value="30" onchange="updateWeightTotal()">
                    <div class="setting-description">스프레드 수익 전략 (기본: 30%)</div>
                </div>
                
                <div class="setting-item">
                    <label class="setting-label">Statistical Arbitrage (통계적 차익거래)</label>
                    <input type="number" id="weight-stat-arb" class="setting-input" 
                           min="0" max="100" step="5" value="20" onchange="updateWeightTotal()">
                    <div class="setting-description">페어 트레이딩 전략 (기본: 20%)</div>
                </div>
                
                <div class="setting-item">
                    <label class="setting-label">Microstructure (마이크로구조)</label>
                    <input type="number" id="weight-microstructure" class="setting-input" 
                           min="0" max="100" step="5" value="20" onchange="updateWeightTotal()">
                    <div class="setting-description">시장 미시구조 분석 (기본: 20%)</div>
                </div>
                
                <div class="setting-item">
                    <label class="setting-label">Momentum Scalping (모멘텀 스캘핑)</label>
                    <input type="number" id="weight-momentum" class="setting-input" 
                           min="0" max="100" step="5" value="15" onchange="updateWeightTotal()">
                    <div class="setting-description">단기 모멘텀 포착 (기본: 15%)</div>
                </div>
                
                <div class="setting-item">
                    <label class="setting-label">Mean Reversion (평균 회귀)</label>
                    <input type="number" id="weight-mean-reversion" class="setting-input" 
                           min="0" max="100" step="5" value="15" onchange="updateWeightTotal()">
                    <div class="setting-description">과매수/과매도 포착 (기본: 15%)</div>
                </div>
                
                <div class="setting-item" style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <div class="setting-description">
                        <strong>팁:</strong> 가중치 합계는 100%가 되어야 합니다.<br>
                        • 신호가 약하다면 주요 전략의 가중치를 높이세요<br>
                        • 특정 전략이 잘 작동한다면 해당 가중치를 증가시키세요
                    </div>
                </div>
                
                <button class="btn btn-primary" onclick="saveStrategyWeights()">가중치 저장</button>
                <button class="btn" onclick="loadStrategyWeights()">현재 가중치 불러오기</button>
            </div>
        </div>
        
        <!-- 로그 탭 -->
        <div id="logs-tab" class="tab-content">
            <div class="card">
                <h2>시스템 로그</h2>
                <div class="log-content" id="log-content">
                    Loading logs...
                </div>
                <button class="btn" onclick="loadLogs()">로그 새로고침</button>
            </div>
        </div>
    </div>
    
    <!-- 거래 상세 모달 -->
    <div id="tradeModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>거래 상세 정보</h2>
            <div id="trade-details"></div>
        </div>
    </div>
    
    <script>
        // 탭 전환
        function switchTab(tabName, element) {
            // 모든 탭 비활성화
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // 선택한 탭 활성화
            element.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // 로그 탭이면 로그 로드
            if (tabName === 'logs') {
                loadLogs();
            } else if (tabName === 'settings') {
                loadSettings();
            }
        }
        
        // 모달 닫기
        function closeModal() {
            document.getElementById('tradeModal').style.display = 'none';
        }
        
        // 거래 상세 보기
        function showTradeDetails(trade) {
            const modal = document.getElementById('tradeModal');
            const details = document.getElementById('trade-details');
            
            const sideClass = trade.side === 'BUY' ? 'buy' : 'sell';
            const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
            
            details.innerHTML = `
                <div class="metric">
                    <span class="metric-label">거래 시간:</span>
                    <span class="metric-value">${new Date(trade.timestamp).toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">거래 방향:</span>
                    <span class="metric-value" style="color: ${trade.side === 'BUY' ? '#4CAF50' : '#f44336'}; font-weight: bold;">
                        ${trade.side || trade.action || 'N/A'}
                    </span>
                </div>
                <div class="metric">
                    <span class="metric-label">거래 가격:</span>
                    <span class="metric-value">₩${Math.floor(trade.price || 0).toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">거래 수량:</span>
                    <span class="metric-value">${((trade.quantity || trade.amount || 0) / (trade.price || 1)).toFixed(8)} BTC</span>
                </div>
                <div class="metric">
                    <span class="metric-label">거래 금액:</span>
                    <span class="metric-value">₩${Math.floor(trade.quantity || trade.amount || 0).toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">전략:</span>
                    <span class="metric-value">${trade.strategy || 'ensemble'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">신호 강도:</span>
                    <span class="metric-value">${(trade.signal_strength || 0).toFixed(3)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">거래 근거:</span>
                    <span class="metric-value" style="font-size: 0.9em;">${trade.reason || 'N/A'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">손익:</span>
                    <span class="metric-value" style="color: ${trade.pnl >= 0 ? '#4CAF50' : '#f44336'}; font-weight: bold;">
                        ₩${Math.floor(trade.pnl || 0).toLocaleString()}
                    </span>
                </div>
            `;
            
            modal.style.display = 'block';
        }
        
        // 설정 저장
        async function saveSettings() {
            const settings = {
                signal_threshold: parseFloat(document.getElementById('signal-threshold').value),
                max_position: parseInt(document.getElementById('max-position').value),
                trading_interval: parseInt(document.getElementById('trading-interval').value),
                daily_loss_limit: parseFloat(document.getElementById('daily-loss-limit').value)
            };
            
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings)
                });
                
                if (response.ok) {
                    alert('설정이 저장되었습니다. 시스템을 재시작하세요.');
                } else {
                    alert('설정 저장 실패');
                }
            } catch (error) {
                alert('Error: ' + error);
            }
        }
        
        // 설정 불러오기
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                document.getElementById('signal-threshold').value = settings.signal_threshold || 0.25;
                document.getElementById('max-position').value = settings.max_position || 1000000;
                document.getElementById('trading-interval').value = settings.trading_interval || 60;
                document.getElementById('daily-loss-limit').value = settings.daily_loss_limit || 5;
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        }
        
        // 가중치 합계 업데이트
        function updateWeightTotal() {
            const weights = [
                'weight-market-making',
                'weight-stat-arb', 
                'weight-microstructure',
                'weight-momentum',
                'weight-mean-reversion'
            ];
            
            let total = 0;
            weights.forEach(id => {
                total += parseFloat(document.getElementById(id).value) || 0;
            });
            
            document.getElementById('weight-total').textContent = total;
            
            // 합계가 100이 아니면 경고 색상
            const totalElement = document.getElementById('weight-total');
            if (Math.abs(total - 100) < 0.01) {
                totalElement.style.color = '#4ade80';
            } else {
                totalElement.style.color = '#f87171';
            }
        }
        
        // 전략 가중치 저장
        async function saveStrategyWeights() {
            const weights = {
                market_making: parseFloat(document.getElementById('weight-market-making').value) / 100,
                stat_arb: parseFloat(document.getElementById('weight-stat-arb').value) / 100,
                microstructure: parseFloat(document.getElementById('weight-microstructure').value) / 100,
                momentum_scalping: parseFloat(document.getElementById('weight-momentum').value) / 100,
                mean_reversion: parseFloat(document.getElementById('weight-mean-reversion').value) / 100
            };
            
            // 합계 검증
            const total = Object.values(weights).reduce((a, b) => a + b, 0);
            if (Math.abs(total - 1.0) > 0.01) {
                alert('가중치 합계는 100%가 되어야 합니다. 현재: ' + (total * 100).toFixed(0) + '%');
                return;
            }
            
            try {
                const response = await fetch('/api/strategy-weights', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(weights)
                });
                
                if (response.ok) {
                    alert('전략 가중치가 저장되었습니다. 시스템을 재시작하세요.');
                } else {
                    alert('가중치 저장 실패');
                }
            } catch (error) {
                alert('Error: ' + error);
            }
        }
        
        // 전략 가중치 불러오기
        async function loadStrategyWeights() {
            try {
                const response = await fetch('/api/strategy-weights');
                const weights = await response.json();
                
                document.getElementById('weight-market-making').value = (weights.market_making || 0.30) * 100;
                document.getElementById('weight-stat-arb').value = (weights.stat_arb || 0.20) * 100;
                document.getElementById('weight-microstructure').value = (weights.microstructure || 0.20) * 100;
                document.getElementById('weight-momentum').value = (weights.momentum_scalping || 0.15) * 100;
                document.getElementById('weight-mean-reversion').value = (weights.mean_reversion || 0.15) * 100;
                
                updateWeightTotal();
            } catch (error) {
                console.error('Error loading strategy weights:', error);
            }
        }
        
        // 로그 로드
        async function loadLogs() {
            try {
                const response = await fetch('/api/logs');
                const data = await response.json();
                document.getElementById('log-content').innerHTML = 
                    '<pre>' + (data.logs || 'No logs available').replace(/\\n/g, '<br>') + '</pre>';
            } catch (error) {
                document.getElementById('log-content').textContent = 'Error loading logs';
            }
        }
        
        // 거래 시작
        async function startTrading() {
            if (confirm('거래를 시작하시겠습니까?')) {
                try {
                    const response = await fetch('/api/control', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({action: 'start'})
                    });
                    const data = await response.json();
                    alert(data.message || 'Trading started');
                } catch (error) {
                    alert('Error: ' + error);
                }
            }
        }
        
        // 거래 중지
        async function stopTrading() {
            if (confirm('정말로 거래를 중지하시겠습니까?')) {
                try {
                    const response = await fetch('/api/control', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({action: 'stop'})
                    });
                    const data = await response.json();
                    alert(data.message || 'Trading stopped');
                } catch (error) {
                    alert('Error: ' + error);
                }
            }
        }
        
        // 상태 업데이트
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // 시스템 상태 업데이트
                document.getElementById('system-status').textContent = data.system_status || 'Unknown';
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                
                // 상태 인디케이터
                const indicator = document.getElementById('status-indicator');
                indicator.className = 'status-indicator status-' + 
                    (data.system_status === 'Running' ? 'running' : 'stopped');
                
                // 계좌 정보 업데이트
                document.getElementById('total-balance').textContent = 
                    '₩' + Math.floor(data.total_balance || 0).toLocaleString();
                document.getElementById('krw-balance').textContent = 
                    '₩' + Math.floor(data.krw_balance || 0).toLocaleString();
                document.getElementById('btc-balance').textContent = 
                    (data.btc_balance || 0).toFixed(8) + ' BTC';
                document.getElementById('position-value').textContent = 
                    '₩' + Math.floor(data.position_value || 0).toLocaleString();
                    
                // BTC 손익
                if (data.btc_pnl) {
                    const pnlElement = document.getElementById('btc-pnl');
                    pnlElement.textContent = '₩' + Math.floor(data.btc_pnl).toLocaleString();
                    pnlElement.className = data.btc_pnl >= 0 ? 'positive' : 'negative';
                }
                
                // 성과 업데이트
                const pnlElement = document.getElementById('daily-pnl');
                const pnl = data.daily_pnl || 0;
                pnlElement.textContent = '₩' + Math.floor(pnl).toLocaleString();
                pnlElement.className = pnl >= 0 ? 'positive' : 'negative';
                
                document.getElementById('trade-count').textContent = data.trade_count || '0';
                document.getElementById('buy-count').textContent = data.buy_count || '0';
                document.getElementById('sell-count').textContent = data.sell_count || '0';
                document.getElementById('win-rate').textContent = 
                    (data.win_rate || 0).toFixed(1) + '%';
                document.getElementById('avg-signal').textContent = 
                    (data.avg_signal_strength || 0).toFixed(3);
                document.getElementById('current-threshold').textContent = 
                    (data.current_threshold || 0.25).toFixed(2);
                
                // 가격 범위 표시
                if (data.min_price && data.max_price) {
                    document.getElementById('price-range').textContent = 
                        `₩${Math.floor(data.min_price).toLocaleString()} ~ ₩${Math.floor(data.max_price).toLocaleString()}`;
                }
                
                // 최근 거래
                if (data.recent_trades && data.recent_trades.length > 0) {
                    const tradesHtml = data.recent_trades.map(trade => {
                        const sideClass = trade.side === 'BUY' ? 'buy' : 'sell';
                        const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
                        return `
                            <div class="trade-item ${sideClass}" onclick='showTradeDetails(${JSON.stringify(trade).replace(/'/g, "&apos;")})' style="cursor: pointer;">
                                <span class="trade-time">${new Date(trade.timestamp).toLocaleTimeString()}</span>
                                <span class="trade-side ${sideClass}">${trade.side}</span>
                                <span class="trade-price">₩${Math.floor(trade.price).toLocaleString()}</span>
                                <span class="trade-signal">신호: ${(trade.signal_strength || 0).toFixed(3)}</span>
                                ${trade.pnl !== 0 ? `<span class="trade-pnl ${pnlClass}">₩${Math.floor(trade.pnl).toLocaleString()}</span>` : ''}
                            </div>
                        `;
                    }).join('');
                    document.getElementById('recent-trades').innerHTML = tradesHtml;
                } else {
                    document.getElementById('recent-trades').innerHTML = '<div class="trade-item">거래 내역이 없습니다</div>';
                }
                
            } catch (error) {
                console.error('Error updating status:', error);
            }
        }
        
        // 페이지 로드 시 초기화
        window.onload = function() {
            updateStatus();
            loadSettings();
            loadStrategyWeights();
            setInterval(updateStatus, 5000);  // 5초마다 업데이트
        };
        
        // 모달 외부 클릭 시 닫기
        window.onclick = function(event) {
            const modal = document.getElementById('tradeModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """메인 대시보드"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def get_status():
    """시스템 상태 API"""
    try:
        # 프로세스 실행 상태 확인
        result = os.popen("ps aux | grep 'quantum_trading.py' | grep -v grep").read()
        is_running = bool(result.strip())
        
        status = {
            'system_status': 'Running' if is_running else 'Stopped',
            'timestamp': datetime.now().isoformat(),
            'is_running': is_running
        }
        
        # 설정 파일에서 현재 임계값 읽기
        try:
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
                status['current_threshold'] = config.get('trading', {}).get('signal_threshold', 0.25)
        except:
            status['current_threshold'] = 0.25
        
        # Upbit 잔고 조회
        try:
            upbit = pyupbit.Upbit(
                os.getenv('UPBIT_ACCESS_KEY'),
                os.getenv('UPBIT_SECRET_KEY')
            )
            balances = upbit.get_balances()
            
            krw_balance = 0
            btc_balance = 0
            btc_avg_price = 0
            position_value = 0
            
            for b in balances:
                currency = b['currency']
                balance = float(b['balance'])
                
                if currency == 'KRW':
                    krw_balance = balance
                elif currency == 'BTC' and balance > 0:
                    btc_balance = balance
                    btc_avg_price = float(b['avg_buy_price'])
                    # BTC 현재가 조회
                    try:
                        current_btc_price = pyupbit.get_current_price('KRW-BTC')
                        if current_btc_price:
                            position_value = btc_balance * current_btc_price
                            status['btc_current_price'] = current_btc_price
                            status['btc_pnl'] = position_value - (btc_balance * btc_avg_price)
                            status['btc_pnl_percent'] = ((current_btc_price - btc_avg_price) / btc_avg_price * 100) if btc_avg_price > 0 else 0
                    except:
                        position_value = btc_balance * btc_avg_price
            
            status['krw_balance'] = krw_balance
            status['btc_balance'] = btc_balance
            status['btc_avg_price'] = btc_avg_price
            status['position_value'] = position_value
            status['total_balance'] = krw_balance + position_value
            status['available_balance'] = krw_balance
            
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            status['total_balance'] = 0
            status['krw_balance'] = 0
            status['btc_balance'] = 0
        
        # 거래 통계
        try:
            conn = sqlite3.connect('data/quantum.db')
            cursor = conn.cursor()
            
            # 오늘의 거래 상세 통계
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN side = 'BUY' THEN 1 END) as buy_count,
                    COUNT(CASE WHEN side = 'SELL' THEN 1 END) as sell_count,
                    SUM(pnl) as total_pnl,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(price) as avg_price
                FROM trades 
                WHERE DATE(timestamp) = ?
            """, (today,))
            
            stats = cursor.fetchone()
            trade_count = stats[0] or 0
            buy_count = stats[1] or 0
            sell_count = stats[2] or 0
            daily_pnl = stats[3] or 0
            min_price = stats[4] or 0
            max_price = stats[5] or 0
            avg_price = stats[6] or 0
            
            status['trade_count'] = trade_count
            status['buy_count'] = buy_count
            status['sell_count'] = sell_count
            status['daily_pnl'] = daily_pnl
            status['min_price'] = min_price
            status['max_price'] = max_price
            status['avg_price'] = avg_price
            
            # 승률 계산
            cursor.execute("""
                SELECT COUNT(*) FROM trades 
                WHERE DATE(timestamp) = ? AND pnl > 0
            """, (today,))
            
            win_count = cursor.fetchone()[0] or 0
            status['win_rate'] = (win_count / trade_count * 100) if trade_count > 0 else 0
            
            # 평균 신호 강도 (signals 테이블에서)
            cursor.execute("""
                SELECT AVG(strength) 
                FROM signals 
                WHERE DATE(timestamp) = ?
            """, (today,))
            
            avg_signal = cursor.fetchone()[0] or 0
            status['avg_signal_strength'] = avg_signal
            
            # 최근 거래 (신호 정보와 함께)
            cursor.execute("""
                SELECT 
                    t.timestamp,
                    t.side,
                    t.price,
                    t.quantity,
                    t.pnl,
                    t.strategy_name,
                    s.strength,
                    s.reason
                FROM trades t
                LEFT JOIN signals s ON 
                    s.timestamp BETWEEN datetime(t.timestamp, '-5 seconds') 
                    AND datetime(t.timestamp, '+5 seconds')
                    AND s.action = t.side
                ORDER BY t.timestamp DESC 
                LIMIT 10
            """)
            
            trades = cursor.fetchall()
            status['recent_trades'] = []
            for trade in trades:
                status['recent_trades'].append({
                    'timestamp': trade[0],
                    'side': trade[1],
                    'price': trade[2],
                    'quantity': trade[3],
                    'pnl': trade[4] or 0,
                    'strategy': trade[5],
                    'signal_strength': trade[6] or 0,
                    'reason': trade[7] or 'N/A'
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error getting trade data: {e}")
            status['trade_count'] = 0
            status['daily_pnl'] = 0
            status['win_rate'] = 0
            status['recent_trades'] = []
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error in get_status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/control', methods=['POST'])
def control():
    """시스템 제어 API"""
    try:
        data = request.json
        action = data.get('action')
        
        if action == 'start':
            # 거래 시작 - 프로세스 직접 실행
            # 이미 실행 중인지 확인
            result = os.popen("ps aux | grep 'quantum_trading.py' | grep -v grep").read()
            if result:
                return jsonify({'status': 'warning', 'message': 'Trading already running'})
            
            # 새로 시작
            subprocess.Popen(
                ['bash', '-c', 'cd /opt/bit_auto_v2_250712 && source venv/bin/activate && nohup python3 quantum_trading.py > logs/quantum_trading.log 2>&1 &'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            return jsonify({'status': 'success', 'message': 'Trading started'})
            
        elif action == 'stop':
            # 거래 중지 - 프로세스 종료
            os.system("pkill -f 'quantum_trading.py'")
            
            return jsonify({'status': 'success', 'message': 'Trading stopped'})
            
        elif action == 'restart':
            # 재시작
            os.system("pkill -f 'quantum_trading.py'")
            os.system('sleep 2')
            subprocess.Popen(
                ['bash', '-c', 'cd /opt/bit_auto_v2_250712 && source venv/bin/activate && nohup python3 quantum_trading.py > logs/quantum_trading.log 2>&1 &'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            return jsonify({'status': 'success', 'message': 'Trading restarted'})
            
        else:
            return jsonify({'error': 'Unknown action'}), 400
            
    except Exception as e:
        logger.error(f"Error in control: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """설정 관리 API"""
    config_path = 'config/config.yaml'
    
    if request.method == 'GET':
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            return jsonify({
                'signal_threshold': config.get('trading', {}).get('signal_threshold', 0.25),
                'max_position': config.get('trading', {}).get('limits', {}).get('max_position', 1000000),
                'trading_interval': config.get('trading', {}).get('interval', 60),
                'daily_loss_limit': config.get('risk', {}).get('limits', {}).get('max_daily_loss_percent', 5.0)
            })
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return jsonify({'error': str(e)}), 500
    
    else:  # POST
        try:
            data = request.json
            
            # 현재 설정 로드
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # 설정 업데이트
            if 'signal_threshold' in data:
                config['trading']['signal_threshold'] = data['signal_threshold']
            if 'max_position' in data:
                config['trading']['limits']['max_position'] = data['max_position']
            if 'trading_interval' in data:
                config['trading']['interval'] = data['trading_interval']
            if 'daily_loss_limit' in data:
                config['risk']['limits']['max_daily_loss_percent'] = data['daily_loss_limit']
            
            # 설정 저장
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            return jsonify({'status': 'success', 'message': 'Settings saved'})
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def get_trades():
    """거래 내역 조회 API (상세 정보 포함)"""
    try:
        conn = sqlite3.connect('data/quantum.db')
        cursor = conn.cursor()
        
        # 거래 내역과 신호 정보 조인
        cursor.execute('''
            SELECT 
                t.id,
                t.timestamp,
                t.strategy_name,
                t.symbol,
                t.side,
                t.price,
                t.quantity,
                t.fee,
                t.pnl,
                s.strength,
                s.reason
            FROM trades t
            LEFT JOIN signals s ON 
                s.timestamp BETWEEN datetime(t.timestamp, '-5 seconds') 
                AND datetime(t.timestamp, '+5 seconds')
                AND s.action = t.side
            ORDER BY t.timestamp DESC
            LIMIT 50
        ''')
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'id': row[0],
                'timestamp': row[1],
                'strategy': row[2],
                'symbol': row[3],
                'side': row[4],
                'price': row[5],
                'quantity': row[6],
                'fee': row[7] or 0,
                'pnl': row[8] or 0,
                'signal_strength': row[9] or 0,
                'reason': row[10] or 'N/A'
            })
        
        conn.close()
        return jsonify({'trades': trades})
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategy-weights', methods=['GET', 'POST'])
def strategy_weights():
    """전략별 가중치 관리 API"""
    config_file = 'config/config.yaml'
    
    if request.method == 'GET':
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            weights = {
                'market_making': config.get('strategies', {}).get('market_making', {}).get('weight', 0.30),
                'stat_arb': config.get('strategies', {}).get('statistical_arbitrage', {}).get('weight', 0.20),
                'microstructure': config.get('strategies', {}).get('microstructure', {}).get('weight', 0.20),
                'momentum_scalping': config.get('strategies', {}).get('momentum_scalping', {}).get('weight', 0.15),
                'mean_reversion': config.get('strategies', {}).get('mean_reversion', {}).get('weight', 0.15)
            }
            
            return jsonify(weights)
        except Exception as e:
            logger.error(f"Error loading strategy weights: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            weights = request.json
            
            # config 파일 읽기
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # 가중치 업데이트
            if 'strategies' not in config:
                config['strategies'] = {}
            
            config['strategies']['market_making']['weight'] = weights['market_making']
            config['strategies']['statistical_arbitrage']['weight'] = weights['stat_arb']
            config['strategies']['microstructure']['weight'] = weights['microstructure']
            config['strategies']['momentum_scalping']['weight'] = weights['momentum_scalping']
            config['strategies']['mean_reversion']['weight'] = weights['mean_reversion']
            
            # 파일 저장
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Strategy weights updated: {weights}")
            return jsonify({'status': 'success', 'message': 'Strategy weights saved'})
            
        except Exception as e:
            logger.error(f"Error saving strategy weights: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """로그 조회 API"""
    try:
        log_path = 'logs/quantum_trading.log'
        if os.path.exists(log_path):
            # 마지막 100줄만 읽기
            with open(log_path, 'r') as f:
                lines = f.readlines()
                recent_logs = ''.join(lines[-100:])
                return jsonify({'logs': recent_logs})
        else:
            return jsonify({'logs': 'Log file not found'})
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.getenv('DASHBOARD_PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)