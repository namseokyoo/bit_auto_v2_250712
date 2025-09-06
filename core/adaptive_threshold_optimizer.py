"""
적응형 임계값 최적화 시스템
시장 상황과 전략 성과에 따라 실시간으로 임계값을 조정하는 AI 기반 시스템
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import sqlite3

from config.config_manager import config_manager


class MarketRegime(Enum):
    """시장 체제"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass
class ThresholdAdjustment:
    """임계값 조정 결과"""
    strategy_id: str
    parameter: str
    old_value: float
    new_value: float
    adjustment_reason: str
    confidence: float
    expected_impact: str


@dataclass
class MarketAnalysis:
    """시장 분석 결과"""
    regime: MarketRegime
    volatility: float
    trend_strength: float
    volume_profile: str
    momentum: float
    confidence: float


class AdaptiveThresholdOptimizer:
    """적응형 임계값 최적화기"""
    
    def __init__(self):
        self.logger = logging.getLogger('AdaptiveThresholdOptimizer')
        self.config = config_manager
        
        # 전략별 기본 임계값 설정
        self.strategy_thresholds = {
            'rsi_momentum': {
                'oversold': 30,
                'overbought': 70,
                'momentum_threshold': 0.02,
                'volume_threshold': 1.5
            },
            'bollinger_band': {
                'std_dev': 2.0,
                'volume_threshold': 1.3,
                'breakout_threshold': 0.01
            },
            'support_resistance': {
                'strength_threshold': 0.8,
                'volume_threshold': 1.2,
                'break_threshold': 0.005
            },
            'ema_crossover': {
                'volume_threshold': 1.2,
                'min_crossover_strength': 0.001
            },
            'macd': {
                'signal_threshold': 0.0001,
                'volume_threshold': 1.1,
                'divergence_threshold': 0.5
            },
            'stochastic': {
                'oversold': 20,
                'overbought': 80,
                'volume_threshold': 1.2
            },
            'williams_r': {
                'oversold': -80,
                'overbought': -20,
                'volume_threshold': 1.1
            },
            'cci': {
                'oversold': -100,
                'overbought': 100,
                'volume_threshold': 1.1
            },
            'volume_surge': {
                'surge_threshold': 2.0,
                'price_threshold': 0.01
            },
            'price_action': {
                'breakout_threshold': 0.008,
                'volume_threshold': 1.3
            }
        }
        
        # 시장 체제별 최적화 규칙
        self.regime_rules = {
            MarketRegime.TRENDING_UP: {
                'rsi_momentum': {'oversold': 35, 'overbought': 75},
                'bollinger_band': {'std_dev': 1.8},
                'ema_crossover': {'min_crossover_strength': 0.0008},
                'macd': {'signal_threshold': 0.00008}
            },
            MarketRegime.TRENDING_DOWN: {
                'rsi_momentum': {'oversold': 25, 'overbought': 65},
                'bollinger_band': {'std_dev': 2.2},
                'ema_crossover': {'min_crossover_strength': 0.0012},
                'macd': {'signal_threshold': 0.00012}
            },
            MarketRegime.HIGH_VOLATILITY: {
                'rsi_momentum': {'momentum_threshold': 0.03, 'volume_threshold': 1.8},
                'bollinger_band': {'std_dev': 2.5, 'breakout_threshold': 0.015},
                'volume_surge': {'surge_threshold': 2.5},
                'price_action': {'breakout_threshold': 0.012}
            },
            MarketRegime.LOW_VOLATILITY: {
                'rsi_momentum': {'momentum_threshold': 0.015, 'volume_threshold': 1.2},
                'bollinger_band': {'std_dev': 1.5, 'breakout_threshold': 0.008},
                'volume_surge': {'surge_threshold': 1.5},
                'price_action': {'breakout_threshold': 0.006}
            }
        }
        
        self.logger.info("AdaptiveThresholdOptimizer 초기화 완료")
    
    def analyze_market_regime(self, market_data: Dict[str, Any]) -> MarketAnalysis:
        """시장 체제 분석"""
        try:
            candles = market_data.get('candles_5m', [])
            if len(candles) < 50:
                return MarketAnalysis(
                    regime=MarketRegime.SIDEWAYS,
                    volatility=0.0,
                    trend_strength=0.0,
                    volume_profile="normal",
                    momentum=0.0,
                    confidence=0.0
                )
            
            df = pd.DataFrame(candles)
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume'])
            
            # 변동성 계산 (ATR 기반)
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = true_range.rolling(14).mean().iloc[-1]
            volatility = atr / df['close'].iloc[-1]
            
            # 트렌드 강도 계산 (EMA 기반)
            ema_20 = df['close'].ewm(span=20).mean()
            ema_50 = df['close'].ewm(span=50).mean()
            trend_strength = abs(ema_20.iloc[-1] - ema_50.iloc[-1]) / df['close'].iloc[-1]
            
            # 거래량 프로필
            recent_volume = df['volume'].tail(10).mean()
            avg_volume = df['volume'].mean()
            volume_ratio = recent_volume / avg_volume
            
            if volume_ratio > 1.5:
                volume_profile = "high"
            elif volume_ratio < 0.7:
                volume_profile = "low"
            else:
                volume_profile = "normal"
            
            # 모멘텀 계산
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20]
            momentum = price_change
            
            # 시장 체제 결정
            if volatility > 0.03:
                regime = MarketRegime.HIGH_VOLATILITY
            elif volatility < 0.015:
                regime = MarketRegime.LOW_VOLATILITY
            elif trend_strength > 0.02 and momentum > 0.01:
                regime = MarketRegime.TRENDING_UP
            elif trend_strength > 0.02 and momentum < -0.01:
                regime = MarketRegime.TRENDING_DOWN
            else:
                regime = MarketRegime.SIDEWAYS
            
            confidence = min(0.9, 0.5 + abs(trend_strength) * 10 + abs(momentum) * 5)
            
            return MarketAnalysis(
                regime=regime,
                volatility=volatility,
                trend_strength=trend_strength,
                volume_profile=volume_profile,
                momentum=momentum,
                confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"시장 체제 분석 오류: {e}")
            return MarketAnalysis(
                regime=MarketRegime.SIDEWAYS,
                volatility=0.0,
                trend_strength=0.0,
                volume_profile="normal",
                momentum=0.0,
                confidence=0.0
            )
    
    def optimize_thresholds_for_regime(self, market_analysis: MarketAnalysis) -> List[ThresholdAdjustment]:
        """시장 체제에 따른 임계값 최적화"""
        adjustments = []
        
        try:
            # 시장 체제별 규칙 적용
            regime_rules = self.regime_rules.get(market_analysis.regime, {})
            
            for strategy_id, rules in regime_rules.items():
                if strategy_id in self.strategy_thresholds:
                    for param, new_value in rules.items():
                        old_value = self.strategy_thresholds[strategy_id].get(param, 0)
                        
                        # 동적 조정 (시장 상황에 따라 세밀하게 조정)
                        if market_analysis.regime == MarketRegime.HIGH_VOLATILITY:
                            # 고변동성 시장에서는 더 보수적으로
                            if param in ['momentum_threshold', 'breakout_threshold']:
                                new_value *= 1.2
                            elif param in ['volume_threshold', 'surge_threshold']:
                                new_value *= 1.3
                        
                        elif market_analysis.regime == MarketRegime.LOW_VOLATILITY:
                            # 저변동성 시장에서는 더 민감하게
                            if param in ['momentum_threshold', 'breakout_threshold']:
                                new_value *= 0.8
                            elif param in ['volume_threshold', 'surge_threshold']:
                                new_value *= 0.9
                        
                        # 거래량 프로필에 따른 추가 조정
                        if market_analysis.volume_profile == "high":
                            if 'volume_threshold' in param:
                                new_value *= 1.2
                        elif market_analysis.volume_profile == "low":
                            if 'volume_threshold' in param:
                                new_value *= 0.8
                        
                        adjustment = ThresholdAdjustment(
                            strategy_id=strategy_id,
                            parameter=param,
                            old_value=old_value,
                            new_value=new_value,
                            adjustment_reason=f"{market_analysis.regime.value} 시장 체제에 최적화",
                            confidence=market_analysis.confidence,
                            expected_impact=f"신호 생성 빈도 {'증가' if new_value < old_value else '감소'}"
                        )
                        adjustments.append(adjustment)
            
            # 성과 기반 추가 최적화
            performance_adjustments = self._optimize_based_on_performance()
            adjustments.extend(performance_adjustments)
            
            self.logger.info(f"임계값 최적화 완료: {len(adjustments)}개 조정")
            return adjustments
            
        except Exception as e:
            self.logger.error(f"임계값 최적화 오류: {e}")
            return []
    
    def _optimize_based_on_performance(self) -> List[ThresholdAdjustment]:
        """성과 기반 임계값 최적화"""
        adjustments = []
        
        try:
            # 최근 거래 성과 분석
            conn = sqlite3.connect('data/trading_data.db')
            
            # 전략별 성과 분석 (최근 7일)
            query = """
            SELECT strategy_id, 
                   COUNT(*) as total_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                   AVG(pnl) as avg_pnl
            FROM trades 
            WHERE created_at >= datetime('now', '-7 days')
            AND strategy_id != 'manual'
            GROUP BY strategy_id
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            for _, row in df.iterrows():
                strategy_id = row['strategy_id']
                total_trades = row['total_trades']
                win_rate = row['winning_trades'] / total_trades if total_trades > 0 else 0
                avg_pnl = row['avg_pnl'] if row['avg_pnl'] else 0
                
                # 성과가 좋은 전략은 더 적극적으로
                if win_rate > 0.6 and avg_pnl > 0:
                    if strategy_id in self.strategy_thresholds:
                        for param in self.strategy_thresholds[strategy_id]:
                            if 'threshold' in param.lower():
                                old_value = self.strategy_thresholds[strategy_id][param]
                                new_value = old_value * 0.9  # 임계값 낮춤
                                
                                adjustment = ThresholdAdjustment(
                                    strategy_id=strategy_id,
                                    parameter=param,
                                    old_value=old_value,
                                    new_value=new_value,
                                    adjustment_reason=f"성과 기반 최적화 (승률: {win_rate:.1%})",
                                    confidence=win_rate,
                                    expected_impact="신호 생성 빈도 증가"
                                )
                                adjustments.append(adjustment)
                
                # 성과가 나쁜 전략은 더 보수적으로
                elif win_rate < 0.4 or avg_pnl < 0:
                    if strategy_id in self.strategy_thresholds:
                        for param in self.strategy_thresholds[strategy_id]:
                            if 'threshold' in param.lower():
                                old_value = self.strategy_thresholds[strategy_id][param]
                                new_value = old_value * 1.1  # 임계값 높임
                                
                                adjustment = ThresholdAdjustment(
                                    strategy_id=strategy_id,
                                    parameter=param,
                                    old_value=old_value,
                                    new_value=new_value,
                                    adjustment_reason=f"성과 기반 최적화 (승률: {win_rate:.1%})",
                                    confidence=1-win_rate,
                                    expected_impact="신호 생성 빈도 감소"
                                )
                                adjustments.append(adjustment)
            
        except Exception as e:
            self.logger.error(f"성과 기반 최적화 오류: {e}")
        
        return adjustments
    
    def apply_threshold_adjustments(self, adjustments: List[ThresholdAdjustment]) -> bool:
        """임계값 조정 적용"""
        try:
            applied_count = 0
            
            for adjustment in adjustments:
                if adjustment.strategy_id in self.strategy_thresholds:
                    self.strategy_thresholds[adjustment.strategy_id][adjustment.parameter] = adjustment.new_value
                    applied_count += 1
                    
                    self.logger.info(
                        f"임계값 조정 적용: {adjustment.strategy_id}.{adjustment.parameter} "
                        f"{adjustment.old_value:.4f} → {adjustment.new_value:.4f} "
                        f"({adjustment.adjustment_reason})"
                    )
            
            # 설정 파일에 저장
            self._save_thresholds_to_config()
            
            self.logger.info(f"임계값 조정 완료: {applied_count}개 적용")
            return True
            
        except Exception as e:
            self.logger.error(f"임계값 조정 적용 오류: {e}")
            return False
    
    def _save_thresholds_to_config(self):
        """최적화된 임계값을 설정 파일에 저장"""
        try:
            # 전략별 최적화된 설정 생성
            optimized_config = {}
            
            for strategy_id, thresholds in self.strategy_thresholds.items():
                optimized_config[f"strategies.{strategy_id}"] = thresholds
            
            # 설정 파일에 저장
            for key, value in optimized_config.items():
                self.config.set_config(key, value)
            
            self.logger.info("최적화된 임계값 설정 저장 완료")
            
        except Exception as e:
            self.logger.error(f"임계값 설정 저장 오류: {e}")
    
    def get_optimized_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """최적화된 임계값 반환"""
        return self.strategy_thresholds.copy()
    
    def run_optimization(self, market_data: Dict[str, Any]) -> bool:
        """전체 최적화 프로세스 실행"""
        try:
            self.logger.info("=== 적응형 임계값 최적화 시작 ===")
            
            # 1. 시장 체제 분석
            market_analysis = self.analyze_market_regime(market_data)
            self.logger.info(f"시장 체제: {market_analysis.regime.value} (신뢰도: {market_analysis.confidence:.2f})")
            
            # 2. 임계값 최적화
            adjustments = self.optimize_thresholds_for_regime(market_analysis)
            
            if not adjustments:
                self.logger.info("적용할 임계값 조정이 없습니다.")
                return False
            
            # 3. 조정 적용
            success = self.apply_threshold_adjustments(adjustments)
            
            if success:
                self.logger.info("=== 적응형 임계값 최적화 완료 ===")
                return True
            else:
                self.logger.error("임계값 최적화 적용 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"최적화 프로세스 오류: {e}")
            return False


# 전역 인스턴스
adaptive_optimizer = AdaptiveThresholdOptimizer()
