"""
신호 통합 엔진
여러 전략의 신호를 수집하고 통합하여 최종 거래 결정을 내리는 시스템
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

@dataclass
class TradingSignal:
    strategy_id: str
    action: str  # 'buy', 'sell', 'hold'
    confidence: float  # 0.0 ~ 1.0
    price: float
    suggested_amount: float
    reasoning: str
    timestamp: datetime
    timeframe: str  # '15m', '1h', '1d'
    priority: int = 1  # 1=highest, 5=lowest

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class MarketCondition(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"

@dataclass
class ConsolidatedSignal:
    action: str
    confidence: float
    suggested_amount: float
    reasoning: str
    contributing_strategies: List[str]
    final_score: float
    market_condition: MarketCondition
    timestamp: datetime

class SignalManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = self._setup_logger()
        self.signal_history = []
        self.max_history_size = 1000
        
        # 전략별 성능 가중치 (동적으로 조정됨)
        self.performance_weights = {}
        
        # 시장 상황별 전략 효과성
        self.market_strategy_effectiveness = {
            MarketCondition.TRENDING_UP: {
                'h1': 1.2, 'h5': 1.3, 'd1': 1.4, 'd5': 1.3  # 추세추종 전략 강화
            },
            MarketCondition.TRENDING_DOWN: {
                'h2': 1.3, 'd4': 1.4, 'd6': 1.2  # 역추세/감정 전략 강화
            },
            MarketCondition.SIDEWAYS: {
                'h3': 1.4, 'h6': 1.3, 'h2': 1.2  # 지지저항/역추세 전략 강화
            },
            MarketCondition.HIGH_VOLATILITY: {
                'h8': 1.3, 'd3': 1.4  # 돌파/변동성 전략 강화
            },
            MarketCondition.LOW_VOLATILITY: {
                'h3': 1.2, 'h4': 1.3  # 안정적 전략 강화
            }
        }

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('SignalManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def collect_signals(self, strategy_signals: Dict[str, TradingSignal]) -> List[TradingSignal]:
        """활성 전략들로부터 신호 수집"""
        valid_signals = []
        min_confidence = self.config.get_config('strategies.min_signal_strength')
        
        for strategy_id, signal in strategy_signals.items():
            if signal and signal.confidence >= min_confidence:
                # 시간 기반 신호 유효성 검증
                signal_age = datetime.now() - signal.timestamp
                timeout_minutes = self.config.get_config('strategies.signal_timeout_minutes')
                
                if signal_age.total_seconds() <= timeout_minutes * 60:
                    valid_signals.append(signal)
                    self.logger.debug(f"신호 수집: {strategy_id} - {signal.action} (신뢰도: {signal.confidence:.2f})")
                else:
                    self.logger.warning(f"신호 만료: {strategy_id} (나이: {signal_age})")
        
        return valid_signals

    def detect_market_condition(self, market_data) -> MarketCondition:
        """현재 시장 상황 분석"""
        try:
            if not market_data:
                return MarketCondition.SIDEWAYS
            
            # 간단한 시장 상황 분석 (실제로는 더 복잡한 로직 필요)
            price_change = (market_data.price - market_data.prev_close) / market_data.prev_close
            volatility = abs(market_data.high - market_data.low) / market_data.open
            
            # 변동성 기준
            if volatility > 0.05:  # 5% 이상
                return MarketCondition.HIGH_VOLATILITY
            elif volatility < 0.02:  # 2% 미만
                return MarketCondition.LOW_VOLATILITY
            
            # 추세 기준
            if price_change > 0.02:  # 2% 이상 상승
                return MarketCondition.TRENDING_UP
            elif price_change < -0.02:  # 2% 이상 하락
                return MarketCondition.TRENDING_DOWN
            else:
                return MarketCondition.SIDEWAYS
                
        except Exception as e:
            self.logger.error(f"시장 상황 분석 오류: {e}")
            return MarketCondition.SIDEWAYS

    def calculate_strategy_weight(self, strategy_id: str, market_condition: MarketCondition) -> float:
        """전략별 가중치 계산"""
        # 기본 설정 가중치
        base_weight = self.config.get_config(f'strategies.strategy_weights.{strategy_id}') or 0.1
        
        # 시장 상황별 효과성 가중치
        market_multiplier = self.market_strategy_effectiveness.get(market_condition, {}).get(strategy_id, 1.0)
        
        # 성능 기반 가중치 (과거 성과 반영)
        performance_multiplier = self.performance_weights.get(strategy_id, 1.0)
        
        final_weight = base_weight * market_multiplier * performance_multiplier
        
        return min(final_weight, 2.0)  # 최대 2배까지만 가중치 적용

    def resolve_signal_conflicts(self, signals: List[TradingSignal], market_condition: MarketCondition) -> ConsolidatedSignal:
        """신호 충돌 해결 및 통합"""
        if not signals:
            return ConsolidatedSignal(
                action='hold',
                confidence=0.0,
                suggested_amount=0.0,
                reasoning="신호 없음",
                contributing_strategies=[],
                final_score=0.0,
                market_condition=market_condition,
                timestamp=datetime.now()
            )

        # 신호별 가중 점수 계산
        buy_score = 0.0
        sell_score = 0.0
        buy_strategies = []
        sell_strategies = []
        total_weight = 0.0
        
        for signal in signals:
            weight = self.calculate_strategy_weight(signal.strategy_id, market_condition)
            weighted_confidence = signal.confidence * weight
            total_weight += weight
            
            if signal.action == 'buy':
                buy_score += weighted_confidence
                buy_strategies.append(signal.strategy_id)
            elif signal.action == 'sell':
                sell_score += weighted_confidence
                sell_strategies.append(signal.strategy_id)
        
        # 정규화
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
        
        # 최종 결정
        decision_threshold = self.config.get_config('strategies.min_signal_strength')
        
        if buy_score > sell_score and buy_score >= decision_threshold:
            # 매수 결정
            suggested_amount = self._calculate_position_size(signals, buy_score)
            return ConsolidatedSignal(
                action='buy',
                confidence=buy_score,
                suggested_amount=suggested_amount,
                reasoning=f"매수 신호 통합 (가중점수: {buy_score:.2f}, 기여전략: {buy_strategies})",
                contributing_strategies=buy_strategies,
                final_score=buy_score,
                market_condition=market_condition,
                timestamp=datetime.now()
            )
        
        elif sell_score > buy_score and sell_score >= decision_threshold:
            # 매도 결정
            return ConsolidatedSignal(
                action='sell',
                confidence=sell_score,
                suggested_amount=0.0,  # 매도는 전량
                reasoning=f"매도 신호 통합 (가중점수: {sell_score:.2f}, 기여전략: {sell_strategies})",
                contributing_strategies=sell_strategies,
                final_score=sell_score,
                market_condition=market_condition,
                timestamp=datetime.now()
            )
        
        else:
            # 홀드 결정
            return ConsolidatedSignal(
                action='hold',
                confidence=max(buy_score, sell_score),
                suggested_amount=0.0,
                reasoning=f"신호 불충분 (매수:{buy_score:.2f}, 매도:{sell_score:.2f}, 임계값:{decision_threshold})",
                contributing_strategies=buy_strategies + sell_strategies,
                final_score=0.0,
                market_condition=market_condition,
                timestamp=datetime.now()
            )

    def _calculate_position_size(self, signals: List[TradingSignal], confidence: float) -> float:
        """신호 강도와 리스크 관리를 고려한 포지션 크기 계산"""
        max_trade_amount = self.config.get_config('trading.max_trade_amount')
        
        # 신호 강도에 따른 크기 조정
        confidence_multiplier = min(confidence, 1.0)
        
        # 여러 전략이 동의할수록 크기 증가
        strategy_agreement_bonus = min(len(signals) / 5.0, 0.3)  # 최대 30% 보너스
        
        final_multiplier = confidence_multiplier * (1.0 + strategy_agreement_bonus)
        suggested_amount = max_trade_amount * final_multiplier
        
        return min(suggested_amount, max_trade_amount)

    def update_strategy_performance(self, strategy_id: str, performance_metrics: Dict):
        """전략 성과에 따른 가중치 업데이트"""
        try:
            win_rate = performance_metrics.get('win_rate', 0.5)
            sharpe_ratio = performance_metrics.get('sharpe_ratio', 0.0)
            profit_factor = performance_metrics.get('profit_factor', 1.0)
            
            # 성과 기반 가중치 계산
            performance_score = (win_rate * 0.4 + 
                               min(sharpe_ratio / 2.0, 0.3) * 0.3 + 
                               min(profit_factor / 2.0, 0.3) * 0.3)
            
            # 0.5 ~ 1.5 범위로 제한
            self.performance_weights[strategy_id] = max(0.5, min(1.5, performance_score))
            
            self.logger.info(f"전략 {strategy_id} 성과 가중치 업데이트: {self.performance_weights[strategy_id]:.2f}")
            
        except Exception as e:
            self.logger.error(f"성과 가중치 업데이트 오류: {e}")

    def log_signal_decision(self, consolidated_signal: ConsolidatedSignal):
        """신호 결정 과정 로깅"""
        self.signal_history.append(consolidated_signal)
        
        # 히스토리 크기 제한
        if len(self.signal_history) > self.max_history_size:
            self.signal_history = self.signal_history[-self.max_history_size:]
        
        self.logger.info(
            f"신호 통합 완료: {consolidated_signal.action.upper()} "
            f"(신뢰도: {consolidated_signal.confidence:.2f}, "
            f"시장상황: {consolidated_signal.market_condition.value}, "
            f"기여전략: {consolidated_signal.contributing_strategies})"
        )

    def get_signal_statistics(self) -> Dict:
        """신호 통계 정보 반환"""
        if not self.signal_history:
            return {"message": "신호 히스토리 없음"}
        
        recent_signals = self.signal_history[-100:]  # 최근 100개
        
        buy_signals = len([s for s in recent_signals if s.action == 'buy'])
        sell_signals = len([s for s in recent_signals if s.action == 'sell'])
        hold_signals = len([s for s in recent_signals if s.action == 'hold'])
        
        avg_confidence = np.mean([s.confidence for s in recent_signals])
        
        return {
            "total_signals": len(recent_signals),
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "hold_signals": hold_signals,
            "avg_confidence": avg_confidence,
            "performance_weights": self.performance_weights.copy()
        }

# 사용 예시
if __name__ == "__main__":
    from config.config_manager import config_manager
    
    signal_manager = SignalManager(config_manager)
    
    # 테스트 신호들
    test_signals = {
        'h1': TradingSignal(
            strategy_id='h1',
            action='buy',
            confidence=0.8,
            price=50000000,
            suggested_amount=config_manager.get_trading_config().get('max_trade_amount', 100000),
            reasoning='EMA 골든크로스',
            timestamp=datetime.now(),
            timeframe='1h'
        ),
        'h4': TradingSignal(
            strategy_id='h4',
            action='buy',
            confidence=0.6,
            price=50000000,
            suggested_amount=int(config_manager.get_trading_config().get('max_trade_amount', 100000) * 0.8),
            reasoning='VWAP 지지',
            timestamp=datetime.now(),
            timeframe='1h'
        )
    }
    
    # 신호 수집 및 통합
    valid_signals = signal_manager.collect_signals(test_signals)
    market_condition = MarketCondition.TRENDING_UP
    
    consolidated = signal_manager.resolve_signal_conflicts(valid_signals, market_condition)
    signal_manager.log_signal_decision(consolidated)
    
    print(f"통합 신호: {consolidated.action} (신뢰도: {consolidated.confidence:.2f})")
    print(f"제안 금액: {consolidated.suggested_amount:,.0f}")
    print(f"사유: {consolidated.reasoning}")