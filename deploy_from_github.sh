#!/bin/bash
# GitHub에서 최신 코드 받아서 배포하는 스크립트

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}📦 GitHub 기반 배포 스크립트${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. Git 상태 확인
echo -e "\n${YELLOW}Step 1: Git 상태 확인...${NC}"
git status

# 2. 로컬 변경사항 커밋
echo -e "\n${YELLOW}Step 2: 로컬 변경사항이 있습니까? (y/n)${NC}"
read -r has_changes

if [ "$has_changes" = "y" ]; then
    echo -e "${YELLOW}커밋 메시지를 입력하세요:${NC}"
    read -r commit_msg
    git add .
    git commit -m "$commit_msg"
    git push origin main
    echo -e "${GREEN}✓ GitHub에 푸시 완료${NC}"
fi

# 3. 서버에서 배포
echo -e "\n${YELLOW}Step 3: 서버에 배포 중...${NC}"

ssh -i ssh-key-2025-07-14.key ubuntu@158.180.82.112 << 'EOF'
cd /home/ubuntu/bit_auto_v2

# Git pull
echo "Pulling latest changes from GitHub..."
git pull origin main

# 현재 실행 중인 프로세스 확인
echo "Checking running processes..."
ps aux | grep python | grep -v grep

# 프로세스 재시작 여부 확인
echo "프로세스를 재시작하시겠습니까? (y/n)"
read -r restart

if [ "$restart" = "y" ]; then
    echo "Stopping existing processes..."
    pkill -f integrated_trading_system.py || true
    pkill -f multi_coin_trading.py || true
    pkill -f quantum_trading.py || true
    
    echo "Starting system..."
    cd /home/ubuntu/bit_auto_v2
    source venv/bin/activate
    nohup python integrated_trading_system.py > logs/integrated_system.log 2>&1 &
    echo "✓ System restarted"
fi

echo "✓ Deployment complete!"
EOF

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 배포 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "대시보드: http://158.180.82.112:8080/"