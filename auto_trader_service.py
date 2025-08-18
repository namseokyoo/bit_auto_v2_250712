#!/usr/bin/env python3
"""
자동 거래 봇 독립 실행 스크립트
웹 서버와 독립적으로 실행되는 자동 거래 서비스
"""

import os
import sys
import signal
import logging
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config_manager import config_manager
from core.auto_trader import AutoTrader
from data.database import db

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_trader.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('AutoTraderService')

class AutoTraderService:
    """자동 거래 서비스"""
    
    def __init__(self):
        self.trader = AutoTrader()
        self.running = False
        self.kst = pytz.timezone('Asia/Seoul')
        
    def start(self):
        """서비스 시작"""
        try:
            # 환경 변수 확인
            if not self._check_environment():
                logger.error("환경 변수가 설정되지 않았습니다.")
                return False
            
            # 데이터베이스 초기화
            logger.info("데이터베이스 초기화 중...")
            db.init_database()
            
            # 설정 로드 및 확인
            logger.info("설정 로드 중...")
            trading_config = config_manager.get_trading_config()
            
            logger.info("=" * 50)
            logger.info("🤖 자동 거래 봇 시작")
            logger.info("=" * 50)
            logger.info(f"시작 시간: {datetime.now(self.kst).strftime('%Y-%m-%d %H:%M:%S KST')}")
            logger.info(f"시스템 활성화: {config_manager.is_system_enabled()}")
            logger.info(f"자동 거래 활성화: {config_manager.is_trading_enabled()}")
            logger.info(f"거래 간격: {trading_config.get('trade_interval_minutes', 10)}분")
            logger.info(f"최대 거래 금액: {trading_config.get('max_trade_amount', 100000):,} KRW")
            
            # 시스템이 활성화되어 있지 않으면 종료
            if not config_manager.is_system_enabled():
                logger.warning("시스템이 비활성화되어 있습니다. 설정을 확인하세요.")
                return False
            
            # 자동 거래 시작
            self.running = True
            
            # AutoTrader 초기화 및 시작
            if not self.trader.initialize():
                logger.error("AutoTrader 초기화 실패")
                return False
            
            # 스케줄러 시작
            self.trader.running = True
            self.trader._setup_schedule()
            
            logger.info("✅ 자동 거래 봇이 성공적으로 시작되었습니다.")
            logger.info(f"다음 실행: {self.trader.next_execution_time.strftime('%Y-%m-%d %H:%M:%S KST') if self.trader.next_execution_time else 'N/A'}")
            
            # 메인 루프
            while self.running:
                try:
                    # 자동 거래가 활성화되어 있는지 주기적으로 확인
                    if config_manager.is_trading_enabled():
                        import schedule
                        schedule.run_pending()
                    else:
                        logger.debug("자동 거래가 비활성화 상태입니다.")
                    
                    # 10초마다 체크
                    time.sleep(10)
                    
                    # 설정 파일이 변경되었는지 확인 (옵션)
                    # self._check_config_changes()
                    
                except KeyboardInterrupt:
                    logger.info("사용자에 의해 중단됨")
                    break
                except Exception as e:
                    logger.error(f"메인 루프 오류: {e}")
                    time.sleep(60)  # 오류 시 1분 대기
            
            return True
            
        except Exception as e:
            logger.error(f"서비스 시작 오류: {e}")
            return False
    
    def stop(self):
        """서비스 정지"""
        logger.info("자동 거래 봇 정지 중...")
        self.running = False
        
        if self.trader.running:
            self.trader.stop()
        
        logger.info("✅ 자동 거래 봇이 정지되었습니다.")
    
    def _check_environment(self):
        """환경 변수 확인"""
        required_vars = ['UPBIT_ACCESS_KEY', 'UPBIT_SECRET_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"필수 환경 변수가 설정되지 않았습니다: {missing_vars}")
            return False
        
        return True
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"시그널 {signum} 수신")
        self.stop()
        sys.exit(0)

def main():
    """메인 함수"""
    service = AutoTraderService()
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, service._signal_handler)
    signal.signal(signal.SIGTERM, service._signal_handler)
    
    # 서비스 시작
    success = service.start()
    
    if not success:
        logger.error("자동 거래 봇 시작 실패")
        sys.exit(1)

if __name__ == "__main__":
    main()