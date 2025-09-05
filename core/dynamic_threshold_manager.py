"""
동적 임계값 관리 시스템 (Dynamic Threshold Manager)
시장 체제에 따라 전략별 임계값을 동적으로 조정
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from core.regime_detector import MarketRegime, RegimeResult


@dataclass
class ThresholdAdjustment:
    """임계값 조정 정보"""
    parameter_name: str
    base_value: float
    adjusted_value: float
    adjustment_factor: float
    adjustment_reason: str


@dataclass
class StrategyThresholds:
    """전략별 동적 임계값"""
    strategy_name: str
    adjustments: Dict[str, ThresholdAdjustment]
    regime: MarketRegime
    confidence: float


class DynamicThresholdManager:
    """동적 임계값 관리자"""
    
    def __init__(self):
        self.logger = logging.getLogger('DynamicThresholdManager')
        
        # 기본 임계값 정의 (현재 설정에서 추출)
        self.base_thresholds = {
            "rsi_momentum": {
                "rsi_period": 14,
                "oversold": 30,
                "overbought": 70,
                "momentum_threshold": 0.002
            },
            "bollinger_squeeze": {
                "bb_period": 20,
                "bb_std": 2.0,
                "squeeze_threshold": 0.01
            },
            "support_resistance": {
                "lookback_period": 20,
                "touch_tolerance": 0.005
            },
            "ema_crossover": {
                "fast_ema": 12,
                "slow_ema": 26,
                "signal_ema": 9,
                "trend_ema": 50,
                "volume_threshold": 1.2,
                "min_crossover_strength": 0.001
            },
            "macd_signal": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "histogram_threshold": 0.0001,
                "signal_crossover_strength": 0.0005,
                "zero_line_threshold": 0.0002
            },
            "stochastic_oscillator": {
                "k_period": 14,
                "d_period": 3,
                "smooth_k": 3,
                "overbought": 80,
                "oversold": 20,
                "crossover_threshold": 5
            },
            "williams_r": {
                "period": 14,
                "overbought": -20,
                "oversold": -80
            },
            "cci_oscillator": {
                "period": 20,
                "overbought": 100,
                "oversold": -100
            },
            "volume_surge": {
                "volume_threshold": 1.5,
                "momentum_period": 10
            },
            "price_action": {
                "pattern_threshold": 0.3,
                "min_touches": 2
            }
        }
        
        # 체제별 조정 규칙 정의
        self.regime_adjustments = {
            MarketRegime.BULL_MARKET: {
                "rsi_momentum": {
                    "oversold": 0.8,      # 30 -> 24 (더 공격적 매수)
                    "overbought": 1.1,    # 70 -> 77 (더 오래 보유)
                    "momentum_threshold": 0.7  # 더 민감한 신호
                },
                "bollinger_squeeze": {
                    "squeeze_threshold": 0.8  # 더 민감한 스퀴즈 감지
                },
                "ema_crossover": {
                    "min_crossover_strength": 0.5,  # 더 약한 크로스오버도 허용
                    "volume_threshold": 0.8  # 거래량 요구 완화
                },
                "macd_signal": {
                    "histogram_threshold": 0.5,  # 더 민감한 신호
                    "signal_crossover_strength": 0.5
                },
                "stochastic_oscillator": {
                    "overbought": 1.1,    # 80 -> 88 (더 오래 보유)
                    "oversold": 0.8,      # 20 -> 16 (더 공격적 매수)
                    "crossover_threshold": 0.8  # 더 민감한 크로스오버
                },
                "williams_r": {
                    "overbought": 1.1,    # -20 -> -22 (더 오래 보유)
                    "oversold": 0.8       # -80 -> -64 (더 공격적 매수)
                }
            },
            
            MarketRegime.BEAR_MARKET: {
                "rsi_momentum": {
                    "oversold": 1.2,      # 30 -> 36 (더 신중한 매수)
                    "overbought": 0.9,     # 70 -> 63 (빠른 매도)
                    "momentum_threshold": 1.3  # 더 강한 신호 요구
                },
                "bollinger_squeeze": {
                    "squeeze_threshold": 1.2  # 더 강한 스퀴즈 요구
                },
                "ema_crossover": {
                    "min_crossover_strength": 1.5,  # 더 강한 크로스오버 요구
                    "volume_threshold": 1.3  # 거래량 요구 강화
                },
                "macd_signal": {
                    "histogram_threshold": 1.5,  # 더 강한 신호 요구
                    "signal_crossover_strength": 1.5
                },
                "stochastic_oscillator": {
                    "overbought": 0.9,    # 80 -> 72 (빠른 매도)
                    "oversold": 1.2,      # 20 -> 24 (더 신중한 매수)
                    "crossover_threshold": 1.2  # 더 강한 크로스오버 요구
                },
                "williams_r": {
                    "overbought": 0.9,    # -20 -> -18 (빠른 매도)
                    "oversold": 1.2        # -80 -> -96 (더 신중한 매수)
                }
            },
            
            MarketRegime.HIGH_VOLATILITY: {
                "rsi_momentum": {
                    "oversold": 1.1,      # 더 신중한 매수
                    "overbought": 0.9,     # 빠른 매도
                    "momentum_threshold": 1.2  # 더 강한 신호 요구
                },
                "bollinger_squeeze": {
                    "bb_std": 1.2,        # 2.0 -> 2.4 (더 넓은 밴드)
                    "squeeze_threshold": 1.3  # 더 강한 스퀴즈 요구
                },
                "ema_crossover": {
                    "min_crossover_strength": 1.3,  # 더 강한 크로스오버 요구
                    "volume_threshold": 1.2  # 거래량 요구 강화
                },
                "macd_signal": {
                    "histogram_threshold": 1.3,  # 더 강한 신호 요구
                    "signal_crossover_strength": 1.3
                },
                "stochastic_oscillator": {
                    "overbought": 0.9,    # 빠른 매도
                    "oversold": 1.1,      # 더 신중한 매수
                    "crossover_threshold": 1.2  # 더 강한 크로스오버 요구
                },
                "williams_r": {
                    "overbought": 0.9,    # 빠른 매도
                    "oversold": 1.1       # 더 신중한 매수
                }
            },
            
            MarketRegime.LOW_VOLATILITY: {
                "rsi_momentum": {
                    "oversold": 0.9,      # 더 공격적 매수
                    "overbought": 1.1,     # 더 오래 보유
                    "momentum_threshold": 0.8  # 더 민감한 신호
                },
                "bollinger_squeeze": {
                    "bb_std": 0.8,        # 2.0 -> 1.6 (더 좁은 밴드)
                    "squeeze_threshold": 0.7  # 더 민감한 스퀴즈 감지
                },
                "ema_crossover": {
                    "min_crossover_strength": 0.7,  # 더 약한 크로스오버도 허용
                    "volume_threshold": 0.9  # 거래량 요구 완화
                },
                "macd_signal": {
                    "histogram_threshold": 0.7,  # 더 민감한 신호
                    "signal_crossover_strength": 0.7
                },
                "stochastic_oscillator": {
                    "overbought": 1.1,    # 더 오래 보유
                    "oversold": 0.9,      # 더 공격적 매수
                    "crossover_threshold": 0.8  # 더 민감한 크로스오버
                },
                "williams_r": {
                    "overbought": 1.1,    # 더 오래 보유
                    "oversold": 0.9       # 더 공격적 매수
                }
            },
            
            MarketRegime.SIDEWAYS: {
                "rsi_momentum": {
                    "oversold": 0.8,      # 더 공격적 매수
                    "overbought": 1.1,     # 더 오래 보유
                    "momentum_threshold": 0.7  # 더 민감한 신호
                },
                "bollinger_squeeze": {
                    "squeeze_threshold": 0.8  # 더 민감한 스퀴즈 감지
                },
                "ema_crossover": {
                    "min_crossover_strength": 0.8,  # 약간 완화
                    "volume_threshold": 0.9  # 거래량 요구 완화
                },
                "macd_signal": {
                    "histogram_threshold": 0.8,  # 약간 민감하게
                    "signal_crossover_strength": 0.8
                },
                "stochastic_oscillator": {
                    "overbought": 1.1,    # 더 오래 보유
                    "oversold": 0.8,      # 더 공격적 매수
                    "crossover_threshold": 0.8  # 더 민감한 크로스오버
                },
                "williams_r": {
                    "overbought": 1.1,    # 더 오래 보유
                    "oversold": 0.8       # 더 공격적 매수
                }
            },
            
            MarketRegime.TRENDING_UP: {
                "rsi_momentum": {
                    "oversold": 0.8,      # 더 공격적 매수
                    "overbought": 1.1,     # 더 오래 보유
                    "momentum_threshold": 0.7  # 더 민감한 신호
                },
                "ema_crossover": {
                    "min_crossover_strength": 0.7,  # 더 약한 크로스오버도 허용
                    "volume_threshold": 0.8  # 거래량 요구 완화
                },
                "macd_signal": {
                    "histogram_threshold": 0.7,  # 더 민감한 신호
                    "signal_crossover_strength": 0.7
                }
            },
            
            MarketRegime.TRENDING_DOWN: {
                "rsi_momentum": {
                    "oversold": 1.1,      # 더 신중한 매수
                    "overbought": 0.9,     # 빠른 매도
                    "momentum_threshold": 1.2  # 더 강한 신호 요구
                },
                "ema_crossover": {
                    "min_crossover_strength": 1.3,  # 더 강한 크로스오버 요구
                    "volume_threshold": 1.2  # 거래량 요구 강화
                },
                "macd_signal": {
                    "histogram_threshold": 1.3,  # 더 강한 신호 요구
                    "signal_crossover_strength": 1.3
                }
            }
        }
        
        self.logger.info("DynamicThresholdManager 초기화 완료")
    
    def get_dynamic_thresholds(self, regime_result: RegimeResult, strategy_name: str) -> Optional[StrategyThresholds]:
        """체제에 따른 동적 임계값 계산"""
        try:
            if not regime_result:
                self.logger.warning("체제 정보가 없습니다")
                return None
            
            regime = regime_result.primary_regime
            confidence = regime_result.confidence
            
            # 기본 임계값 가져오기
            if strategy_name not in self.base_thresholds:
                self.logger.warning(f"전략 {strategy_name}의 기본 임계값이 없습니다")
                return None
            
            base_thresholds = self.base_thresholds[strategy_name]
            
            # 체제별 조정 규칙 가져오기
            if regime not in self.regime_adjustments:
                self.logger.warning(f"체제 {regime.value}에 대한 조정 규칙이 없습니다")
                return None
            
            regime_rules = self.regime_adjustments[regime]
            if strategy_name not in regime_rules:
                self.logger.warning(f"체제 {regime.value}에서 전략 {strategy_name}에 대한 조정 규칙이 없습니다")
                return None
            
            strategy_rules = regime_rules[strategy_name]
            
            # 임계값 조정 계산
            adjustments = {}
            for param_name, adjustment_factor in strategy_rules.items():
                if param_name in base_thresholds:
                    base_value = base_thresholds[param_name]
                    adjusted_value = base_value * adjustment_factor
                    
                    # 조정 이유 생성
                    if adjustment_factor < 1.0:
                        reason = f"{regime.value} 체제로 인해 {param_name} 완화 ({base_value:.3f} -> {adjusted_value:.3f})"
                    elif adjustment_factor > 1.0:
                        reason = f"{regime.value} 체제로 인해 {param_name} 강화 ({base_value:.3f} -> {adjusted_value:.3f})"
                    else:
                        reason = f"{regime.value} 체제에서 {param_name} 유지 ({base_value:.3f})"
                    
                    adjustments[param_name] = ThresholdAdjustment(
                        parameter_name=param_name,
                        base_value=base_value,
                        adjusted_value=adjusted_value,
                        adjustment_factor=adjustment_factor,
                        adjustment_reason=reason
                    )
            
            result = StrategyThresholds(
                strategy_name=strategy_name,
                adjustments=adjustments,
                regime=regime,
                confidence=confidence
            )
            
            self.logger.info(f"전략 {strategy_name}의 동적 임계값 계산 완료 (체제: {regime.value}, 신뢰도: {confidence:.3f})")
            return result
            
        except Exception as e:
            self.logger.error(f"동적 임계값 계산 오류: {e}")
            return None
    
    def get_all_strategy_thresholds(self, regime_result: RegimeResult) -> Dict[str, StrategyThresholds]:
        """모든 전략의 동적 임계값 계산"""
        all_thresholds = {}
        
        for strategy_name in self.base_thresholds.keys():
            thresholds = self.get_dynamic_thresholds(regime_result, strategy_name)
            if thresholds:
                all_thresholds[strategy_name] = thresholds
        
        return all_thresholds
    
    def get_adjusted_parameter(self, strategy_name: str, parameter_name: str, regime_result: RegimeResult) -> Optional[float]:
        """특정 파라미터의 조정된 값 반환"""
        thresholds = self.get_dynamic_thresholds(regime_result, strategy_name)
        if thresholds and parameter_name in thresholds.adjustments:
            return thresholds.adjustments[parameter_name].adjusted_value
        return None
    
    def get_adjustment_summary(self, regime_result: RegimeResult) -> Dict[str, Any]:
        """조정 요약 정보 반환"""
        if not regime_result:
            return {}
        
        all_thresholds = self.get_all_strategy_thresholds(regime_result)
        
        summary = {
            "regime": regime_result.primary_regime.value,
            "confidence": regime_result.confidence,
            "reasoning": regime_result.reasoning,
            "strategy_count": len(all_thresholds),
            "strategies": {}
        }
        
        for strategy_name, thresholds in all_thresholds.items():
            strategy_summary = {
                "regime": thresholds.regime.value,
                "confidence": thresholds.confidence,
                "adjustments": {}
            }
            
            for param_name, adjustment in thresholds.adjustments.items():
                strategy_summary["adjustments"][param_name] = {
                    "base_value": adjustment.base_value,
                    "adjusted_value": adjustment.adjusted_value,
                    "adjustment_factor": adjustment.adjustment_factor,
                    "reason": adjustment.adjustment_reason
                }
            
            summary["strategies"][strategy_name] = strategy_summary
        
        return summary
    
    def log_threshold_changes(self, regime_result: RegimeResult):
        """임계값 변경사항 로깅"""
        if not regime_result:
            return
        
        all_thresholds = self.get_all_strategy_thresholds(regime_result)
        
        self.logger.info(f"=== 동적 임계값 조정 ({regime_result.primary_regime.value}) ===")
        self.logger.info(f"신뢰도: {regime_result.confidence:.3f}")
        self.logger.info(f"판단 근거: {regime_result.reasoning}")
        
        for strategy_name, thresholds in all_thresholds.items():
            self.logger.info(f"\n📊 {strategy_name}:")
            for param_name, adjustment in thresholds.adjustments.items():
                if adjustment.adjustment_factor != 1.0:
                    self.logger.info(f"  {param_name}: {adjustment.base_value:.3f} -> {adjustment.adjusted_value:.3f} "
                                   f"(x{adjustment.adjustment_factor:.2f})")
                else:
                    self.logger.info(f"  {param_name}: {adjustment.base_value:.3f} (변경 없음)")
    
    def validate_thresholds(self, thresholds: StrategyThresholds) -> bool:
        """임계값 유효성 검증"""
        try:
            for param_name, adjustment in thresholds.adjustments.items():
                # 기본적인 범위 검증
                if param_name in ["oversold", "overbought"]:
                    if adjustment.adjusted_value < 0 or adjustment.adjusted_value > 100:
                        self.logger.warning(f"{param_name} 값이 범위를 벗어남: {adjustment.adjusted_value}")
                        return False
                
                elif param_name in ["rsi_period", "bb_period", "lookback_period"]:
                    if adjustment.adjusted_value < 1:
                        self.logger.warning(f"{param_name} 값이 너무 작음: {adjustment.adjusted_value}")
                        return False
                
                elif param_name in ["momentum_threshold", "squeeze_threshold"]:
                    if adjustment.adjusted_value < 0:
                        self.logger.warning(f"{param_name} 값이 음수: {adjustment.adjusted_value}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"임계값 검증 오류: {e}")
            return False
