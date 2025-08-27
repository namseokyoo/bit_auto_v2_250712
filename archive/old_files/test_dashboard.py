#!/usr/bin/env python3
"""
대시보드 및 시스템 전체 테스트
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://158.180.82.112:8080"

def test_endpoint(endpoint, name):
    """API 엔드포인트 테스트"""
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        if response.status_code == 200:
            print(f"✅ {name}: OK")
            return response.json()
        else:
            print(f"❌ {name}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ {name}: {e}")
        return None

def main():
    print("=" * 60)
    print("🔍 Quantum Trading System - Dashboard Test")
    print("=" * 60)
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"URL: {BASE_URL}")
    print()
    
    # 1. 시스템 상태
    print("1. 시스템 상태 확인")
    status = test_endpoint("/api/system-status", "System Status")
    if status:
        print(f"   - CPU: {status.get('cpu_usage', 'N/A')}%")
        print(f"   - Memory: {status.get('memory_usage', 'N/A')}%")
        print(f"   - Uptime: {status.get('uptime', 'N/A')}")
        print(f"   - Running: {status.get('is_running', False)}")
    print()
    
    # 2. Upbit 연결
    print("2. Upbit API 연결 확인")
    upbit = test_endpoint("/api/check-upbit", "Upbit Connection")
    if upbit:
        print(f"   - Connected: {upbit.get('connected', False)}")
    print()
    
    # 3. 포트폴리오
    print("3. 포트폴리오 상태")
    portfolio = test_endpoint("/api/portfolio", "Portfolio")
    if portfolio:
        print(f"   - Total Value: {portfolio.get('total_value', 0):,.0f} KRW")
        print(f"   - KRW Balance: {portfolio.get('krw_balance', 0):,.0f} KRW")
        print(f"   - Total P&L: {portfolio.get('total_pnl', 0):,.0f} KRW")
    print()
    
    # 4. 최근 거래
    print("4. 최근 거래")
    trades = test_endpoint("/api/trades/recent", "Recent Trades")
    if trades:
        trade_list = trades.get('trades', [])
        print(f"   - 거래 수: {len(trade_list)}")
    print()
    
    # 5. 멀티코인 상태
    print("5. 멀티코인 거래 상태")
    multi = test_endpoint("/api/multi-coin-status", "Multi-Coin Status")
    if multi:
        positions = multi.get('positions', [])
        print(f"   - 포지션 수: {len(positions)}")
    print()
    
    # 6. AI 분석
    print("6. AI 분석 결과")
    ai = test_endpoint("/api/ai-analysis", "AI Analysis")
    if ai:
        analyses = ai.get('analyses', [])
        print(f"   - 분석 수: {len(analyses)}")
    print()
    
    # 7. 전략 상태
    print("7. 전략 목록")
    strategies = test_endpoint("/api/strategies", "Strategies")
    if strategies:
        strat_list = strategies.get('strategies', [])
        print(f"   - 전략 수: {len(strat_list)}")
    print()
    
    # 8. 프로세스 모니터
    print("8. 프로세스 상태")
    processes = test_endpoint("/api/processes", "Process Monitor")
    if processes:
        proc_list = processes.get('processes', [])
        for proc in proc_list:
            print(f"   - {proc.get('name', 'Unknown')}: {proc.get('status', 'N/A')}")
    print()
    
    print("=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    main()