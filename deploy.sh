#!/bin/bash

# 비트코인 자동거래 시스템 배포 스크립트 (Oracle Cloud)

set -e

echo "=== Bitcoin Auto Trading v2 배포 시작 ==="

# 색상 설정
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수 정의
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 운영체제 감지
if [ -f /etc/oracle-release ]; then
    OS="oracle"
    PKG_MGR="yum"
elif [ -f /etc/ubuntu-release ] || [ -f /etc/debian_version ]; then
    OS="ubuntu"
    PKG_MGR="apt"
else
    log_error "지원하지 않는 운영체제입니다"
    exit 1
fi

log_info "감지된 OS: $OS"

# 시스템 업데이트
log_info "시스템 패키지 업데이트 중..."
if [ "$OS" = "oracle" ]; then
    sudo yum update -y
else
    sudo apt update && sudo apt upgrade -y
fi

# Python 3.11 설치
log_info "Python 3.11 설치 중..."
if [ "$OS" = "oracle" ]; then
    sudo yum install -y python3 python3-pip python3-dev build-essential
else
    sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential
fi

# Git 설치
log_info "Git 설치 중..."
if [ "$OS" = "oracle" ]; then
    sudo yum install -y git
else
    sudo apt install -y git
fi

# 필요한 시스템 패키지 설치
log_info "시스템 의존성 설치 중..."
if [ "$OS" = "oracle" ]; then
    sudo yum install -y gcc gcc-c++ make sqlite-dev libffi-dev openssl-dev
else
    sudo apt install -y gcc g++ make libsqlite3-dev libffi-dev libssl-dev
fi

# 프로젝트 디렉토리 생성
PROJECT_DIR="/opt/bitcoin_auto_trading"
log_info "프로젝트 디렉토리 생성: $PROJECT_DIR"
sudo mkdir -p $PROJECT_DIR
sudo chown -R $USER:$USER $PROJECT_DIR

# 현재 디렉토리에서 프로젝트 파일 복사
log_info "프로젝트 파일 복사 중..."
CURRENT_DIR=$(pwd)
sudo cp -r $CURRENT_DIR/* $PROJECT_DIR/
sudo chown -R $USER:$USER $PROJECT_DIR

# 가상환경 생성
log_info "Python 가상환경 생성 중..."
cd $PROJECT_DIR
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
log_info "Python 패키지 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# 환경 변수 파일 템플릿 생성
log_info ".env 파일 템플릿 생성 중..."
cat > .env.template << 'EOF'
# Upbit API 키 (실제 키로 교체 필요)
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here

# Flask 설정
FLASK_PORT=9000
FLASK_ENV=production

# 데이터베이스 설정
DATABASE_PATH=/opt/bitcoin_auto_trading/data/trading_data.db

# 로그 설정
LOG_LEVEL=INFO
LOG_DIR=/opt/bitcoin_auto_trading/logs
EOF

# 디렉토리 구조 생성
log_info "필수 디렉토리 생성 중..."
mkdir -p logs data backtesting/results

# 방화벽 설정
log_info "방화벽 포트 9000 개방 중..."
if [ "$OS" = "oracle" ]; then
    sudo firewall-cmd --permanent --add-port=9000/tcp
    sudo firewall-cmd --reload
else
    sudo ufw allow 9000/tcp
    sudo ufw --force enable
fi

# systemd 서비스 파일 생성
log_info "systemd 서비스 파일 생성 중..."
sudo tee /etc/systemd/system/bitcoin-trading.service > /dev/null << EOF
[Unit]
Description=Bitcoin Auto Trading System v2
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --config $PROJECT_DIR/gunicorn.conf.py web.app:app
Restart=always
RestartSec=10

# 환경 변수
EnvironmentFile=$PROJECT_DIR/.env

# 로그 설정
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bitcoin-trading

[Install]
WantedBy=multi-user.target
EOF

# 서비스 등록 및 활성화
log_info "systemd 서비스 등록 중..."
sudo systemctl daemon-reload
sudo systemctl enable bitcoin-trading

# 로그 로테이션 설정
log_info "로그 로테이션 설정 중..."
sudo tee /etc/logrotate.d/bitcoin-trading > /dev/null << EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF

# cron 작업 설정 (자동 백업)
log_info "자동 백업 cron 작업 설정 중..."
(crontab -l 2>/dev/null; echo "0 2 * * * $PROJECT_DIR/venv/bin/python $PROJECT_DIR/utils/backup.py") | crontab -

log_info "=== 배포 완료 ==="
echo ""
log_warn "다음 단계를 수행하세요:"
echo "1. .env 파일을 생성하고 실제 API 키를 입력하세요:"
echo "   cp .env.template .env"
echo "   nano .env"
echo ""
echo "2. 업비트 API에서 현재 서버 IP를 허용 목록에 추가하세요"
echo "   현재 서버 공인 IP: $(curl -s ipinfo.io/ip)"
echo ""
echo "3. 서비스를 시작하세요:"
echo "   sudo systemctl start bitcoin-trading"
echo "   sudo systemctl status bitcoin-trading"
echo ""
echo "4. 웹 대시보드에 접속하세요:"
echo "   http://$(curl -s ipinfo.io/ip):9000"
echo ""
log_info "로그 확인: sudo journalctl -u bitcoin-trading -f"