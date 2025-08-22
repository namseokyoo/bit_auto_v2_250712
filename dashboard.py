#!/usr/bin/env python3
"""
Quantum Trading System - Web Dashboard
실시간 모니터링 및 제어 인터페이스
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request, session
from flask_cors import CORS
from functools import wraps
import redis
import pyupbit
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv('.env')

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'quantum-trading-secret-key')
CORS(app)

# Redis 연결
try:
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected for dashboard")
except:
    logger.warning("Redis not available for dashboard")
    redis_client = None

# 기본 인증 (간단한 버전)
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != 'admin' or auth.password != os.getenv('DASHBOARD_PASSWORD', 'quantum123'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# HTML 템플릿
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quantum Trading Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        .card h2 {
            margin-bottom: 15px;
            font-size: 1.3em;
            color: #ffd700;
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
        .status-warning { background: #fbbf24; }
        .chart-container {
            height: 200px;
            margin-top: 15px;
        }
        .trade-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .trade-item {
            padding: 8px;
            margin: 5px 0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            font-size: 0.9em;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Quantum Trading System</h1>
        
        <div class="grid">
            <!-- 시스템 상태 -->
            <div class="card">
                <h2>시스템 상태</h2>
                <div class="metric">
                    <span class="metric-label">
                        <span class="status-indicator status-running"></span>
                        상태
                    </span>
                    <span class="metric-value" id="system-status">Running</span>
                </div>
                <div class="metric">
                    <span class="metric-label">가동 시간</span>
                    <span class="metric-value" id="uptime">2h 34m</span>
                </div>
                <div class="metric">
                    <span class="metric-label">마지막 업데이트</span>
                    <span class="metric-value" id="last-update">-</span>
                </div>
                <div class="controls">
                    <button class="btn btn-primary" onclick="startTrading()">시작</button>
                    <button class="btn btn-danger" onclick="stopTrading()">중지</button>
                </div>
            </div>
            
            <!-- 계좌 정보 -->
            <div class="card">
                <h2>계좌 정보</h2>
                <div class="metric">
                    <span class="metric-label">총 잔고</span>
                    <span class="metric-value" id="total-balance">₩0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">포지션 가치</span>
                    <span class="metric-value" id="position-value">₩0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">가용 잔고</span>
                    <span class="metric-value" id="available-balance">₩0</span>
                </div>
            </div>
            
            <!-- 오늘의 성과 -->
            <div class="card">
                <h2>오늘의 성과</h2>
                <div class="metric">
                    <span class="metric-label">손익</span>
                    <span class="metric-value positive" id="daily-pnl">+₩0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">수익률</span>
                    <span class="metric-value positive" id="daily-return">+0.00%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">거래 횟수</span>
                    <span class="metric-value" id="trade-count">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">승률</span>
                    <span class="metric-value" id="win-rate">0%</span>
                </div>
            </div>
            
            <!-- 전략 성과 -->
            <div class="card">
                <h2>전략별 성과</h2>
                <div class="metric">
                    <span class="metric-label">Market Making</span>
                    <span class="metric-value positive">+2.3%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Stat Arb</span>
                    <span class="metric-value positive">+1.5%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Microstructure</span>
                    <span class="metric-value negative">-0.2%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Momentum</span>
                    <span class="metric-value positive">+0.8%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Mean Rev</span>
                    <span class="metric-value positive">+0.5%</span>
                </div>
            </div>
            
            <!-- 리스크 지표 -->
            <div class="card">
                <h2>리스크 지표</h2>
                <div class="metric">
                    <span class="metric-label">VaR (95%)</span>
                    <span class="metric-value" id="var">₩0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">최대 낙폭</span>
                    <span class="metric-value negative" id="max-drawdown">-0.0%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">샤프 비율</span>
                    <span class="metric-value" id="sharpe-ratio">0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">리스크 레벨</span>
                    <span class="metric-value neutral">Medium</span>
                </div>
            </div>
            
            <!-- 최근 거래 -->
            <div class="card">
                <h2>최근 거래</h2>
                <div class="trade-list" id="recent-trades">
                    <div class="trade-item">
                        <span>Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 데이터 업데이트
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // 시스템 상태 업데이트
                document.getElementById('system-status').textContent = data.system_status || 'Unknown';
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                
                // 계좌 정보 업데이트
                document.getElementById('total-balance').textContent = 
                    '₩' + (data.total_balance || 0).toLocaleString();
                document.getElementById('position-value').textContent = 
                    '₩' + (data.position_value || 0).toLocaleString();
                
                // 성과 업데이트
                const pnlElement = document.getElementById('daily-pnl');
                const pnl = data.daily_pnl || 0;
                pnlElement.textContent = (pnl >= 0 ? '+' : '') + '₩' + pnl.toLocaleString();
                pnlElement.className = 'metric-value ' + (pnl >= 0 ? 'positive' : 'negative');
                
                document.getElementById('trade-count').textContent = data.trade_count || 0;
                document.getElementById('win-rate').textContent = 
                    ((data.win_rate || 0) * 100).toFixed(1) + '%';
                
                // 리스크 지표
                document.getElementById('sharpe-ratio').textContent = 
                    (data.sharpe_ratio || 0).toFixed(2);
                
                // 최근 거래 업데이트
                if (data.recent_trades && data.recent_trades.length > 0) {
                    const tradesHtml = data.recent_trades.map(trade => `
                        <div class="trade-item">
                            <span>${new Date(trade.timestamp).toLocaleTimeString()}</span>
                            <span class="${trade.side === 'BUY' ? 'positive' : 'negative'}">
                                ${trade.side}
                            </span>
                            <span>₩${trade.price.toLocaleString()}</span>
                            <span>${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}%</span>
                        </div>
                    `).join('');
                    document.getElementById('recent-trades').innerHTML = tradesHtml;
                }
                
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }
        
        // 거래 시작
        async function startTrading() {
            try {
                const response = await fetch('/api/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: 'start'})
                });
                const data = await response.json();
                alert(data.message || 'Trading started');
                updateDashboard();
            } catch (error) {
                alert('Failed to start trading');
            }
        }
        
        // 거래 중지
        async function stopTrading() {
            if (!confirm('정말로 거래를 중지하시겠습니까?')) return;
            
            try {
                const response = await fetch('/api/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: 'stop'})
                });
                const data = await response.json();
                alert(data.message || 'Trading stopped');
                updateDashboard();
            } catch (error) {
                alert('Failed to stop trading');
            }
        }
        
        // 주기적 업데이트
        setInterval(updateDashboard, 5000);
        updateDashboard();
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
        status = {
            'system_status': 'Running',
            'timestamp': datetime.now().isoformat()
        }
        
        # Redis에서 최신 데이터 가져오기
        if redis_client:
            metrics = redis_client.get('metrics:latest')
            if metrics:
                status.update(json.loads(metrics))
        
        # SQLite에서 추가 데이터 가져오기
        db = sqlite3.connect('data/quantum.db')
        cursor = db.cursor()
        
        # 오늘의 거래 통계
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) as count,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(pnl) as total_pnl
            FROM trades
            WHERE DATE(timestamp) = ?
        ''', (today,))
        
        result = cursor.fetchone()
        if result:
            status['trade_count'] = result[0]
            status['win_rate'] = result[1] / result[0] if result[0] > 0 else 0
            status['daily_pnl'] = result[2] if result[2] else 0
        
        # 최근 거래
        cursor.execute('''
            SELECT timestamp, side, price, pnl
            FROM trades
            ORDER BY id DESC
            LIMIT 10
        ''')
        
        trades = cursor.fetchall()
        status['recent_trades'] = [
            {
                'timestamp': trade[0],
                'side': trade[1],
                'price': trade[2],
                'pnl': trade[3] if trade[3] else 0
            }
            for trade in trades
        ]
        
        db.close()
        
        # Upbit 잔고 조회
        try:
            upbit = pyupbit.Upbit(
                os.getenv('UPBIT_ACCESS_KEY'),
                os.getenv('UPBIT_SECRET_KEY')
            )
            balances = upbit.get_balances()
            total_balance = sum(float(b['balance']) * float(b['avg_buy_price']) 
                              if b['currency'] != 'KRW' else float(b['balance']) 
                              for b in balances)
            status['total_balance'] = total_balance
        except:
            status['total_balance'] = 0
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/control', methods=['POST'])
@require_auth
def control():
    """시스템 제어 API"""
    try:
        data = request.json
        action = data.get('action')
        
        if action == 'start':
            # 거래 시작 (실제로는 systemd 서비스 제어)
            os.system('sudo systemctl start quantum-trading')
            return jsonify({'status': 'success', 'message': 'Trading started'})
            
        elif action == 'stop':
            # 거래 중지
            os.system('sudo systemctl stop quantum-trading')
            return jsonify({'status': 'success', 'message': 'Trading stopped'})
            
        elif action == 'restart':
            # 재시작
            os.system('sudo systemctl restart quantum-trading')
            return jsonify({'status': 'success', 'message': 'Trading restarted'})
            
        else:
            return jsonify({'error': 'Unknown action'}), 400
            
    except Exception as e:
        logger.error(f"Error in control: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

def create_app():
    """Flask 앱 생성 함수 (for gunicorn)"""
    return app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)