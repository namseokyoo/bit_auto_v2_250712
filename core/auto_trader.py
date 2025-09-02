"""
실제 자동거래 엔진
- TradingEngine과 통합하여 실제 자동매매 실행
- 스케줄링, 신호 처리, 리스크 관리 통합
- 운영 중단 없는 안전한 업그레이드
"""

from data.database import db
from config.config_manager import config_manager
import pytz
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import schedule
import time
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class AutoTraderState:
    running: bool = False
    last_started_at: float | None = None
    next_execution_time: Optional[datetime] = None
    last_execution_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0


class AutoTrader:
    def __init__(self):
        self.state = AutoTraderState()
        self._thread: threading.Thread | None = None
        self._schedule_thread: threading.Thread | None = None

        # 로거 설정
        self.logger = self._setup_logger()

        # 한국 시간대
        self.kst = pytz.timezone('Asia/Seoul')

        # TradingEngine은 lazy import로 순환 참조 방지
        self._trading_engine = None

        # VotingStrategyEngine - 새로운 투표 기반 전략
        self._voting_engine = None

        # 5분 캔들 데이터 수집 시스템
        from core.data_collection_scheduler import data_scheduler
        self.data_scheduler = data_scheduler

        # 설정 변경 콜백 등록
        self._setup_config_callbacks()

        self.logger.info("AutoTrader 초기화 완료")

    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger('AutoTrader')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            # 로그 디렉토리 생성
            os.makedirs('logs', exist_ok=True)

            # 파일 핸들러
            file_handler = logging.FileHandler('logs/auto_trader.log')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(file_formatter)
            logger.addHandler(console_handler)

        return logger

    def _setup_config_callbacks(self):
        """설정 변경 콜백 등록"""
        def on_config_change(key_path: str, new_value, old_value):
            if key_path == 'trading.trade_interval_minutes':
                self.logger.info(f"거래 주기 변경 감지: {old_value}분 -> {new_value}분")
                if self.state.running:
                    self.logger.info("AutoTrader 스케줄 재설정 중...")
                    self._setup_schedule()
                    self.logger.info("AutoTrader 스케줄 재설정 완료")

            elif key_path == 'trading.auto_trade_enabled':
                if new_value:
                    self.logger.info("자동거래 활성화됨")
                else:
                    self.logger.info("자동거래 비활성화됨")

        config_manager.register_callback(on_config_change)

    @property
    def running(self) -> bool:
        return self.state.running

    @property
    def trading_engine(self):
        """TradingEngine을 lazy import로 로드"""
        if self._trading_engine is None:
            try:
                from core.trading_engine import TradingEngine
                self._trading_engine = TradingEngine()
                self.logger.info("TradingEngine 로드 완료")
            except Exception as e:
                self.logger.error(f"TradingEngine 로드 실패: {e}")
                return None
        return self._trading_engine

    @property
    def voting_engine(self):
        """VotingStrategyEngine을 lazy import로 로드"""
        if self._voting_engine is None:
            try:
                from core.voting_strategy_engine import VotingStrategyEngine
                from core.upbit_api import UpbitAPI

                # UpbitAPI 인스턴스 생성 (설정에 따라)
                upbit_api = UpbitAPI(
                    paper_trading=config_manager.get_config(
                        'system.mode') == 'paper_trading'
                )

                self._voting_engine = VotingStrategyEngine(upbit_api)
                self.logger.info("VotingStrategyEngine 로드 완료")
            except Exception as e:
                self.logger.error(f"VotingStrategyEngine 로드 실패: {e}")
                return None
        return self._voting_engine

    def initialize(self) -> bool:
        """자동거래 시스템 초기화"""
        try:
            self.logger.info("자동거래 시스템 초기화 시작...")

            # 설정 확인
            if not config_manager.is_system_enabled():
                self.logger.warning("시스템이 비활성화되어 있습니다.")
                return False

            # 거래 비활성화 상태에서도 스케줄과 전략 계산은 수행하고, 주문만 TradingEngine에서 차단

            # 데이터베이스 확인
            try:
                # 간단한 DB 연결 테스트 (최근 거래 1개만 조회)
                recent_trades = db.get_trades()
                self.logger.info(
                    f"데이터베이스 연결 확인됨 - 총 거래: {len(recent_trades)}개")
            except Exception as e:
                self.logger.error(f"데이터베이스 연결 실패: {e}")
                return False

            # TradingEngine 초기화
            if self.trading_engine is None:
                self.logger.error("TradingEngine 초기화 실패")
                return False

            self.logger.info("자동거래 시스템 초기화 완료")
            return True

        except Exception as e:
            self.logger.error(f"초기화 중 오류 발생: {e}")
            return False

    def _setup_schedule(self):
        """스케줄 설정"""
        schedule.clear()  # 기존 스케줄 클리어

        trading_config = config_manager.get_trading_config()
        interval_minutes = trading_config.get('trade_interval_minutes', 10)

        # 주기적 자동거래 실행
        if interval_minutes >= 60:
            # 1시간 이상인 경우 시간별 스케줄
            for hour in range(0, 24, interval_minutes // 60):
                schedule.every().day.at(f"{hour:02d}:00").do(
                    self._execute_auto_trading)
        else:
            # 분 단위 스케줄
            schedule.every(interval_minutes).minutes.do(
                self._execute_auto_trading)

        # 일일 성과 리포트 (23:55)
        schedule.every().day.at("23:55").do(self._daily_performance_check)

        # 리스크 체크 (매 5분)
        schedule.every(5).minutes.do(self._risk_check)

        self._update_next_execution_time()
        self.logger.info(f"스케줄 설정 완료 - 거래 간격: {interval_minutes}분")

    def _update_next_execution_time(self):
        """다음 실행 시간 업데이트"""
        jobs = schedule.get_jobs()
        if jobs:
            next_run = min(job.next_run for job in jobs if job.next_run)
            self.state.next_execution_time = next_run
            self.logger.debug(f"다음 실행 시간: {next_run}")

    def start(self):
        """자동거래 시작"""
        if self.state.running:
            self.logger.warning("이미 실행 중입니다.")
            return True

        try:
            # 초기화
            if not self.initialize():
                self.logger.error("초기화 실패로 시작할 수 없습니다.")
                return False

            self.state.running = True
            self.state.last_started_at = time.time()

            # 5분 캔들 데이터 수집 시작
            self.data_scheduler.start()
            self.logger.info("5분 캔들 데이터 수집 시작됨")

            # 스케줄 설정
            self._setup_schedule()

            # 메인 루프 스레드 시작
            self._thread = threading.Thread(
                target=self._main_loop, daemon=True)
            self._thread.start()

            # 스케줄러 스레드 시작
            self._schedule_thread = threading.Thread(
                target=self._schedule_loop, daemon=True)
            self._schedule_thread.start()

            self.logger.info("🤖 자동거래 시작됨")
            self.logger.info(f"다음 실행: {self.state.next_execution_time}")

            # 시작 로그 기록
            db.insert_log('INFO', 'AutoTrader', '자동거래 시작',
                          f'시작 시간: {datetime.now(self.kst)}')

            return True

        except Exception as e:
            self.logger.error(f"시작 중 오류: {e}")
            self.state.running = False
            return False

    def stop(self):
        """자동거래 중지"""
        if not self.state.running:
            return

        self.logger.info("자동거래 중지 중...")
        self.state.running = False

        # 5분 캔들 데이터 수집 중지
        self.data_scheduler.stop()
        self.logger.info("5분 캔들 데이터 수집 중지됨")

        # 스케줄 클리어
        schedule.clear()

        # 중지 로그 기록
        db.insert_log('INFO', 'AutoTrader', '자동거래 중지',
                      f'중지 시간: {datetime.now(self.kst)}')

        self.logger.info("✅ 자동거래 중지됨")

    def _main_loop(self):
        """메인 모니터링 루프"""
        while self.state.running:
            try:
                # 시스템 상태 체크
                if not config_manager.is_system_enabled():
                    self.logger.warning("시스템이 비활성화되어 자동거래를 일시 중지합니다.")
                    time.sleep(60)
                    continue

                # 기본 모니터링 (30초마다)
                time.sleep(30)

            except Exception as e:
                self.logger.error(f"메인 루프 오류: {e}")
                time.sleep(60)

    def _schedule_loop(self):
        """스케줄러 실행 루프"""
        while self.state.running:
            try:
                schedule.run_pending()
                self._update_next_execution_time()
                time.sleep(10)  # 10초마다 스케줄 체크

            except Exception as e:
                self.logger.error(f"스케줄러 오류: {e}")
                time.sleep(30)

    def _execute_auto_trading(self):
        """자동거래 실행 - 개선된 신호 처리"""
        if not self.state.running:
            return

        try:
            self.logger.info("=" * 50)
            self.logger.info(f"🤖 자동거래 실행 시작 - {datetime.now(self.kst)}")
            self.logger.info("=" * 50)

            self.state.total_executions += 1
            self.state.last_execution_time = datetime.now(self.kst)

            # 거래 가능 여부 확인
            if not config_manager.is_trading_enabled():
                self.logger.info("자동거래가 비활성화되어 있습니다.")
                return

            # 시장 활성도 체크 (밤 시간대 등)
            if not self._is_market_active():
                self.logger.info("시장 활성도가 낮아 거래를 건너뜁니다.")
                return

            # TradingEngine을 통한 전략 실행
            if self.trading_engine:
                execution_success = False

                try:
                    # 1. 시장 데이터 확인
                    if not self._validate_market_data():
                        self.logger.warning("시장 데이터 검증 실패")
                        return

                    # 2. 리스크 사전 체크
                    if not self._pre_trade_risk_check():
                        self.logger.warning("사전 리스크 체크 실패")
                        return

                    # 3. 투표 기반 전략 실행 (새로운 시스템)
                    self.logger.info("🗳️ 투표 기반 전략 실행 중...")
                    if self.voting_engine:
                        voting_signal = self.voting_engine.get_trading_signal()
                        if voting_signal:
                            self.logger.info(
                                f"투표 결과: {voting_signal.action} (신뢰도: {voting_signal.confidence:.3f})")
                            # TradingEngine을 통해 실제 거래 실행
                            if self.trading_engine:
                                self.trading_engine.execute_signal(
                                    voting_signal)
                        else:
                            self.logger.info("투표 결과: HOLD (거래 없음)")

                    # 3-1. 기존 시간별 전략 (병행 실행 - 추후 단계적 교체)
                    legacy_strategies_enabled = config_manager.get_config(
                        'strategies.legacy_enabled', False)
                    if legacy_strategies_enabled:
                        self.logger.info("📊 기존 시간별 전략 실행 중...")
                        self.trading_engine.execute_hourly_strategies()

                    # 4. 포지션 모니터링 (개선된 로깅)
                    self.logger.info("📈 포지션 모니터링 중...")
                    self.trading_engine.monitor_positions()

                    # 5. 대기 주문 처리 (개선된 로깅)
                    self.logger.info("⏳ 대기 주문 처리 중...")
                    self.trading_engine.process_pending_orders()

                    execution_success = True
                    self.state.successful_executions += 1

                    # 성공 메트릭 기록
                    self._log_execution_metrics(success=True)

                except Exception as te:
                    self.logger.error(f"TradingEngine 실행 오류: {te}")
                    raise te

                self.logger.info(
                    f"✅ 자동거래 실행 완료 - 성공률: {self.state.successful_executions}/{self.state.total_executions}")

            else:
                raise Exception("TradingEngine을 사용할 수 없습니다.")

        except Exception as e:
            self.state.failed_executions += 1
            self.logger.error(f"❌ 자동거래 실행 실패: {e}")

            # 실패 메트릭 기록
            self._log_execution_metrics(success=False, error=str(e))

            # 에러 로그 기록
            db.insert_log('ERROR', 'AutoTrader', '자동거래 실행 실패', str(e))

    def _is_market_active(self) -> bool:
        """시장 활성도 체크"""
        try:
            now = datetime.now(self.kst)
            hour = now.hour

            # 업비트는 24시간 거래하지만,
            # 한국 새벽 2-6시는 거래량이 적어 건너뛸 수 있음
            trading_config = config_manager.get_trading_config()
            if trading_config.get('skip_low_volume_hours', False):
                if 2 <= hour < 6:
                    return False

            # 주말 체크 (필요시)
            if trading_config.get('skip_weekends', False):
                if now.weekday() >= 5:  # Saturday, Sunday
                    return False

            return True

        except Exception as e:
            self.logger.error(f"시장 활성도 체크 오류: {e}")
            return True  # 오류 시 기본적으로 거래 허용

    def _validate_market_data(self) -> bool:
        """시장 데이터 검증"""
        try:
            if not self.trading_engine or not self.trading_engine.api:
                return False

            # 현재가 조회로 간단한 API 연결 테스트
            current_price = self.trading_engine.api.get_current_price(
                "KRW-BTC")
            if not current_price or current_price <= 0:
                self.logger.warning("유효하지 않은 현재가 데이터")
                return False

            # 최근 거래량 체크 (옵션)
            market_data = self.trading_engine.api.get_market_data("KRW-BTC")
            if market_data and market_data.volume == 0:
                self.logger.warning("거래량이 0입니다.")
                return False

            return True

        except Exception as e:
            self.logger.error(f"시장 데이터 검증 오류: {e}")
            return False

    def _pre_trade_risk_check(self) -> bool:
        """거래 전 리스크 체크"""
        try:
            if not self.trading_engine or not self.trading_engine.risk_manager:
                return False

            can_trade, reason = self.trading_engine.risk_manager.can_trade()
            if not can_trade:
                self.logger.warning(f"리스크 체크 실패: {reason}")
                return False

            # 추가적인 AutoTrader 레벨 체크
            if self.state.failed_executions > 5:
                # 연속 실패가 5회 이상이면 잠시 대기
                last_success_time = getattr(
                    self.state, 'last_success_time', None)
                if last_success_time:
                    time_since_success = (datetime.now(
                        self.kst) - last_success_time).total_seconds()
                    if time_since_success > 3600:  # 1시간 이상 성공이 없으면
                        self.logger.warning("장기간 성공이 없어 거래를 일시 중단합니다.")
                        return False

            return True

        except Exception as e:
            self.logger.error(f"사전 리스크 체크 오류: {e}")
            return False

    def _log_execution_metrics(self, success: bool, error: str = None):
        """실행 메트릭 로깅"""
        try:
            if success:
                self.state.last_success_time = datetime.now(self.kst)

            # 성공률 계산
            success_rate = (self.state.successful_executions /
                            max(1, self.state.total_executions)) * 100

            # 통계 로그
            self.logger.info(f"📊 실행 통계: 성공 {self.state.successful_executions}회, "
                             f"실패 {self.state.failed_executions}회, "
                             f"성공률 {success_rate:.1f}%")

            # 데이터베이스에 메트릭 기록
            metric_data = {
                'timestamp': datetime.now(self.kst).isoformat(),
                'success': success,
                'total_executions': self.state.total_executions,
                'success_rate': success_rate,
                'error': error
            }

            db.insert_log('METRIC', 'AutoTrader',
                          '실행 메트릭' if success else '실행 실패 메트릭',
                          str(metric_data))

        except Exception as e:
            self.logger.error(f"메트릭 로깅 오류: {e}")

    def _daily_performance_check(self):
        """일일 성과 체크"""
        try:
            self.logger.info("📊 일일 성과 체크 시작")

            if self.trading_engine and hasattr(self.trading_engine, 'strategy_manager'):
                self.trading_engine.strategy_manager.daily_performance_check()

            # 자동거래 통계 로그
            success_rate = (self.state.successful_executions /
                            max(1, self.state.total_executions)) * 100
            self.logger.info(f"📈 일일 자동거래 통계:")
            self.logger.info(f"   - 총 실행: {self.state.total_executions}회")
            self.logger.info(f"   - 성공: {self.state.successful_executions}회")
            self.logger.info(f"   - 실패: {self.state.failed_executions}회")
            self.logger.info(f"   - 성공률: {success_rate:.1f}%")

        except Exception as e:
            self.logger.error(f"일일 성과 체크 오류: {e}")

    def _risk_check(self):
        """리스크 체크"""
        try:
            if not self.state.running:
                return

            # 긴급 상황 체크
            if self.trading_engine and hasattr(self.trading_engine, 'risk_manager'):
                can_trade, reason = self.trading_engine.risk_manager.can_trade()
                if not can_trade and "긴급" in reason:
                    self.logger.critical(f"🚨 긴급 상황 감지: {reason}")
                    self.stop()

        except Exception as e:
            self.logger.error(f"리스크 체크 오류: {e}")

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        return {
            'running': self.state.running,
            'last_started_at': self.state.last_started_at,
            'next_execution_time': self.state.next_execution_time.isoformat() if self.state.next_execution_time else None,
            'last_execution_time': self.state.last_execution_time.isoformat() if self.state.last_execution_time else None,
            'total_executions': self.state.total_executions,
            'successful_executions': self.state.successful_executions,
            'failed_executions': self.state.failed_executions,
            'success_rate': (self.state.successful_executions / max(1, self.state.total_executions)) * 100
        }


auto_trader = AutoTrader()


def start_auto_trading():
    """자동거래 시작 (호환성 함수)"""
    return auto_trader.start()


def stop_auto_trading():
    """자동거래 중지 (호환성 함수)"""
    auto_trader.stop()


def get_auto_trading_status() -> dict:
    """자동거래 상태 반환 (호환성 함수)"""
    status = auto_trader.get_status()
    # 기존 API 호환성을 위한 간소화된 상태
    return {
        "running": status['running'],
        "last_started_at": status['last_started_at'],
        "next_execution_time": status['next_execution_time'],
        "last_execution_time": status['last_execution_time'],
        "auto_trading_enabled": status['running'],
        "success_rate": status['success_rate'],
        "total_executions": status['total_executions']
    }
