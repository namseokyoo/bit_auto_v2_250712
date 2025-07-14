# Bitcoin Auto Trading System v2.0

자동화된 비트코인 트레이딩 시스템으로, 16가지 전략을 활용하여 Upbit 거래소에서 자동 매매를 수행합니다.

## 🚀 주요 기능

- **16가지 트레이딩 전략** (시간/일 단위)
- **실시간 웹 관리 패널**
- **동적 설정 관리** (외부에서 실시간 변경 가능)
- **리스크 관리 시스템**
- **모의거래 모드**
- **자동 백업 및 로깅**
- **오라클 클라우드 배포 지원**

## 📋 시스템 요구사항

- Python 3.8+
- Ubuntu 20.04+ (오라클 클라우드)
- 최소 1GB RAM
- 10GB 저장공간

## 🛠️ 로컬 설치 및 실행

### 1. 프로젝트 클론
```bash
git clone <repository_url>
cd bit_auto_v2_250712
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 설정
```bash
cp .env.example .env
nano .env
```

`.env` 파일에 Upbit API 키 입력:
```env
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here
```

### 4. 데이터베이스 초기화
```bash
python main.py --init-db
```

### 5. 실행
```bash
# 전체 시스템 실행 (트레이딩 엔진 + 웹 서버)
python main.py

# 트레이딩 엔진만 실행
python main.py --mode trading

# 웹 서버만 실행
python main.py --mode web

# 모의거래 모드로 실행
python main.py --paper-trading
```

### 6. 웹 인터페이스 접속
http://localhost:5000

## 🌩️ 오라클 클라우드 배포

### 1. 서버 접속
```bash
ssh ubuntu@your-server-ip
```

### 2. 프로젝트 업로드
```bash
# 로컬에서 서버로 파일 전송
scp -r . ubuntu@your-server-ip:~/btc-trading/
```

### 3. 자동 설치 스크립트 실행
```bash
cd ~/btc-trading
sudo chmod +x deploy/setup_oracle.sh
sudo ./deploy/setup_oracle.sh
```

### 4. API 키 설정
```bash
sudo nano /opt/btc-trading/.env
```

### 5. 서비스 시작
```bash
sudo systemctl start btc-trading-engine
sudo systemctl start btc-trading-web
sudo systemctl start nginx
```

### 6. 서비스 상태 확인
```bash
sudo systemctl status btc-trading-engine
sudo systemctl status btc-trading-web
```

## 📊 트레이딩 전략

### 시간 단위 전략 (8개)
1. **EMA 골든/데드크로스**: 12-EMA와 26-EMA 교차
2. **RSI 다이버전스**: 가격과 RSI 지표 역행
3. **피봇 포인트**: 일일 지지/저항선 반등
4. **VWAP 되돌림**: 거래량 가중 평균가 기준
5. **MACD 0선 교차**: 모멘텀 변화 감지
6. **볼린저 밴드**: 변동성 기반 매매
7. **미체결 약정**: 선물 거래량 분석
8. **깃발/페넌트**: 지속형 패턴 돌파

### 일 단위 전략 (8개)
1. **주봉+일봉 눌림목**: 다중 시간대 분석
2. **일목균형표**: 구름대 돌파/지지
3. **볼린저 밴드 폭**: 변동성 수축 후 돌파
4. **공포탐욕지수**: 감정 지표 역이용
5. **골든크로스**: 50일/200일선 교차
6. **MVRV Z-Score**: 온체인 가치 투자
7. **스토캐스틱 RSI**: 과매수/과매도 탈출
8. **ADX 필터**: 추세 강도 기반 전략 선택

## ⚙️ 설정 관리

### 주요 설정 항목
- **초기 잔고**: 1,000,000 KRW (모의거래)
- **최대 거래 금액**: 100,000 KRW
- **긴급 정지 손실**: 100,000 KRW
- **일일 손실 한도**: 50,000 KRW
- **최대 동시 포지션**: 3개

### 동적 설정 변경
웹 인터페이스에서 실시간으로 설정 변경 가능:
- 시스템 ON/OFF
- 자동거래 ON/OFF
- 거래 금액 조정
- 전략 활성화/비활성화
- 리스크 관리 파라미터

## 🔒 보안 기능

- API 키 암호화 저장
- 환경 변수 기반 설정
- 다중 안전장치
- 모의거래 모드
- 긴급 정지 기능
- 접근 로그 기록

## 📈 모니터링

### 웹 대시보드
- 실시간 잔고 현황
- 거래 내역 조회
- 전략별 성능 분석
- 시스템 로그 확인

### 로그 파일
```bash
# 트레이딩 엔진 로그
sudo journalctl -f -u btc-trading-engine

# 웹 서버 로그
sudo journalctl -f -u btc-trading-web

# 파일 로그
tail -f logs/trading_engine.log
```

## 🛡️ 리스크 관리

### 자동 보호 기능
- 일일 손실 한도 제한
- 연속 손실 시 자동 정지
- 최대 포지션 크기 제한
- 거래 빈도 제한
- 긴급 정지 기능

### 수동 제어
- 웹 인터페이스를 통한 즉시 정지
- 개별 전략 비활성화
- 거래 모드 변경 (실거래 ↔ 모의거래)

## 🔧 유지보수

### 로그 정리
```bash
# 90일 이전 데이터 정리
python -c "from data.database import db; db.cleanup_old_data(90)"
```

### 백업
```bash
# 데이터베이스 백업
python -c "from data.database import db; db.backup_database()"
```

### 서비스 관리
```bash
# 서비스 재시작
sudo systemctl restart btc-trading-engine

# 설정 파일 리로드
sudo systemctl reload btc-trading-engine

# 서비스 로그 확인
sudo journalctl -f -u btc-trading-engine
```

## 📞 지원

### 설정 확인
```bash
python main.py --config-check
```

### 문제 해결
1. **API 연결 오류**: .env 파일의 API 키 확인
2. **거래 실행 안됨**: 시스템/자동거래 활성화 상태 확인
3. **웹 접속 안됨**: 방화벽 설정 및 서비스 상태 확인

### 로그 위치
- 애플리케이션 로그: `/var/log/btc-trading/`
- 시스템 로그: `journalctl -u btc-trading-*`
- 데이터베이스: `/opt/btc-trading/data/`

## ⚠️ 주의사항

1. **실거래 전 충분한 테스트**: 모의거래로 검증 후 실거래 진행
2. **API 키 보안**: .env 파일 권한 및 접근 제한
3. **정기적인 모니터링**: 거래 성과 및 시스템 상태 확인
4. **백업**: 정기적인 데이터베이스 백업
5. **자금 관리**: 감당할 수 있는 범위 내에서 거래

## 📄 라이선스

이 프로젝트는 교육 및 연구 목적으로 제작되었습니다. 실제 거래 시 발생하는 손실에 대해서는 책임지지 않습니다.

---

**면책 조항**: 암호화폐 거래는 고위험 투자입니다. 투자 전 충분한 검토와 이해가 필요하며, 감당할 수 있는 범위 내에서만 투자하시기 바랍니다.