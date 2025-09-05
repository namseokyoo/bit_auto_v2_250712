"""
전략 어댑터 (Strategy Adapter)
기존 전략들을 동적 임계값과 연동하는 어댑터 클래스
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.regime_detector import RegimeDetector, RegimeResult
from core.dynamic_threshold_manager import DynamicThresholdManager, StrategyThresholds
from core.independent_strategies import IndependentStrategy
from core.independent_strategy_engine import StrategyVote


@dataclass
class AdaptedStrategyConfig:
    """어댑터된 전략 설정"""
    strategy_name: str
    original_config: Dict[str, Any]
    dynamic_config: Dict[str, Any]
    regime: str
    confidence: float
    last_updated: str


class StrategyAdapter:
    """전략 어댑터 - 동적 임계값을 기존 전략에 적용"""
    
    def __init__(self, regime_detector: RegimeDetector, threshold_manager: DynamicThresholdManager):
        self.regime_detector = regime_detector
        self.threshold_manager = threshold_manager
        self.logger = logging.getLogger('StrategyAdapter')
        
        # 현재 적용된 설정 캐시
        self.current_configs: Dict[str, AdaptedStrategyConfig] = {}
        
        # 전략별 기본 설정 매핑
        self.strategy_config_mapping = {
            "rsi_momentum": "rsi_momentum",
            "bollinger_squeeze": "bollinger_squeeze", 
            "support_resistance": "support_resistance",
            "ema_crossover": "ema_crossover",
            "macd_signal": "macd_signal",
            "stochastic_oscillator": "stochastic_oscillator",
            "williams_r": "williams_r",
            "cci_oscillator": "cci_oscillator",
            "volume_surge": "volume_surge",
            "price_action": "price_action"
        }
        
        self.logger.info("StrategyAdapter 초기화 완료")
    
    def adapt_strategy(self, strategy: IndependentStrategy, market_data: Dict[str, Any], 
                      original_config: Dict[str, Any]) -> Optional[StrategyVote]:
        """전략을 동적 임계값으로 어댑트하여 실행"""
        try:
            # 1. 현재 시장 체제 감지
            regime_result = self.regime_detector.detect_regime()
            if not regime_result:
                self.logger.warning("체제 감지 실패, 기본 설정으로 실행")
                return strategy.analyze(market_data, original_config)
            
            # 2. 동적 임계값 계산
            strategy_name = self.strategy_config_mapping.get(strategy.strategy_name, strategy.strategy_name)
            dynamic_thresholds = self.threshold_manager.get_dynamic_thresholds(regime_result, strategy_name)
            
            if not dynamic_thresholds:
                self.logger.warning(f"전략 {strategy_name}의 동적 임계값 계산 실패, 기본 설정으로 실행")
                return strategy.analyze(market_data, original_config)
            
            # 3. 어댑터된 설정 생성
            adapted_config = self._create_adapted_config(original_config, dynamic_thresholds)
            
            # 4. 설정 캐시 업데이트
            self._update_config_cache(strategy.strategy_name, adapted_config, regime_result)
            
            # 5. 어댑터된 설정으로 전략 실행
            vote = strategy.analyze(market_data, adapted_config)
            
            # 6. 로깅
            if vote:
                self.logger.debug(f"전략 {strategy.strategy_name} 어댑트 실행 완료 "
                                f"(체제: {regime_result.primary_regime.value}, "
                                f"신호: {vote.signal.value}, 신뢰도: {vote.confidence:.3f})")
            
            return vote
            
        except Exception as e:
            self.logger.error(f"전략 어댑트 오류 ({strategy.strategy_name}): {e}")
            # 오류 시 기본 설정으로 폴백
            return strategy.analyze(market_data, original_config)
    
    def _create_adapted_config(self, original_config: Dict[str, Any], 
                              dynamic_thresholds: StrategyThresholds) -> Dict[str, Any]:
        """어댑터된 설정 생성"""
        adapted_config = original_config.copy()
        
        # 동적 임계값 적용
        for param_name, adjustment in dynamic_thresholds.adjustments.items():
            adapted_config[param_name] = adjustment.adjusted_value
        
        return adapted_config
    
    def _update_config_cache(self, strategy_name: str, adapted_config: Dict[str, Any], 
                           regime_result: RegimeResult):
        """설정 캐시 업데이트"""
        from datetime import datetime
        
        self.current_configs[strategy_name] = AdaptedStrategyConfig(
            strategy_name=strategy_name,
            original_config={},  # 원본 설정은 별도 저장 필요
            dynamic_config=adapted_config,
            regime=regime_result.primary_regime.value,
            confidence=regime_result.confidence,
            last_updated=datetime.now().isoformat()
        )
    
    def get_current_regime(self) -> Optional[RegimeResult]:
        """현재 시장 체제 반환"""
        return self.regime_detector.detect_regime()
    
    def get_strategy_config(self, strategy_name: str) -> Optional[AdaptedStrategyConfig]:
        """전략의 현재 어댑터된 설정 반환"""
        return self.current_configs.get(strategy_name)
    
    def get_all_strategy_configs(self) -> Dict[str, AdaptedStrategyConfig]:
        """모든 전략의 현재 설정 반환"""
        return self.current_configs.copy()
    
    def force_regime_update(self, market: str = "KRW-BTC") -> Optional[RegimeResult]:
        """강제로 체제 업데이트"""
        try:
            regime_result = self.regime_detector.detect_regime(market)
            if regime_result:
                self.logger.info(f"체제 강제 업데이트 완료: {regime_result.primary_regime.value}")
            return regime_result
        except Exception as e:
            self.logger.error(f"체제 강제 업데이트 오류: {e}")
            return None
    
    def get_regime_summary(self) -> Dict[str, Any]:
        """체제 요약 정보 반환"""
        regime_result = self.get_current_regime()
        if not regime_result:
            return {"status": "unavailable", "message": "체제 감지 불가"}
        
        # 모든 전략의 동적 임계값 요약
        all_thresholds = self.threshold_manager.get_all_strategy_thresholds(regime_result)
        
        summary = {
            "status": "active",
            "regime": regime_result.primary_regime.value,
            "confidence": regime_result.confidence,
            "reasoning": regime_result.reasoning,
            "timestamp": regime_result.timestamp.isoformat(),
            "strategy_count": len(all_thresholds),
            "strategies": {}
        }
        
        for strategy_name, thresholds in all_thresholds.items():
            strategy_summary = {
                "regime": thresholds.regime.value,
                "confidence": thresholds.confidence,
                "adjustment_count": len(thresholds.adjustments),
                "adjustments": {}
            }
            
            for param_name, adjustment in thresholds.adjustments.items():
                strategy_summary["adjustments"][param_name] = {
                    "base": adjustment.base_value,
                    "adjusted": adjustment.adjusted_value,
                    "factor": adjustment.adjustment_factor,
                    "reason": adjustment.adjustment_reason
                }
            
            summary["strategies"][strategy_name] = strategy_summary
        
        return summary
    
    def log_adaptation_summary(self):
        """어댑테이션 요약 로깅"""
        regime_result = self.get_current_regime()
        if not regime_result:
            self.logger.warning("체제 정보 없음, 어댑테이션 요약 불가")
            return
        
        self.logger.info("=== 전략 어댑테이션 요약 ===")
        self.logger.info(f"현재 체제: {regime_result.primary_regime.value}")
        self.logger.info(f"신뢰도: {regime_result.confidence:.3f}")
        self.logger.info(f"판단 근거: {regime_result.reasoning}")
        
        all_thresholds = self.threshold_manager.get_all_strategy_thresholds(regime_result)
        self.logger.info(f"적용된 전략 수: {len(all_thresholds)}")
        
        for strategy_name, thresholds in all_thresholds.items():
            adjustment_count = len([adj for adj in thresholds.adjustments.values() if adj.adjustment_factor != 1.0])
            self.logger.info(f"  {strategy_name}: {adjustment_count}개 파라미터 조정")
    
    def validate_adaptation(self, strategy_name: str) -> bool:
        """어댑테이션 유효성 검증"""
        try:
            config = self.get_strategy_config(strategy_name)
            if not config:
                self.logger.warning(f"전략 {strategy_name}의 설정이 없습니다")
                return False
            
            # 기본적인 설정 검증
            dynamic_config = config.dynamic_config
            
            # RSI 관련 검증
            if "oversold" in dynamic_config and "overbought" in dynamic_config:
                oversold = dynamic_config["oversold"]
                overbought = dynamic_config["overbought"]
                if oversold >= overbought:
                    self.logger.error(f"RSI 설정 오류: oversold({oversold}) >= overbought({overbought})")
                    return False
            
            # 볼린저 밴드 검증
            if "bb_std" in dynamic_config:
                bb_std = dynamic_config["bb_std"]
                if bb_std <= 0:
                    self.logger.error(f"볼린저 밴드 표준편차 오류: {bb_std}")
                    return False
            
            # 기간 관련 검증
            period_params = ["rsi_period", "bb_period", "lookback_period", "k_period", "d_period"]
            for param in period_params:
                if param in dynamic_config:
                    period = dynamic_config[param]
                    if period <= 0:
                        self.logger.error(f"{param} 오류: {period}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"어댑테이션 검증 오류 ({strategy_name}): {e}")
            return False
    
    def reset_to_default(self, strategy_name: str = None):
        """기본 설정으로 리셋"""
        if strategy_name:
            if strategy_name in self.current_configs:
                del self.current_configs[strategy_name]
                self.logger.info(f"전략 {strategy_name} 설정 리셋 완료")
        else:
            self.current_configs.clear()
            self.logger.info("모든 전략 설정 리셋 완료")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 반환"""
        regime_result = self.get_current_regime()
        if not regime_result:
            return {"status": "unavailable"}
        
        return {
            "status": "active",
            "regime_detection_confidence": regime_result.confidence,
            "active_strategies": len(self.current_configs),
            "last_regime_update": regime_result.timestamp.isoformat(),
            "regime_stability": self._calculate_regime_stability()
        }
    
    def _calculate_regime_stability(self) -> float:
        """체제 안정성 계산 (간단한 구현)"""
        # 실제 구현에서는 과거 체제 변화 이력을 분석
        regime_result = self.get_current_regime()
        if regime_result:
            return regime_result.confidence
        return 0.0
