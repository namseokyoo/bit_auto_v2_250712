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
    <title>Quantum Trading Dashboard v3.0</title>
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
            <h1>Quantum Trading Dashboard v3.0</h1>
            <div class="subtitle">AI-Powered Multi-Coin Trading System with DeepSeek Analysis</div>
        </div>
        
        <div class="tabs">
            <button class="tab active" data-tab="overview">📊 Overview</button>
            <button class="tab" data-tab="ai">🤖 AI Analysis</button>
            <button class="tab" data-tab="multi-coin">💰 Multi-Coin</button>
            <button class="tab" data-tab="control">🎮 Control</button>
            <button class="tab" data-tab="trades">📈 Trades</button>
            <button class="tab" data-tab="settings">⚙️ Settings</button>
            <button class="tab" data-tab="logs">📝 Logs</button>
        </div>
        
        <!-- Overview Tab -->
        <div class="tab-content active" id="overview-content">
            <div class="grid">
                <div class="card">
                    <h3>📊 System Status</h3>
                    <div id="system-status">
                        <div class="loading">Loading system status...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>💵 Portfolio Summary</h3>
                    <div id="portfolio-summary">
                        <div class="loading">Loading portfolio...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📈 Today's Performance</h3>
                    <div id="today-performance">
                        <div class="loading">Loading performance...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>🎯 Active Strategies</h3>
                    <div id="active-strategies">
                        <div class="loading">Loading strategies...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- AI Analysis Tab -->
        <div class="tab-content" id="ai-analysis-content">
            <div class="card">
                <h3>🤖 DeepSeek AI Analysis</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="refreshAIAnalysis()">Refresh</button>
                    <button class="btn btn-warning" onclick="triggerAnalysis()">Trigger Analysis Now</button>
                </div>
                <div id="ai-analysis-list">
                    <div class="loading">Loading AI analysis...</div>
                </div>
            </div>
        </div>
        
        <!-- Multi-Coin Tab -->
        <div class="tab-content" id="multi-coin-content">
            <div class="card">
                <h3>💰 Multi-Coin Trading Status</h3>
                <div class="coin-grid" id="coin-status-grid">
                    <div class="loading">Loading coin status...</div>
                </div>
            </div>
            
            <div class="card">
                <h3>📊 Coin Performance</h3>
                <table id="coin-performance-table">
                    <thead>
                        <tr>
                            <th>Coin</th>
                            <th>Holdings</th>
                            <th>Avg Price</th>
                            <th>Current Price</th>
                            <th>PnL</th>
                            <th>PnL %</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="6" class="loading">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Control Tab -->
        <div class="tab-content" id="control-content">
            <div class="card">
                <h3>🎮 System Control</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="controlSystem('start')">▶️ Start Trading</button>
                    <button class="btn btn-danger" onclick="controlSystem('stop')">⏹️ Stop Trading</button>
                    <button class="btn btn-warning" onclick="controlSystem('restart')">🔄 Restart System</button>
                </div>
                <div id="control-status" class="status-message"></div>
            </div>
            
            <div class="card">
                <h3>🛠️ Quick Actions</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="emergencyStop()">🚨 Emergency Stop</button>
                    <button class="btn btn-warning" onclick="closeAllPositions()">💸 Close All Positions</button>
                    <button class="btn btn-primary" onclick="runBacktest()">📊 Run Backtest</button>
                </div>
            </div>
            
            <div class="card">
                <h3>📊 Process Monitor</h3>
                <div id="process-monitor">
                    <div class="loading">Loading process status...</div>
                </div>
            </div>
        </div>
        
        <!-- Trades Tab -->
        <div class="tab-content" id="trades-content">
            <div class="card">
                <h3>📈 Recent Trades</h3>
                <table id="trades-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Coin</th>
                            <th>Strategy</th>
                            <th>Side</th>
                            <th>Price</th>
                            <th>Amount</th>
                            <th>PnL</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="7" class="loading">Loading trades...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Settings Tab -->
        <div class="tab-content" id="settings-content">
            <div class="card">
                <h3>⚙️ Trading Configuration</h3>
                <div id="trading-config">
                    <div class="loading">Loading configuration...</div>
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
                <h3>📝 System Logs</h3>
                <div class="control-panel">
                    <button class="btn btn-primary" onclick="refreshLogs()">Refresh</button>
                    <select id="log-filter" onchange="filterLogs()">
                        <option value="all">All Logs</option>
                        <option value="error">Errors Only</option>
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
                        ${data.is_running ? 'Running' : 'Stopped'}
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
        
        // Emergency Stop
        async function emergencyStop() {
            if (confirm('Are you sure you want to execute emergency stop? This will close all positions immediately.')) {
                await controlSystem('emergency-stop');
            }
        }
        
        // Close All Positions
        async function closeAllPositions() {
            if (confirm('Are you sure you want to close all positions?')) {
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
            alert('Backtest functionality will be available soon');
        }
        
        // Load Process Monitor
        async function loadProcessMonitor() {
            try {
                const response = await fetch('/api/processes');
                const data = await response.json();
                
                let html = '<table style="width: 100%;">';
                html += '<tr><th>Process</th><th>Status</th><th>PID</th></tr>';
                
                const processes = data.processes || [];
                processes.forEach(proc => {
                    const statusIcon = proc.running ? '🟢' : '🔴';
                    html += `
                        <tr>
                            <td>${proc.name}</td>
                            <td>${statusIcon} ${proc.running ? 'Running' : 'Stopped'}</td>
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
                    trades.forEach(trade => {
                        const time = new Date(trade.timestamp).toLocaleString();
                        const pnlColor = trade.pnl >= 0 ? 'positive' : 'negative';
                        const sideColor = trade.side === 'buy' ? 'positive' : 'negative';
                        
                        html += `
                            <tr>
                                <td>${time}</td>
                                <td>${trade.coin || trade.symbol}</td>
                                <td>${trade.strategy}</td>
                                <td class="${sideColor}">${trade.side}</td>
                                <td>₩${Number(trade.price).toLocaleString()}</td>
                                <td>${Number(trade.quantity).toFixed(8)}</td>
                                <td class="${pnlColor}">₩${Number(trade.pnl || 0).toLocaleString()}</td>
                            </tr>
                        `;
                    });
                } else {
                    html = '<tr><td colspan="7" style="text-align: center; color: #94a3b8;">No trades yet</td></tr>';
                }
                
                document.querySelector('#trades-table tbody').innerHTML = html;
            } catch (error) {
                document.querySelector('#trades-table tbody').innerHTML = 
                    '<tr><td colspan="7" style="color: #ef4444;">Failed to load trades</td></tr>';
            }
        }
        
        // Load Settings
        async function loadSettings() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                
                let html = '';
                html += `<div class="metric">
                    <span class="metric-label">Trading Mode:</span>
                    <span class="metric-value ${data.trading_mode === 'live' ? 'positive' : 'neutral'}">
                        ${data.trading_mode || 'dry-run'}
                    </span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Max Position Size:</span>
                    <span class="metric-value">₩${(data.max_position || 0).toLocaleString()}</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Daily Loss Limit:</span>
                    <span class="metric-value negative">${(data.daily_loss_limit || -3)}%</span>
                </div>`;
                html += `<div class="metric">
                    <span class="metric-label">Signal Threshold:</span>
                    <span class="metric-value">${data.signal_threshold || 0.65}</span>
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
                let logHtml = logs.join('\n');
                
                if (!logHtml) {
                    logHtml = 'No logs available';
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
            // Add click event listeners to tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', function() {
                    const tabName = this.getAttribute('data-tab');
                    if (tabName) {
                        switchTab(tabName);
                    }
                });
            });
            
            // Load initial data
            await loadSystemStatus();
            await loadPortfolioSummary();
            await loadTodayPerformance();
            await loadActiveStrategies();
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
        # Get from Redis if available
        if redis_client:
            portfolio = redis_client.hgetall('portfolio:summary')
            if portfolio:
                return jsonify({
                    'total_value': float(portfolio.get('total_value', 0)),
                    'krw_balance': float(portfolio.get('krw_balance', 0)),
                    'invested': float(portfolio.get('invested', 0)),
                    'total_pnl': float(portfolio.get('total_pnl', 0))
                })
        
        # Fallback to database
        conn = sqlite3.connect('data/multi_coin.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(current_value), SUM(unrealized_pnl)
            FROM positions
        """)
        result = cursor.fetchone()
        total_value = result[0] or 0
        total_pnl = result[1] or 0
        
        conn.close()
        
        return jsonify({
            'total_value': total_value,
            'krw_balance': 0,  # Would need Upbit API
            'invested': total_value - total_pnl,
            'total_pnl': total_pnl
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance/today')
def get_today_performance():
    """오늘의 성과 조회"""
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
        
        return jsonify({
            'trade_count': trade_count,
            'win_rate': win_rate,
            'daily_pnl': daily_pnl,
            'return_rate': return_rate
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies')
def get_strategies():
    """전략 목록 조회"""
    strategies = [
        {'name': 'Market Making', 'active': True},
        {'name': 'Statistical Arbitrage', 'active': True},
        {'name': 'Momentum Scalping', 'active': True},
        {'name': 'Mean Reversion', 'active': True},
        {'name': 'AI Prediction', 'active': False}
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

@app.route('/api/trades/recent')
def get_recent_trades():
    """최근 거래 내역"""
    try:
        conn = sqlite3.connect('data/quantum.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, symbol, strategy, side, price, quantity, pnl
            FROM trades
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'timestamp': row[0],
                'symbol': row[1],
                'strategy': row[2],
                'side': row[3],
                'price': row[4],
                'quantity': row[5],
                'pnl': row[6]
            })
        
        conn.close()
        return jsonify({'trades': trades})
    except Exception as e:
        return jsonify({'trades': []})

@app.route('/api/config')
def get_config():
    """설정 정보 조회"""
    try:
        # Load from environment
        config = {
            'trading_mode': os.getenv('TRADING_MODE', 'dry-run'),
            'max_position': int(os.getenv('MAX_POSITION_SIZE', 10000000)),
            'daily_loss_limit': float(os.getenv('DAILY_LOSS_LIMIT', -0.03)) * 100,
            'signal_threshold': float(os.getenv('SIGNAL_THRESHOLD', 0.65))
        }
        return jsonify(config)
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
            return jsonify({'logs': ['No logs available']})
        
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

@app.route('/health')
def health():
    """헬스 체크"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.getenv('DASHBOARD_PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)