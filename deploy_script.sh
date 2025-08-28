#!/bin/bash
set -e  # 오류 발생시 중단

echo "========================================="
echo "🚀 Starting Auto Deployment..."
echo "========================================="

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 프로젝트 디렉토리 확인 및 이동
PROJECT_DIR="/home/ubuntu/bit_auto_v2"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}Error: Project directory not found!${NC}"
    exit 1
fi
cd "$PROJECT_DIR"
echo -e "${GREEN}✓ Changed to project directory${NC}"

# 2. Git 상태 확인
echo "Checking Git status..."
git status --short

# 3. 기존 프로세스 중지
echo -e "${YELLOW}Stopping existing processes...${NC}"
pkill -f "dashboard.py" || echo "Dashboard not running"
pkill -f "integrated_trading_system.py" || echo "Trading system not running"
pkill -f "quantum_trading.py" || echo "Quantum trading not running"
pkill -f "multi_coin_trading.py" || echo "Multi-coin trading not running"
sleep 2

# 4. 최신 코드 가져오기
echo -e "${YELLOW}Pulling latest code from GitHub...${NC}"
git fetch origin
git reset --hard origin/main
git pull origin main
echo -e "${GREEN}✓ Code updated${NC}"

# 5. 가상환경 설정
echo -e "${YELLOW}Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 5.5 Redis 확인 (설치는 건너뜀 - sudo 권한 문제 방지)
echo -e "${YELLOW}Checking Redis...${NC}"
if command -v redis-server &> /dev/null; then
    echo -e "${GREEN}✓ Redis is installed${NC}"
    # Redis 실행 상태만 확인
    if pgrep -x "redis-server" > /dev/null; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${YELLOW}⚠️ Redis not running (will work without it)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ Redis not installed (will work without it)${NC}"
fi

# 6. 의존성 설치
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet || {
    # requirements.txt가 없으면 개별 설치
    pip install --quiet \
        pyupbit \
        pandas \
        numpy \
        redis \
        apscheduler \
        httpx \
        psutil \
        pyyaml \
        flask \
        flask-cors \
        python-dotenv \
        scikit-learn \
        ta \
        pytz
}
echo -e "${GREEN}✓ Dependencies installed${NC}"

# 7. 필요한 디렉토리 생성
mkdir -p data logs config
echo -e "${GREEN}✓ Directories created${NC}"

# 8. 데이터베이스 초기화
echo -e "${YELLOW}Initializing databases...${NC}"
python3 << 'EOF'
import sqlite3
import os

# 데이터베이스 파일 경로
db_files = {
    'data/quantum.db': [
        '''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            strategy TEXT, symbol TEXT, side TEXT,
            price REAL, quantity REAL, fee REAL,
            pnl REAL, signal_strength REAL
        )'''
    ],
    'data/ai_analysis.db': [
        '''CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            type TEXT, analysis TEXT,
            implemented BOOLEAN DEFAULT FALSE
        )'''
    ],
    'data/multi_coin.db': [
        '''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            coin TEXT, strategy TEXT, side TEXT,
            price REAL, quantity REAL, amount REAL,
            fee REAL, pnl REAL, signal_strength REAL,
            market_conditions TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS positions (
            coin TEXT PRIMARY KEY, quantity REAL,
            avg_price REAL, current_value REAL,
            unrealized_pnl REAL, last_updated DATETIME
        )'''
    ],
    'data/backtest_results.db': [
        '''CREATE TABLE IF NOT EXISTS backtest_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            strategy TEXT, symbol TEXT,
            period_start DATETIME, period_end DATETIME,
            initial_capital REAL, final_capital REAL,
            total_trades INTEGER, win_rate REAL,
            total_pnl REAL, max_drawdown REAL,
            sharpe_ratio REAL
        )''',
        '''CREATE TABLE IF NOT EXISTS backtest_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            timestamp DATETIME, side TEXT,
            price REAL, quantity REAL,
            commission REAL, slippage REAL,
            pnl REAL,
            FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
        )'''
    ],
    'data/optimization_results.db': [
        '''CREATE TABLE IF NOT EXISTS optimization_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            strategy TEXT, method TEXT, symbol TEXT,
            days INTEGER, best_roi REAL,
            best_fitness REAL, best_params TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS optimization_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            params TEXT, roi REAL,
            sharpe_ratio REAL, max_drawdown REAL,
            win_rate REAL, total_trades INTEGER,
            fitness REAL,
            FOREIGN KEY (session_id) REFERENCES optimization_sessions(id)
        )'''
    ]
}

# 각 데이터베이스 생성 및 테이블 초기화
for db_file, tables in db_files.items():
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        for table_sql in tables:
            cursor.execute(table_sql)
        conn.commit()
        conn.close()
        print(f"✓ {db_file} initialized")
    except Exception as e:
        print(f"✗ Error initializing {db_file}: {e}")

print("✓ All databases initialized")
EOF

echo -e "${GREEN}✓ Databases initialized${NC}"

# 9. 환경 변수 확인
if [ ! -f "config/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    if [ -f "config/secrets.env.example" ]; then
        echo "You may need to copy and configure config/secrets.env.example to config/.env"
    fi
fi

# 10. AI 분석 데이터 초기화
echo -e "${YELLOW}Initializing AI analysis data...${NC}"
if [ -f "init_ai_analysis.py" ]; then
    python3 init_ai_analysis.py > logs/ai_init.log 2>&1
    echo -e "${GREEN}✓ AI analysis data initialized${NC}"
else
    echo -e "${YELLOW}⚠️ AI analysis script not found${NC}"
fi

# 11. 대시보드 시작
echo -e "${YELLOW}Starting dashboard...${NC}"
export DASHBOARD_PORT=8080
nohup python3 dashboard.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo $DASHBOARD_PID > dashboard.pid
sleep 3
if ps -p $DASHBOARD_PID > /dev/null; then
    echo -e "${GREEN}✓ Dashboard started with PID: $DASHBOARD_PID on port 8080${NC}"
else
    echo -e "${RED}❌ Dashboard failed to start. Check logs/dashboard.log${NC}"
    tail -10 logs/dashboard.log
fi

# 11-1. AI 분석 스케줄러 시작
echo -e "${YELLOW}Starting AI analysis scheduler...${NC}"
if [ -f "ai_analysis_scheduler.py" ]; then
    # 기존 스케줄러 중지
    pkill -f "ai_analysis_scheduler.py" || true
    sleep 1
    
    # 새로 시작
    nohup python3 ai_analysis_scheduler.py > logs/ai_scheduler.log 2>&1 &
    SCHEDULER_PID=$!
    echo $SCHEDULER_PID > ai_scheduler.pid
    echo -e "${GREEN}✓ AI scheduler started with PID: $SCHEDULER_PID${NC}"
else
    echo -e "${YELLOW}⚠️ AI scheduler not found${NC}"
fi

# 12. 거래 시스템 시작 (config 파일 확인 후)
if [ -f "config/config.yaml" ]; then
    TRADING_MODE=$(python3 -c "import yaml; config=yaml.safe_load(open('config/config.yaml')); print(config.get('trading', {}).get('mode', 'dry_run'))")
    echo -e "${YELLOW}Trading mode: $TRADING_MODE${NC}"
    
    if [ "$TRADING_MODE" != "off" ]; then
        echo -e "${YELLOW}Starting trading systems in $TRADING_MODE mode...${NC}"
        
        # Integrated Trading System (이미 실행중일 수 있음)
        if [ -f "integrated_trading_system.py" ]; then
            if ! pgrep -f "integrated_trading_system.py" > /dev/null; then
                nohup python3 integrated_trading_system.py > logs/integrated_system.log 2>&1 &
                TRADING_PID=$!
                echo $TRADING_PID > trading_system.pid
                echo -e "${GREEN}✓ Integrated trading system started with PID: $TRADING_PID${NC}"
            else
                echo -e "${GREEN}✓ Integrated trading system already running${NC}"
            fi
        fi
        
        # Quantum Trading
        if [ -f "quantum_trading.py" ]; then
            pkill -f "quantum_trading.py" || true
            sleep 1
            
            # 먼저 필요한 모듈들이 설치되어 있는지 확인
            echo -e "${YELLOW}Checking Quantum Trading dependencies...${NC}"
            python3 -c "import redis" 2>/dev/null || pip3 install redis
            python3 -c "import sklearn" 2>/dev/null || pip3 install scikit-learn
            python3 -c "import pytz" 2>/dev/null || pip3 install pytz
            python3 -c "import ta" 2>/dev/null || pip3 install ta
            
            # strategies.py 파일이 있는지 확인
            if [ ! -f "strategies.py" ]; then
                echo -e "${RED}❌ strategies.py not found! Quantum trading cannot start.${NC}"
            else
                # Quantum Trading 시작 시도
                echo -e "${YELLOW}Starting Quantum Trading in $TRADING_MODE mode...${NC}"
                
                # 먼저 Python 문법 체크
                python3 -m py_compile quantum_trading.py 2>&1 || {
                    echo -e "${RED}❌ Quantum trading has syntax errors!${NC}"
                }
                
                # Quantum Trading 시작
                if [ "$TRADING_MODE" = "live" ]; then
                    nohup python3 quantum_trading.py > logs/quantum_trading.log 2>&1 &
                else
                    nohup python3 quantum_trading.py --dry-run > logs/quantum_trading.log 2>&1 &
                fi
                QT_PID=$!
                echo $QT_PID > quantum_trading.pid
                
                # 프로세스가 실제로 실행 중인지 확인 (5초 대기)
                sleep 5
                if ps -p $QT_PID > /dev/null; then
                    echo -e "${GREEN}✓ Quantum trading started with PID: $QT_PID${NC}"
                else
                    echo -e "${RED}❌ Quantum trading failed to start. Check logs/quantum_trading.log${NC}"
                    # 로그 마지막 20줄 출력
                    if [ -f "logs/quantum_trading.log" ]; then
                        echo -e "${YELLOW}Last 20 lines of log:${NC}"
                        tail -20 logs/quantum_trading.log
                    fi
                    
                    # Python import 테스트
                    echo -e "${YELLOW}Testing imports...${NC}"
                    python3 -c "import quantum_trading" 2>&1 | head -10
                fi
            fi
        else
            echo -e "${YELLOW}⚠️ quantum_trading.py not found${NC}"
        fi
        
        # Multi-Coin Trading
        if [ -f "multi_coin_trading.py" ]; then
            pkill -f "multi_coin_trading.py" || true
            sleep 1
            nohup python3 multi_coin_trading.py > logs/multi_coin.log 2>&1 &
            MC_PID=$!
            echo $MC_PID > multi_coin.pid
            echo -e "${GREEN}✓ Multi-coin trading started with PID: $MC_PID${NC}"
        fi
        
        # AI Feedback Scheduler
        if [ -f "feedback_scheduler.py" ]; then
            pkill -f "feedback_scheduler.py" || true
            sleep 1
            nohup python3 feedback_scheduler.py > logs/feedback.log 2>&1 &
            FB_PID=$!
            echo $FB_PID > feedback.pid
            echo -e "${GREEN}✓ AI Feedback started with PID: $FB_PID${NC}"
        fi
    else
        echo -e "${YELLOW}Trading system is set to 'off' mode${NC}"
    fi
else
    echo -e "${YELLOW}Warning: config.yaml not found${NC}"
fi

# 13. 헬스 체크
echo -e "${YELLOW}Performing health check...${NC}"
sleep 5

# 대시보드 체크
if ps -p $DASHBOARD_PID > /dev/null; then
    echo -e "${GREEN}✓ Dashboard is running${NC}"
    
    # HTTP 체크
    for i in {1..10}; do
        if curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Dashboard HTTP server is responsive${NC}"
            break
        else
            echo "Waiting for dashboard to be ready... ($i/10)"
            sleep 2
        fi
    done
else
    echo -e "${RED}✗ Dashboard failed to start${NC}"
    tail -n 20 logs/dashboard.log
fi

# 프로세스 리스트
echo -e "\n${YELLOW}Active processes:${NC}"
ps aux | grep -E "dashboard|trading|quantum|multi_coin" | grep -v grep || echo "No trading processes found"

# 14. 최종 상태
echo ""
echo "========================================="
if [ -f "dashboard.pid" ] && ps -p $(cat dashboard.pid) > /dev/null; then
    echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
    echo -e "${GREEN}Dashboard: http://$(hostname -I | awk '{print $1}'):8080${NC}"
else
    echo -e "${YELLOW}⚠️ Deployment completed with warnings${NC}"
    echo "Please check logs for details:"
    echo "  tail -f logs/dashboard.log"
    echo "  tail -f logs/integrated_system.log"
fi
echo "========================================="
