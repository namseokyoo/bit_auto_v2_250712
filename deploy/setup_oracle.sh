#!/bin/bash

# Bitcoin Auto Trading v2.0 - Oracle Cloud 배포 스크립트
# Ubuntu 20.04/22.04용

set -e

echo "🚀 Bitcoin Auto Trading v2.0 - Oracle Cloud 설정 시작"
echo "=================================================="

# 시스템 업데이트
echo "📦 시스템 패키지 업데이트 중..."
sudo apt update && sudo apt upgrade -y

# Python 3.9+ 설치 확인
echo "🐍 Python 설치 확인 중..."
if ! command -v python3 &> /dev/null; then
    sudo apt install -y python3 python3-pip python3-venv
fi

python3 --version

# 필수 시스템 패키지 설치
echo "📚 필수 패키지 설치 중..."
sudo apt install -y \
    git \
    curl \
    wget \
    nginx \
    supervisor \
    sqlite3 \
    build-essential \
    python3-dev \
    python3-pip \
    ufw

# 방화벽 설정
echo "🔥 방화벽 설정 중..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 5000/tcp  # Flask 웹 서버
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS

# 사용자 및 디렉토리 생성
echo "👤 사용자 설정 중..."
sudo useradd -r -s /bin/false btc-trading || true
sudo mkdir -p /opt/btc-trading
sudo mkdir -p /var/log/btc-trading
sudo mkdir -p /etc/btc-trading

# 프로젝트 파일 복사 (현재 디렉토리에서)
echo "📂 프로젝트 파일 복사 중..."
if [ -f "main.py" ]; then
    sudo cp -r . /opt/btc-trading/
else
    echo "❌ 오류: main.py 파일이 없습니다. 프로젝트 디렉토리에서 실행하세요."
    exit 1
fi

# 권한 설정
sudo chown -R btc-trading:btc-trading /opt/btc-trading
sudo chown -R btc-trading:btc-trading /var/log/btc-trading
sudo chmod +x /opt/btc-trading/main.py

# Python 가상환경 설정
echo "🐍 Python 가상환경 설정 중..."
cd /opt/btc-trading
sudo -u btc-trading python3 -m venv venv
sudo -u btc-trading ./venv/bin/pip install --upgrade pip
sudo -u btc-trading ./venv/bin/pip install -r requirements.txt

# .env 파일 템플릿 생성
echo "⚙️  환경 설정 파일 생성 중..."
if [ ! -f "/opt/btc-trading/.env" ]; then
    sudo cp /opt/btc-trading/.env.example /opt/btc-trading/.env
    sudo chown btc-trading:btc-trading /opt/btc-trading/.env
    sudo chmod 600 /opt/btc-trading/.env
    
    echo "📝 .env 파일이 생성되었습니다."
    echo "   /opt/btc-trading/.env 파일에 Upbit API 키를 설정하세요:"
    echo "   UPBIT_ACCESS_KEY=your_access_key_here"
    echo "   UPBIT_SECRET_KEY=your_secret_key_here"
fi

# Systemd 서비스 파일 생성
echo "🔧 시스템 서비스 설정 중..."

# 트레이딩 엔진 서비스
sudo tee /etc/systemd/system/btc-trading-engine.service > /dev/null <<EOF
[Unit]
Description=Bitcoin Auto Trading Engine
After=network.target

[Service]
Type=simple
User=btc-trading
Group=btc-trading
WorkingDirectory=/opt/btc-trading
Environment=PATH=/opt/btc-trading/venv/bin
ExecStart=/opt/btc-trading/venv/bin/python main.py --mode trading
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=btc-trading-engine

[Install]
WantedBy=multi-user.target
EOF

# 웹 서버 서비스
sudo tee /etc/systemd/system/btc-trading-web.service > /dev/null <<EOF
[Unit]
Description=Bitcoin Auto Trading Web Interface
After=network.target

[Service]
Type=simple
User=btc-trading
Group=btc-trading
WorkingDirectory=/opt/btc-trading
Environment=PATH=/opt/btc-trading/venv/bin
ExecStart=/opt/btc-trading/venv/bin/python main.py --mode web
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=btc-trading-web

[Install]
WantedBy=multi-user.target
EOF

# Nginx 설정
echo "🌐 Nginx 설정 중..."
sudo tee /etc/nginx/sites-available/btc-trading > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # 정적 파일 서빙
    location /static {
        alias /opt/btc-trading/web/static;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/btc-trading /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# 로그 로테이션 설정
echo "📝 로그 로테이션 설정 중..."
sudo tee /etc/logrotate.d/btc-trading > /dev/null <<EOF
/var/log/btc-trading/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 btc-trading btc-trading
    postrotate
        systemctl reload btc-trading-engine
        systemctl reload btc-trading-web
    endscript
}
EOF

# 데이터베이스 초기화
echo "💾 데이터베이스 초기화 중..."
cd /opt/btc-trading
sudo -u btc-trading ./venv/bin/python main.py --init-db

# 서비스 활성화 및 시작
echo "🎯 서비스 활성화 중..."
sudo systemctl daemon-reload
sudo systemctl enable btc-trading-engine
sudo systemctl enable btc-trading-web
sudo systemctl enable nginx

# 서비스 시작 (일단 중지된 상태로 두고 수동 시작)
echo "⚠️  서비스는 수동으로 시작해야 합니다:"
echo "   1. .env 파일에 API 키 설정 후"
echo "   2. sudo systemctl start btc-trading-engine"
echo "   3. sudo systemctl start btc-trading-web"
echo "   4. sudo systemctl start nginx"

# 유용한 명령어 안내
echo "=================================================="
echo "✅ 설치 완료!"
echo ""
echo "📋 유용한 명령어:"
echo "   환경 설정: sudo nano /opt/btc-trading/.env"
echo "   로그 확인: sudo journalctl -f -u btc-trading-engine"
echo "   웹 로그 확인: sudo journalctl -f -u btc-trading-web"
echo "   서비스 상태: sudo systemctl status btc-trading-engine"
echo "   서비스 재시작: sudo systemctl restart btc-trading-engine"
echo "   설정 확인: cd /opt/btc-trading && sudo -u btc-trading ./venv/bin/python main.py --config-check"
echo ""
echo "🌐 웹 인터페이스: http://YOUR_SERVER_IP"
echo "🔑 .env 파일에 Upbit API 키를 설정하는 것을 잊지 마세요!"

echo "🎉 설정 완료! API 키 설정 후 서비스를 시작하세요."