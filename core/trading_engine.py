"""
메인 트레이딩 엔진
전략 실행, 리스크 관리, 주문 처리를 담당하는 핵심 모듈
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

from config.config_manager import config_manager
from core.upbit_api import UpbitAPI, OrderResult, MarketData
from core.signal_manager import SignalManager, TradingSignal, ConsolidatedSignal, MarketCondition
from core.position_manager import PositionManager
from core.advanced_risk_manager import AdvancedRiskManager
from core.enhanced_strategy_implementation import EnhancedStrategyAnalyzer
from core.strategy_router import StrategyRouter
from core.data_collector import DataCollector
from core.performance_monitor import PerformanceMonitor
from core.signal_recorder import signal_recorder
from strategy_manager import StrategyManager, TradeRecord
import pandas as pd
import numpy as np
# TA-Lib import를 조건부로 처리
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logging.warning("TA-Lib not available. Some technical indicators will use fallback implementations.")

# Position 클래스는 position_manager.py에서 가져옴

class RiskManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.daily_pnl = 0
        self.daily_trades = 0
        self.last_reset = datetime.now().date()
        self.consecutive_losses = 0
        self.logger = logging.getLogger('RiskManager')

    def reset_daily_stats(self):
        """일일 통계 리셋"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.daily_pnl = 0
            self.daily_trades = 0
            self.last_reset = today
            self.logger.info("일일 통계 리셋됨")

    def can_trade(self) -> Tuple[bool, str]:
        """거래 가능 여부 확인"""
        self.reset_daily_stats()
        
        # 시스템 활성화 확인
        if not self.config.is_system_enabled():
            return False, "시스템이 비활성화됨"
        
        # 자동거래 활성화 확인
        if not self.config.is_trading_enabled():
            return False, "자동거래가 비활성화됨"
        
        # 일일 손실 한도 확인
        daily_loss_limit = self.config.get_config('trading.daily_loss_limit')
        if self.daily_pnl <= -daily_loss_limit:
            return False, f"일일 손실 한도 초과: {self.daily_pnl:,.0f}"
        
        # 긴급 정지 손실 확인
        emergency_stop = self.config.get_emergency_stop_loss()
        total_loss = self.get_total_loss()
        if total_loss >= emergency_stop:
            self.config.emergency_stop()
            return False, f"긴급 정지 손실 도달: {total_loss:,.0f}"
        
        # 일일 거래 횟수 확인
        max_daily_trades = self.config.get_config('risk_management.max_daily_trades')
        if self.daily_trades >= max_daily_trades:
            return False, f"일일 거래 한도 초과: {self.daily_trades}"
        
        return True, "거래 가능"

    def calculate_position_size(self, signal: TradingSignal, balance: float) -> float:
        """포지션 크기 계산"""
        max_trade_amount = self.config.get_trade_amount_limit()
        
        # 잔고의 일정 비율로 제한
        max_position_percent = self.config.get_config('risk_management.max_position_size_percent') / 100
        max_by_balance = balance * max_position_percent
        
        # 신호 강도에 따른 조정
        confidence_multiplier = signal.confidence
        
        # 최종 거래 금액 결정
        trade_amount = min(
            max_trade_amount,
            max_by_balance,
            signal.suggested_amount
        ) * confidence_multiplier
        
        return max(trade_amount, 10000)  # 최소 거래 금액

    def get_total_loss(self) -> float:
        """총 손실 계산 (임시 구현)"""
        # 실제로는 데이터베이스에서 총 손실을 계산해야 함
        return abs(min(0, self.daily_pnl))

    def update_trade_result(self, pnl: float):
        """거래 결과 업데이트"""
        self.daily_pnl += pnl
        self.daily_trades += 1
        
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        self.logger.info(f"거래 결과 업데이트: PnL={pnl:,.0f}, 일일PnL={self.daily_pnl:,.0f}")

class TradingEngine:
    def __init__(self):
        self.config = config_manager
        self.api = UpbitAPI()  # 실거래 API
        self.strategy_manager = StrategyManager()
        self.risk_manager = RiskManager(self.config)
        self.advanced_risk_manager = AdvancedRiskManager(self.config)  # 고급 리스크 관리자 추가
        self.enhanced_strategy_analyzer = EnhancedStrategyAnalyzer()  # 개선된 전략 분석기 추가
        
        # 새로운 통합 시스템
        self.strategy_router = StrategyRouter(self.config.get_all_config())
        self.data_collector = DataCollector()
        self.performance_monitor = PerformanceMonitor()
        
        # 새로운 통합 관리자들
        self.signal_manager = SignalManager(self.config)
        self.position_manager = PositionManager(self.config, self.api)
        
        self.running = False
        self.pending_orders = {}
        
        self.logger = self._setup_logger()
        self._setup_config_callbacks()
        self._schedule_tasks()
        
        self.logger.info("통합 트레이딩 엔진 초기화 완료")

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('TradingEngine')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # 파일 핸들러 추가
            file_handler = logging.FileHandler('logs/trading_engine.log')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            # 콘솔 핸들러 추가
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(file_formatter)
            logger.addHandler(console_handler)
        
        return logger

    def _setup_config_callbacks(self):
        """설정 변경 콜백 등록"""
        def on_config_change(key_path: str, new_value, old_value):
            self.logger.info(f"설정 변경 감지: {key_path} = {old_value} -> {new_value}")
            
            if key_path == 'system.enabled':
                if new_value:
                    self.logger.info("시스템 활성화됨")
                else:
                    self.logger.warning("시스템 비활성화됨")
            
            elif key_path == 'trading.auto_trade_enabled':
                if new_value:
                    self.logger.info("자동거래 활성화됨")
                else:
                    self.logger.warning("자동거래 비활성화됨")
                    
            elif key_path == 'system.mode':
                self.logger.critical("실거래 모드로 전환! 주의 필요")
                self.api = UpbitAPI()

        self.config.register_callback(on_config_change)

    def _schedule_tasks(self):
        """작업 스케줄링"""
        # 1시간마다 시간 전략 실행
        schedule.every().hour.at(":00").do(self.execute_hourly_strategies)
        
        # 매일 0시에 일일 전략 실행
        schedule.every().day.at("00:00").do(self.execute_daily_strategies)
        
        # 설정 기반 포지션 모니터링 간격
        monitoring_interval = self.config.get_monitoring_config().get('position_monitoring', {}).get('check_interval_seconds', 30)
        schedule.every(monitoring_interval // 60 if monitoring_interval >= 60 else 1).minutes.do(self.monitor_positions)
        
        # 매일 성능 체크
        schedule.every().day.at("23:59").do(self.strategy_manager.daily_performance_check)

    def start(self):
        """트레이딩 엔진 시작"""
        self.running = True
        self.logger.info("트레이딩 엔진 시작됨")
        
        # 스케줄 실행 스레드
        schedule_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        schedule_thread.start()
        
        # 메인 모니터링 루프
        self._main_loop()

    def stop(self):
        """트레이딩 엔진 정지"""
        self.running = False
        self.logger.info("트레이딩 엔진 정지됨")

    def _run_scheduler(self):
        """스케줄러 실행"""
        while self.running:
            schedule.run_pending()
            # 설정 기반 스케줄러 체크 간격
            scheduler_interval = min(60, self.config.get_trading_config().get('trade_interval_minutes', 10) * 60 // 10)
            time.sleep(scheduler_interval)

    def _main_loop(self):
        """메인 모니터링 루프"""
        while self.running:
            try:
                # 기본 상태 체크
                if self.config.is_system_enabled():
                    self.monitor_positions()
                    self.process_pending_orders()
                
                # 설정 기반 체크 간격
                check_interval = self.config.get_monitoring_config().get('position_monitoring', {}).get('check_interval_seconds', 30)
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("사용자에 의해 중단됨")
                break
            except Exception as e:
                self.logger.error(f"메인 루프 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기

    def execute_hourly_strategies(self):
        """시간 단위 전략 실행 - 다층 전략 시스템 사용"""
        self.logger.info("다층 전략 시스템 실행 시작")
        
        try:
            # 다층 전략 엔진 실행
            from core.multi_tier_strategy_engine import multi_tier_engine
            multi_tier_decision = multi_tier_engine.analyze()
            
            # 다층 결정을 ConsolidatedSignal로 변환
            consolidated_signal = self._convert_multitier_to_consolidated(multi_tier_decision)
            
            # 거래 비활성화 시: 신호 계산/기록만 수행하고 주문 실행은 생략
            if not self.config.is_trading_enabled():
                if consolidated_signal:
                    self.logger.info(f"거래 비활성화 상태 - 다층 신호({consolidated_signal.action})만 기록, 주문 미실행")
                return
            
            # 3. 통합 신호 처리 (거래 활성화 시에만)
            if consolidated_signal and consolidated_signal.action in ['buy', 'sell']:
                self._process_consolidated_signal(consolidated_signal)
                
        except Exception as e:
            self.logger.error(f"다층 전략 실행 오류: {e}")
            # 기존 방식으로 폴백
            self._execute_legacy_hourly_strategies()

    def execute_daily_strategies(self):
        """일일 전략 실행 - 통합 신호 처리"""
        self.logger.info("일일 전략 통합 실행 시작")
        
        # 1. 모든 활성 일일 전략에서 신호 수집
        strategy_signals = self._collect_all_signals('daily')
        
        # 2. 신호 통합 및 최종 결정
        consolidated_signal = self._consolidate_signals(strategy_signals)
        
        # 거래 비활성화 시: 신호 계산/기록만 수행하고 주문 실행은 생략
        if not self.config.is_trading_enabled():
            if consolidated_signal:
                self.logger.info(f"거래 비활성화 상태 - 신호({consolidated_signal.action})만 기록, 주문 미실행")
            return
        
        # 3. 통합 신호 처리 (거래 활성화 시에만)
        if consolidated_signal and consolidated_signal.action in ['buy', 'sell']:
            self._process_consolidated_signal(consolidated_signal)

    def _collect_all_signals(self, timeframe: str) -> Dict[str, TradingSignal]:
        """모든 활성 전략에서 신호 수집"""
        strategy_signals = {}
        
        if timeframe == 'hourly':
            active_strategies = self.strategy_manager.get_active_strategies('hourly')
        else:
            active_strategies = self.strategy_manager.get_active_strategies('daily')
        
        for strategy_id, strategy in active_strategies.items():
            try:
                signal = self.generate_signal(strategy_id, strategy)
                if signal:
                    strategy_signals[strategy_id] = signal
            except Exception as e:
                self.logger.error(f"전략 {strategy_id} 신호 생성 오류: {e}")
        
        return strategy_signals

    def _consolidate_signals(self, strategy_signals: Dict[str, TradingSignal]) -> Optional[ConsolidatedSignal]:
        """신호 통합 처리"""
        if not strategy_signals:
            return None
        
        # 현재 시장 데이터 가져오기
        market_data = self.api.get_market_data("KRW-BTC")
        if not market_data:
            self.logger.warning("시장 데이터를 가져올 수 없음")
            return None
        
        # 시장 상황 분석
        market_condition = self.signal_manager.detect_market_condition(market_data)
        
        # 유효한 신호만 수집
        valid_signals = self.signal_manager.collect_signals(strategy_signals)
        
        # 신호 통합
        consolidated_signal = self.signal_manager.resolve_signal_conflicts(valid_signals, market_condition)
        
        # 결정 과정 로깅
        self.signal_manager.log_signal_decision(consolidated_signal)
        
        return consolidated_signal

    def _convert_multitier_to_consolidated(self, multi_tier_decision) -> Optional['ConsolidatedSignal']:
        """다층 결정을 ConsolidatedSignal로 변환"""
        try:
            from core.signal_manager import ConsolidatedSignal, MarketCondition
            
            # MarketCondition 매핑
            regime_to_condition = {
                'bullish': MarketCondition.TRENDING_UP,
                'bearish': MarketCondition.TRENDING_DOWN,
                'sideways': MarketCondition.SIDEWAYS,
                'high_vol': MarketCondition.HIGH_VOLATILITY,
                'low_vol': MarketCondition.LOW_VOLATILITY
            }
            
            market_condition = regime_to_condition.get(
                multi_tier_decision.market_regime.value, 
                MarketCondition.SIDEWAYS
            )
            
            # 기여 전략 목록 생성
            contributing_strategies = []
            for tier, contribution in multi_tier_decision.tier_contributions.items():
                if abs(contribution) > 0.1:  # 유의미한 기여만 포함
                    contributing_strategies.append(f"{tier.value}_layer")
            
            return ConsolidatedSignal(
                action=multi_tier_decision.final_action,
                confidence=multi_tier_decision.confidence,
                suggested_amount=multi_tier_decision.suggested_amount,
                reasoning=multi_tier_decision.reasoning,
                contributing_strategies=contributing_strategies,
                final_score=sum(multi_tier_decision.tier_contributions.values()),
                market_condition=market_condition,
                timestamp=multi_tier_decision.timestamp
            )
            
        except Exception as e:
            self.logger.error(f"다층 결정 변환 오류: {e}")
            return None

    def _execute_legacy_hourly_strategies(self):
        """기존 시간별 전략 실행 (폴백)"""
        self.logger.info("기존 시간 단위 전략 실행 (폴백)")
        
        # 1. 모든 활성 전략에서 신호 수집
        strategy_signals = self._collect_all_signals('hourly')
        
        # 2. 신호 통합 및 최종 결정
        consolidated_signal = self._consolidate_signals(strategy_signals)
        
        # 거래 비활성화 시: 신호 계산/기록만 수행하고 주문 실행은 생략
        if not self.config.is_trading_enabled():
            if consolidated_signal:
                self.logger.info(f"거래 비활성화 상태 - 신호({consolidated_signal.action})만 기록, 주문 미실행")
            return
        
        # 3. 통합 신호 처리 (거래 활성화 시에만)
        if consolidated_signal and consolidated_signal.action in ['buy', 'sell']:
            self._process_consolidated_signal(consolidated_signal)

    def _process_consolidated_signal(self, consolidated_signal: ConsolidatedSignal):
        """통합된 신호 처리"""
        try:
            # 리스크 관리 체크
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                self.logger.warning(f"거래 불가: {reason}")
                return
            
            if consolidated_signal.action == 'buy':
                self._execute_consolidated_buy(consolidated_signal)
            elif consolidated_signal.action == 'sell':
                self._execute_consolidated_sell(consolidated_signal)
                
        except Exception as e:
            self.logger.error(f"통합 신호 처리 오류: {e}")

    def _execute_consolidated_buy(self, signal: ConsolidatedSignal):
        """통합 매수 신호 실행 - 고급 리스크 관리 적용"""
        # 1. 고급 리스크 관리 - 손실 한도 체크
        loss_limits = self.advanced_risk_manager.check_loss_limits()
        if not loss_limits['can_trade']:
            self.logger.warning(f"손실 한도로 거래 불가: {loss_limits['reason']}")
            return
        
        # 2. 포지션 상관관계 체크
        correlation_check = self.advanced_risk_manager.check_position_correlation(
            "KRW-BTC", "long"
        )
        if not correlation_check['allowed']:
            self.logger.warning(f"포지션 상관관계 체크 실패: {correlation_check['reason']}")
            return
        
        # 3. 시장 데이터 가져오기 (ATR 계산용)
        market_data = self.api.get_market_data("KRW-BTC")
        if not market_data:
            self.logger.error("시장 데이터 조회 실패")
            return
        
        # 현재가 조회
        current_price = self.api.get_current_price("KRW-BTC")
        if not current_price:
            self.logger.error("현재가 조회 실패")
            return
        
        # 4. 고급 리스크 메트릭 계산
        account_balance = self.api.get_balance("KRW")
        
        # DataFrame 생성 (실제로는 더 많은 데이터 필요)
        df = pd.DataFrame({
            'high': [market_data.high_price],
            'low': [market_data.low_price],
            'close': [current_price],
            'volume': [market_data.volume]
        })
        
        risk_metrics = self.advanced_risk_manager.get_risk_metrics(
            df=df,
            entry_price=current_price,
            direction="long",
            signal_strength=signal.confidence,
            account_balance=account_balance
        )
        
        # 5. Kelly Criterion 기반 포지션 크기 조정
        adjusted_amount = min(
            signal.suggested_amount,
            risk_metrics.position_size,
            loss_limits['max_risk_amount']
        )
        
        if adjusted_amount < 10000:  # 최소 거래 금액
            self.logger.warning("조정된 포지션 크기가 최소 거래 금액 미만")
            return
        
        # 포지션 생성 가능 여부 확인
        can_open, reason = self.position_manager.can_open_position(
            "multi_strategy", adjusted_amount
        )
        
        if not can_open:
            self.logger.warning(f"포지션 생성 불가: {reason}")
            return
        
        # 매수 수량 계산
        quantity = adjusted_amount / current_price
        
        # 실제 매수 주문 실행
        result = self.api.place_buy_order("KRW-BTC", current_price, amount=adjusted_amount)
        
        if result.success:
            # 고급 리스크 관리자에 포지션 추가
            self.advanced_risk_manager.add_position(
                position_id=result.order_id,
                symbol="KRW-BTC",
                direction="long",
                size=adjusted_amount
            )
            
            # 포지션 생성
            position = self.position_manager.create_position(
                strategy_id="multi_strategy",
                symbol="KRW-BTC",
                side="long",
                size=quantity,
                entry_price=current_price
            )
            
            if position:
                self.logger.info(
                    f"통합 매수 완료: {adjusted_amount:,.0f}원 "
                    f"(원래: {signal.suggested_amount:,.0f}원) "
                    f"신뢰도: {signal.confidence:.2f}, "
                    f"Kelly fraction: {risk_metrics.kelly_fraction:.3f}, "
                    f"손절가: {risk_metrics.stop_loss:,.0f}, "
                    f"리스크/리워드: {risk_metrics.risk_reward_ratio:.2f}, "
                    f"기여전략: {signal.contributing_strategies}"
                )
                
                # 거래 기록 추가
                trade_record = TradeRecord(
                    strategy_id="multi_strategy",
                    entry_time=datetime.now(),
                    exit_time=None,
                    entry_price=current_price,
                    exit_price=None,
                    position_size=quantity,
                    side='long',
                    pnl=None,
                    fees=signal.suggested_amount * 0.0005,
                    status='open'
                )
                self.strategy_manager.add_trade_record(trade_record)
            
        else:
            self.logger.error(f"통합 매수 실패: {result.message}")

    def _execute_consolidated_sell(self, signal: ConsolidatedSignal):
        """통합 매도 신호 실행"""
        # 보유 BTC 확인
        btc_balance = self.api.get_balance("BTC")
        if btc_balance < 0.0001:
            self.logger.warning("매도할 BTC 잔고 부족")
            return
        
        # 현재가 조회
        current_price = self.api.get_current_price("KRW-BTC")
        if not current_price:
            self.logger.error("현재가 조회 실패")
            return
        
        # 전량 매도
        result = self.api.place_sell_order("KRW-BTC", current_price, btc_balance)
        
        if result.success:
            # 고급 리스크 관리자에서 포지션 업데이트
            sell_amount = btc_balance * current_price
            for position_id in list(self.advanced_risk_manager.active_positions.keys()):
                # 실제 PnL 계산 (간단한 예시)
                pnl = sell_amount * 0.01  # 실제로는 정확한 계산 필요
                self.advanced_risk_manager.update_position(position_id, pnl)
            
            # 관련 포지션들 종료
            open_positions = list(self.position_manager.positions.keys())
            for position_id in open_positions:
                self.position_manager.close_position(position_id, "통합 매도 신호")
            
            self.logger.info(
                f"통합 매도 완료: {btc_balance:.8f} BTC "
                f"(신뢰도: {signal.confidence:.2f}, "
                f"기여전략: {signal.contributing_strategies})"
            )
        else:
            self.logger.error(f"통합 매도 실패: {result.message}")

    def generate_signal(self, strategy_id: str, strategy: Dict) -> Optional[TradingSignal]:
        """전략 신호 생성 - 통합 라우터 사용"""
        try:
            # 히스토리컬 데이터 우선 사용 (데이터베이스에서)
            df = self._get_historical_dataframe("KRW-BTC", strategy_id)
            
            if df is None or len(df) < 50:
                # 실시간 데이터 폴백
                df = self._get_market_dataframe("KRW-BTC", period=200)
                if df is None or len(df) < 50:
                    return None
            
            # 추가 데이터 준비 (특정 전략용)
            additional_data = {}
            
            # H7 전략용 OI 데이터 (실제로는 API에서 가져와야 함)
            if strategy_id == "h7":
                additional_data['oi_data'] = {
                    'current': 1000000,
                    'previous': 950000,
                    'long_ratio': 0.52
                }
                additional_data['funding_rate'] = 0.01
            
            # D1 전략용 주봉 데이터
            if strategy_id == "d1":
                weekly_df = self._get_historical_dataframe("KRW-BTC", "weekly")
                additional_data['weekly_df'] = weekly_df
            
            # 전략 라우터를 통한 신호 생성
            signal = self.strategy_router.route_strategy(strategy_id, df, additional_data)
            
            # 신호 기록 (모든 신호를 기록, 실행 여부는 나중에 결정)
            if signal:
                try:
                    signal_recorder.record_signal({
                        'strategy_id': strategy_id,
                        'action': signal.action,
                        'confidence': signal.confidence,
                        'price': signal.price,
                        'suggested_amount': signal.suggested_amount,
                        'reasoning': signal.reasoning,
                        'market_data': {
                            'current_price': df['close'].iloc[-1] if not df.empty else 0,
                            'volume': df['volume'].iloc[-1] if not df.empty else 0
                        }
                    }, executed=False)
                except Exception as e:
                    self.logger.error(f"신호 기록 오류: {e}")
            
            # 성능 기록
            if signal and signal.action != 'hold':
                # 거래 기록
                trade_id = self.performance_monitor.record_trade(
                    strategy_id=strategy_id,
                    action=signal.action,
                    price=signal.price,
                    quantity=signal.suggested_amount / signal.price if signal.price > 0 else 0,
                    amount=signal.suggested_amount,
                    confidence=signal.confidence,
                    reasoning=signal.reasoning
                )
                
                # 포지션 오픈 (buy 신호인 경우)
                if signal.action == 'buy':
                    self.performance_monitor.open_position(
                        strategy_id=strategy_id,
                        entry_price=signal.price,
                        quantity=signal.suggested_amount / signal.price,
                        side='long'
                    )
            
            return signal
            
            # EnhancedSignal을 TradingSignal로 변환
            if enhanced_signal:
                return TradingSignal(
                    strategy_id=strategy_id,
                    action=enhanced_signal.direction if enhanced_signal.direction != 'neutral' else 'hold',
                    confidence=enhanced_signal.confidence,
                    price=enhanced_signal.entry_price,
                    suggested_amount=enhanced_signal.position_size,
                    reasoning=enhanced_signal.reason,
                    timestamp=datetime.now(),
                    timeframe=strategy.get('timeframe', '1h')
                )
            
            # 기존 간단한 전략들도 여전히 사용
            market_data = self.api.get_market_data("KRW-BTC")
            if not market_data:
                return None
            
            if strategy_id == "h4":  # VWAP 되돌림 전략
                return self._vwap_signal(market_data, strategy)
            
            # 기본 홀드 신호
            return TradingSignal(
                strategy_id=strategy_id,
                action='hold',
                confidence=0.5,
                price=market_data.price if market_data else 0,
                suggested_amount=0,
                reasoning="신호 없음",
                timestamp=datetime.now(),
                timeframe=strategy.get('timeframe', '1h')
            )
            
        except Exception as e:
            self.logger.error(f"신호 생성 오류 {strategy_id}: {e}")
            return None

    def _ema_cross_signal(self, market_data: MarketData, strategy: Dict) -> TradingSignal:
        """EMA 크로스 신호 생성 - 실제 데이터 기반"""
        try:
            # 실제 캔들 데이터 가져오기
            df = self._get_market_dataframe("KRW-BTC", period=50)
            if df is None or len(df) < 26:
                return self._default_hold_signal("h1", market_data.price, "데이터 부족")
            
            # EMA 계산
            df['ema12'] = talib.EMA(df['close'].values, timeperiod=12)
            df['ema26'] = talib.EMA(df['close'].values, timeperiod=26)
            
            # 현재와 이전 값
            current_ema12 = df['ema12'].iloc[-1]
            current_ema26 = df['ema26'].iloc[-1]
            prev_ema12 = df['ema12'].iloc[-2]
            prev_ema26 = df['ema26'].iloc[-2]
            
            # 골든크로스/데드크로스 체크
            if prev_ema12 <= prev_ema26 and current_ema12 > current_ema26:
                # 골든크로스 - 매수 신호
                # 설정 기반 거래 금액 계산
                max_trade_amount = self.config.get_trading_config().get('max_trade_amount', 100000)
                suggested_amount = max_trade_amount * 0.5  # 최대 금액의 50%
                
                return TradingSignal(
                    strategy_id="h1",
                    action='buy',
                    confidence=0.7,
                    price=market_data.price,
                    suggested_amount=int(suggested_amount),
                    reasoning=f"EMA 골든크로스 (12: {current_ema12:,.0f}, 26: {current_ema26:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            elif prev_ema12 >= prev_ema26 and current_ema12 < current_ema26:
                # 데드크로스 - 매도 신호
                return TradingSignal(
                    strategy_id="h1",
                    action='sell',
                    confidence=0.6,
                    price=market_data.price,
                    suggested_amount=0,
                    reasoning=f"EMA 데드크로스 (12: {current_ema12:,.0f}, 26: {current_ema26:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            # 추세 방향에 따른 약한 신호
            if current_ema12 > current_ema26:
                confidence = min(0.5 + abs(current_ema12 - current_ema26) / market_data.price * 10, 0.65)
                return TradingSignal(
                    strategy_id="h1",
                    action='hold',
                    confidence=confidence,
                    price=market_data.price,
                    suggested_amount=0,
                    reasoning=f"상승 추세 유지 (EMA12 > EMA26)",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._default_hold_signal("h1", market_data.price, "EMA 크로스 신호 없음")
            
        except Exception as e:
            self.logger.error(f"EMA 신호 생성 오류: {e}")
            return self._default_hold_signal("h1", market_data.price, f"오류: {e}")
    
    def _default_hold_signal(self, strategy_id: str, price: float, reason: str) -> TradingSignal:
        """기본 홀드 신호"""
        return TradingSignal(
            strategy_id=strategy_id,
            action='hold',
            confidence=0.5,
            price=price,
            suggested_amount=0,
            reasoning=reason,
            timestamp=datetime.now(),
            timeframe="1h"
        )

    def _rsi_divergence_signal(self, df: pd.DataFrame, strategy: Dict) -> TradingSignal:
        """RSI 다이버전스 신호 생성"""
        try:
            if len(df) < 30:
                return self._default_hold_signal("h2", df['close'].iloc[-1], "데이터 부족")
            
            # RSI 계산
            rsi = talib.RSI(df['close'].values, timeperiod=14)
            current_price = df['close'].iloc[-1]
            
            # 최근 20봉에서 고점/저점 찾기
            recent_high_idx = df['high'].iloc[-20:].idxmax()
            recent_low_idx = df['low'].iloc[-20:].idxmin()
            
            # RSI 다이버전스 체크
            if rsi[-1] < 30:  # 과매도 구간
                # 가격은 더 낮은데 RSI는 더 높으면 상승 다이버전스
                if df['low'].iloc[-1] < df['low'].iloc[-10] and rsi[-1] > rsi[-10]:
                    # 설정 기반 거래 금액 계산
                    max_trade_amount = self.config.get_trading_config().get('max_trade_amount', 100000)
                    suggested_amount = max_trade_amount * 0.4  # 최대 금액의 40%
                    
                    return TradingSignal(
                        strategy_id="h2",
                        action='buy',
                        confidence=0.65,
                        price=current_price,
                        suggested_amount=int(suggested_amount),
                        reasoning=f"RSI 상승 다이버전스 (RSI: {rsi[-1]:.1f})",
                        timestamp=datetime.now(),
                        timeframe="1h"
                    )
            elif rsi[-1] > 70:  # 과매수 구간
                # 가격은 더 높은데 RSI는 더 낮으면 하락 다이버전스
                if df['high'].iloc[-1] > df['high'].iloc[-10] and rsi[-1] < rsi[-10]:
                    return TradingSignal(
                        strategy_id="h2",
                        action='sell',
                        confidence=0.6,
                        price=current_price,
                        suggested_amount=0,
                        reasoning=f"RSI 하락 다이버전스 (RSI: {rsi[-1]:.1f})",
                        timestamp=datetime.now(),
                        timeframe="1h"
                    )
            
            return self._default_hold_signal("h2", current_price, f"RSI: {rsi[-1]:.1f} - 신호 없음")
            
        except Exception as e:
            self.logger.error(f"RSI 신호 생성 오류: {e}")
            return self._default_hold_signal("h2", df['close'].iloc[-1], f"오류: {e}")
    
    def _macd_signal(self, df: pd.DataFrame, strategy: Dict) -> TradingSignal:
        """MACD 신호 생성"""
        try:
            if len(df) < 35:
                return self._default_hold_signal("h5", df['close'].iloc[-1], "데이터 부족")
            
            # MACD 계산
            macd, macdsignal, macdhist = talib.MACD(df['close'].values, 
                                                    fastperiod=12, 
                                                    slowperiod=26, 
                                                    signalperiod=9)
            
            current_price = df['close'].iloc[-1]
            
            # MACD 히스토그램 0선 교차
            if macdhist[-2] < 0 and macdhist[-1] > 0:
                # 매수 신호
                # 설정 기반 거래 금액 계산
                max_trade_amount = self.config.get_trading_config().get('max_trade_amount', 100000)
                suggested_amount = max_trade_amount * 0.45  # 최대 금액의 45%
                
                return TradingSignal(
                    strategy_id="h5",
                    action='buy',
                    confidence=0.65,
                    price=current_price,
                    suggested_amount=int(suggested_amount),
                    reasoning=f"MACD 골든크로스 (Hist: {macdhist[-1]:.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            elif macdhist[-2] > 0 and macdhist[-1] < 0:
                # 매도 신호
                return TradingSignal(
                    strategy_id="h5",
                    action='sell',
                    confidence=0.6,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"MACD 데드크로스 (Hist: {macdhist[-1]:.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._default_hold_signal("h5", current_price, f"MACD Hist: {macdhist[-1]:.0f}")
            
        except Exception as e:
            self.logger.error(f"MACD 신호 생성 오류: {e}")
            return self._default_hold_signal("h5", df['close'].iloc[-1], f"오류: {e}")
    
    def _pivot_point_signal(self, df: pd.DataFrame, strategy: Dict) -> TradingSignal:
        """피봇 포인트 신호 생성"""
        try:
            if len(df) < 2:
                return self._default_hold_signal("h3", df['close'].iloc[-1], "데이터 부족")
            
            # 전일 데이터로 피봇 포인트 계산
            prev_high = df['high'].iloc[-2]
            prev_low = df['low'].iloc[-2]
            prev_close = df['close'].iloc[-2]
            current_price = df['close'].iloc[-1]
            
            # 피봇 포인트 계산
            pivot = (prev_high + prev_low + prev_close) / 3
            r1 = 2 * pivot - prev_low
            r2 = pivot + (prev_high - prev_low)
            s1 = 2 * pivot - prev_high
            s2 = pivot - (prev_high - prev_low)
            
            # 지지/저항 근처에서 반등 신호
            # 설정 기반 임계값
            poc_threshold = self.config.get_risk_management_config().get('volume_profile', {}).get('poc_distance_threshold', 0.02)
            pivot_threshold = poc_threshold / 4  # 피봇 포인트는 더 타이트한 임계값 사용
            
            if abs(current_price - s1) / current_price < pivot_threshold:  # S1 근처
                # 설정 기반 거래 금액 계산
                max_trade_amount = self.config.get_trading_config().get('max_trade_amount', 100000)
                suggested_amount = max_trade_amount * 0.35  # 최대 금액의 35%
                
                return TradingSignal(
                    strategy_id="h3",
                    action='buy',
                    confidence=0.6,
                    price=current_price,
                    suggested_amount=int(suggested_amount),
                    reasoning=f"S1 지지선 반등 (S1: {s1:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            elif abs(current_price - r1) / current_price < pivot_threshold:  # R1 근처
                return TradingSignal(
                    strategy_id="h3",
                    action='sell',
                    confidence=0.55,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"R1 저항선 도달 (R1: {r1:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._default_hold_signal("h3", current_price, 
                                            f"PP: {pivot:,.0f}, S1: {s1:,.0f}, R1: {r1:,.0f}")
            
        except Exception as e:
            self.logger.error(f"피봇 포인트 신호 생성 오류: {e}")
            return self._default_hold_signal("h3", df['close'].iloc[-1], f"오류: {e}")
    
    def _vwap_signal(self, market_data: MarketData, strategy: Dict) -> TradingSignal:
        """VWAP 신호 생성"""
        try:
            df = self._get_market_dataframe("KRW-BTC", period=30)
            if df is None or len(df) < 10:
                return self._default_hold_signal("h4", market_data.price, "데이터 부족")
            
            # VWAP 계산
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            current_vwap = vwap.iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # 가격과 VWAP 관계
            distance = (current_price - current_vwap) / current_vwap
            
            if distance < -0.01:  # VWAP 아래 1%
                return TradingSignal(
                    strategy_id="h4",
                    action='buy',
                    confidence=0.6,
                    price=current_price,
                    suggested_amount=int(self.config.get_trading_config().get('max_trade_amount', 100000) * 0.35),
                    reasoning=f"VWAP 하단 매수 기회 (VWAP: {current_vwap:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            elif distance > 0.015:  # VWAP 위 1.5%
                return TradingSignal(
                    strategy_id="h4",
                    action='sell',
                    confidence=0.55,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"VWAP 상단 매도 신호 (VWAP: {current_vwap:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._default_hold_signal("h4", current_price, 
                                            f"VWAP: {current_vwap:,.0f}, 거리: {distance:.1%}")
            
        except Exception as e:
            self.logger.error(f"VWAP 신호 생성 오류: {e}")
            return self._default_hold_signal("h4", market_data.price, f"오류: {e}")
    
    def _open_interest_signal(self, df: pd.DataFrame, strategy: Dict) -> TradingSignal:
        """미체결 약정 신호 (간단 구현)"""
        try:
            current_price = df['close'].iloc[-1]
            # OI 데이터는 실제로 별도 API가 필요함
            # 여기서는 거래량 기반 간단 시뮬레이션
            volume_ma = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            
            if current_volume > volume_ma * 2:
                if df['close'].iloc[-1] > df['close'].iloc[-2]:
                    return TradingSignal(
                        strategy_id="h7",
                        action='buy',
                        confidence=0.6,
                        price=current_price,
                        suggested_amount=int(self.config.get_trading_config().get('max_trade_amount', 100000) * 0.3),
                        reasoning=f"거래량 급증 + 가격 상승",
                        timestamp=datetime.now(),
                        timeframe="1h"
                    )
            
            return self._default_hold_signal("h7", current_price, "OI 신호 없음")
        except Exception as e:
            return self._default_hold_signal("h7", df['close'].iloc[-1], f"오류: {e}")
    
    def _flag_pattern_signal(self, df: pd.DataFrame, strategy: Dict) -> TradingSignal:
        """깃발 패턴 신호 (간단 구현)"""
        try:
            current_price = df['close'].iloc[-1]
            # 실제로는 복잡한 패턴 인식 필요
            # 여기서는 간단한 추세 지속 패턴
            
            if len(df) < 20:
                return self._default_hold_signal("h8", current_price, "데이터 부족")
            
            # 최근 20봉 추세
            trend = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20]
            
            # 최근 5봉 횡보
            recent_range = (df['high'].iloc[-5:].max() - df['low'].iloc[-5:].min()) / df['close'].iloc[-5].mean()
            
            if trend > 0.05 and recent_range < 0.02:  # 상승 추세 후 횡보
                return TradingSignal(
                    strategy_id="h8",
                    action='buy',
                    confidence=0.58,
                    price=current_price,
                    suggested_amount=int(self.config.get_trading_config().get('max_trade_amount', 100000) * 0.25),
                    reasoning="상승 깃발 패턴",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._default_hold_signal("h8", current_price, "패턴 미형성")
        except Exception as e:
            return self._default_hold_signal("h8", df['close'].iloc[-1], f"오류: {e}")
    
    def _daily_strategy_signal(self, strategy_id: str, strategy: Dict) -> TradingSignal:
        """일봉 전략 신호 (통합 간단 구현)"""
        try:
            # 일봉 데이터 가져오기
            df = self._get_daily_dataframe("KRW-BTC", period=50)
            if df is None or len(df) < 20:
                return self._default_hold_signal(strategy_id, 0, "일봉 데이터 부족")
            
            current_price = df['close'].iloc[-1]
            
            if strategy_id == "d1":  # 주봉 필터링 + 50일선
                sma50 = talib.SMA(df['close'].values, timeperiod=min(50, len(df)-1))
                if sma50[-1] > 0 and abs(current_price - sma50[-1]) / sma50[-1] < 0.01:
                    return TradingSignal(
                        strategy_id="d1",
                        action='buy',
                        confidence=0.62,
                        price=current_price,
                        suggested_amount=int(self.config.get_trading_config().get('max_trade_amount', 100000) * 0.6),
                        reasoning=f"50일선 지지 (SMA50: {sma50[-1]:,.0f})",
                        timestamp=datetime.now(),
                        timeframe="1d"
                    )
            
            elif strategy_id == "d4":  # 공포탐욕 RSI
                rsi = talib.RSI(df['close'].values, timeperiod=14)
                if rsi[-1] < 30:
                    return TradingSignal(
                        strategy_id="d4",
                        action='buy',
                        confidence=0.61,
                        price=current_price,
                        suggested_amount=int(self.config.get_trading_config().get('max_trade_amount', 100000) * 0.4),
                        reasoning=f"극도의 공포 구간 (RSI: {rsi[-1]:.1f})",
                        timestamp=datetime.now(),
                        timeframe="1d"
                    )
                elif rsi[-1] > 70:
                    return TradingSignal(
                        strategy_id="d4",
                        action='sell',
                        confidence=0.58,
                        price=current_price,
                        suggested_amount=0,
                        reasoning=f"극도의 탐욕 구간 (RSI: {rsi[-1]:.1f})",
                        timestamp=datetime.now(),
                        timeframe="1d"
                    )
            
            return self._default_hold_signal(strategy_id, current_price, "일봉 신호 없음")
            
        except Exception as e:
            self.logger.error(f"일봉 전략 신호 생성 오류: {e}")
            return self._default_hold_signal(strategy_id, 0, f"오류: {e}")
    
    def _get_daily_dataframe(self, symbol: str, period: int = 50) -> Optional[pd.DataFrame]:
        """일봉 데이터 가져오기"""
        try:
            # 일봉 데이터는 1440분으로 요청
            candles = self.api.get_candles(market=symbol, minutes=1440, count=period)
            
            if not candles or len(candles) < 10:
                return None
            
            df = pd.DataFrame(candles)
            df = df.rename(columns={
                'opening_price': 'open',
                'high_price': 'high', 
                'low_price': 'low',
                'trade_price': 'close',
                'candle_acc_trade_volume': 'volume'
            })
            
            df = df[['open', 'high', 'low', 'close', 'volume']]
            return df
            
        except Exception as e:
            self.logger.error(f"일봉 데이터 가져오기 오류: {e}")
            return None
    
    def _get_historical_dataframe(self, symbol: str, strategy_id: str) -> Optional[pd.DataFrame]:
        """히스토리컬 데이터를 DataFrame으로 가져오기 - 데이터베이스 우선"""
        try:
            # 전략별 적절한 timeframe 설정
            if strategy_id.startswith('h'):  # 시간봉 전략
                timeframe = "60"  # 1시간
                days_back = 30
            elif strategy_id.startswith('d'):  # 일봉 전략
                timeframe = "1440"  # 1일
                days_back = 200
            elif strategy_id == "weekly":  # 주봉 데이터 요청
                timeframe = "10080"  # 1주
                days_back = 365
            else:
                timeframe = "60"
                days_back = 30
            
            # 데이터베이스에서 먼저 조회
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            df = self.data_collector.get_historical_data(
                market=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            # 데이터가 부족하면 API에서 수집
            if df is None or len(df) < 50:
                self.logger.info(f"데이터베이스 데이터 부족, API에서 수집 중...")
                df = self.data_collector.collect_historical_candles(
                    market=symbol,
                    timeframe=timeframe,
                    days_back=days_back
                )
            
            if df is not None and not df.empty:
                # timestamp를 인덱스로 설정
                if 'timestamp' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
                    df.set_index('timestamp', inplace=True)
                
                self.logger.info(f"히스토리컬 데이터 {len(df)}개 로드 완료 (전략: {strategy_id})")
            
            return df
            
        except Exception as e:
            self.logger.error(f"히스토리컬 데이터 DataFrame 생성 오류: {e}")
            return None
    
    def _get_market_dataframe(self, symbol: str, period: int = 100) -> Optional[pd.DataFrame]:
        """시장 데이터를 DataFrame으로 가져오기 - 실제 캔들 데이터 사용"""
        try:
            # Upbit API에서 실제 캔들 데이터 가져오기
            # 시간봉 데이터 사용 (60분)
            candles = self.api.get_candles(market=symbol, minutes=60, count=period)
            
            if not candles or len(candles) < 20:  # 최소 20개 이상의 데이터 필요
                self.logger.warning(f"캔들 데이터 부족: {len(candles) if candles else 0}개")
                return None
            
            # DataFrame 생성
            df = pd.DataFrame(candles)
            
            # 컬럼명 변경 (Upbit API 응답 형식에 맞춤)
            df = df.rename(columns={
                'opening_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'trade_price': 'close',
                'candle_acc_trade_volume': 'volume'
            })
            
            # 필요한 컬럼만 선택
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # 인덱스를 시간으로 설정 (선택사항)
            if 'candle_date_time_kst' in candles[0]:
                df['timestamp'] = pd.to_datetime([c['candle_date_time_kst'] for c in candles])
                df.set_index('timestamp', inplace=True)
            
            self.logger.info(f"실제 캔들 데이터 {len(df)}개 로드 완료")
            
            return df
            
        except Exception as e:
            self.logger.error(f"시장 데이터 DataFrame 생성 오류: {e}")
            return None

    def process_signal(self, signal: TradingSignal):
        """거래 신호 처리"""
        try:
            # 리스크 관리 체크
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                self.logger.warning(f"거래 불가: {reason}")
                return
            
            # 신호 강도 체크
            min_confidence = self.config.get_config('strategies.min_signal_strength')
            if signal.confidence < min_confidence:
                self.logger.info(f"신호 강도 부족: {signal.confidence} < {min_confidence}")
                return
            
            if signal.action == 'buy':
                self.execute_buy_order(signal)
            elif signal.action == 'sell':
                self.execute_sell_order(signal)
                
        except Exception as e:
            self.logger.error(f"신호 처리 오류: {e}")

    def execute_buy_order(self, signal: TradingSignal):
        """매수 주문 실행"""
        try:
            balance = self.api.get_balance("KRW")
            if balance < 10000:
                self.logger.warning("매수할 원화 잔고 부족")
                return
            
            # 포지션 크기 계산
            position_size = self.risk_manager.calculate_position_size(signal, balance)
            
            # 주문 실행
            result = self.api.place_buy_order("KRW-BTC", signal.price, amount=position_size)
            
            if result.success:
                self.logger.info(f"매수 주문 성공: {result.order_id} - {position_size:,.0f}원")
                
                # 거래 기록 추가
                trade_record = TradeRecord(
                    strategy_id=signal.strategy_id,
                    entry_time=datetime.now(),
                    exit_time=None,
                    entry_price=signal.price,
                    exit_price=None,
                    position_size=position_size / signal.price,
                    side='long',
                    pnl=None,
                    fees=position_size * 0.0005,  # 0.05% 수수료
                    status='open'
                )
                
                self.strategy_manager.add_trade_record(trade_record)
                self.pending_orders[result.order_id] = {
                    'trade_record': trade_record,
                    'signal': signal,
                    'timestamp': datetime.now()
                }
                
            else:
                self.logger.error(f"매수 주문 실패: {result.message}")
                
        except Exception as e:
            self.logger.error(f"매수 주문 실행 오류: {e}")

    def execute_sell_order(self, signal: TradingSignal):
        """매도 주문 실행"""
        try:
            btc_balance = self.api.get_balance("BTC")
            if btc_balance < 0.0001:  # 최소 거래 단위
                self.logger.warning("매도할 BTC 잔고 부족")
                return
            
            # 주문 실행
            result = self.api.place_sell_order("KRW-BTC", signal.price, btc_balance)
            
            if result.success:
                self.logger.info(f"매도 주문 성공: {result.order_id} - {btc_balance:.8f}BTC")
                
            else:
                self.logger.error(f"매도 주문 실패: {result.message}")
                
        except Exception as e:
            self.logger.error(f"매도 주문 실행 오류: {e}")

    def monitor_positions(self):
        """포지션 모니터링 - 통합 관리"""
        try:
            # 1. 미체결 주문 확인
            for order_id, order_info in list(self.pending_orders.items()):
                order_status = self.api.get_order_status(order_id)
                if order_status and order_status.get('state') == 'done':
                    self.logger.info(f"주문 체결 완료: {order_id}")
                    del self.pending_orders[order_id]
            
            # 2. 현재가 업데이트
            current_price = self.api.get_current_price("KRW-BTC")
            if current_price:
                current_prices = {"KRW-BTC": current_price}
                self.position_manager.update_positions(current_prices)
            
            # 3. 포지션 요약 정보 로깅 (주기적)
            if datetime.now().minute % 10 == 0:  # 10분마다
                summary = self.position_manager.get_position_summary()
                self.logger.info(
                    f"포지션 요약: {summary.total_positions}개 포지션, "
                    f"총노출: {summary.total_exposure:,.0f}, "
                    f"미실현손익: {summary.unrealized_pnl:+,.0f}, "
                    f"리스크레벨: {summary.risk_level}"
                )
            
        except Exception as e:
            self.logger.error(f"포지션 모니터링 오류: {e}")

    def process_pending_orders(self):
        """미체결 주문 처리"""
        # 타임아웃된 주문 취소 등의 로직
        timeout_minutes = self.config.get_config('strategies.signal_timeout_minutes')
        cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
        
        for order_id, order_info in list(self.pending_orders.items()):
            if order_info['timestamp'] < cutoff_time:
                self.logger.info(f"주문 타임아웃으로 취소: {order_id}")
                self.api.cancel_order(order_id)
                del self.pending_orders[order_id]

# 실행 함수
def main():
    """메인 실행 함수"""
    print("=== Bitcoin Auto Trading System v2.0 ===")
    print("모의거래 모드로 시작합니다.")
    
    try:
        engine = TradingEngine()
        engine.start()
    except KeyboardInterrupt:
        print("\n시스템 종료 중...")
    except Exception as e:
        print(f"시스템 오류: {e}")
    finally:
        print("시스템 종료 완료")

if __name__ == "__main__":
    # 로그 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    main()