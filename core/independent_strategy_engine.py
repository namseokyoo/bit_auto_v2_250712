"""
독립 전략 엔진 (Independent Strategy Engine)
각 전략이 독립적으로 매수/매도/홀드 신호를 생성하는 시스템
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

from core.upbit_api import UpbitAPI
from core.candle_data_collector import candle_collector
from core.technical_indicators import TechnicalIndicators
from config.config_manager import config_manager


class StrategySignal(Enum):
    """전략 신호 타입"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategyVote:
    """전략 투표 결과"""
    strategy_id: str
    strategy_name: str
    signal: StrategySignal
    confidence: float  # 0.0 ~ 1.0 (신뢰도)
    strength: float  # 0.0 ~ 1.0 (신호 강도)
    reasoning: str  # 근거/이유
    indicators: Dict[str, float]  # 사용된 지표값들
    timestamp: datetime
    
    def __post_init__(self):
        # 유효성 검사
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"Strength must be between 0.0 and 1.0, got {self.strength}")


class IndependentStrategy(ABC):
    """독립 전략 기본 클래스"""
    
    def __init__(self, strategy_id: str, strategy_name: str, enabled: bool = True):
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.enabled = enabled
        self.logger = logging.getLogger(f'Strategy_{strategy_id}')
        self.indicators = TechnicalIndicators()
        
    @abstractmethod
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """
        시장 데이터를 분석하여 투표 결과 반환
        
        Args:
            market_data: 시장 데이터 (캔들, 현재가 등)
            config: 전략별 설정 파라미터
            
        Returns:
            StrategyVote: 전략의 투표 결과
        """
        pass
    
    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """전략의 기본 설정값 반환"""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """설정값 유효성 검사"""
        try:
            default_config = self.get_default_config()
            for key in default_config:
                if key not in config:
                    self.logger.warning(f"Missing config key: {key}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Config validation error: {e}")
            return False
    
    def _create_vote(self, signal: StrategySignal, confidence: float, strength: float, 
                     reasoning: str, indicators: Dict[str, float]) -> StrategyVote:
        """투표 결과 생성 헬퍼"""
        return StrategyVote(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            signal=signal,
            confidence=confidence,
            strength=strength,
            reasoning=reasoning,
            indicators=indicators,
            timestamp=datetime.now()
        )
    
    def _safe_get_candles(self, timeframe: str, period: int, count: int) -> Optional[List[Dict]]:
        """안전한 캔들 데이터 조회"""
        try:
            if timeframe == "minutes":
                return candle_collector.get_candles_cached("minutes", period, count)
            elif timeframe == "hours":
                return candle_collector.get_candles_cached("minutes", 60, count)
            elif timeframe == "days":
                return candle_collector.get_candles_cached("days", 1, count)
            else:
                self.logger.error(f"Unsupported timeframe: {timeframe}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to get candles: {e}")
            return None


class VotingDecision:
    """투표 결과 종합 결정"""
    
    def __init__(self, final_signal: StrategySignal, confidence: float, 
                 total_votes: int, vote_distribution: Dict[str, int],
                 contributing_strategies: List[StrategyVote], reasoning: str):
        self.final_signal = final_signal
        self.confidence = confidence
        self.total_votes = total_votes
        self.vote_distribution = vote_distribution  # {"buy": 3, "sell": 1, "hold": 2}
        self.contributing_strategies = contributing_strategies
        self.reasoning = reasoning
        self.timestamp = datetime.now()


class VotingManager:
    """전략 투표 관리자"""
    
    def __init__(self):
        self.logger = logging.getLogger('VotingManager')
        self.strategy_weights = {}  # 전략별 가중치
        
    def set_strategy_weight(self, strategy_id: str, weight: float):
        """전략별 가중치 설정 (0.0 ~ 1.0)"""
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {weight}")
        self.strategy_weights[strategy_id] = weight
    
    def calculate_weighted_decision(self, votes: List[StrategyVote], 
                                  config: Dict[str, Any]) -> VotingDecision:
        """가중 투표로 최종 결정 계산"""
        if not votes:
            return self._create_hold_decision("No votes received")
        
        # 설정값 로드
        buy_threshold = config.get('buy_threshold', 0.6)
        sell_threshold = config.get('sell_threshold', -0.6)
        min_participation = config.get('min_participation_rate', 0.7)
        
        # 활성화된 전략 수 확인
        total_strategies = len(self.strategy_weights)
        active_votes = len(votes)
        
        if active_votes < total_strategies * min_participation:
            return self._create_hold_decision(
                f"Insufficient participation: {active_votes}/{total_strategies}"
            )
        
        # 가중 점수 계산
        weighted_scores = {"buy": 0.0, "sell": 0.0, "hold": 0.0}
        total_weight = 0.0
        
        for vote in votes:
            weight = self.strategy_weights.get(vote.strategy_id, 1.0)
            score = weight * vote.confidence
            
            if vote.signal == StrategySignal.BUY:
                weighted_scores["buy"] += score
            elif vote.signal == StrategySignal.SELL:
                weighted_scores["sell"] += score
            else:
                weighted_scores["hold"] += score
            
            total_weight += weight
        
        # 정규화
        if total_weight > 0:
            for key in weighted_scores:
                weighted_scores[key] /= total_weight
        
        # 최종 결정
        net_score = weighted_scores["buy"] - weighted_scores["sell"]
        
        if net_score >= buy_threshold:
            final_signal = StrategySignal.BUY
            confidence = min(net_score, 1.0)
        elif net_score <= sell_threshold:
            final_signal = StrategySignal.SELL
            confidence = min(abs(net_score), 1.0)
        else:
            final_signal = StrategySignal.HOLD
            confidence = weighted_scores["hold"]
        
        # 투표 분포 계산
        vote_distribution = {"buy": 0, "sell": 0, "hold": 0}
        for vote in votes:
            vote_distribution[vote.signal.value] += 1
        
        reasoning = self._generate_decision_reasoning(
            final_signal, net_score, weighted_scores, vote_distribution
        )
        
        return VotingDecision(
            final_signal=final_signal,
            confidence=confidence,
            total_votes=len(votes),
            vote_distribution=vote_distribution,
            contributing_strategies=votes,
            reasoning=reasoning
        )
    
    def _create_hold_decision(self, reason: str) -> VotingDecision:
        """홀드 결정 생성"""
        return VotingDecision(
            final_signal=StrategySignal.HOLD,
            confidence=0.0,
            total_votes=0,
            vote_distribution={"buy": 0, "sell": 0, "hold": 1},
            contributing_strategies=[],
            reasoning=reason
        )
    
    def _generate_decision_reasoning(self, signal: StrategySignal, net_score: float,
                                   weighted_scores: Dict[str, float], 
                                   vote_distribution: Dict[str, int]) -> str:
        """결정 근거 생성"""
        total_votes = sum(vote_distribution.values())
        
        reasoning_parts = [
            f"총 {total_votes}개 전략 투표",
            f"분포: 매수({vote_distribution['buy']}) 매도({vote_distribution['sell']}) 홀드({vote_distribution['hold']})",
            f"가중 점수: {net_score:.3f}",
            f"최종 결정: {signal.value.upper()}"
        ]
        
        if signal == StrategySignal.BUY:
            reasoning_parts.append(f"매수 신호 우세 (가중점수 >= 0.6)")
        elif signal == StrategySignal.SELL:
            reasoning_parts.append(f"매도 신호 우세 (가중점수 <= -0.6)")
        else:
            reasoning_parts.append(f"중립/불확실한 신호")
        
        return " | ".join(reasoning_parts)


class IndependentStrategyEngine:
    """독립 전략 엔진 메인 클래스"""
    
    def __init__(self, upbit_api: UpbitAPI):
        self.upbit_api = upbit_api
        self.logger = logging.getLogger('IndependentStrategyEngine')
        self.strategies: Dict[str, IndependentStrategy] = {}
        self.voting_manager = VotingManager()
        self._load_config()
        
    def _load_config(self):
        """설정 로드"""
        try:
            config = config_manager.get_config('independent_strategies') or {}
            self.config = {
                'buy_threshold': config.get('buy_threshold', 0.6),
                'sell_threshold': config.get('sell_threshold', -0.6),
                'min_participation_rate': config.get('min_participation_rate', 0.7),
                'enabled': config.get('enabled', True)
            }
            
            # 전략별 가중치 로드
            weights = config.get('strategy_weights', {})
            for strategy_id, weight in weights.items():
                self.voting_manager.set_strategy_weight(strategy_id, weight)
                
        except Exception as e:
            self.logger.error(f"Config load error: {e}")
            # 기본값 사용
            self.config = {
                'buy_threshold': 0.6,
                'sell_threshold': -0.6,
                'min_participation_rate': 0.7,
                'enabled': True
            }
    
    def register_strategy(self, strategy: IndependentStrategy, weight: float = 1.0):
        """전략 등록"""
        self.strategies[strategy.strategy_id] = strategy
        self.voting_manager.set_strategy_weight(strategy.strategy_id, weight)
        self.logger.info(f"Strategy registered: {strategy.strategy_name} (weight: {weight})")
    
    def analyze_market(self) -> Optional[VotingDecision]:
        """시장 분석 및 투표 결정"""
        if not self.config.get('enabled', True):
            self.logger.info("Independent strategy engine is disabled")
            return None
        
        try:
            # 시장 데이터 수집
            market_data = self._collect_market_data()
            if not market_data:
                self.logger.warning("Failed to collect market data")
                return None
            
            # 각 전략에서 투표 수집
            votes = []
            for strategy_id, strategy in self.strategies.items():
                if not strategy.enabled:
                    continue
                
                try:
                    strategy_config = self._get_strategy_config(strategy_id)
                    vote = strategy.analyze(market_data, strategy_config)
                    votes.append(vote)
                    
                    self.logger.debug(
                        f"Strategy {strategy_id}: {vote.signal.value} "
                        f"(confidence: {vote.confidence:.3f}, strength: {vote.strength:.3f})"
                    )
                    
                except Exception as e:
                    self.logger.error(f"Strategy {strategy_id} analysis failed: {e}")
                    continue
            
            # 투표 결과 계산
            decision = self.voting_manager.calculate_weighted_decision(votes, self.config)
            
            self.logger.info(
                f"Voting decision: {decision.final_signal.value} "
                f"(confidence: {decision.confidence:.3f}, votes: {decision.total_votes})"
            )
            
            return decision
            
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
            return None
    
    def _collect_market_data(self) -> Optional[Dict[str, Any]]:
        """시장 데이터 수집"""
        try:
            # 다양한 시간대 캔들 데이터 수집
            candles_1m = candle_collector.get_candles_cached("minutes", 1, 100)
            candles_5m = candle_collector.get_candles_cached("minutes", 5, 100) 
            candles_15m = candle_collector.get_candles_cached("minutes", 15, 100)
            candles_1h = candle_collector.get_candles_cached("minutes", 60, 100)
            
            # 현재가 정보
            ticker = self.upbit_api._make_request('GET', '/v1/ticker', {'markets': 'KRW-BTC'})
            current_price = float(ticker[0]['trade_price']) if ticker else None
            
            market_data = {
                'candles_1m': candles_1m,
                'candles_5m': candles_5m,
                'candles_15m': candles_15m,
                'candles_1h': candles_1h,
                'current_price': current_price,
                'timestamp': datetime.now()
            }
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Market data collection failed: {e}")
            return None
    
    def _get_strategy_config(self, strategy_id: str) -> Dict[str, Any]:
        """전략별 설정 조회"""
        try:
            strategies_config = config_manager.get_config('independent_strategies.strategies') or {}
            strategy_config = strategies_config.get(strategy_id, {})
            
            # 기본값과 병합
            if strategy_id in self.strategies:
                default_config = self.strategies[strategy_id].get_default_config()
                for key, value in default_config.items():
                    if key not in strategy_config:
                        strategy_config[key] = value
            
            return strategy_config
            
        except Exception as e:
            self.logger.error(f"Failed to get strategy config for {strategy_id}: {e}")
            return {}
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """전략 엔진 요약 정보"""
        return {
            'total_strategies': len(self.strategies),
            'enabled_strategies': len([s for s in self.strategies.values() if s.enabled]),
            'strategy_list': [
                {
                    'id': strategy.strategy_id,
                    'name': strategy.strategy_name,
                    'enabled': strategy.enabled,
                    'weight': self.voting_manager.strategy_weights.get(strategy.strategy_id, 1.0)
                }
                for strategy in self.strategies.values()
            ],
            'config': self.config
        }
