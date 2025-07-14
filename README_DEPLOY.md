# 🚀 Bitcoin Auto Trading v2 - Oracle Cloud 배포 가이드

## 📋 사전 준비사항

### 1. Oracle Cloud 인스턴스 생성
- **권장 스펙**: 
  - Shape: VM.Standard.E2.1.Micro (Always Free) 또는 더 높은 사양
  - OS: Oracle Linux 8.x
  - Storage: 최소 50GB
  - RAM: 최소 1GB (권장 2GB+)

### 2. 네트워크 설정
- **보안 그룹**: 9000 포트 인바운드 허용
- **방화벽**: Oracle Cloud Console에서 9000 포트 개방

## 🛠️ 배포 단계

### 1단계: 서버 접속 및 소스 업로드

```bash
# SSH로 Oracle Cloud 인스턴스 접속
ssh -i your-key.pem opc@your-server-ip

# 프로젝트 소스 업로드 (여러 방법 중 선택)

# 방법 1: Git Clone (추천)
git clone https://github.com/your-repo/bit_auto_v2_250712.git
cd bit_auto_v2_250712

# 방법 2: SCP로 직접 업로드
# 로컬에서 실행:
# scp -i your-key.pem -r /path/to/bit_auto_v2_250712 opc@your-server-ip:~/

# 방법 3: ZIP 압축 후 업로드
# 로컬에서: zip -r bitcoin_trading.zip bit_auto_v2_250712/
# 서버에서: unzip bitcoin_trading.zip
```

### 2단계: 자동 배포 스크립트 실행

```bash
# 실행 권한 부여
chmod +x deploy.sh

# 배포 스크립트 실행
sudo ./deploy.sh

# 배포 과정에서 필요한 패키지들이 자동 설치됩니다:
# - Python 3.11
# - Git, 빌드 도구
# - SQLite, 시스템 라이브러리
# - Python 가상환경 및 의존성
```

### 3단계: 환경 설정

```bash
# 프로젝트 디렉토리로 이동
cd /opt/bitcoin_auto_trading

# .env 파일 생성 (템플릿에서 복사)
cp .env.template .env

# API 키 설정
nano .env
```

**.env 파일 예시:**
```bash
# Upbit API 키 (실제 키로 교체)
UPBIT_ACCESS_KEY=YOUR_ACTUAL_ACCESS_KEY
UPBIT_SECRET_KEY=YOUR_ACTUAL_SECRET_KEY

# Flask 설정
FLASK_PORT=9000
FLASK_ENV=production

# 데이터베이스 설정
DATABASE_PATH=/opt/bitcoin_auto_trading/data/trading_data.db

# 로그 설정
LOG_LEVEL=INFO
LOG_DIR=/opt/bitcoin_auto_trading/logs
```

### 4단계: IP 허용 설정

**업비트 API 설정에서 현재 서버 IP를 허용 목록에 추가:**

```bash
# 현재 서버의 공인 IP 확인
curl ipinfo.io/ip

# 출력된 IP를 업비트 Open API 관리에서 허용 IP로 등록
```

### 5단계: 서비스 시작

```bash
# 서비스 시작
sudo systemctl start bitcoin-trading

# 서비스 상태 확인
sudo systemctl status bitcoin-trading

# 서비스 로그 확인
sudo journalctl -u bitcoin-trading -f

# 자동 시작 설정 (이미 배포 스크립트에서 설정됨)
sudo systemctl enable bitcoin-trading
```

## 🌐 접속 확인

### 웹 대시보드 접속
```
http://YOUR_SERVER_IP:9000
```

### API 엔드포인트 테스트
```bash
# 시스템 상태 확인
curl http://YOUR_SERVER_IP:9000/api/system/status

# 잔고 조회 (IP 인증 후)
curl http://YOUR_SERVER_IP:9000/api/balance

# 전략 분석
curl -X POST http://YOUR_SERVER_IP:9000/api/manual_trading/analyze \
     -H "Content-Type: application/json" -d '{}'
```

## 📊 모니터링

### 1. 서비스 상태 모니터링
```bash
# 실시간 로그 확인
sudo journalctl -u bitcoin-trading -f

# 서비스 재시작
sudo systemctl restart bitcoin-trading

# 서비스 중지
sudo systemctl stop bitcoin-trading
```

### 2. 로그 파일 위치
```
/opt/bitcoin_auto_trading/logs/
├── gunicorn_access.log    # 웹 서버 접속 로그
├── gunicorn_error.log     # 웹 서버 오류 로그
├── errors.log             # 애플리케이션 오류 로그
├── trades.log             # 거래 로그
├── system.log             # 시스템 로그
└── backup.log             # 백업 로그
```

### 3. 백업 시스템
```bash
# 수동 백업 실행
/opt/bitcoin_auto_trading/venv/bin/python /opt/bitcoin_auto_trading/utils/backup.py

# 백업 파일 확인
ls -la /opt/bitcoin_auto_trading/backups/

# 자동 백업 (cron) - 매일 새벽 2시 실행
crontab -l
```

## 🔧 문제 해결

### 1. 포트 접속 불가
```bash
# 방화벽 상태 확인
sudo firewall-cmd --list-all

# 포트 개방 (재실행)
sudo firewall-cmd --permanent --add-port=9000/tcp
sudo firewall-cmd --reload

# Oracle Cloud Console에서도 보안 그룹 확인
```

### 2. API 키 오류
```bash
# .env 파일 확인
cat /opt/bitcoin_auto_trading/.env

# 로그에서 오류 확인
sudo journalctl -u bitcoin-trading -n 50
```

### 3. 메모리 부족
```bash
# 메모리 사용량 확인
free -h

# swap 파일 생성 (필요시)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 4. 서비스 재배포
```bash
# 코드 업데이트 후
cd /opt/bitcoin_auto_trading
git pull  # 또는 새 소스 업로드

# 가상환경에서 의존성 업데이트
source venv/bin/activate
pip install -r requirements.txt

# 서비스 재시작
sudo systemctl restart bitcoin-trading
```

## 🛡️ 보안 권장사항

### 1. 방화벽 설정
```bash
# 필요한 포트만 개방
sudo firewall-cmd --permanent --add-port=22/tcp    # SSH
sudo firewall-cmd --permanent --add-port=9000/tcp  # 웹 대시보드
sudo firewall-cmd --reload
```

### 2. SSL/HTTPS 설정 (선택사항)
```bash
# Let's Encrypt 인증서 설치
sudo yum install -y certbot
sudo certbot certonly --standalone -d your-domain.com

# gunicorn.conf.py에서 SSL 설정 활성화
```

### 3. 정기 보안 업데이트
```bash
# 시스템 업데이트 자동화
echo "0 3 * * 0 yum update -y" | sudo crontab -
```

## 📈 성능 최적화

### 1. Gunicorn Worker 조정
```python
# gunicorn.conf.py에서 워커 수 조정
workers = multiprocessing.cpu_count() * 2 + 1
```

### 2. 데이터베이스 최적화
```bash
# SQLite 최적화 (정기 실행 권장)
echo "VACUUM; REINDEX;" | sqlite3 /opt/bitcoin_auto_trading/data/trading_data.db
```

### 3. 로그 로테이션
```bash
# logrotate 설정 확인
sudo logrotate -d /etc/logrotate.d/bitcoin-trading
```

---

## 🆘 지원

문제 발생 시:
1. 로그 파일 확인
2. 서비스 상태 확인  
3. 네트워크 및 방화벽 설정 확인
4. API 키 및 IP 허용 설정 확인

**성공적인 배포를 위해 각 단계를 순서대로 진행하세요!**