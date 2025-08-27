#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}🚀 Quantum Trading System Setup${NC}"
echo -e "${GREEN}================================${NC}"

# 가상환경 활성화
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
fi

# 1. Python 패키지 설치
echo -e "\n${YELLOW}Installing Python packages...${NC}"
pip install apscheduler httpx pandas numpy pyupbit redis psutil

# 2. 디렉토리 생성
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p data logs reports config

# 3. 데이터베이스 초기화
echo -e "\n${YELLOW}Initializing databases...${NC}"
python3 -c "
import sqlite3

# AI 분석 DB
conn = sqlite3.connect('data/ai_analysis.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        type TEXT,
        analysis TEXT,
        implemented BOOLEAN DEFAULT FALSE
    )
''')
conn.commit()
conn.close()

# 멀티 코인 DB
conn = sqlite3.connect('data/multi_coin.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        coin TEXT,
        strategy TEXT,
        side TEXT,
        price REAL,
        quantity REAL,
        amount REAL,
        fee REAL,
        pnl REAL,
        signal_strength REAL,
        market_conditions TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS positions (
        coin TEXT PRIMARY KEY,
        quantity REAL,
        avg_price REAL,
        current_value REAL,
        unrealized_pnl REAL,
        last_updated DATETIME
    )
''')
conn.commit()
conn.close()

print('Databases initialized')
"

# 4. 환경 변수 확인
echo -e "\n${YELLOW}Checking environment variables...${NC}"
if [ ! -f "config/.env" ]; then
    echo -e "${RED}Warning: config/.env not found${NC}"
    echo "Creating template..."
    cat > config/.env << 'EOF'
# Upbit API Keys
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here

# DeepSeek API Key (for AI analysis)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Dashboard
DASHBOARD_PORT=8080
FLASK_SECRET_KEY=your-secret-key-here

# Redis (optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
EOF
    echo -e "${YELLOW}Please edit config/.env with your API keys${NC}"
fi

# 5. Redis 확인
echo -e "\n${YELLOW}Checking Redis...${NC}"
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}Redis is running${NC}"
    else
        echo -e "${YELLOW}Redis is not running. Starting Redis...${NC}"
        redis-server --daemonize yes
    fi
else
    echo -e "${YELLOW}Redis not installed. Some features will be disabled.${NC}"
fi

# 6. 시스템 선택 메뉴
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}Select System to Run:${NC}"
echo -e "${GREEN}================================${NC}"
echo "1) Full Integrated System (AI + Multi-Coin + Dashboard)"
echo "2) Multi-Coin Trading Only"
echo "3) AI Feedback System Only"
echo "4) Original Single-Coin System"
echo "5) Dashboard Only"
echo "6) Test Mode (Dry Run)"
echo "0) Exit"

read -p "Enter your choice [0-6]: " choice

case $choice in
    1)
        echo -e "\n${GREEN}Starting Integrated Trading System...${NC}"
        python3 integrated_trading_system.py
        ;;
    2)
        echo -e "\n${GREEN}Starting Multi-Coin Trading...${NC}"
        python3 multi_coin_trading.py
        ;;
    3)
        echo -e "\n${GREEN}Starting AI Feedback System...${NC}"
        python3 feedback_scheduler.py
        ;;
    4)
        echo -e "\n${GREEN}Starting Original Quantum Trading...${NC}"
        python3 quantum_trading.py
        ;;
    5)
        echo -e "\n${GREEN}Starting Dashboard...${NC}"
        python3 dashboard.py
        ;;
    6)
        echo -e "\n${GREEN}Starting Test Mode...${NC}"
        python3 -c "
import asyncio
from ai_analyzer import FeedbackLoop
from multi_coin_trading import MultiCoinTrader

async def test():
    print('Testing AI Feedback System...')
    feedback = FeedbackLoop()
    report = await feedback.run_daily_analysis()
    print(f'AI Analysis: {report}')
    
    print('\nTesting Multi-Coin System...')
    trader = MultiCoinTrader()
    await trader.initialize()
    print('Multi-coin system initialized successfully')
    
    await feedback.close()

asyncio.run(test())
        "
        ;;
    0)
        echo -e "${GREEN}Exiting...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac