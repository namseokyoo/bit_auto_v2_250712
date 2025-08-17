#!/bin/bash

# Oracle Cloud 서버 정보
SERVER_IP="158.180.82.112"
SERVER_USER="ubuntu"
PROJECT_DIR="/opt/btc-trading"

echo "🚀 Oracle Cloud로 배포 시작..."

# 1. GitHub에 푸시
echo "📤 GitHub에 코드 푸시 중..."
git add .
git commit -m "Update: $(date +'%Y-%m-%d %H:%M:%S')"
git push origin main

# 2. 서버에서 pull 및 재시작
echo "🔄 서버에서 코드 업데이트 중..."
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /opt/btc-trading
sudo git pull origin main
echo "📦 의존성 설치..."
sudo /opt/btc-trading/venv/bin/pip install -r requirements.txt
echo "♻️ 서비스 재시작..."
sudo systemctl restart btc-trading-engine
sudo systemctl restart btc-trading-web
echo "✅ 배포 완료!"
sudo systemctl status btc-trading-engine --no-pager | head -10
ENDSSH

echo "🎉 배포가 완료되었습니다!"