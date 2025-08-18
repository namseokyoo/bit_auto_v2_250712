"""
자동 거래 스케줄러 - 서버에서 독립적으로 실행되는 거래 봇
Auto Trading Scheduler - Independent trading bot running on server
"""

import threading
import schedule
import time
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, Optional

from config.config_manager import config_manager
from core.signal_recorder import signal_recorder
from utils.error_logger import log_trade, log_system

class AutoTrader:
    """자동 거래 스케줄러"""
    
    def __init__(self):
        self.logger = logging.getLogger('AutoTrader')
        self.trading_engine = None
        self.scheduler_thread = None
        self.running = False
        self.kst = pytz.timezone('Asia/Seoul')
        
        # 마지막 실행 시간 추적
        self.last_execution_time = None
        self.next_execution_time = None
        
    def initialize(self):
        """거래 엔진 초기화"""
        try:
            # 순환 import 방지를 위해 여기서 import
            from core.trading_engine import TradingEngine
            self.trading_engine = TradingEngine(config_manager)
            self.logger.info("자동 거래 시스템 초기화 완료")
            return True
        except ImportError as e:
            self.logger.error(f"자동 거래 시스템 import 오류: {e}")
            self.logger.info("TradingEngine 없이 기본 모드로 실행")
            return False
        except Exception as e:
            self.logger.error(f"자동 거래 시스템 초기화 실패: {e}")
            return False
    
    def start(self):
        """자동 거래 시작"""
        if self.running:
            self.logger.warning("자동 거래가 이미 실행 중입니다")
            return False
        
        if not self.initialize():
            return False
        
        self.running = True
        
        # 스케줄 설정
        self._setup_schedule()
        
        # 백그라운드 스레드에서 스케줄러 실행
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("자동 거래 시스템 시작됨")
        log_system("자동 거래 시스템이 시작되었습니다")
        
        return True
    
    def stop(self):
        """자동 거래 정지"""
        if not self.running:
            self.logger.warning("자동 거래가 실행 중이 아닙니다")
            return False
        
        self.running = False
        
        # 스케줄 클리어
        schedule.clear()
        
        self.logger.info("자동 거래 시스템 정지됨")
        log_system("자동 거래 시스템이 정지되었습니다")
        
        return True
    
    def _setup_schedule(self):
        """스케줄 설정"""
        try:
            # 설정에서 거래 간격 가져오기
            trading_config = config_manager.get_trading_config()
            trade_interval_minutes = trading_config.get('trade_interval_minutes', 10)
            
            # 거래 간격에 따라 스케줄 설정
            schedule.every(trade_interval_minutes).minutes.do(self._execute_trading_cycle)
            
            # 다음 실행 시간 계산
            self._update_next_execution_time(trade_interval_minutes)
            
            self.logger.info(f"거래 스케줄 설정: {trade_interval_minutes}분마다 실행")
            
        except Exception as e:
            self.logger.error(f"스케줄 설정 오류: {e}")
    
    def _run_scheduler(self):
        """스케줄러 실행 루프"""
        while self.running:
            try:
                # 자동 거래가 활성화되어 있는지 확인
                if config_manager.is_trading_enabled():
                    schedule.run_pending()
                else:
                    # 비활성화 상태에서도 다음 실행 시간은 업데이트
                    if self.next_execution_time and datetime.now(self.kst) > self.next_execution_time:
                        trading_config = config_manager.get_trading_config()
                        trade_interval_minutes = trading_config.get('trade_interval_minutes', 10)
                        self._update_next_execution_time(trade_interval_minutes)
                
                time.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                self.logger.error(f"스케줄러 실행 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기
    
    def _execute_trading_cycle(self):
        """거래 사이클 실행"""
        try:
            # 자동 거래가 활성화되어 있는지 다시 확인
            if not config_manager.is_trading_enabled():
                self.logger.info("자동 거래가 비활성화되어 있어 실행을 건너뜁니다")
                return
            
            current_time = datetime.now(self.kst)
            self.logger.info(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S KST')}] 거래 사이클 시작")
            
            # 거래 엔진이 있는 경우만 실행
            if self.trading_engine:
                result = self.trading_engine.analyze_and_execute()
            else:
                self.logger.warning("거래 엔진이 초기화되지 않아 실행할 수 없습니다")
                result = None
            
            # 실행 시간 업데이트
            self.last_execution_time = current_time
            
            # 다음 실행 시간 업데이트
            trading_config = config_manager.get_trading_config()
            trade_interval_minutes = trading_config.get('trade_interval_minutes', 10)
            self._update_next_execution_time(trade_interval_minutes)
            
            # 결과 로깅
            if result and 'consolidated_signal' in result:
                signal = result['consolidated_signal']
                action = signal.get('action', 'hold')
                confidence = signal.get('confidence', 0)
                
                log_message = f"거래 사이클 완료 - 액션: {action}, 신뢰도: {confidence:.2f}"
                self.logger.info(log_message)
                log_system(log_message)
                
                # 실제 거래가 실행된 경우
                if 'execution' in result and result['execution'].get('success'):
                    execution = result['execution']
                    trade_message = f"거래 실행: {execution.get('action')} - 금액: {execution.get('amount', 0):,.0f} KRW"
                    self.logger.info(trade_message)
                    log_trade(trade_message)
            else:
                self.logger.info("거래 사이클 완료 - 신호 없음")
            
        except Exception as e:
            self.logger.error(f"거래 사이클 실행 오류: {e}")
            log_system(f"거래 사이클 오류: {e}")
    
    def _update_next_execution_time(self, interval_minutes: int):
        """다음 실행 시간 업데이트"""
        current_time = datetime.now(self.kst)
        self.next_execution_time = current_time + timedelta(minutes=interval_minutes)
        self.logger.debug(f"다음 실행 시간: {self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    
    def get_status(self) -> Dict:
        """현재 상태 조회"""
        return {
            'running': self.running,
            'last_execution': self.last_execution_time.strftime('%Y-%m-%d %H:%M:%S KST') if self.last_execution_time else None,
            'next_execution': self.next_execution_time.strftime('%Y-%m-%d %H:%M:%S KST') if self.next_execution_time else None,
            'auto_trading_enabled': config_manager.is_trading_enabled()
        }
    
    def force_execute(self):
        """강제 실행 (테스트용)"""
        if not self.running:
            self.logger.warning("자동 거래가 실행 중이 아닙니다")
            return False
        
        self.logger.info("강제 거래 사이클 실행")
        self._execute_trading_cycle()
        return True

# 싱글톤 인스턴스
auto_trader = AutoTrader()

# 애플리케이션 시작 시 자동 거래 시작
def start_auto_trading():
    """자동 거래 시작"""
    if config_manager.is_system_enabled():
        auto_trader.start()
        return True
    return False

def stop_auto_trading():
    """자동 거래 정지"""
    return auto_trader.stop()

def get_auto_trading_status():
    """자동 거래 상태 조회"""
    return auto_trader.get_status()