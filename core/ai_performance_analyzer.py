#!/usr/bin/env python3
"""
AI 기반 전략 성과 분석기
전략별 성과를 분석하고 최적화 제안을 생성하는 고급 분석 모듈
"""

import sqlite3
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
import statistics
from pathlib import Path

from config.config_manager import config_manager


class PerformanceMetric(Enum):
    """성과 지표 유형"""
    SHARPE_RATIO = "sharpe_ratio"           # 샤프 비율
    WIN_RATE = "win_rate"                   # 승률
    PROFIT_FACTOR = "profit_factor"         # 이익 팩터
    MAX_DRAWDOWN = "max_drawdown"           # 최대 낙폭
    AVERAGE_RETURN = "average_return"       # 평균 수익률
    VOLATILITY = "volatility"               # 변동성
    CALMAR_RATIO = "calmar_ratio"           # 칼마 비율
    SORTINO_RATIO = "sortino_ratio"         # 소르티노 비율


@dataclass
class AdvancedPerformanceMetrics:
    """고급 성과 지표"""
    strategy_id: str
    period_days: int

    # 기본 지표
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    # 수익성 지표
    total_pnl: float
    average_pnl: float
    average_win: float
    average_loss: float
    profit_factor: float

    # 리스크 지표
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    volatility: float

    # 효율성 지표
    avg_confidence: float
    signal_accuracy: float        # 신호 정확도
    execution_efficiency: float   # 실행 효율성

    # 시간 분석
    best_performance_hour: int
    worst_performance_hour: int
    avg_execution_time: float

    # 트렌드 분석
    performance_trend: str        # 'improving', 'stable', 'declining'
    recent_performance: float     # 최근 7일 성과

    # AI 점수
    ai_optimization_score: float  # 0-100점
    optimization_priority: int    # 1(높음) - 5(낮음)

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class OptimizationRecommendation:
    """최적화 권장사항"""
    strategy_id: str
    priority: int                 # 1(긴급) - 5(낮음)
    category: str                # 'weight', 'parameter', 'timing', 'disable'
    action: str                  # 구체적 액션
    expected_improvement: float  # 예상 개선율 (%)
    confidence: float           # 권장 신뢰도
    reasoning: str              # 권장 이유
    parameters: Dict[str, Any]  # 권장 파라미터 변경


class AIPerformanceAnalyzer:
    """AI 기반 성과 분석기"""

    def __init__(self, db_path: str = "data/strategy_executions.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('AIPerformanceAnalyzer')

        # 분석 파라미터
        self.min_trades_for_analysis = 10
        self.analysis_periods = [7, 30, 90]  # 분석 기간 (일)
        self.risk_free_rate = 0.025  # 무위험 수익률 (연 2.5%)

        self.logger.info("AI 성과 분석기 초기화 완료")

    def analyze_strategy_performance(self, strategy_id: str,
                                     days: int = 30) -> Optional[AdvancedPerformanceMetrics]:
        """전략별 고급 성과 분석"""
        try:
            # 전략 실행 데이터 수집
            executions = self._get_strategy_executions(strategy_id, days)

            if len(executions) < self.min_trades_for_analysis:
                self.logger.warning(
                    f"분석을 위한 최소 거래 수({self.min_trades_for_analysis}) 미달: {len(executions)}")
                return None

            # 데이터프레임 생성
            df = pd.DataFrame(executions)
            df['execution_time'] = pd.to_datetime(df['execution_time'])
            df['pnl'] = df['pnl'].astype(float)
            df['confidence'] = df['confidence'].astype(float)

            # 기본 지표 계산
            total_trades = len(df)
            winning_trades = len(df[df['pnl'] > 0])
            losing_trades = len(df[df['pnl'] < 0])
            win_rate = winning_trades / total_trades if total_trades > 0 else 0

            # 수익성 지표
            total_pnl = df['pnl'].sum()
            average_pnl = df['pnl'].mean()
            average_win = df[df['pnl'] > 0]['pnl'].mean(
            ) if winning_trades > 0 else 0
            average_loss = abs(df[df['pnl'] < 0]['pnl'].mean()
                               ) if losing_trades > 0 else 0
            profit_factor = average_win / \
                average_loss if average_loss > 0 else float('inf')

            # 리스크 지표 계산
            returns = df['pnl'].values
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sortino_ratio = self._calculate_sortino_ratio(returns)
            max_drawdown = self._calculate_max_drawdown(returns)
            volatility = np.std(returns) if len(returns) > 1 else 0
            calmar_ratio = abs(average_pnl) / \
                max_drawdown if max_drawdown > 0 else 0

            # 효율성 지표
            avg_confidence = df['confidence'].mean()
            signal_accuracy = self._calculate_signal_accuracy(df)
            execution_efficiency = self._calculate_execution_efficiency(df)

            # 시간 분석
            hourly_performance = self._analyze_hourly_performance(df)
            best_hour = max(hourly_performance.items(), key=lambda x: x[1])[
                0] if hourly_performance else 0
            worst_hour = min(hourly_performance.items(), key=lambda x: x[1])[
                0] if hourly_performance else 0
            avg_execution_time = df['execution_duration'].mean(
            ) if 'execution_duration' in df.columns else 0

            # 트렌드 분석
            performance_trend = self._analyze_performance_trend(df)
            recent_performance = self._calculate_recent_performance(df, 7)

            # AI 최적화 점수
            ai_score = self._calculate_ai_optimization_score(
                win_rate, sharpe_ratio, max_drawdown, signal_accuracy, performance_trend
            )
            optimization_priority = self._determine_optimization_priority(
                ai_score, total_trades)

            return AdvancedPerformanceMetrics(
                strategy_id=strategy_id,
                period_days=days,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                average_pnl=average_pnl,
                average_win=average_win,
                average_loss=average_loss,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=max_drawdown,
                volatility=volatility,
                avg_confidence=avg_confidence,
                signal_accuracy=signal_accuracy,
                execution_efficiency=execution_efficiency,
                best_performance_hour=best_hour,
                worst_performance_hour=worst_hour,
                avg_execution_time=avg_execution_time,
                performance_trend=performance_trend,
                recent_performance=recent_performance,
                ai_optimization_score=ai_score,
                optimization_priority=optimization_priority
            )

        except Exception as e:
            self.logger.error(f"전략 성과 분석 오류 ({strategy_id}): {e}")
            return None

    def generate_optimization_recommendations(self,
                                              strategy_metrics: List[AdvancedPerformanceMetrics]) -> List[OptimizationRecommendation]:
        """최적화 권장사항 생성"""
        recommendations = []

        for metrics in strategy_metrics:
            try:
                # 전략별 권장사항 생성
                strategy_recommendations = self._analyze_strategy_for_optimization(
                    metrics)
                recommendations.extend(strategy_recommendations)

            except Exception as e:
                self.logger.error(f"권장사항 생성 오류 ({metrics.strategy_id}): {e}")

        # 우선순위별 정렬
        recommendations.sort(key=lambda x: (
            x.priority, -x.expected_improvement))

        return recommendations

    def get_portfolio_performance_summary(self, days: int = 30) -> Dict[str, Any]:
        """포트폴리오 전체 성과 요약"""
        try:
            # 모든 활성 전략 목록 가져오기
            active_strategies = self._get_active_strategies()

            portfolio_metrics = {}
            total_pnl = 0
            total_trades = 0
            weighted_win_rate = 0

            for strategy_id in active_strategies:
                metrics = self.analyze_strategy_performance(strategy_id, days)
                if metrics:
                    portfolio_metrics[strategy_id] = metrics
                    total_pnl += metrics.total_pnl
                    total_trades += metrics.total_trades
                    weighted_win_rate += metrics.win_rate * metrics.total_trades

            overall_win_rate = weighted_win_rate / total_trades if total_trades > 0 else 0

            # 포트폴리오 리스크 계산
            strategy_returns = []
            for metrics in portfolio_metrics.values():
                if metrics.total_trades > 0:
                    strategy_returns.append(metrics.average_pnl)

            portfolio_volatility = np.std(strategy_returns) if len(
                strategy_returns) > 1 else 0
            portfolio_sharpe = self._calculate_sharpe_ratio(
                strategy_returns) if strategy_returns else 0

            return {
                'analysis_period': days,
                'total_strategies': len(portfolio_metrics),
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'overall_win_rate': overall_win_rate,
                'portfolio_volatility': portfolio_volatility,
                'portfolio_sharpe_ratio': portfolio_sharpe,
                'best_performing_strategy': max(portfolio_metrics.items(),
                                                key=lambda x: x[1].ai_optimization_score)[0] if portfolio_metrics else None,
                'worst_performing_strategy': min(portfolio_metrics.items(),
                                                 key=lambda x: x[1].ai_optimization_score)[0] if portfolio_metrics else None,
                'strategies_needing_optimization': len([m for m in portfolio_metrics.values()
                                                        if m.optimization_priority <= 2]),
                'avg_ai_score': np.mean([m.ai_optimization_score for m in portfolio_metrics.values()]) if portfolio_metrics else 0
            }

        except Exception as e:
            self.logger.error(f"포트폴리오 성과 요약 오류: {e}")
            return {}

    def _get_strategy_executions(self, strategy_id: str, days: int) -> List[Dict]:
        """전략 실행 데이터 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                start_date = (datetime.now() -
                              timedelta(days=days)).isoformat()

                cursor = conn.execute('''
                    SELECT execution_time, strategy_id, signal_action, confidence, 
                           strength, pnl, trade_executed, execution_duration
                    FROM strategy_executions 
                    WHERE strategy_id = ? AND execution_time >= ?
                    ORDER BY execution_time DESC
                ''', (strategy_id, start_date))

                columns = [description[0]
                           for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"전략 실행 데이터 조회 오류: {e}")
            return []

    def _calculate_sharpe_ratio(self, returns: np.ndarray) -> float:
        """샤프 비율 계산"""
        if len(returns) < 2:
            return 0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0

        # 일일 무위험 수익률
        daily_risk_free = self.risk_free_rate / 365
        return (mean_return - daily_risk_free) / std_return

    def _calculate_sortino_ratio(self, returns: np.ndarray) -> float:
        """소르티노 비율 계산 (하방 리스크만 고려)"""
        if len(returns) < 2:
            return 0

        mean_return = np.mean(returns)
        negative_returns = returns[returns < 0]

        if len(negative_returns) == 0:
            return float('inf')

        downside_deviation = np.std(negative_returns)
        if downside_deviation == 0:
            return 0

        daily_risk_free = self.risk_free_rate / 365
        return (mean_return - daily_risk_free) / downside_deviation

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """최대 낙폭 계산"""
        if len(returns) < 2:
            return 0

        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max

        return abs(np.min(drawdown))

    def _calculate_signal_accuracy(self, df: pd.DataFrame) -> float:
        """신호 정확도 계산"""
        if len(df) == 0:
            return 0

        # 매수/매도 신호의 정확도 계산
        buy_signals = df[df['signal_action'] == 'buy']
        sell_signals = df[df['signal_action'] == 'sell']

        buy_accuracy = len(buy_signals[buy_signals['pnl'] > 0]) / \
            len(buy_signals) if len(buy_signals) > 0 else 0
        sell_accuracy = len(sell_signals[sell_signals['pnl'] > 0]) / \
            len(sell_signals) if len(sell_signals) > 0 else 0

        # 가중 평균
        total_signals = len(buy_signals) + len(sell_signals)
        if total_signals == 0:
            return 0

        weighted_accuracy = (buy_accuracy * len(buy_signals) +
                             sell_accuracy * len(sell_signals)) / total_signals
        return weighted_accuracy

    def _calculate_execution_efficiency(self, df: pd.DataFrame) -> float:
        """실행 효율성 계산"""
        if len(df) == 0:
            return 0

        # 거래 실행률
        executed_trades = len(df[df['trade_executed'] == True])
        execution_rate = executed_trades / len(df)

        # 고신뢰도 신호의 실행률
        high_confidence_signals = df[df['confidence'] > 0.7]
        if len(high_confidence_signals) > 0:
            high_conf_execution_rate = len(
                high_confidence_signals[high_confidence_signals['trade_executed'] == True]) / len(high_confidence_signals)
        else:
            high_conf_execution_rate = 0

        # 효율성 점수 (실행률 + 고신뢰도 실행률의 가중 평균)
        efficiency = (execution_rate * 0.6) + (high_conf_execution_rate * 0.4)
        return efficiency

    def _analyze_hourly_performance(self, df: pd.DataFrame) -> Dict[int, float]:
        """시간대별 성과 분석"""
        if len(df) == 0:
            return {}

        df['hour'] = df['execution_time'].dt.hour
        hourly_pnl = df.groupby('hour')['pnl'].mean().to_dict()
        return hourly_pnl

    def _analyze_performance_trend(self, df: pd.DataFrame) -> str:
        """성과 트렌드 분석"""
        if len(df) < 10:
            return 'insufficient_data'

        # 최근 데이터를 시간순으로 정렬
        df_sorted = df.sort_values('execution_time')

        # 이동평균을 사용한 트렌드 분석
        window_size = min(7, len(df_sorted) // 3)
        if window_size < 3:
            return 'insufficient_data'

        rolling_pnl = df_sorted['pnl'].rolling(window=window_size).mean()

        # 트렌드 기울기 계산
        recent_avg = rolling_pnl.tail(window_size).mean()
        older_avg = rolling_pnl.head(window_size).mean()

        trend_slope = (recent_avg - older_avg) / len(rolling_pnl)

        if trend_slope > 0.01:  # 임계값
            return 'improving'
        elif trend_slope < -0.01:
            return 'declining'
        else:
            return 'stable'

    def _calculate_recent_performance(self, df: pd.DataFrame, recent_days: int) -> float:
        """최근 성과 계산"""
        if len(df) == 0:
            return 0

        recent_date = datetime.now() - timedelta(days=recent_days)
        recent_df = df[df['execution_time'] >= recent_date]

        if len(recent_df) == 0:
            return 0

        return recent_df['pnl'].mean()

    def _calculate_ai_optimization_score(self, win_rate: float, sharpe_ratio: float,
                                         max_drawdown: float, signal_accuracy: float,
                                         performance_trend: str) -> float:
        """AI 최적화 점수 계산 (0-100)"""

        # 각 지표별 점수 (0-25점)
        win_rate_score = min(win_rate * 50, 25)  # 50% 승률에서 만점
        sharpe_score = min(max(sharpe_ratio * 10, 0), 25)  # 2.5 샤프비율에서 만점
        drawdown_score = max(25 - (max_drawdown * 100), 0)  # 낙폭이 적을수록 높은 점수
        accuracy_score = signal_accuracy * 25

        # 트렌드 보너스/페널티
        trend_bonus = {'improving': 5, 'stable': 0,
                       'declining': -5, 'insufficient_data': 0}
        trend_score = trend_bonus.get(performance_trend, 0)

        total_score = win_rate_score + sharpe_score + \
            drawdown_score + accuracy_score + trend_score
        return max(min(total_score, 100), 0)  # 0-100 범위로 제한

    def _determine_optimization_priority(self, ai_score: float, total_trades: int) -> int:
        """최적화 우선순위 결정 (1=높음, 5=낮음)"""

        # 거래 수가 적으면 우선순위 낮춤
        if total_trades < self.min_trades_for_analysis * 2:
            return 4

        if ai_score >= 80:
            return 5  # 우수한 성과, 낮은 우선순위
        elif ai_score >= 60:
            return 4  # 양호한 성과
        elif ai_score >= 40:
            return 3  # 보통 성과, 개선 필요
        elif ai_score >= 20:
            return 2  # 저조한 성과, 높은 우선순위
        else:
            return 1  # 매우 저조한 성과, 긴급 개선 필요

    def _analyze_strategy_for_optimization(self, metrics: AdvancedPerformanceMetrics) -> List[OptimizationRecommendation]:
        """전략별 최적화 분석"""
        recommendations = []

        try:
            # 1. 가중치 조정 권장
            if metrics.ai_optimization_score < 40:
                if metrics.win_rate < 0.4:
                    recommendations.append(OptimizationRecommendation(
                        strategy_id=metrics.strategy_id,
                        priority=1,
                        category='weight',
                        action='reduce_weight',
                        expected_improvement=15.0,
                        confidence=0.8,
                        reasoning=f"승률이 {metrics.win_rate:.1%}로 낮아 가중치 감소 필요",
                        parameters={'new_weight': 0.5}
                    ))

            # 2. 파라미터 조정 권장
            if metrics.signal_accuracy < 0.5:
                recommendations.append(OptimizationRecommendation(
                    strategy_id=metrics.strategy_id,
                    priority=2,
                    category='parameter',
                    action='adjust_sensitivity',
                    expected_improvement=10.0,
                    confidence=0.7,
                    reasoning=f"신호 정확도가 {metrics.signal_accuracy:.1%}로 낮아 민감도 조정 필요",
                    parameters={'sensitivity_adjustment': 0.8}
                ))

            # 3. 타이밍 최적화 권장
            if abs(metrics.best_performance_hour - metrics.worst_performance_hour) > 2:
                recommendations.append(OptimizationRecommendation(
                    strategy_id=metrics.strategy_id,
                    priority=3,
                    category='timing',
                    action='optimize_trading_hours',
                    expected_improvement=8.0,
                    confidence=0.6,
                    reasoning=f"시간대별 성과 차이가 커서 거래 시간 최적화 권장",
                    parameters={'preferred_hours': [
                        metrics.best_performance_hour]}
                ))

            # 4. 전략 비활성화 권장
            if metrics.ai_optimization_score < 20 and metrics.total_trades > 20:
                recommendations.append(OptimizationRecommendation(
                    strategy_id=metrics.strategy_id,
                    priority=1,
                    category='disable',
                    action='temporary_disable',
                    expected_improvement=5.0,
                    confidence=0.9,
                    reasoning=f"AI 점수가 {metrics.ai_optimization_score:.1f}점으로 매우 낮아 일시 비활성화 권장",
                    parameters={'disable_duration_hours': 24}
                ))

        except Exception as e:
            self.logger.error(f"전략 최적화 분석 오류 ({metrics.strategy_id}): {e}")

        return recommendations

    def _get_active_strategies(self) -> List[str]:
        """활성화된 전략 목록 조회"""
        try:
            # VotingStrategyEngine에서 활성 전략 목록 가져오기
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


# 전역 인스턴스
ai_performance_analyzer = AIPerformanceAnalyzer()
