#!/bin/bash

# 웹 서버 포트를 5000으로 변경
ssh -i ssh-key-2025-07-14.key ubuntu@158.180.82.112 << 'EOF'
echo "🔧 포트 설정 변경 중..."

# app.py 파일에서 포트 변경
cd /opt/btc-trading
sudo sed -i "s/port=9000/port=5000/g" web/app.py
sudo sed -i "s/localhost:9000/localhost:5000/g" web/app.py

# 서비스 재시작
sudo systemctl restart btc-trading-web

# 방화벽 규칙 추가
sudo iptables -I INPUT -p tcp --dport 9000 -j ACCEPT

sleep 3
echo "✅ 포트 설정 완료!"
echo "📍 접속 주소: http://158.180.82.112:9000"
sudo ss -tlnp | grep python
EOF