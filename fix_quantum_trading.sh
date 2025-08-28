#!/bin/bash
# Quantum Trading 강제 수정 및 시작 스크립트

echo "=== Quantum Trading 문제 해결 스크립트 ==="
echo ""

# 1. 프로세스 확인
echo "1. 현재 Quantum Trading 프로세스 확인..."
if pgrep -f "quantum_trading.py" > /dev/null; then
    echo "  - 이미 실행 중입니다."
    exit 0
else
    echo "  - 실행되지 않음. 시작 준비..."
fi

# 2. Python 환경 확인
echo "2. Python 환경 확인..."
python3 --version

# 3. 필수 패키지 설치
echo "3. 필수 패키지 설치..."
pip3 install redis scikit-learn --quiet

# 4. quantum_trading.py 파일 수정 (AI Prediction import 제거)
echo "4. quantum_trading.py 임시 수정..."
# AI Prediction 관련 import를 주석 처리
sed -i.bak 's/^from ai_prediction_strategy import/#from ai_prediction_strategy import/' quantum_trading.py 2>/dev/null || true

# 5. 테스트 실행
echo "5. Quantum Trading 테스트 실행..."
timeout 5 python3 quantum_trading.py --dry-run > /tmp/qt_test.log 2>&1
if [ $? -eq 124 ]; then
    echo "  - 테스트 성공 (타임아웃 = 정상 실행)"
else
    echo "  - 테스트 실패. 로그 확인:"
    tail -20 /tmp/qt_test.log
fi

# 6. 실제 시작
echo "6. Quantum Trading 시작..."
nohup python3 quantum_trading.py --dry-run > logs/quantum_trading.log 2>&1 &
QT_PID=$!
echo $QT_PID > quantum_trading.pid

# 7. 실행 확인
sleep 3
if ps -p $QT_PID > /dev/null; then
    echo "✅ Quantum Trading이 성공적으로 시작됨 (PID: $QT_PID)"
else
    echo "❌ Quantum Trading 시작 실패"
    echo "로그 마지막 30줄:"
    tail -30 logs/quantum_trading.log
fi

echo ""
echo "=== 완료 ==="