"""
AI 분석 스케줄러
주기적으로 AI 시장 분석 및 거래 조언을 실행하는 스케줄러
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

from .ai_advisor import ai_advisor, now_kst
from config.config_manager import config_manager


class AIScheduler:
    """AI 분석 스케줄러"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_execution: Optional[datetime] = None
        
    def start(self):
        """스케줄러 시작"""
        if self._thread and self._thread.is_alive():
            self.logger.warning("AI 스케줄러가 이미 실행 중입니다")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.logger.info("AI 분석 스케줄러 시작됨")
        
    def stop(self):
        """스케줄러 중지"""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=5)
            self.logger.info("AI 분석 스케줄러 중지됨")
            
    def is_running(self) -> bool:
        """스케줄러 실행 상태 확인"""
        return self._thread and self._thread.is_alive()
        
    def get_last_execution(self) -> Optional[datetime]:
        """마지막 실행 시간 반환"""
        return self._last_execution
        
    def execute_now(self) -> bool:
        """즉시 AI 분석 실행"""
        try:
            self.logger.info("수동 AI 분석 실행 시작")
            
            # 시장 분석 실행
            market_analysis = ai_advisor.analyze_market(force_refresh=True)
            self.logger.info(f"시장 분석 완료 (신뢰도: {market_analysis.confidence:.1%})")
            
            # 거래 조언 실행
            trading_advice = ai_advisor.get_trading_advice(force_refresh=True)
            self.logger.info(f"거래 조언 완료 (신뢰도: {trading_advice.confidence:.1%})")
            
            # 실행 시간 기록
            self._last_execution = now_kst()
            self._update_last_execution_config()
            
            return True
            
        except Exception as e:
            self.logger.error(f"AI 분석 실행 중 오류: {e}")
            return False
            
    def _run(self):
        """스케줄러 메인 루프"""
        self.logger.info("AI 분석 스케줄러 루프 시작")
        
        while not self._stop_event.is_set():
            try:
                # 설정 확인
                ai_config = config_manager.get_config('trading.ai_analysis') or {}
                if not ai_config.get('enabled', False):
                    time.sleep(30)  # 30초마다 설정 확인
                    continue
                    
                interval_minutes = ai_config.get('interval_minutes', 30)
                
                # 실행 시간 체크
                if self._should_execute(interval_minutes):
                    self.logger.info("주기적 AI 분석 실행")
                    self.execute_now()
                    
                # 1분마다 체크
                time.sleep(60)
                
            except Exception as e:
                self.logger.error(f"AI 스케줄러 오류: {e}")
                time.sleep(60)
                
    def _should_execute(self, interval_minutes: int) -> bool:
        """실행 여부 판단"""
        if self._last_execution is None:
            return True
            
        next_execution = self._last_execution + timedelta(minutes=interval_minutes)
        return now_kst() >= next_execution
        
    def _update_last_execution_config(self):
        """설정 파일에 마지막 실행 시간 업데이트"""
        try:
            config_manager.update_config({
                'trading.ai_analysis.last_execution': self._last_execution.isoformat()
            })
        except Exception as e:
            self.logger.error(f"설정 업데이트 실패: {e}")


# 전역 스케줄러 인스턴스
ai_scheduler = AIScheduler()
