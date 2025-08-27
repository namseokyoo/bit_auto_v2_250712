# 배포 가이드 - 파라미터 최적화 업데이트

## 최신 업데이트 내용
- **고급 전략 추가**: 6개의 새로운 트레이딩 전략 (ML 예측, 통계적 차익거래, 오더북 불균형, VWAP, 일목균형표, 복합 신호)
- **파라미터 최적화 시스템**: Grid Search, Random Search, Genetic Algorithm 지원
- **대시보드 UI 업그레이드**: 파라미터 최적화 탭 추가 및 실시간 진행 상황 표시

## Oracle 서버 배포 절차

### 1. SSH 접속 및 코드 업데이트
```bash
# SSH 접속
ssh ubuntu@158.180.82.112

# 프로젝트 디렉토리로 이동
cd /home/ubuntu/bit_auto_v2

# 최신 코드 Pull
git pull origin main
```

### 2. 필요 패키지 설치 (필요한 경우)
```bash
# 가상환경 활성화
source venv/bin/activate

# 새로운 의존성 설치
pip install scikit-learn  # ML 전략용
```

### 3. 대시보드 재시작
```bash
# 기존 대시보드 프로세스 종료
pkill -f dashboard.py

# 대시보드 재시작
nohup python3 dashboard.py > logs/dashboard.log 2>&1 &
```

### 4. 새로운 기능 테스트

#### 대시보드에서 파라미터 최적화 테스트
1. 웹 브라우저에서 `http://158.180.82.112:8080` 접속
2. "🎯 최적화" 탭 클릭
3. 전략과 최적화 방법 선택 후 "🚀 최적화 시작" 클릭
4. 진행 상황 모니터링 및 결과 확인

#### API를 통한 최적화 테스트
```bash
# Grid Search 최적화 실행
curl -X POST http://localhost:8080/api/optimization/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "momentum_scalping",
    "method": "grid_search",
    "symbol": "KRW-BTC",
    "days": 30
  }'

# 최적화 히스토리 조회
curl http://localhost:8080/api/optimization/history
```

### 5. 모니터링
```bash
# 로그 확인
tail -f logs/dashboard.log

# 프로세스 상태 확인
ps aux | grep dashboard

# 시스템 리소스 확인
htop
```

## 주요 변경 사항

### 새로운 파일들
- `advanced_strategies.py`: 6개의 고급 트레이딩 전략
- `parameter_optimizer.py`: 파라미터 최적화 엔진

### 업데이트된 파일들
- `dashboard.py`: 최적화 탭 및 API 엔드포인트 추가
- `backtest_runner.py`: 새로운 전략들 통합

## 트러블슈팅

### 문제: 대시보드가 실행되지 않음
```bash
# 포트 확인
lsof -i :8080

# 필요시 포트 변경
export DASHBOARD_PORT=8081
python3 dashboard.py
```

### 문제: 최적화가 너무 오래 걸림
- Grid Search는 모든 조합을 테스트하므로 시간이 오래 걸림
- Random Search나 Genetic Algorithm 사용 권장
- 테스트 기간(days)을 줄여서 실행

### 문제: 메모리 부족
```bash
# 메모리 사용량 확인
free -h

# 필요시 다른 프로세스 중지
pkill -f quantum_trading.py
```

## 성능 최적화 팁

1. **백테스트 캐싱**: 동일한 심볼/기간의 데이터는 재사용
2. **병렬 처리**: 여러 전략을 동시에 최적화 가능
3. **데이터베이스 인덱싱**: SQLite 데이터베이스에 인덱스 추가로 조회 속도 향상

## 보안 주의사항

- API 키는 절대 코드에 하드코딩하지 마세요
- `.env` 파일 사용 권장
- 대시보드는 내부망에서만 접근 가능하도록 방화벽 설정

## 문의사항
배포 중 문제가 발생하면 다음을 확인해주세요:
1. GitHub 최신 코드와 동기화 여부
2. Python 패키지 버전 호환성
3. 서버 리소스 상태 (CPU, 메모리, 디스크)