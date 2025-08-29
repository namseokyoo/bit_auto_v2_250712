#!/usr/bin/env python3
"""
통합 트레이딩 시스템
AI 피드백 + 멀티 코인 + 기존 전략 통합
"""

import asyncio
import sys
import os
import signal
import logging
from datetime import datetime
import multiprocessing as mp
from typing import Dict

# 모듈 임포트
from multi_coin_trading import MultiCoinTrader
from ai_analyzer import FeedbackLoop
from feedback_scheduler import FeedbackScheduler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/integrated_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IntegratedTradingSystem:
    """통합 트레이딩 시스템"""
    
    def __init__(self):
        self.processes = {}
        self.is_running = False
        
        # AI 피드백 시스템
        self.feedback_scheduler = FeedbackScheduler()
        
        # 멀티 코인 트레이더
        self.multi_coin_trader = MultiCoinTrader()
        
    async def start(self):
        """시스템 시작"""
        
        logger.info("=" * 50)
        logger.info("🚀 Integrated Trading System Starting...")
        logger.info("=" * 50)
        
        self.is_running = True
        
        try:
            # 1. AI 피드백 스케줄러 시작
            logger.info("Starting AI feedback scheduler...")
            self.feedback_scheduler.start()
            
            # 2. 멀티 코인 트레이딩 시작
            logger.info("Starting multi-coin trading...")
            trading_task = asyncio.create_task(
                self.multi_coin_trader.run()
            )
            
            # 3. 모니터링 루프
            monitoring_task = asyncio.create_task(
                self.monitoring_loop()
            )
            
            # 4. 대시보드 서버 시작 (별도 프로세스)
            self.start_dashboard()
            
            # 실행
            await asyncio.gather(
                trading_task,
                monitoring_task
            )
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            await self.shutdown()
        except Exception as e:
            logger.error(f"System error: {e}")
            await self.shutdown()
    
    async def monitoring_loop(self):
        """시스템 모니터링 루프"""
        
        while self.is_running:
            try:
                # 시스템 상태 체크
                status = await self.check_system_health()
                
                # 상태 로깅
                if status['healthy']:
                    logger.debug(f"System healthy - CPU: {status['cpu']:.1f}%, "
                               f"Memory: {status['memory']:.1f}%")
                else:
                    logger.warning(f"System issue detected: {status['issues']}")
                
                # 30초 대기
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def check_system_health(self) -> Dict:
        """시스템 건강 상태 체크"""
        
        import psutil
        
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        issues = []
        
        if cpu_percent > 80:
            issues.append(f"High CPU usage: {cpu_percent}%")
        
        if memory_percent > 80:
            issues.append(f"High memory usage: {memory_percent}%")
        
        if disk_percent > 90:
            issues.append(f"Low disk space: {disk_percent}%")
        
        return {
            'healthy': len(issues) == 0,
            'cpu': cpu_percent,
            'memory': memory_percent,
            'disk': disk_percent,
            'issues': issues,
            'timestamp': datetime.now()
        }
    
    def start_dashboard(self):
        """대시보드 서버 시작"""
        
        try:
            # dashboard.py를 별도 프로세스로 실행
            import subprocess
            
            dashboard_process = subprocess.Popen(
                [sys.executable, 'dashboard.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes['dashboard'] = dashboard_process
            logger.info(f"Dashboard started with PID: {dashboard_process.pid}")
            
        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}")
    
    async def shutdown(self):
        """시스템 종료"""
        
        logger.info("Shutting down integrated trading system...")
        
        self.is_running = False
        
        # 피드백 스케줄러 중지
        self.feedback_scheduler.stop()
        
        # 프로세스 종료
        for name, process in self.processes.items():
            if process and process.poll() is None:
                logger.info(f"Terminating {name} process...")
                process.terminate()
                process.wait(timeout=5)
        
        logger.info("Shutdown complete")


async def main():
    """메인 실행 함수"""
    
    system = IntegratedTradingSystem()
    
    # 시그널 핸들러 설정
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(system.shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 시스템 실행
    await system.start()


if __name__ == "__main__":
    # 이벤트 루프 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("System terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)