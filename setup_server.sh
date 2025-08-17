#!/bin/bash

# Oracle Cloud 서버 초기 설정 스크립트
SERVER_IP="158.180.82.112"
echo "🔧 Oracle Cloud 서버 초기 설정 시작..."

ssh -i ssh-key-2025-07-14.key ubuntu@$SERVER_IP << 'EOF'
echo "📦 서버 설정 시작..."

# 1. 필요한 패키지 설치
echo "1. 패키지 업데이트 및 설치..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git nginx

# 2. 프로젝트 디렉토리 생성
echo "2. 프로젝트 디렉토리 생성..."
sudo mkdir -p /opt/btc-trading
sudo chown -R ubuntu:ubuntu /opt/btc-trading

# 3. Git 저장소 클론
echo "3. 저장소 클론..."
cd /opt
sudo rm -rf btc-trading
sudo git clone https://github.com/namseokyoo/bit_auto_v2_250712.git btc-trading
sudo chown -R ubuntu:ubuntu /opt/btc-trading

# 4. Python 가상환경 설정
echo "4. Python 가상환경 생성..."
cd /opt/btc-trading
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. 로그 디렉토리 생성
echo "5. 디렉토리 구조 생성..."
mkdir -p /opt/btc-trading/logs
mkdir -p /opt/btc-trading/data

# 6. 서비스 파일 생성 - 트레이딩 엔진
echo "6. systemd 서비스 생성..."
sudo tee /etc/systemd/system/btc-trading-engine.service > /dev/null <<'SERVICE'
[Unit]
Description=Bitcoin Trading Engine
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/btc-trading
Environment="PATH=/opt/btc-trading/venv/bin"
ExecStart=/opt/btc-trading/venv/bin/python main.py --mode trading
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# 7. 서비스 파일 생성 - 웹 서버
sudo tee /etc/systemd/system/btc-trading-web.service > /dev/null <<'SERVICE'
[Unit]
Description=Bitcoin Trading Web Interface
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/btc-trading
Environment="PATH=/opt/btc-trading/venv/bin"
ExecStart=/opt/btc-trading/venv/bin/python web/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# 8. 서비스 등록 및 시작
echo "7. 서비스 등록..."
sudo systemctl daemon-reload
sudo systemctl enable btc-trading-engine
sudo systemctl enable btc-trading-web

# 9. 권한 설정
echo "8. 권한 설정..."
sudo chown -R ubuntu:ubuntu /opt/btc-trading
sudo chmod -R 755 /opt/btc-trading

echo "✅ 서버 초기 설정 완료!"
echo "📍 프로젝트 경로: /opt/btc-trading"
echo "📍 Python 경로: /opt/btc-trading/venv/bin/python"
echo ""
echo "다음 명령으로 서비스를 시작할 수 있습니다:"
echo "sudo systemctl start btc-trading-engine"
echo "sudo systemctl start btc-trading-web"
EOF

echo "🎉 서버 설정이 완료되었습니다!"
echo "이제 GitHub Actions를 다시 실행하거나 수동으로 배포할 수 있습니다."