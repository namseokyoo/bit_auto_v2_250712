#!/usr/bin/env python3
"""
동적 가중치 자동 조정 시스템
전략별 성과를 기반으로 실시간으로 가중치를 자동 조정하는 시스템
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
import threading
import time

from config.config_manager import config_manager
from core.ai_performance_analyzer import ai_performance_analyzer, AdvancedPerformanceMetrics


class WeightAdjustmentStrategy(Enum):
    """가중치 조정 전략"""
    PERFORMANCE_BASED = "performance_based"      # 성과 기반
    RISK_ADJUSTED = "risk_adjusted"              # 리스크 조정
    MOMENTUM_BASED = "momentum_based"            # 모멘텀 기반
    MEAN_REVERSION = "mean_reversion"            # 평균 회귀
    KELLY_CRITERION = "kelly_criterion"          # 켈리 공식
    SHARPE_OPTIMIZATION = "sharpe_optimization"  # 샤프 비율 최적화


@dataclass
class WeightAdjustment:
    """가중치 조정 기록"""
    strategy_id: str
    old_weight: float
    new_weight: float
    adjustment_reason: str
    adjustment_strategy: WeightAdjustmentStrategy
    confidence: float
    expected_improvement: float
    timestamp: datetime

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'strategy_id': self.strategy_id,
            'old_weight': self.old_weight,
            'new_weight': self.new_weight,
            'adjustment_reason': self.adjustment_reason,
            'adjustment_strategy': self.adjustment_strategy.value,
            'confidence': self.confidence,
            'expected_improvement': self.expected_improvement,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class PortfolioOptimizationResult:
    """포트폴리오 최적화 결과"""
    original_weights: Dict[str, float]
    optimized_weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    optimization_method: str
    confidence: float
    adjustments: List[WeightAdjustment]


class DynamicWeightOptimizer:
    """동적 가중치 최적화기"""

    def __init__(self):
        self.logger = logging.getLogger('DynamicWeightOptimizer')

        # 최적화 파라미터
        self.min_weight = 0.1        # 최소 가중치
        self.max_weight = 2.0        # 최대 가중치
        self.adjustment_frequency = 24  # 조정 빈도 (시간)
        self.lookback_period = 30    # 분석 기간 (일)
        self.min_confidence = 0.6    # 최소 신뢰도

        # 조정 기록
        self.adjustment_history: List[WeightAdjustment] = []
        self.last_optimization_time = None

        # 스레드 안전성
        self._lock = threading.Lock()

        self.logger.info("동적 가중치 최적화기 초기화 완료")

    def optimize_portfolio_weights(self,
                                   optimization_method: WeightAdjustmentStrategy = WeightAdjustmentStrategy.PERFORMANCE_BASED) -> Optional[PortfolioOptimizationResult]:
        """포트폴리오 가중치 최적화"""

        with self._lock:
            try:
                self.logger.info(
                    f"포트폴리오 가중치 최적화 시작: {optimization_method.value}")

                # 현재 가중치 가져오기
                current_weights = self._get_current_weights()
                if not current_weights:
                    self.logger.warning("현재 가중치를 가져올 수 없음")
                    return None

                # 전략별 성과 분석
                strategy_metrics = self._analyze_all_strategies()
                if not strategy_metrics:
                    self.logger.warning("전략 성과 데이터 없음")
                    return None

                # 최적화 방법에 따른 가중치 계산
                optimized_weights = self._calculate_optimized_weights(
                    current_weights, strategy_metrics, optimization_method
                )

                # 최적화 결과 평가
                optimization_result = self._evaluate_optimization_result(
                    current_weights, optimized_weights, strategy_metrics, optimization_method
                )

                # 조정 기록 생성
                adjustments = self._create_weight_adjustments(
                    current_weights, optimized_weights, strategy_metrics, optimization_method
                )

                result = PortfolioOptimizationResult(
                    original_weights=current_weights,
                    optimized_weights=optimized_weights,
                    expected_return=optimization_result['expected_return'],
                    expected_risk=optimization_result['expected_risk'],
                    sharpe_ratio=optimization_result['sharpe_ratio'],
                    optimization_method=optimization_method.value,
                    confidence=optimization_result['confidence'],
                    adjustments=adjustments
                )

                self.adjustment_history.extend(adjustments)
                self.last_optimization_time = datetime.now()

                self.logger.info(f"포트폴리오 최적화 완료: {len(adjustments)}개 조정")
                return result

            except Exception as e:
                self.logger.error(f"포트폴리오 최적화 오류: {e}")
                return None

    def apply_weight_adjustments(self, optimization_result: PortfolioOptimizationResult) -> bool:
        """가중치 조정 적용"""
        try:
            if optimization_result.confidence < self.min_confidence:
                self.logger.warning(
                    f"신뢰도가 낮아 조정 적용 취소: {optimization_result.confidence:.3f}")
                return False

            # 설정 파일에 새로운 가중치 적용
            strategy_weights = optimization_result.optimized_weights

            success = config_manager.update_config(
                'independent_strategies.strategy_weights',
                strategy_weights
            )

            if success:
                self.logger.info(f"가중치 조정 적용 완료: {len(strategy_weights)}개 전략")

                # 조정 내역 로깅
                for adjustment in optimization_result.adjustments:
                    self.logger.info(
                        f"  {adjustment.strategy_id}: {adjustment.old_weight:.3f} → {adjustment.new_weight:.3f}")

                return True
            else:
                self.logger.error("설정 파일 업데이트 실패")
                return False

        except Exception as e:
            self.logger.error(f"가중치 조정 적용 오류: {e}")
            return False

    def should_run_optimization(self) -> bool:
        """최적화 실행 여부 판단"""
        if self.last_optimization_time is None:
            return True

        hours_since_last = (
            datetime.now() - self.last_optimization_time).total_seconds() / 3600
        return hours_since_last >= self.adjustment_frequency

    def auto_optimize_weights(self) -> Optional[PortfolioOptimizationResult]:
        """자동 가중치 최적화 (정기 실행용)"""

        if not self.should_run_optimization():
            return None

        try:
            # 성과 기반 최적화 실행
            result = self.optimize_portfolio_weights(
                WeightAdjustmentStrategy.PERFORMANCE_BASED)

            if result and result.confidence >= self.min_confidence:
                # 자동 적용
                applied = self.apply_weight_adjustments(result)
                if applied:
                    self.logger.info("자동 가중치 최적화 완료 및 적용")
                    return result

            self.logger.info("자동 최적화 조건 미충족")
            return result

        except Exception as e:
            self.logger.error(f"자동 가중치 최적화 오류: {e}")
            return None

    def _get_current_weights(self) -> Dict[str, float]:
        """현재 전략 가중치 조회"""
        try:
            weights = config_manager.get_config(
                'independent_strategies.strategy_weights', {})

            # 기본값 설정
            if not weights:
                active_strategies = self._get_active_strategies()
                weights = {
                    strategy_id: 1.0 for strategy_id in active_strategies}

            return weights

        except Exception as e:
            self.logger.error(f"현재 가중치 조회 오류: {e}")
            return {}

    def _analyze_all_strategies(self) -> Dict[str, AdvancedPerformanceMetrics]:
        """모든 전략 성과 분석"""
        strategy_metrics = {}

        try:
            active_strategies = self._get_active_strategies()

            for strategy_id in active_strategies:
                metrics = ai_performance_analyzer.analyze_strategy_performance(
                    strategy_id, self.lookback_period
                )
                if metrics:
                    strategy_metrics[strategy_id] = metrics

            return strategy_metrics

        except Exception as e:
            self.logger.error(f"전략 성과 분석 오류: {e}")
            return {}

    def _calculate_optimized_weights(self,
                                     current_weights: Dict[str, float],
                                     strategy_metrics: Dict[str, AdvancedPerformanceMetrics],
                                     method: WeightAdjustmentStrategy) -> Dict[str, float]:
        """최적화된 가중치 계산"""

        if method == WeightAdjustmentStrategy.PERFORMANCE_BASED:
            return self._performance_based_weights(strategy_metrics)
        elif method == WeightAdjustmentStrategy.RISK_ADJUSTED:
            return self._risk_adjusted_weights(strategy_metrics)
        elif method == WeightAdjustmentStrategy.SHARPE_OPTIMIZATION:
            return self._sharpe_optimized_weights(strategy_metrics)
        elif method == WeightAdjustmentStrategy.KELLY_CRITERION:
            return self._kelly_criterion_weights(strategy_metrics)
        else:
            return self._performance_based_weights(strategy_metrics)

    def _performance_based_weights(self, strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> Dict[str, float]:
        """성과 기반 가중치 계산"""
        weights = {}

        # AI 최적화 점수와 수익률 기반
        scores = {}
        for strategy_id, metrics in strategy_metrics.items():
            # 복합 점수: AI 점수 + 수익률 점수
            ai_score = metrics.ai_optimization_score / 100
            return_score = max(min(metrics.average_pnl / 1000, 1), -1)  # 정규화

            composite_score = (ai_score * 0.7) + (return_score * 0.3)
            scores[strategy_id] = max(composite_score, 0.1)  # 최소값 보장

        # 점수를 가중치로 변환
        total_score = sum(scores.values())
        if total_score > 0:
            for strategy_id, score in scores.items():
                weight = (score / total_score) * len(scores)  # 평균 1.0 유지
                weights[strategy_id] = max(
                    min(weight, self.max_weight), self.min_weight)

        return self._normalize_weights(weights)

    def _risk_adjusted_weights(self, strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> Dict[str, float]:
        """리스크 조정 가중치 계산"""
        weights = {}

        # 샤프 비율과 최대 낙폭 기반
        risk_scores = {}
        for strategy_id, metrics in strategy_metrics.items():
            sharpe_score = max(metrics.sharpe_ratio, 0) / 3  # 정규화 (3.0이 최대)
            drawdown_penalty = max(
                1 - (metrics.max_drawdown / 1000), 0.1)  # 낙폭 페널티

            risk_score = sharpe_score * drawdown_penalty
            risk_scores[strategy_id] = max(risk_score, 0.1)

        # 리스크 점수를 가중치로 변환
        total_score = sum(risk_scores.values())
        if total_score > 0:
            for strategy_id, score in risk_scores.items():
                weight = (score / total_score) * len(risk_scores)
                weights[strategy_id] = max(
                    min(weight, self.max_weight), self.min_weight)

        return self._normalize_weights(weights)

    def _sharpe_optimized_weights(self, strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> Dict[str, float]:
        """샤프 비율 최적화 가중치"""
        weights = {}

        sharpe_ratios = {}
        for strategy_id, metrics in strategy_metrics.items():
            sharpe_ratios[strategy_id] = max(metrics.sharpe_ratio, 0)

        # 샤프 비율 기반 가중치
        total_sharpe = sum(sharpe_ratios.values())
        if total_sharpe > 0:
            for strategy_id, sharpe in sharpe_ratios.items():
                weight = (sharpe / total_sharpe) * len(sharpe_ratios)
                weights[strategy_id] = max(
                    min(weight, self.max_weight), self.min_weight)

        return self._normalize_weights(weights)

    def _kelly_criterion_weights(self, strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> Dict[str, float]:
        """켈리 공식 기반 가중치"""
        weights = {}

        kelly_weights = {}
        for strategy_id, metrics in strategy_metrics.items():
            if metrics.average_loss > 0:
                # 켈리 공식: f = (bp - q) / b
                # b = 승률 시 평균 수익, p = 승률, q = 패율
                b = metrics.average_win / metrics.average_loss if metrics.average_loss > 0 else 1
                p = metrics.win_rate
                q = 1 - p

                kelly_fraction = (b * p - q) / b if b > 0 else 0
                kelly_weights[strategy_id] = max(kelly_fraction, 0.1)
            else:
                kelly_weights[strategy_id] = 0.1

        # 켈리 가중치 정규화
        total_kelly = sum(kelly_weights.values())
        if total_kelly > 0:
            for strategy_id, kelly in kelly_weights.items():
                weight = (kelly / total_kelly) * len(kelly_weights)
                weights[strategy_id] = max(
                    min(weight, self.max_weight), self.min_weight)

        return self._normalize_weights(weights)

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """가중치 정규화 (평균 1.0 유지)"""
        if not weights:
            return {}

        total_weight = sum(weights.values())
        if total_weight <= 0:
            return {k: 1.0 for k in weights.keys()}

        # 평균이 1.0이 되도록 정규화
        target_total = len(weights)
        normalization_factor = target_total / total_weight

        normalized = {}
        for strategy_id, weight in weights.items():
            normalized_weight = weight * normalization_factor
            normalized[strategy_id] = max(
                min(normalized_weight, self.max_weight), self.min_weight)

        return normalized

    def _evaluate_optimization_result(self,
                                      original_weights: Dict[str, float],
                                      optimized_weights: Dict[str, float],
                                      strategy_metrics: Dict[str, AdvancedPerformanceMetrics],
                                      method: WeightAdjustmentStrategy) -> Dict[str, float]:
        """최적화 결과 평가"""

        # 예상 수익률 계산
        original_return = self._calculate_portfolio_return(
            original_weights, strategy_metrics)
        optimized_return = self._calculate_portfolio_return(
            optimized_weights, strategy_metrics)

        # 예상 리스크 계산
        original_risk = self._calculate_portfolio_risk(
            original_weights, strategy_metrics)
        optimized_risk = self._calculate_portfolio_risk(
            optimized_weights, strategy_metrics)

        # 샤프 비율
        optimized_sharpe = optimized_return / optimized_risk if optimized_risk > 0 else 0

        # 신뢰도 계산
        confidence = self._calculate_optimization_confidence(
            original_weights, optimized_weights, strategy_metrics
        )

        return {
            'expected_return': optimized_return,
            'expected_risk': optimized_risk,
            'sharpe_ratio': optimized_sharpe,
            'confidence': confidence,
            'improvement': optimized_return - original_return
        }

    def _calculate_portfolio_return(self, weights: Dict[str, float],
                                    strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> float:
        """포트폴리오 예상 수익률 계산"""
        total_return = 0
        total_weight = sum(weights.values())

        for strategy_id, weight in weights.items():
            if strategy_id in strategy_metrics:
                strategy_return = strategy_metrics[strategy_id].average_pnl
                weighted_return = (weight / total_weight) * strategy_return
                total_return += weighted_return

        return total_return

    def _calculate_portfolio_risk(self, weights: Dict[str, float],
                                  strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> float:
        """포트폴리오 예상 리스크 계산"""
        total_variance = 0
        total_weight = sum(weights.values())

        for strategy_id, weight in weights.items():
            if strategy_id in strategy_metrics:
                strategy_volatility = strategy_metrics[strategy_id].volatility
                weighted_variance = ((weight / total_weight)
                                     ** 2) * (strategy_volatility ** 2)
                total_variance += weighted_variance

        return np.sqrt(total_variance)

    def _calculate_optimization_confidence(self,
                                           original_weights: Dict[str, float],
                                           optimized_weights: Dict[str, float],
                                           strategy_metrics: Dict[str, AdvancedPerformanceMetrics]) -> float:
        """최적화 신뢰도 계산"""

        # 1. 데이터 충분성 (거래 수 기반)
        avg_trades = np.mean(
            [m.total_trades for m in strategy_metrics.values()])
        data_confidence = min(avg_trades / 50, 1.0)  # 50회 거래에서 최대 신뢰도

        # 2. 가중치 변화 크기 (작은 변화일수록 신뢰도 높음)
        weight_changes = []
        for strategy_id in original_weights:
            if strategy_id in optimized_weights:
                change = abs(
                    optimized_weights[strategy_id] - original_weights[strategy_id])
                weight_changes.append(change)

        avg_change = np.mean(weight_changes) if weight_changes else 0
        change_confidence = max(1 - (avg_change / 1.0), 0.3)  # 최소 30%

        # 3. 성과 일관성
        performance_scores = [
            m.ai_optimization_score for m in strategy_metrics.values()]
        performance_consistency = 1 - (np.std(performance_scores) / 100)
        performance_confidence = max(performance_consistency, 0.4)

        # 종합 신뢰도
        total_confidence = (data_confidence * 0.4 +
                            change_confidence * 0.3 +
                            performance_confidence * 0.3)

        return max(min(total_confidence, 1.0), 0.1)

    def _create_weight_adjustments(self,
                                   original_weights: Dict[str, float],
                                   optimized_weights: Dict[str, float],
                                   strategy_metrics: Dict[str, AdvancedPerformanceMetrics],
                                   method: WeightAdjustmentStrategy) -> List[WeightAdjustment]:
        """가중치 조정 기록 생성"""
        adjustments = []

        for strategy_id in optimized_weights:
            old_weight = original_weights.get(strategy_id, 1.0)
            new_weight = optimized_weights[strategy_id]

            if abs(new_weight - old_weight) > 0.05:  # 5% 이상 변화만 기록
                metrics = strategy_metrics.get(strategy_id)

                # 조정 이유 생성
                if new_weight > old_weight:
                    reason = f"성과 개선으로 가중치 증가 (AI점수: {metrics.ai_optimization_score:.1f})" if metrics else "성과 개선으로 가중치 증가"
                else:
                    reason = f"성과 저하로 가중치 감소 (AI점수: {metrics.ai_optimization_score:.1f})" if metrics else "성과 저하로 가중치 감소"

                adjustment = WeightAdjustment(
                    strategy_id=strategy_id,
                    old_weight=old_weight,
                    new_weight=new_weight,
                    adjustment_reason=reason,
                    adjustment_strategy=method,
                    confidence=0.7,  # 기본 신뢰도
                    expected_improvement=abs(
                        (new_weight - old_weight) / old_weight) * 10,
                    timestamp=datetime.now()
                )

                adjustments.append(adjustment)

        return adjustments

    def _get_active_strategies(self) -> List[str]:
        """활성화된 전략 목록 조회"""
        try:
            strategy_config = config_manager.get_config(
                'independent_strategies.strategies', {})
            active_strategies = []

            for strategy_id, config in strategy_config.items():
                if config.get('enabled', True):
                    active_strategies.append(strategy_id)

            return active_strategies

        except Exception as e:
            self.logger.error(f"활성 전략 목록 조회 오류: {e}")
            return []

    def get_optimization_history(self, days: int = 7) -> List[Dict]:
        """최적화 이력 조회"""
        cutoff_date = datetime.now() - timedelta(days=days)

        recent_adjustments = [
            adj.to_dict() for adj in self.adjustment_history
            if adj.timestamp >= cutoff_date
        ]

        return recent_adjustments


# 전역 인스턴스
dynamic_weight_optimizer = DynamicWeightOptimizer()
