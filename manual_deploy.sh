#!/bin/bash
# Manual deployment script - Run this locally to deploy to server

echo "======================================"
echo "📦 Manual Deployment Script"
echo "======================================"
echo ""

# Configuration
SERVER_IP="158.180.82.112"
SERVER_USER="ubuntu"
DEPLOY_DIR="/home/ubuntu/bit_auto_v2"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}This script will help you deploy manually when GitHub Actions fails${NC}"
echo ""

# Check if SSH key exists
echo -e "${YELLOW}Step 1: SSH Key Setup${NC}"
echo "Please ensure your SSH key is set up correctly."
echo "If you can SSH to the server manually, this script should work."
echo ""

# Create deployment package
echo -e "${YELLOW}Step 2: Creating deployment package...${NC}"
tar -czf deploy_package.tar.gz \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    --exclude='playwright-*' \
    --exclude='test-results' \
    --exclude='*.png' \
    --exclude='*.log' \
    *.py \
    *.sh \
    *.md \
    config/ \
    2>/dev/null || echo "Some files excluded"

echo -e "${GREEN}✓ Package created${NC}"

# Provide manual deployment instructions
echo ""
echo -e "${YELLOW}Step 3: Manual Deployment Instructions${NC}"
echo "=========================================="
echo ""
echo "1. Copy the deployment package to server:"
echo -e "${GREEN}scp deploy_package.tar.gz $SERVER_USER@$SERVER_IP:/tmp/${NC}"
echo ""
echo "2. SSH to the server:"
echo -e "${GREEN}ssh $SERVER_USER@$SERVER_IP${NC}"
echo ""
echo "3. Once connected, run these commands:"
cat << 'EOF'

# Navigate to deployment directory
cd /home/ubuntu
mkdir -p bit_auto_v2
cd bit_auto_v2

# Extract the package
tar -xzf /tmp/deploy_package.tar.gz

# Install Python dependencies
pip3 install --user pyupbit pandas numpy redis apscheduler httpx psutil pyyaml flask flask-cors python-dotenv

# Create necessary directories
mkdir -p logs data config

# Create .env file (IMPORTANT: Add your API keys)
cat > config/.env << 'ENVFILE'
# Upbit API Keys
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here

# DeepSeek API Key (IMPORTANT: Add your key here)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Dashboard
DASHBOARD_PORT=8080
FLASK_SECRET_KEY=quantum-trading-secret-$(date +%s)

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Trading Configuration
TRADING_MODE=dry-run
MAX_POSITION_SIZE=10000000
DAILY_LOSS_LIMIT=-0.03
SIGNAL_THRESHOLD=0.65
ENVFILE

# Initialize databases
python3 << 'PYEOF'
import sqlite3
import os

os.makedirs('data', exist_ok=True)

# Create quantum.db
conn = sqlite3.connect('data/quantum.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
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
)''')
conn.commit()
conn.close()

# Create ai_analysis.db
conn = sqlite3.connect('data/ai_analysis.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT,
    analysis TEXT,
    implemented BOOLEAN DEFAULT FALSE
)''')
conn.commit()
conn.close()

# Create multi_coin.db
conn = sqlite3.connect('data/multi_coin.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
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
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS positions (
    coin TEXT PRIMARY KEY,
    quantity REAL,
    avg_price REAL,
    current_value REAL,
    unrealized_pnl REAL,
    last_updated DATETIME
)''')
conn.commit()
conn.close()

print("✓ Databases initialized")
PYEOF

# Stop existing services
pkill -f dashboard.py || true
pkill -f integrated_trading_system.py || true
pkill -f quantum_trading.py || true

# Start dashboard
nohup python3 dashboard.py > logs/dashboard.log 2>&1 &
echo "✓ Dashboard started"

# Check status
sleep 3
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Dashboard is running at http://158.180.82.112:8080/"
else
    echo "⚠️ Dashboard may not be running, check logs/dashboard.log"
fi

# Optional: Start full trading system (remove # to enable)
# nohup python3 integrated_trading_system.py > logs/integrated_system.log 2>&1 &

EOF

echo ""
echo -e "${YELLOW}Step 4: Important Notes${NC}"
echo "=========================================="
echo ""
echo -e "${RED}CRITICAL: You MUST add your API keys to config/.env:${NC}"
echo "  - UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY"
echo "  - DEEPSEEK_API_KEY (your new API key)"
echo ""
echo -e "${YELLOW}To start the trading system after setup:${NC}"
echo "  ./setup_and_run.sh"
echo ""
echo -e "${YELLOW}To check logs:${NC}"
echo "  tail -f logs/dashboard.log"
echo "  tail -f logs/integrated_system.log"
echo ""
echo -e "${GREEN}Deployment package ready: deploy_package.tar.gz${NC}"