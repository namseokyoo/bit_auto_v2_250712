#!/usr/bin/env python3
"""
모든 거래 프로세스 중지 스크립트
"""

import psutil
import logging
import signal
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def stop_process(script_name, display_name):
    """프로세스 중지"""
    found = False
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if script_name in cmdline:
                found = True
                pid = proc.info['pid']
                
                # SIGTERM 신호 전송
                proc.send_signal(signal.SIGTERM)
                
                # 종료 대기 (최대 5초)
                for _ in range(5):
                    if not proc.is_running():
                        logger.info(f"✅ {display_name} 중지됨 (PID: {pid})")
                        return True
                    time.sleep(1)
                
                # 강제 종료
                proc.kill()
                logger.warning(f"⚠️ {display_name} 강제 종료됨 (PID: {pid})")
                return True
                
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"프로세스 중지 오류: {e}")
    
    if not found:
        logger.info(f"ℹ️ {display_name} 실행중이 아님")
    
    return not found

def main():
    """메인 함수"""
    print("=" * 60)
    print("🛑 Quantum Trading System - 프로세스 중지")
    print("=" * 60)
    
    # 프로세스 목록
    processes = [
        ('integrated_trading_system.py', 'Integrated System'),
        ('quantum_trading.py', 'Quantum Trading'),
        ('multi_coin_trading.py', 'Multi-Coin Trading'),
        ('feedback_scheduler.py', 'AI Feedback'),
        ('ai_analysis_scheduler.py', 'AI Analysis Scheduler'),
        ('dashboard.py', 'Dashboard')
    ]
    
    print("\n프로세스 중지중...")
    print("-" * 40)
    
    stopped_count = 0
    for script, name in processes:
        if stop_process(script, name):
            stopped_count += 1
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print(f"완료: {stopped_count}개 프로세스 처리됨")
    print("=" * 60)

if __name__ == "__main__":
    main()