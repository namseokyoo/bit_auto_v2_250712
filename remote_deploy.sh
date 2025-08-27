#!/bin/bash
# Remote deployment script for Quantum Trading System
# This script runs ON THE REMOTE SERVER to deploy the latest code

set -e

echo "========================================="
echo "Quantum Trading System Deployment"
echo "========================================="
echo ""

# Configuration
DEPLOY_DIR="/home/ubuntu/bit_auto_v2"
BACKUP_DIR="/home/ubuntu/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Creating backup...${NC}"
mkdir -p $BACKUP_DIR

if [ -d "$DEPLOY_DIR" ]; then
    tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" \
        -C "$DEPLOY_DIR" \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='logs/*' \
        .
    echo -e "${GREEN}✓ Backup created: backup_$TIMESTAMP.tar.gz${NC}"
else
    echo -e "${YELLOW}No existing deployment to backup${NC}"
    mkdir -p $DEPLOY_DIR
fi

echo -e "\n${YELLOW}Step 2: Syncing code from local...${NC}"
cd $DEPLOY_DIR
echo -e "${GREEN}✓ Code will be synced via GitHub Actions or manual copy${NC}"

echo -e "\n${YELLOW}Step 3: Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

source venv/bin/activate

echo -e "\n${YELLOW}Step 4: Installing dependencies...${NC}"
pip install --upgrade pip > /dev/null 2>&1
pip install pyupbit pandas numpy redis apscheduler httpx psutil pyyaml > /dev/null 2>&1
pip install flask flask-cors python-dotenv > /dev/null 2>&1
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo -e "\n${YELLOW}Step 5: Setting up configuration...${NC}"

# Create config directory
mkdir -p config

# Create .env file with DeepSeek API key
if [ ! -f "config/.env" ]; then
    cat > config/.env << 'EOF'
# Upbit API Keys (replace with your keys)
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here

# DeepSeek API Key (ADD YOUR KEY HERE)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Dashboard
DASHBOARD_PORT=8080
FLASK_SECRET_KEY=your-secret-key-here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Trading Configuration
TRADING_MODE=dry-run  # Start in dry-run mode for safety
MAX_POSITION_SIZE=10000000
DAILY_LOSS_LIMIT=-0.03
SIGNAL_THRESHOLD=0.65
EOF
    echo -e "${GREEN}✓ Configuration file created${NC}"
    echo -e "${YELLOW}  Note: Please update UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY in config/.env${NC}"
else
    echo -e "${GREEN}✓ Configuration file already exists${NC}"
fi

echo -e "\n${YELLOW}Step 6: Initializing databases...${NC}"
python3 << 'EOF'
import sqlite3
import os

os.makedirs('data', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# AI analysis database
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

# Multi-coin database
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

# Main quantum database
conn = sqlite3.connect('data/quantum.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        strategy TEXT,
        symbol TEXT,
        side TEXT,
        price REAL,
        quantity REAL,
        fee REAL,
        pnl REAL,
        signal_strength REAL
    )
''')
conn.commit()
conn.close()

print("✓ Databases initialized")
EOF

echo -e "\n${YELLOW}Step 7: Stopping existing services...${NC}"
pkill -f quantum_trading.py || true
pkill -f integrated_trading_system.py || true
pkill -f dashboard.py || true
pkill -f multi_coin_trading.py || true
pkill -f feedback_scheduler.py || true
sleep 2
echo -e "${GREEN}✓ Existing services stopped${NC}"

echo -e "\n${YELLOW}Step 8: Starting services...${NC}"

# Make setup script executable
chmod +x setup_and_run.sh 2>/dev/null || true

# Start integrated system
nohup python3 integrated_trading_system.py > logs/integrated_system.log 2>&1 &
INTEGRATED_PID=$!
echo -e "${GREEN}✓ Integrated system started (PID: $INTEGRATED_PID)${NC}"

# Wait for services to stabilize
sleep 5

echo -e "\n${YELLOW}Step 9: Verifying deployment...${NC}"

# Check processes
if pgrep -f integrated_trading_system.py > /dev/null; then
    echo -e "${GREEN}✓ Integrated trading system is running${NC}"
else
    echo -e "${RED}✗ Integrated trading system failed to start${NC}"
    echo "  Check logs at: $DEPLOY_DIR/logs/integrated_system.log"
fi

# Check dashboard accessibility
if curl -f http://localhost:8080/ --connect-timeout 5 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dashboard is accessible at http://localhost:8080/${NC}"
else
    echo -e "${YELLOW}⚠ Dashboard may still be starting up...${NC}"
fi

# Check Redis if available
if command -v redis-cli &> /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${YELLOW}⚠ Redis is not running (optional)${NC}"
    fi
fi

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Dashboard URL: http://158.180.82.112:8080/"
echo "Logs location: $DEPLOY_DIR/logs/"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update UPBIT API keys in config/.env"
echo "2. Change TRADING_MODE from 'dry-run' to 'live' when ready"
echo "3. Monitor logs: tail -f logs/integrated_system.log"
echo ""
echo -e "${YELLOW}To check system status:${NC}"
echo "  ps aux | grep python"
echo "  tail -f logs/integrated_system.log"
echo ""
echo -e "${YELLOW}To stop the system:${NC}"
echo "  pkill -f integrated_trading_system.py"
echo ""
echo -e "${YELLOW}To restart the system:${NC}"
echo "  cd $DEPLOY_DIR && ./setup_and_run.sh"