#!/bin/bash

# Quantum Trading System Deployment Script
# This script will be executed on the Oracle server

set -e  # Exit on error

echo "======================================"
echo "🚀 Quantum Trading System Deployment"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Change to project directory
cd /opt/bit_auto_v2_250712 || {
    print_error "Project directory not found!"
    exit 1
}

print_status "Current directory: $(pwd)"

# Pull latest code
print_status "Pulling latest code from GitHub..."
git pull origin main || {
    print_warning "Git pull failed, continuing anyway..."
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install/Update dependencies
print_status "Installing dependencies..."
pip install -r requirements.txt || {
    print_warning "Some dependencies failed to install"
    # Try installing missing packages individually
    pip install pyupbit
    pip install redis
    pip install loguru
    pip install aiohttp
}

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p data logs

# Initialize database
print_status "Initializing database..."
python3 << EOF
import sqlite3
import os

# Create data directory if not exists
os.makedirs('data', exist_ok=True)

# Initialize database
conn = sqlite3.connect('data/quantum.db')
cursor = conn.cursor()

# Create tables
cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        strategy_name TEXT,
        symbol TEXT,
        side TEXT,
        price REAL,
        quantity REAL,
        fee REAL,
        pnl REAL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        strategy_name TEXT,
        action TEXT,
        strength REAL,
        price REAL,
        reason TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS metrics (
        timestamp DATETIME PRIMARY KEY,
        total_balance REAL,
        position_value REAL,
        daily_pnl REAL,
        win_rate REAL,
        sharpe_ratio REAL
    )
''')

conn.commit()
conn.close()
print("Database initialized successfully")
EOF

# Check if Redis is installed and running
print_status "Checking Redis..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        print_status "Redis is running"
    else
        print_warning "Redis is installed but not running"
        sudo systemctl start redis-server 2>/dev/null || print_warning "Could not start Redis"
    fi
else
    print_warning "Redis not installed. Installing..."
    sudo apt-get update && sudo apt-get install -y redis-server
    sudo systemctl start redis-server
fi

# Kill existing processes on ports 5000 and 8080
print_status "Checking for existing processes..."
sudo lsof -ti:8080 | xargs -r sudo kill -9 2>/dev/null || true
print_status "Port 8080 cleared"

# Start Quantum Trading System in test mode
print_status "Starting Quantum Trading System (DRY RUN mode)..."
nohup python3 quantum_trading.py --dry-run > logs/quantum_trading.log 2>&1 &
QUANTUM_PID=$!
echo "Quantum Trading PID: $QUANTUM_PID"

# Wait a moment for the trading system to initialize
sleep 5

# Start Dashboard
print_status "Starting Dashboard on port 8080..."
nohup python3 dashboard.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "Dashboard PID: $DASHBOARD_PID"

# Save PIDs for later management
echo $QUANTUM_PID > quantum_trading.pid
echo $DASHBOARD_PID > dashboard.pid

# Open firewall port 8080
print_status "Configuring firewall..."
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 5000 -j ACCEPT 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true

# Wait for services to start
sleep 5

# Check if services are running
print_status "Checking service status..."

if ps -p $QUANTUM_PID > /dev/null; then
    print_status "Quantum Trading System is running (PID: $QUANTUM_PID)"
else
    print_error "Quantum Trading System failed to start"
    tail -n 20 logs/quantum_trading.log
fi

if ps -p $DASHBOARD_PID > /dev/null; then
    print_status "Dashboard is running (PID: $DASHBOARD_PID)"
else
    print_error "Dashboard failed to start"
    tail -n 20 logs/dashboard.log
fi

# Test dashboard endpoint
print_status "Testing dashboard endpoint..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health | grep -q "200"; then
    print_status "Dashboard is responding on port 8080"
else
    print_warning "Dashboard may not be fully initialized yet"
fi

echo ""
echo "======================================"
echo "📊 Deployment Complete!"
echo "======================================"
echo ""
echo "Access points:"
echo "  Dashboard: http://158.180.82.112:8080/"
echo "  Health Check: http://158.180.82.112:8080/health"
echo ""
echo "Logs:"
echo "  Trading: logs/quantum_trading.log"
echo "  Dashboard: logs/dashboard.log"
echo ""
echo "To stop services:"
echo "  kill \$(cat quantum_trading.pid)"
echo "  kill \$(cat dashboard.pid)"
echo ""
echo "Note: System is running in DRY RUN mode (no real trades)"
echo "To enable real trading, restart without --dry-run flag"
echo "======================================"