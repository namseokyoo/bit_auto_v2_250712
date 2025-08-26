"""
AI 피드백 루프 자동 실행 스케줄러
매일 자정 분석, 주간 심층 분석
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from ai_analyzer import FeedbackLoop, DeepSeekAnalyzer
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/feedback_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

KST = pytz.timezone('Asia/Seoul')

class FeedbackScheduler:
    """피드백 루프 스케줄러"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=KST)
        self.feedback_loop = FeedbackLoop()
        self.analyzer = DeepSeekAnalyzer()
        self.is_running = False
        
    def setup_schedule(self):
        """스케줄 설정"""
        
        # 매일 자정 5분 - 일일 분석
        self.scheduler.add_job(
            self.run_daily_analysis,
            CronTrigger(hour=0, minute=5),
            id='daily_analysis',
            name='Daily Trading Analysis',
            misfire_grace_time=300
        )
        
        # 매주 일요일 자정 30분 - 주간 심층 분석
        self.scheduler.add_job(
            self.run_weekly_analysis,
            CronTrigger(day_of_week=6, hour=0, minute=30),
            id='weekly_analysis',
            name='Weekly Deep Analysis',
            misfire_grace_time=600
        )
        
        # 4시간마다 - 성능 체크 및 긴급 조정
        self.scheduler.add_job(
            self.run_performance_check,
            'interval',
            hours=4,
            id='performance_check',
            name='Performance Check',
            misfire_grace_time=60
        )
        
        # 30분마다 - 실시간 모니터링
        self.scheduler.add_job(
            self.run_realtime_monitoring,
            'interval',
            minutes=30,
            id='realtime_monitoring',
            name='Realtime Monitoring'
        )
        
        logger.info("Feedback scheduler configured")
        
    async def run_daily_analysis(self):
        """일일 분석 실행"""
        
        logger.info("Starting daily analysis...")
        
        try:
            # 피드백 루프 실행
            report = await self.feedback_loop.run_daily_analysis()
            
            # 알림 발송
            await self.send_notification(
                "일일 트레이딩 분석 완료",
                self._format_daily_report(report)
            )
            
            # 전략 재시작 (필요시)
            if report.get('adjustments', {}).get('confidence', 0) > 0.8:
                await self.restart_trading_with_new_params()
            
            logger.info("Daily analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Daily analysis failed: {e}")
            await self.send_notification(
                "일일 분석 실패",
                f"에러 발생: {str(e)}"
            )
    
    async def run_weekly_analysis(self):
        """주간 심층 분석"""
        
        logger.info("Starting weekly deep analysis...")
        
        try:
            # 주간 데이터 수집
            weekly_data = await self._collect_weekly_data()
            
            # 패턴 분석
            patterns = await self.analyzer.identify_patterns(weekly_data)
            
            # 새로운 전략 제안
            new_strategies = await self._propose_new_strategies(patterns)
            
            # 백테스팅
            backtest_results = await self._backtest_strategies(new_strategies)
            
            # 보고서 생성
            report = {
                'patterns': patterns,
                'new_strategies': new_strategies,
                'backtest_results': backtest_results,
                'recommendations': self._generate_recommendations(backtest_results)
            }
            
            # 알림 발송
            await self.send_notification(
                "주간 심층 분석 완료",
                self._format_weekly_report(report)
            )
            
            logger.info("Weekly analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Weekly analysis failed: {e}")
    
    async def run_performance_check(self):
        """성능 체크 및 긴급 조정"""
        
        try:
            # 최근 4시간 성과 체크
            performance = await self._check_recent_performance(hours=4)
            
            # 긴급 조정 필요 여부 판단
            if self._needs_emergency_adjustment(performance):
                logger.warning("Emergency adjustment needed!")
                
                # 긴급 조정 실행
                adjustments = await self._emergency_adjustment(performance)
                
                # 알림 발송
                await self.send_notification(
                    "⚠️ 긴급 전략 조정",
                    f"손실률 {performance['loss_rate']:.2f}% 감지\n조정사항: {adjustments}"
                )
                
                # 전략 재시작
                await self.restart_trading_with_new_params()
                
        except Exception as e:
            logger.error(f"Performance check failed: {e}")
    
    async def run_realtime_monitoring(self):
        """실시간 모니터링"""
        
        try:
            # 현재 상태 체크
            status = await self._get_system_status()
            
            # 이상 징후 감지
            anomalies = self._detect_anomalies(status)
            
            if anomalies:
                logger.warning(f"Anomalies detected: {anomalies}")
                
                # 경고 알림
                await self.send_notification(
                    "⚠️ 이상 징후 감지",
                    f"감지된 문제: {', '.join(anomalies)}"
                )
                
            # Redis에 상태 저장 (대시보드용)
            await self._save_monitoring_status(status)
            
        except Exception as e:
            logger.error(f"Realtime monitoring failed: {e}")
    
    async def _collect_weekly_data(self):
        """주간 데이터 수집"""
        
        import sqlite3
        conn = sqlite3.connect('data/quantum.db')
        cursor = conn.cursor()
        
        # 최근 7일 거래 데이터
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT * FROM trades
            WHERE DATE(timestamp) >= ?
            ORDER BY timestamp DESC
        """, (week_ago,))
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'timestamp': row[1],
                'strategy': row[2],
                'symbol': row[3],
                'side': row[4],
                'price': row[5],
                'quantity': row[6],
                'fee': row[7],
                'pnl': row[8],
                'signal_strength': row[9]
            })
        
        conn.close()
        return trades
    
    async def _propose_new_strategies(self, patterns):
        """패턴 기반 새 전략 제안"""
        
        prompt = f"""
        Based on the identified patterns, propose new trading strategies:
        
        Patterns:
        {json.dumps(patterns, indent=2)}
        
        Suggest 3 new strategies with specific parameters.
        """
        
        response = await self.analyzer._call_api(prompt)
        return self.analyzer._parse_json_response(response)
    
    async def _backtest_strategies(self, strategies):
        """전략 백테스팅"""
        
        # 간단한 백테스팅 로직
        results = {}
        
        for strategy_name, params in strategies.items():
            # 실제로는 복잡한 백테스팅 필요
            results[strategy_name] = {
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0
            }
        
        return results
    
    def _generate_recommendations(self, backtest_results):
        """백테스트 결과 기반 추천"""
        
        recommendations = []
        
        for strategy, results in backtest_results.items():
            if results['sharpe_ratio'] > 1.5:
                recommendations.append(f"Implement {strategy}")
            elif results['sharpe_ratio'] > 1.0:
                recommendations.append(f"Test {strategy} with paper trading")
        
        return recommendations
    
    async def _check_recent_performance(self, hours=4):
        """최근 성과 체크"""
        
        import sqlite3
        conn = sqlite3.connect('data/quantum.db')
        cursor = conn.cursor()
        
        time_threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as loss_trades,
                SUM(pnl) as total_pnl
            FROM trades
            WHERE timestamp >= ?
        """, (time_threshold,))
        
        stats = cursor.fetchone()
        conn.close()
        
        total_trades = stats[0] or 0
        loss_trades = stats[1] or 0
        total_pnl = stats[2] or 0
        
        return {
            'total_trades': total_trades,
            'loss_rate': (loss_trades / total_trades * 100) if total_trades > 0 else 0,
            'total_pnl': total_pnl,
            'return_rate': (total_pnl / 10000000 * 100) if total_trades > 0 else 0
        }
    
    def _needs_emergency_adjustment(self, performance):
        """긴급 조정 필요 여부"""
        
        # 손실률 50% 이상 또는 수익률 -3% 이하
        return (performance['loss_rate'] > 50 or 
                performance['return_rate'] < -3)
    
    async def _emergency_adjustment(self, performance):
        """긴급 전략 조정"""
        
        adjustments = {
            'signal_threshold': 0.1,  # 매우 보수적
            'max_position': 5000000,  # 포지션 축소
            'stop_loss': 0.003,  # 타이트한 손절
            'trading_enabled': performance['return_rate'] > -5  # -5% 이하시 거래 중단
        }
        
        # Config 업데이트
        import yaml
        
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        config['trading']['signal_threshold'] = adjustments['signal_threshold']
        config['trading']['limits']['max_position'] = adjustments['max_position']
        
        with open('config/config.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return adjustments
    
    async def _get_system_status(self):
        """시스템 상태 확인"""
        
        import psutil
        
        return {
            'cpu_usage': psutil.cpu_percent(),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'process_running': self._check_process_running()
        }
    
    def _check_process_running(self):
        """프로세스 실행 상태"""
        
        import subprocess
        
        try:
            result = subprocess.run(['pgrep', '-f', 'quantum_trading.py'], 
                                  capture_output=True, text=True)
            return len(result.stdout.strip()) > 0
        except:
            return False
    
    def _detect_anomalies(self, status):
        """이상 징후 감지"""
        
        anomalies = []
        
        if status['cpu_usage'] > 90:
            anomalies.append("CPU 과부하")
        
        if status['memory_usage'] > 90:
            anomalies.append("메모리 부족")
        
        if status['disk_usage'] > 90:
            anomalies.append("디스크 공간 부족")
        
        if not status['process_running']:
            anomalies.append("트레이딩 프로세스 중단")
        
        return anomalies
    
    async def _save_monitoring_status(self, status):
        """모니터링 상태 저장"""
        
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            
            r.hset('monitoring:status', mapping={
                'timestamp': datetime.now().isoformat(),
                'cpu': status['cpu_usage'],
                'memory': status['memory_usage'],
                'disk': status['disk_usage'],
                'running': status['process_running']
            })
            
            # 1시간 유효
            r.expire('monitoring:status', 3600)
            
        except Exception as e:
            logger.error(f"Failed to save monitoring status: {e}")
    
    async def restart_trading_with_new_params(self):
        """새 파라미터로 트레이딩 재시작"""
        
        import subprocess
        
        try:
            # 기존 프로세스 종료
            subprocess.run(['pkill', '-f', 'quantum_trading.py'])
            await asyncio.sleep(2)
            
            # 새로 시작
            subprocess.Popen([
                'python', 
                '/opt/bit_auto_v2_250712/quantum_trading.py'
            ])
            
            logger.info("Trading restarted with new parameters")
            
        except Exception as e:
            logger.error(f"Failed to restart trading: {e}")
    
    async def send_notification(self, title, message):
        """알림 발송 (텔레그램, 이메일 등)"""
        
        # 콘솔 출력 (실제로는 텔레그램 API 등 사용)
        logger.info(f"📢 {title}: {message}")
        
        # 파일로도 저장
        with open('logs/notifications.log', 'a') as f:
            f.write(f"{datetime.now()}: {title} - {message}\n")
    
    def _format_daily_report(self, report):
        """일일 보고서 포맷"""
        
        summary = report.get('summary', {})
        
        return f"""
일일 트레이딩 분석 결과:

주요 발견사항:
{chr(10).join(f'• {finding}' for finding in summary.get('key_findings', []))}

즉시 실행사항:
{chr(10).join(f'• {action}' for action in summary.get('immediate_actions', []))}

예상 개선율: {summary.get('expected_improvement', 0):.1f}%
"""
    
    def _format_weekly_report(self, report):
        """주간 보고서 포맷"""
        
        return f"""
주간 심층 분석 결과:

발견된 패턴: {len(report.get('patterns', {}))}개
제안된 전략: {len(report.get('new_strategies', {}))}개
추천사항: {len(report.get('recommendations', []))}개

상세 내용은 reports 폴더 확인
"""
    
    def start(self):
        """스케줄러 시작"""
        
        if not self.is_running:
            self.setup_schedule()
            self.scheduler.start()
            self.is_running = True
            logger.info("Feedback scheduler started")
    
    def stop(self):
        """스케줄러 중지"""
        
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Feedback scheduler stopped")
    
    def get_jobs(self):
        """예약된 작업 목록"""
        
        return [(job.id, job.name, job.next_run_time) 
                for job in self.scheduler.get_jobs()]


async def main():
    """메인 실행"""
    
    scheduler = FeedbackScheduler()
    scheduler.start()
    
    try:
        # 계속 실행
        while True:
            await asyncio.sleep(60)
            
            # 상태 출력
            jobs = scheduler.get_jobs()
            logger.info(f"Active jobs: {len(jobs)}")
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())