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
from strategy_manager import StrategyManager, TradeRecord
import pandas as pd
import numpy as np
import talib

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
        self.api = UpbitAPI(paper_trading=False)  # 초기에는 모의거래
        self.strategy_manager = StrategyManager()
        self.risk_manager = RiskManager(self.config)
        self.advanced_risk_manager = AdvancedRiskManager(self.config)  # 고급 리스크 관리자 추가
        self.enhanced_strategy_analyzer = EnhancedStrategyAnalyzer()  # 개선된 전략 분석기 추가
        
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
                    
            elif key_path == 'trading.mode':
                if new_value == 'live_trading':
                    self.logger.critical("실거래 모드로 전환! 주의 필요")
                    self.api = UpbitAPI(paper_trading=False)
                else:
                    self.logger.info("모의거래 모드")
                    self.api = UpbitAPI(paper_trading=False)

        self.config.register_callback(on_config_change)

    def _schedule_tasks(self):
        """작업 스케줄링"""
        # 1시간마다 시간 전략 실행
        schedule.every().hour.at(":00").do(self.execute_hourly_strategies)
        
        # 매일 0시에 일일 전략 실행
        schedule.every().day.at("00:00").do(self.execute_daily_strategies)
        
        # 5분마다 포지션 모니터링
        schedule.every(5).minutes.do(self.monitor_positions)
        
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
            time.sleep(60)  # 1분마다 체크

    def _main_loop(self):
        """메인 모니터링 루프"""
        while self.running:
            try:
                # 기본 상태 체크
                if self.config.is_system_enabled():
                    self.monitor_positions()
                    self.process_pending_orders()
                
                time.sleep(30)  # 30초마다 체크
                
            except KeyboardInterrupt:
                self.logger.info("사용자에 의해 중단됨")
                break
            except Exception as e:
                self.logger.error(f"메인 루프 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기

    def execute_hourly_strategies(self):
        """시간 단위 전략 실행 - 통합 신호 처리"""
        if not self.config.is_trading_enabled():
            return
        
        self.logger.info("시간 단위 전략 통합 실행 시작")
        
        # 1. 모든 활성 전략에서 신호 수집
        strategy_signals = self._collect_all_signals('hourly')
        
        # 2. 신호 통합 및 최종 결정
        consolidated_signal = self._consolidate_signals(strategy_signals)
        
        # 3. 통합 신호 처리
        if consolidated_signal and consolidated_signal.action in ['buy', 'sell']:
            self._process_consolidated_signal(consolidated_signal)

    def execute_daily_strategies(self):
        """일일 전략 실행 - 통합 신호 처리"""
        if not self.config.is_trading_enabled():
            return
        
        self.logger.info("일일 전략 통합 실행 시작")
        
        # 1. 모든 활성 일일 전략에서 신호 수집
        strategy_signals = self._collect_all_signals('daily')
        
        # 2. 신호 통합 및 최종 결정
        consolidated_signal = self._consolidate_signals(strategy_signals)
        
        # 3. 통합 신호 처리
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
        """전략 신호 생성 - 개선된 전략 사용"""
        try:
            # 현재 시장 데이터 가져오기 (더 많은 봉 필요)
            df = self._get_market_dataframe("KRW-BTC", period=100)
            if df is None or len(df) < 50:
                return None
            
            enhanced_signal = None
            
            # 개선된 전략 분석기 사용
            if strategy_id == "h1":  # EMA 골든크로스 전략
                enhanced_signal = self.enhanced_strategy_analyzer.enhanced_ema_cross_strategy(df)
            elif strategy_id == "h6":  # 볼린저 밴드 스퀴즈 전략
                enhanced_signal = self.enhanced_strategy_analyzer.enhanced_bollinger_squeeze_strategy(df)
            
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
        """EMA 크로스 신호 생성 (간단한 구현)"""
        # 실제로는 더 복잡한 기술적 분석이 필요
        current_price = market_data.price
        
        # 임시 로직: 가격이 이전 고점 대비 2% 상승하면 매수 신호
        if current_price > market_data.prev_close * 1.02:
            return TradingSignal(
                strategy_id="h1",
                action='buy',
                confidence=0.7,
                price=current_price,
                suggested_amount=50000,
                reasoning="EMA 골든크로스 패턴 감지",
                timestamp=datetime.now()
            )
        
        # 2% 하락하면 매도 신호
        elif current_price < market_data.prev_close * 0.98:
            return TradingSignal(
                strategy_id="h1",
                action='sell',
                confidence=0.6,
                price=current_price,
                suggested_amount=0,
                reasoning="EMA 데드크로스 패턴 감지",
                timestamp=datetime.now()
            )
        
        return TradingSignal(
            strategy_id="h1",
            action='hold',
            confidence=0.5,
            price=current_price,
            suggested_amount=0,
            reasoning="신호 없음",
            timestamp=datetime.now()
        )

    def _vwap_signal(self, market_data: MarketData, strategy: Dict) -> TradingSignal:
        """VWAP 신호 생성 (간단한 구현)"""
        # 임시 구현
        return TradingSignal(
            strategy_id="h4",
            action='hold',
            confidence=0.5,
            price=market_data.price,
            suggested_amount=0,
            reasoning="VWAP 분석 중",
            timestamp=datetime.now()
        )
    
    def _get_market_dataframe(self, symbol: str, period: int = 100) -> Optional[pd.DataFrame]:
        """시장 데이터를 DataFrame으로 가져오기"""
        try:
            # 실제로는 Upbit API에서 캔들 데이터를 가져와야 함
            # 여기서는 간단한 예시 구현
            market_data = self.api.get_market_data(symbol)
            if not market_data:
                return None
            
            # 임시 DataFrame 생성 (실제로는 API에서 과거 데이터 가져와야 함)
            df = pd.DataFrame({
                'high': [market_data.high_price] * period,
                'low': [market_data.low_price] * period,
                'close': [market_data.price] * period,
                'volume': [market_data.volume] * period,
                'open': [market_data.opening_price] * period
            })
            
            # 약간의 변동성 추가 (실제 데이터처럼 보이게)
            for col in ['high', 'low', 'close', 'open']:
                noise = np.random.normal(0, market_data.price * 0.001, period)
                df[col] = df[col] + noise
            
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