#!/bin/bash

# 서버 설정 확인 스크립트
# 사용법: ./check_server_setup.sh your-server-ip

SERVER_IP=${1:-158.180.82.112}
echo "서버 IP: $SERVER_IP"

echo "🔍 Oracle Cloud 서버 설정 확인 중..."

ssh -i ssh-key-2025-07-14.key ubuntu@$SERVER_IP << 'EOF'
echo "=== 서버 접속 성공 ==="

echo "1. Git 설치 확인:"
which git && git --version || echo "❌ Git 미설치"

echo -e "\n2. 프로젝트 디렉토리 확인:"
ls -la /opt/btc-trading 2>/dev/null || echo "❌ 프로젝트 디렉토리 없음"

echo -e "\n3. Python 가상환경 확인:"
ls -la /opt/btc-trading/venv/bin/python 2>/dev/null || echo "❌ Python venv 없음"

echo -e "\n4. 서비스 상태 확인:"
sudo systemctl status btc-trading-engine --no-pager 2>/dev/null | head -5 || echo "❌ 트레이딩 엔진 서비스 없음"
sudo systemctl status btc-trading-web --no-pager 2>/dev/null | head -5 || echo "❌ 웹 서비스 없음"

echo -e "\n5. sudo 권한 확인:"
sudo -n true 2>/dev/null && echo "✅ Sudo 권한 OK" || echo "⚠️  Sudo 비밀번호 필요"

echo -e "\n6. Git 저장소 확인:"
cd /opt/btc-trading 2>/dev/null && git remote -v || echo "❌ Git 저장소 설정 안됨"
EOF

echo -e "\n✅ 서버 확인 완료!"