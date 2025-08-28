#!/bin/bash
# 긴급 재시작 스크립트
echo "🚨 Emergency Restart Script"
echo "============================"

cd /home/ubuntu/bit_auto_v2

# 모든 프로세스 종료
echo "Stopping all processes..."
pkill -f dashboard.py
pkill -f integrated_trading_system.py
pkill -f quantum_trading.py
pkill -f multi_coin_trading.py
sleep 2

# 가상환경 활성화
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 대시보드만 우선 시작
echo "Starting dashboard only..."
export DASHBOARD_PORT=8080
nohup python3 dashboard.py > logs/dashboard.log 2>&1 &
echo "Dashboard PID: $!"

sleep 5

# 상태 확인
if curl -s http://localhost:8080/health >/dev/null 2>&1; then
    echo "✅ Dashboard is running on port 8080"
else
    echo "❌ Dashboard failed to start"
    tail -20 logs/dashboard.log
fi

echo "============================"
echo "Emergency restart completed"