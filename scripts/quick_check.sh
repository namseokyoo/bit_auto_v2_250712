#!/bin/bash

# 빠른 시스템 상태 체크 스크립트
# 한 줄로 모든 상태를 확인

set -euo pipefail

WEB_URL="http://158.180.82.112:8080"
SSH_KEY="ssh-key-2025-07-14.key"
SSH_HOST="ubuntu@158.180.82.112"
SERVICE_NAME="bitcoin-auto-trading.service"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Bitcoin Auto Trading System - 빠른 상태 체크${NC}"
echo "=================================================="

# 서비스 상태
service_status=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=5 \
    "$SSH_HOST" "sudo systemctl is-active $SERVICE_NAME" 2>/dev/null || echo "inactive")

if [ "$service_status" = "active" ]; then
    echo -e "📊 서비스: ${GREEN}실행 중${NC}"
else
    echo -e "📊 서비스: ${RED}중지됨${NC}"
fi

# 웹 서버 상태
web_status=$(curl -s --max-time 5 "$WEB_URL/health" 2>/dev/null || echo "error")
if [ "$web_status" != "error" ]; then
    echo -e "🌐 웹서버: ${GREEN}정상${NC}"
else
    echo -e "🌐 웹서버: ${RED}오류${NC}"
fi

# 시스템 상태
api_response=$(curl -s --max-time 5 "$WEB_URL/api/system/status" 2>/dev/null || echo "error")
if [ "$api_response" != "error" ]; then
    system_enabled=$(echo "$api_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('system_enabled', False))" 2>/dev/null || echo "False")
    trading_enabled=$(echo "$api_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('trading_enabled', False))" 2>/dev/null || echo "False")
    
    if [ "$system_enabled" = "True" ] && [ "$trading_enabled" = "True" ]; then
        echo -e "⚙️  시스템: ${GREEN}활성화${NC}"
    else
        echo -e "⚙️  시스템: ${YELLOW}부분 활성화${NC}"
    fi
else
    echo -e "⚙️  시스템: ${RED}오류${NC}"
fi

# 체제 정보
regime_response=$(curl -s --max-time 5 "$WEB_URL/api/regime/status" 2>/dev/null || echo "error")
if [ "$regime_response" != "error" ]; then
    regime=$(echo "$regime_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('regime_info', {}).get('regime', 'unknown'))" 2>/dev/null || echo "unknown")
    confidence=$(echo "$regime_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('regime_info', {}).get('confidence', 0))" 2>/dev/null || echo "0")
    
    regime_kr=""
    case "$regime" in
        "bull_market") regime_kr="상승장" ;;
        "bear_market") regime_kr="하락장" ;;
        "sideways") regime_kr="횡보장" ;;
        "high_volatility") regime_kr="고변동성" ;;
        "low_volatility") regime_kr="저변동성" ;;
        "trending_up") regime_kr="상승트렌드" ;;
        "trending_down") regime_kr="하락트렌드" ;;
        *) regime_kr="$regime" ;;
    esac
    
    confidence_percent=$(echo "$confidence * 100" | bc -l | cut -d. -f1)
    echo -e "📈 체제: ${GREEN}$regime_kr${NC} (신뢰도: ${confidence_percent}%)"
else
    echo -e "📈 체제: ${RED}오류${NC}"
fi

echo "=================================================="
echo -e "${BLUE}💡 웹 대시보드: $WEB_URL${NC}"
echo -e "${BLUE}📋 상세 체크: ./scripts/test_system.sh status${NC}"
