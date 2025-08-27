# CLAUDE.md - Quantum Trading System v3

## 🔴 중요: 개발 워크플로우

### GitHub Actions 기반 자동 배포 워크플로우
모든 개발은 **로컬에서 수행**하고, **GitHub Actions를 통해 자동 배포**됩니다:

```bash
# 1. 로컬에서 개발
cd /Users/namseokyoo/project/bit_auto_v2_250712
code .  # VSCode 또는 선호하는 에디터

# 2. 코드 수정 및 테스트
python test_system.py  # 로컬 테스트

# 3. 변경사항 커밋
git add .
git commit -m "feat: [변경 내용]"

# 4. GitHub 푸시 (자동 배포 트리거)
git push origin main

# 5. 배포 확인
# GitHub Actions 탭에서 배포 상태 확인
# 또는 대시보드 접속: http://158.180.82.112:8080/
```

### 개발 원칙
- ✅ **로컬 개발**: 모든 코드 수정은 로컬에서 수행
- ✅ **자동 테스트**: GitHub Actions에서 자동 테스트 실행
- ✅ **자동 배포**: main 브랜치 푸시 시 자동 배포
- ✅ **무중단 배포**: 기존 서비스 중단 없이 새 버전 배포
- ❌ **서버 직접 수정 금지**: 서버에서 직접 코드 수정 방지

## 🚀 프로젝트 개요

**Quantum Trading System**은 전문 퀀트 트레이딩을 위한 고빈도 자동 거래 시스템입니다.
Oracle Cloud 서버에서 24/7 운영되며, GitHub Actions를 통한 자동 배포를 지원합니다.

### 핵심 특징
- **고빈도 거래**: 1-5분 간격 거래 (일 200-500회)
- **멀티 전략**: 5개 퀀트 전략 앙상블
- **리스크 관리**: 실시간 포트폴리오 리스크 모니터링
- **자동 배포**: GitHub Actions + Oracle Cloud 연동

## 📊 시스템 아키텍처

### 1. 전체 구조
```
┌────────────────────────────────────────────────┐
│            Oracle Cloud Server                  │
├────────────────────────────────────────────────┤
│                                                │
│  ┌──────────────────────────────────────┐    │
│  │   Quantum Trading Core (비동기)       │    │
│  │  ├─ Market Making Strategy           │    │
│  │  ├─ Statistical Arbitrage            │    │
│  │  ├─ Microstructure Analysis          │    │
│  │  ├─ Momentum Scalping                │    │
│  │  └─ Mean Reversion                   │    │
│  └──────────────┬───────────────────────┘    │
│                 │                              │
│  ┌──────────────▼───────────────────────┐    │
│  │   Smart Execution Engine              │    │
│  │  ├─ Order Optimization               │    │
│  │  ├─ Slippage Minimization            │    │
│  │  └─ Fee Optimization                 │    │
│  └──────────────┬───────────────────────┘    │
│                 │                              │
│  ┌──────────────▼───────────────────────┐    │
│  │   Risk Management System              │    │
│  │  ├─ Real-time VaR Calculation        │    │
│  │  ├─ Position Sizing (Kelly)          │    │
│  │  └─ Emergency Stop System            │    │
│  └──────────────┬───────────────────────┘    │
│                 │                              │
│  ┌──────────────▼───────────────────────┐    │
│  │   Web Dashboard (모니터링)            │    │
│  │  ├─ Real-time P&L                    │    │
│  │  ├─ Strategy Performance             │    │
│  │  └─ System Control Panel             │    │
│  └──────────────────────────────────────┘    │
│                                                │
└────────────────────────────────────────────────┘
                    │
                    ▼
            [GitHub Actions CI/CD]
```

### 2. 디렉토리 구조
```
quantum-trading-system/
├── .github/
│   └── workflows/
│       └── deploy.yml          # 자동 배포 워크플로우
├── src/
│   ├── quantum_trading.py     # 메인 시스템
│   ├── strategies.py           # 전략 모듈
│   ├── execution.py            # 실행 엔진
│   ├── risk_manager.py         # 리스크 관리
│   └── dashboard.py            # 웹 대시보드
├── config/
│   ├── config.yaml             # 시스템 설정
│   ├── strategies.yaml         # 전략 설정
│   └── secrets.env.example     # 환경 변수 예제
├── data/
│   └── quantum.db              # SQLite DB
├── logs/
│   └── quantum.log             # 시스템 로그
├── tests/
│   ├── test_strategies.py      # 전략 테스트
│   └── test_backtest.py        # 백테스트
├── scripts/
│   ├── install.sh              # 설치 스크립트
│   └── health_check.sh         # 헬스 체크
├── requirements.txt            # Python 의존성
├── Dockerfile                  # 도커 이미지
└── README.md                   # 프로젝트 문서
```

## 🎯 핵심 전략 시스템

### 1. 마켓 메이킹 (30% 가중치)
```python
# 스프레드 수익 + 메이커 리베이트
- 동적 스프레드 조정
- 5단계 레이어 주문
- 재고 관리 시스템
```

### 2. 통계적 차익거래 (20% 가중치)
```python
# Cointegration 기반 페어 트레이딩
- Z-Score 진입/청산
- Ornstein-Uhlenbeck 프로세스
- 평균 회귀 반감기 계산
```

### 3. 마이크로구조 분석 (20% 가중치)
```python
# 시장 미시구조 활용
- Order Flow Imbalance
- Volume Clock
- Tick Rule Probability
```

### 4. 모멘텀 스캘핑 (15% 가중치)
```python
# 초단기 모멘텀 포착
- 1-5분 타임프레임
- 가중 이동평균 모멘텀
- 볼륨 서지 확인
```

### 5. 평균 회귀 (15% 가중치)
```python
# 단기 과매수/과매도 포착
- Bollinger Bands
- RSI Divergence
- Volume Profile
```

## 💰 수익 극대화 전략

### 서버 비용 활용 극대화
```yaml
거래 빈도 최적화:
  - 목표: 일 200-500회 거래
  - 건당 목표 수익: 0.1-0.3%
  - 자금 회전율: 일 10-30회
  - 연간 목표 수익률: 50-100%

수수료 최소화:
  - 메이커 주문 우선 사용
  - 리베이트 프로그램 활용
  - 대량 거래 할인 협상
```

## 🛡️ 리스크 관리

### 포지션 관리
```yaml
한도 설정:
  - 총 포지션: 1,000만원
  - 전략별: 200만원
  - 거래당: 50만원
  - 최대 레버리지: 없음 (현물만)

손실 제한:
  - 일일 최대 손실: -5%
  - 주간 최대 손실: -10%
  - 월간 최대 손실: -15%
  - 긴급 중단 트리거: -3% (즉시)
```

### 리스크 지표
```python
# 실시간 모니터링
- VaR (95% 신뢰수준)
- 샤프 비율 (목표 > 1.5)
- 최대 낙폭 (MDD < 10%)
- 켈리 기준 포지션 사이징
```

## 🎯 2% 일일 수익 달성 전략 (2025-08-27 기준)

### 📊 현재 계좌 상태
```
총 자산: ₩196,760
- KRW: ₩78,528
- BTC: ₩114,977 (0.00073827 BTC)
- 기타: SC, SNT (큰 손실 상태)

일일 목표 수익(2%): ₩3,935
시간당 목표: ₩164
```

### 🎯 핵심 전략: 고빈도 스캘핑 + AI 신호
```yaml
목표 수익률: 하루 2% (₩3,935)
거래 빈도: 200회/일
거래당 목표: ₩20
필요 승률: 55%
포지션 크기: 총자산의 10% (₩19,676)
필요 수익률: 0.1% per trade
```

### ✅ Enhanced Trading System 구현 완료 (2025-08-27)

#### 1. 실시간 데이터 수집 및 분석
- [x] 1분봉 실시간 데이터 수집
- [x] 기술적 지표 계산 (RSI, MACD, Bollinger Bands)
- [x] 주문북 분석 (Order Flow Imbalance)
- [x] 변동성 모니터링

#### 2. 거래 신호 생성
- [x] RSI 기반 과매수/과매도 (30/70)
- [x] MACD 크로스오버 신호
- [x] 볼린저 밴드 터치 신호
- [x] 오더북 불균형 분석

#### 3. 리스크 관리
- [x] 손절매: -0.3%
- [x] 익절매: +0.5%
- [x] 최대 동시 포지션: 5개
- [x] 일일 손실 한도: -5%
- [x] 긴급 중단 시스템

#### 4. 주문 실행 엔진
- [x] 페이퍼 트레이딩 모드 (dry-run)
- [x] 멀티코인 지원 (BTC, ETH, XRP, ADA, SOL)
- [x] 최소 거래 간격: 60초
- [ ] 실거래 모드 (API 키 설정 필요)

#### 5. 모니터링 및 로깅
- [x] Redis 실시간 통계
- [x] 거래 내역 기록
- [x] 한글 대시보드
- [x] 실시간 목표 달성률 표시

### 📊 성과 추적 지표
```yaml
필수 추적 지표:
  - 실시간 PnL
  - 승률
  - 평균 손익
  - 샤프 비율
  - 최대 낙폭 (MDD)
  - 거래 빈도
  - 성공/실패 패턴 분석
```

### 📅 실행 일정
1. **Phase 1 (1일차)**: 백테스트 시스템 구축 및 전략 검증
2. **Phase 2 (2-3일차)**: 실시간 데이터 수집 및 AI 모델 개발
3. **Phase 3 (4-5일차)**: 페이퍼 트레이딩으로 테스트
4. **Phase 4 (6일차~)**: 실거래 적용 및 최적화

## ⚠️ 명심해야 할 사항

1. **작은 자본으로 시작**: 현재 총자산 20만원으로 하루 2% 수익 목표는 매우 도전적
2. **손실 관리 우선**: SC, SNT에서 95% 이상 손실 발생 경험
3. **복리 효과 활용**: 일일 수익을 재투자하여 자본 성장
4. **기술적 안정성**: 시스템 오류로 인한 손실 방지

## 📝 업데이트 로그

- **2025-08-27 12:01**: 초기 계좌 상태 확인 (₩196,760)
- **2025-08-27 11:53**: 대시보드 한글화 및 실거래 모드 활성화
- **2025-08-27 11:30**: GitHub Actions CI/CD 구축

## 🚀 GitHub Actions 자동 배포

### 1. 배포 워크플로우 (.github/workflows/auto_deploy.yml)
```yaml
name: Auto Deploy to Oracle Cloud

on:
  push:
    branches: [ main ]
    paths-ignore:
      - '*.md'
      - 'docs/**'
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Oracle Server
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.ORACLE_HOST }}
          username: ${{ secrets.ORACLE_USER }}
          key: ${{ secrets.ORACLE_SSH_KEY }}
          script: |
            cd /home/ubuntu/bit_auto_v2
            
            # 프로세스 중지
            pkill -f integrated_trading_system.py || true
            pkill -f multi_coin_trading.py || true
            
            # 최신 코드 가져오기
            git fetch origin
            git reset --hard origin/main
            
            # 가상환경 및 의존성
            source venv/bin/activate
            pip install --upgrade pip
            pip install pyupbit pandas numpy redis apscheduler httpx psutil pyyaml flask flask-cors python-dotenv
            
            # 시스템 재시작
            nohup python integrated_trading_system.py > logs/integrated_system.log 2>&1 &
            
            # 대시보드 재시작
            if ! pgrep -f dashboard.py > /dev/null; then
              nohup python dashboard.py > logs/dashboard.log 2>&1 &
            fi
            
            echo "✅ Deployment completed!"
```

### 2. 시크릿 설정 (GitHub Repository Settings)
```yaml
필수 시크릿:
  ORACLE_HOST: Oracle 서버 IP
  ORACLE_USER: SSH 사용자명
  ORACLE_SSH_KEY: SSH 개인키
  TELEGRAM_BOT_TOKEN: 알림 봇 토큰
  TELEGRAM_CHAT_ID: 알림 채널 ID
  UPBIT_ACCESS_KEY: API 액세스 키
  UPBIT_SECRET_KEY: API 시크릿 키
```

## 📦 설치 및 실행

### 1. 로컬 개발 환경
```bash
# 클론
git clone https://github.com/yourusername/quantum-trading-system.git
cd quantum-trading-system

# 가상환경 설정
python3.9 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp config/secrets.env.example config/secrets.env
# secrets.env 파일 편집

# 드라이런 모드로 실행
python src/quantum_trading.py --dry-run
```

### 2. Oracle Cloud 서버 설정
```bash
# 서버 초기 설정
sudo apt update && sudo apt upgrade -y
sudo apt install python3.9 python3.9-venv git nginx redis-server

# 프로젝트 클론
cd /opt
sudo git clone https://github.com/yourusername/quantum-trading-system.git
sudo chown -R ubuntu:ubuntu quantum-trading-system
cd quantum-trading-system

# 가상환경 및 의존성 설치
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# systemd 서비스 설정
sudo cp config/systemd/quantum-trading.service /etc/systemd/system/
sudo cp config/systemd/quantum-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable quantum-trading quantum-dashboard
sudo systemctl start quantum-trading quantum-dashboard

# Nginx 설정
sudo cp config/nginx/quantum.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/quantum.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

## 📈 성능 모니터링

### 실시간 대시보드 (http://서버IP:8080)
```yaml
메인 화면:
  - 현재 포지션 및 P&L
  - 전략별 성능
  - 최근 거래 내역
  - 시스템 상태

성능 지표:
  - 총 수익률
  - 샤프 비율
  - 최대 낙폭
  - 승률
  - 평균 손익비

제어 패널:
  - 거래 시작/중지
  - 전략 활성화/비활성화
  - 긴급 청산
  - 파라미터 조정
```

## 🔧 백테스팅

### 백테스트 실행
```bash
# 최근 30일 백테스트
python scripts/backtest.py --days 30 --strategy all

# 특정 전략 백테스트
python scripts/backtest.py --days 90 --strategy market_making

# 파라미터 최적화
python scripts/optimize.py --strategy stat_arb --metric sharpe
```

## 📝 운영 가이드

### 일일 체크리스트
```yaml
오전 점검 (09:00):
  - [ ] 시스템 상태 확인
  - [ ] 전일 성과 리뷰
  - [ ] 리스크 지표 점검
  - [ ] 오늘의 전략 가중치 조정

실시간 모니터링:
  - [ ] 포지션 크기 확인
  - [ ] 손익 추이 관찰
  - [ ] 이상 거래 감지
  - [ ] 시스템 리소스 체크

종료 점검 (21:00):
  - [ ] 일일 성과 정리
  - [ ] 로그 분석
  - [ ] 백업 확인
  - [ ] 내일 전략 계획
```

### 긴급 상황 대응
```bash
# 긴급 중단
curl -X POST http://localhost:8080/api/emergency-stop

# 모든 포지션 청산
curl -X POST http://localhost:8080/api/close-all-positions

# 시스템 재시작
sudo systemctl restart quantum-trading

# 롤백 (이전 버전으로)
cd /opt/quantum-trading
git checkout HEAD~1
sudo systemctl restart quantum-trading
```

## 🎓 학습 자료

### 추천 도서
- "Advances in Financial Machine Learning" - Marcos López de Prado
- "Quantitative Trading" - Ernest P. Chan
- "High-Frequency Trading" - Irene Aldridge

### 온라인 자료
- [QuantLib Python Cookbook](https://quantlib-python-cookbook.readthedocs.io/)
- [Algorithmic Trading with Python](https://www.quantstart.com/)
- [Kaggle Quant Finance](https://www.kaggle.com/learn/intro-to-financial-concepts)

## 📞 지원 및 문의

- **GitHub Issues**: 버그 리포트 및 기능 요청
- **Telegram**: @quantum_trading_support
- **Email**: quantum.trading@example.com

## ⚠️ 면책 조항

이 시스템은 교육 및 연구 목적으로 제작되었습니다. 실제 거래에 사용할 경우 발생하는 모든 손실에 대한 책임은 사용자에게 있습니다. 투자 전 충분한 테스트와 검증을 수행하세요.

## 🔄 버전 히스토리

- v3.0.0 (2024-01): 퀀트 트레이딩 시스템 전면 재구축
- v2.0.0 (2023-12): 멀티 전략 시스템 도입
- v1.0.0 (2023-11): 초기 버전 출시