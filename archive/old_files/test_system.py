#!/usr/bin/env python3
"""
시스템 테스트 스크립트
모든 컴포넌트가 제대로 작동하는지 확인
"""

import os
import sys
import sqlite3
import importlib
from datetime import datetime

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def print_status(status, message):
    if status:
        print(f"{GREEN}✓{NC} {message}")
    else:
        print(f"{RED}✗{NC} {message}")

def test_imports():
    """필수 모듈 임포트 테스트"""
    print(f"\n{YELLOW}=== Testing Imports ==={NC}")
    
    modules = {
        'pyupbit': 'Upbit API',
        'pandas': 'Data processing',
        'numpy': 'Numerical computing',
        'flask': 'Web framework',
        'redis': 'Redis client',
        'apscheduler': 'Task scheduling',
        'httpx': 'HTTP client',
        'yaml': 'YAML parser',
        'psutil': 'System monitoring'
    }
    
    results = {}
    for module, description in modules.items():
        try:
            importlib.import_module(module)
            print_status(True, f"{module} ({description})")
            results[module] = True
        except ImportError:
            print_status(False, f"{module} ({description}) - Run: pip install {module}")
            results[module] = False
    
    return all(results.values())

def test_project_files():
    """프로젝트 파일 존재 확인"""
    print(f"\n{YELLOW}=== Testing Project Files ==={NC}")
    
    files = [
        'quantum_trading.py',
        'dashboard.py',
        'ai_analyzer.py',
        'feedback_scheduler.py',
        'multi_coin_trading.py',
        'integrated_trading_system.py',
        'setup_and_run.sh',
        'config/config.yaml'
    ]
    
    results = {}
    for file in files:
        exists = os.path.exists(file)
        print_status(exists, file)
        results[file] = exists
    
    return all(results.values())

def test_databases():
    """데이터베이스 초기화 테스트"""
    print(f"\n{YELLOW}=== Testing Databases ==={NC}")
    
    os.makedirs('data', exist_ok=True)
    
    databases = {
        'data/quantum.db': [
            '''CREATE TABLE IF NOT EXISTS trades (
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
            )'''
        ],
        'data/ai_analysis.db': [
            '''CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                type TEXT,
                analysis TEXT,
                implemented BOOLEAN DEFAULT FALSE
            )'''
        ],
        'data/multi_coin.db': [
            '''CREATE TABLE IF NOT EXISTS trades (
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
            )''',
            '''CREATE TABLE IF NOT EXISTS positions (
                coin TEXT PRIMARY KEY,
                quantity REAL,
                avg_price REAL,
                current_value REAL,
                unrealized_pnl REAL,
                last_updated DATETIME
            )'''
        ]
    }
    
    results = {}
    for db_path, tables in databases.items():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for table_sql in tables:
                cursor.execute(table_sql)
            conn.commit()
            conn.close()
            print_status(True, f"{db_path} initialized")
            results[db_path] = True
        except Exception as e:
            print_status(False, f"{db_path} - Error: {e}")
            results[db_path] = False
    
    return all(results.values())

def test_environment():
    """환경 변수 설정 확인"""
    print(f"\n{YELLOW}=== Testing Environment Variables ==={NC}")
    
    from dotenv import load_dotenv
    
    # Try to load .env file
    env_file = 'config/.env'
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print_status(True, f".env file found at {env_file}")
    else:
        print_status(False, f".env file not found at {env_file}")
        print(f"  {YELLOW}Creating template .env file...{NC}")
        
        os.makedirs('config', exist_ok=True)
        with open(env_file, 'w') as f:
            f.write("""# Upbit API Keys
UPBIT_ACCESS_KEY=your_access_key_here
UPBIT_SECRET_KEY=your_secret_key_here

# DeepSeek API Key (IMPORTANT: Add your key here)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Dashboard
DASHBOARD_PORT=8080
FLASK_SECRET_KEY=quantum-trading-secret

# Redis (optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Trading Configuration
TRADING_MODE=dry-run
MAX_POSITION_SIZE=10000000
DAILY_LOSS_LIMIT=-0.03
SIGNAL_THRESHOLD=0.65
""")
        print_status(True, "Template .env file created")
    
    # Check environment variables
    env_vars = {
        'DEEPSEEK_API_KEY': 'DeepSeek API',
        'UPBIT_ACCESS_KEY': 'Upbit Access Key',
        'UPBIT_SECRET_KEY': 'Upbit Secret Key',
        'DASHBOARD_PORT': 'Dashboard Port'
    }
    
    configured = True
    for var, description in env_vars.items():
        value = os.getenv(var)
        is_set = value and len(value) > 10 and not value.startswith('your_')
        
        if var == 'DASHBOARD_PORT':
            is_set = value is not None
        
        print_status(is_set, f"{description} ({var})")
        
        if not is_set and var in ['DEEPSEEK_API_KEY', 'UPBIT_ACCESS_KEY', 'UPBIT_SECRET_KEY']:
            configured = False
    
    return configured

def test_redis():
    """Redis 연결 테스트"""
    print(f"\n{YELLOW}=== Testing Redis Connection ==={NC}")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print_status(True, "Redis is running")
        return True
    except:
        print_status(False, "Redis is not running (optional)")
        return False

def test_dashboard():
    """대시보드 임포트 테스트"""
    print(f"\n{YELLOW}=== Testing Dashboard ==={NC}")
    
    try:
        # Test if dashboard can be imported
        import dashboard
        print_status(True, "Dashboard module can be imported")
        
        # Check if Flask app exists
        if hasattr(dashboard, 'app'):
            print_status(True, "Flask app is configured")
            return True
        else:
            print_status(False, "Flask app not found in dashboard")
            return False
    except Exception as e:
        print_status(False, f"Dashboard import failed: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print(f"{GREEN}{'='*50}{NC}")
    print(f"{GREEN}Quantum Trading System - Test Suite{NC}")
    print(f"{GREEN}{'='*50}{NC}")
    
    results = {
        'Imports': test_imports(),
        'Project Files': test_project_files(),
        'Databases': test_databases(),
        'Environment': test_environment(),
        'Redis': test_redis(),
        'Dashboard': test_dashboard()
    }
    
    # Summary
    print(f"\n{YELLOW}=== Test Summary ==={NC}")
    print(f"{YELLOW}{'='*50}{NC}")
    
    all_passed = True
    for test_name, passed in results.items():
        print_status(passed, test_name)
        if not passed and test_name not in ['Redis', 'Environment']:
            all_passed = False
    
    print(f"{YELLOW}{'='*50}{NC}")
    
    if all_passed:
        print(f"\n{GREEN}✅ System is ready to run!{NC}")
        print(f"\nNext steps:")
        print(f"1. Add your API keys to config/.env")
        print(f"2. Run: {GREEN}./setup_and_run.sh{NC}")
    else:
        print(f"\n{RED}⚠️ Some tests failed. Please fix the issues above.{NC}")
        
        if not results['Imports']:
            print(f"\n{YELLOW}To install missing packages:{NC}")
            print(f"pip install pyupbit pandas numpy redis apscheduler httpx psutil pyyaml flask flask-cors python-dotenv")
        
        if not results['Environment']:
            print(f"\n{YELLOW}To configure API keys:{NC}")
            print(f"1. Edit config/.env")
            print(f"2. Add your actual API keys")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())