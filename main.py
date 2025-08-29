#!/usr/bin/env python3
"""
Bitcoin Auto Trading System v2.0
메인 실행 스크립트
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.trading_engine import TradingEngine
from web.app import app
from config.config_manager import config_manager
from data.database import db
import threading
import time

def setup_logging():
    """로깅 설정"""
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', 'logs/trading.log')
    
    # 로그 디렉토리 생성
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_environment():
    """환경 설정 확인"""
    required_vars = ['UPBIT_ACCESS_KEY', 'UPBIT_SECRET_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ 필수 환경 변수가 설정되지 않았습니다:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n.env 파일을 생성하고 API 키를 설정하세요.")
        print("예시: .env.example 파일을 참고하세요.")
        return False
    
    return True

def run_trading_engine():
    """트레이딩 엔진 실행"""
    try:
        print("🤖 트레이딩 엔진 시작 중...")
        engine = TradingEngine()
        engine.start()
    except KeyboardInterrupt:
        print("\n⏹️  트레이딩 엔진 종료됨")
    except Exception as e:
        print(f"❌ 트레이딩 엔진 오류: {e}")
        logging.error(f"Trading engine error: {e}")

def run_web_server():
    """웹 서버 실행"""
    try:
        # 자동 거래 스케줄러 시작
        from core.auto_trader import auto_trader
        if config_manager.is_system_enabled():
            print("🤖 자동 거래 스케줄러 시작 중...")
            auto_trader.start()
            print("✅ 자동 거래 스케줄러 시작 완료")
        
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5000))
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        
        print(f"🌐 웹 서버 시작 중... http://{host}:{port}")
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except Exception as e:
        print(f"❌ 웹 서버 오류: {e}")
        logging.error(f"Web server error: {e}")

def init_database():
    """데이터베이스 초기화"""
    try:
        print("💾 데이터베이스 초기화 중...")
        db.init_database()
        print("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 오류: {e}")
        return False
    return True

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='Bitcoin Auto Trading System v2.0')
    parser.add_argument('--mode', choices=['trading', 'web', 'both'], default='both',
                       help='실행 모드 선택 (기본값: both)')
    parser.add_argument('--init-db', action='store_true',
                       help='데이터베이스 초기화만 실행')
    parser.add_argument('--paper-trading', action='store_true',
                       help='모의거래 모드로 강제 실행')
    parser.add_argument('--config-check', action='store_true',
                       help='설정 파일 확인만 실행')
    
    args = parser.parse_args()
    
    # 로깅 설정
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("=" * 50)
    print("🪙  Bitcoin Auto Trading System v2.0")
    print("=" * 50)
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 환경 변수 확인
    if not check_environment():
        print("📝 필수 키가 없어 모의거래 모드로 전환합니다.")
        config_manager.set_mode('paper_trading')
    
    print("✅ 환경 변수 확인 완료")
    
    # 데이터베이스 초기화
    if not init_database():
        return 1
    
    # 데이터베이스 초기화만 실행
    if args.init_db:
        print("✅ 데이터베이스 초기화 완료 - 프로그램 종료")
        return 0
    
    # 설정 확인만 실행
    if args.config_check:
        print("📋 현재 설정:")
        print(f"   시스템 활성화: {config_manager.is_system_enabled()}")
        print(f"   자동거래 활성화: {config_manager.is_trading_enabled()}")
        print(f"   최대 거래 금액: {config_manager.get_trade_amount_limit():,} KRW")
        print(f"   긴급 정지 손실: {config_manager.get_emergency_stop_loss():,} KRW")
        print(f"   활성 전략: {config_manager.get_active_strategies()}")
        return 0
    
    # 모의거래 모드 강제 설정
    if args.paper_trading:
        config_manager.set_config('system.mode', 'paper_trading')
        print("📝 모의거래 모드로 설정됨")
    
    # 실행 모드에 따른 처리
    try:
        if args.mode == 'trading':
            # 트레이딩 엔진만 실행
            run_trading_engine()
            
        elif args.mode == 'web':
            # 웹 서버만 실행
            run_web_server()
            
        else:  # both
            # 트레이딩 엔진과 웹 서버 동시 실행
            print("🚀 트레이딩 엔진과 웹 서버를 동시에 시작합니다...")
            
            # 트레이딩 엔진을 별도 스레드에서 실행
            trading_thread = threading.Thread(target=run_trading_engine, daemon=True)
            trading_thread.start()
            
            # 잠시 대기 후 웹 서버 실행
            time.sleep(2)
            run_web_server()
            
    except KeyboardInterrupt:
        print("\n👋 프로그램 종료 중...")
        logger.info("Program terminated by user")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        logger.error(f"Unexpected error: {e}")
        return 1
    
    print("✅ 프로그램 종료 완료")
    return 0

if __name__ == "__main__":
    sys.exit(main())