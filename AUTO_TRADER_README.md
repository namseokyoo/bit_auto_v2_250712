# 자동 거래 봇 사용 가이드

## 시스템 구조

이 시스템은 두 개의 독립적인 컴포넌트로 구성됩니다:

1. **자동 거래 봇** (`auto_trader_service.py`) - 실제 거래를 수행하는 백그라운드 서비스
2. **웹 대시보드** (`main.py --mode web`) - 거래 상태를 모니터링하는 웹 인터페이스

## 설정 방법

### 1. 환경 변수 설정 (.env 파일)

```bash
# Upbit API 키
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# Flask 설정
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### 2. 거래 설정 (config/trading_config.json)

```json
{
  "system": {
    "enabled": true,
    "mode": "real_trading"
  },
  "trading": {
    "enabled": true,
    "max_trade_amount": 100000,
    "trade_interval_minutes": 10,
    "emergency_stop_loss": -100000
  }
}
```

## 실행 방법

### 자동 거래 봇 실행 (서버에서 독립적으로 실행)

```bash
# 백그라운드에서 실행
nohup python auto_trader_service.py > logs/auto_trader.log 2>&1 &

# 또는 포그라운드에서 실행 (로그 확인용)
python auto_trader_service.py
```

### 웹 대시보드 실행 (모니터링용)

```bash
# 웹 서버만 실행
python main.py --mode web

# 또는
python main.py
```

## 운영 방법

### 1. 자동 거래 봇 시작

1. `config/trading_config.json` 파일을 편집하여 설정 변경
2. `python auto_trader_service.py` 실행
3. 봇이 설정된 간격(기본 10분)마다 자동으로 분석 및 거래 실행

### 2. 상태 모니터링

1. 웹 브라우저에서 `http://서버주소:5000` 접속
2. 대시보드에서 다음 정보 확인:
   - 현재 잔고
   - 최근 거래 내역
   - 자동 분석 결과
   - 다음 분석 예정 시간

### 3. 설정 변경

1. 자동 거래 봇 정지 (Ctrl+C 또는 kill 명령)
2. `config/trading_config.json` 파일 수정
3. 자동 거래 봇 재시작

### 4. 로그 확인

```bash
# 자동 거래 봇 로그
tail -f logs/auto_trader.log

# 시스템 전체 로그
tail -f logs/trading.log
```

## 주요 설정 항목

### system.enabled
- `true`: 시스템 활성화
- `false`: 시스템 비활성화 (봇이 실행되어도 거래하지 않음)

### trading.enabled
- `true`: 자동 거래 활성화
- `false`: 분석만 수행, 실제 거래는 하지 않음

### trading.trade_interval_minutes
- 분석 및 거래 실행 간격 (분 단위)
- 기본값: 10분

### trading.max_trade_amount
- 한 번에 거래할 수 있는 최대 금액 (KRW)
- 기본값: 100,000원

## 프로세스 관리 (systemd 사용 예시)

### 1. systemd 서비스 파일 생성

`/etc/systemd/system/bitcoin-auto-trader.service`:

```ini
[Unit]
Description=Bitcoin Auto Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/bit_auto_v2_250712
ExecStart=/usr/bin/python3 /home/ubuntu/bit_auto_v2_250712/auto_trader_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. 서비스 관리 명령

```bash
# 서비스 시작
sudo systemctl start bitcoin-auto-trader

# 서비스 정지
sudo systemctl stop bitcoin-auto-trader

# 서비스 재시작
sudo systemctl restart bitcoin-auto-trader

# 서비스 상태 확인
sudo systemctl status bitcoin-auto-trader

# 부팅 시 자동 시작 설정
sudo systemctl enable bitcoin-auto-trader
```

## 안전 장치

1. **긴급 정지**: 웹 대시보드의 긴급 정지 버튼은 제거됨. 봇을 직접 정지해야 함
2. **손실 제한**: `emergency_stop_loss` 설정으로 최대 손실 제한
3. **거래 금액 제한**: `max_trade_amount`로 한 번에 거래할 수 있는 최대 금액 제한

## 문제 해결

### 봇이 실행되지 않을 때
1. 환경 변수 확인 (.env 파일)
2. 설정 파일 확인 (config/trading_config.json)
3. 로그 파일 확인 (logs/auto_trader.log)

### 거래가 실행되지 않을 때
1. `system.enabled`가 true인지 확인
2. `trading.enabled`가 true인지 확인
3. Upbit API 키가 올바른지 확인
4. 계좌에 충분한 잔고가 있는지 확인

### 대시보드가 연결되지 않을 때
1. 웹 서버가 실행 중인지 확인
2. 방화벽 설정 확인 (포트 5000)
3. Oracle Cloud의 경우 보안 목록에서 포트 5000 허용 확인