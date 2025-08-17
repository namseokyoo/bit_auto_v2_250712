#!/bin/bash

# 서버에 .env 파일 설정
SERVER_IP="158.180.82.112"

echo "🔐 서버에 .env 파일 설정 중..."

ssh -i ssh-key-2025-07-14.key ubuntu@$SERVER_IP << 'EOF'
cd /opt/btc-trading

# .env 파일 생성 (API 키는 직접 입력 필요)
cat > .env << 'ENV'
# Upbit API Keys (실제 값으로 교체 필요!)
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here

# Flask Settings
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log

# Database
DATABASE_PATH=data/trading_data.db
ENV

echo "⚠️  .env 파일이 생성되었습니다."
echo "📝 /opt/btc-trading/.env 파일을 편집하여 실제 API 키를 입력하세요:"
echo "   sudo nano /opt/btc-trading/.env"
EOF