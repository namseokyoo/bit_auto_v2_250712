#!/usr/bin/env python3
"""
적응형 거래 최적화기
시장 상황에 따라 거래 주기와 전략 파라미터를 자동으로 최적화하는 시스템
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
import statistics

from config.config_manager import config_manager
from core.ai_performance_analyzer import ai_performance_analyzer


class MarketCondition(Enum):
    """시장 상황"""
    BULL_MARKET = "bull_market"        # 강세장
    BEAR_MARKET = "bear_market"        # 약세장
    SIDEWAYS = "sideways"              # 횡보장
    HIGH_VOLATILITY = "high_volatility"  # 고변동성
    LOW_VOLATILITY = "low_volatility"   # 저변동성
    TRENDING = "trending"               # 추세장
    RANGE_BOUND = "range_bound"         # 박스권


class OptimizationParameter(Enum):
    """최적화 파라미터"""
    TRADING_INTERVAL = "trading_interval"           # 거래 주기
    CONFIDENCE_THRESHOLD = "confidence_threshold"   # 신뢰도 임계값
    RISK_LIMIT = "risk_limit"                      # 리스크 한계
    POSITION_SIZE = "position_size"                # 포지션 크기
    STRATEGY_SENSITIVITY = "strategy_sensitivity"   # 전략 민감도


@dataclass
class MarketAnalysis:
    """시장 분석 결과"""
    timestamp: datetime
    condition: MarketCondition
    volatility: float
    trend_strength: float
    volume_profile: float
    support_resistance_strength: float
    momentum_score: float
    confidence: float

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'condition': self.condition.value,
            'volatility': self.volatility,
            'trend_strength': self.trend_strength,
            'volume_profile': self.volume_profile,
            'support_resistance_strength': self.support_resistance_strength,
            'momentum_score': self.momentum_score,
            'confidence': self.confidence
        }


@dataclass
class OptimizationRecommendation:
    """최적화 권장사항"""
    parameter: OptimizationParameter
    current_value: Any
    recommended_value: Any
    reason: str
    expected_improvement: float
    confidence: float
    market_condition: MarketCondition
    timestamp: datetime

    def to_dict(self) -> Dict:
        return {
            'parameter': self.parameter.value,
            'current_value': self.current_value,
            'recommended_value': self.recommended_value,
            'reason': self.reason,
            'expected_improvement': self.expected_improvement,
            'confidence': self.confidence,
            'market_condition': self.market_condition.value,
            'timestamp': self.timestamp.isoformat()
        }


class AdaptiveTradingOptimizer:
    """적응형 거래 최적화기"""

    def __init__(self):
        self.logger = logging.getLogger('AdaptiveTradingOptimizer')

        # 최적화 설정
        self.optimization_interval = 6  # 6시간마다 실행
        self.market_analysis_window = 24  # 24시간 시장 분석
        self.min_confidence_for_change = 0.7  # 변경을 위한 최소 신뢰도

        # 거래 주기 범위
        self.min_trading_interval = 1    # 최소 1분
        self.max_trading_interval = 60   # 최대 60분

        # 시장 분석 이력
        self.market_analysis_history: List[MarketAnalysis] = []
        self.optimization_history: List[OptimizationRecommendation] = []

        # 스레드 안전성
        self._lock = threading.Lock()

        self.logger.info("적응형 거래 최적화기 초기화 완료")

    def analyze_market_condition(self) -> Optional[MarketAnalysis]:
        """현재 시장 상황 분석"""
        try:
            # 시장 데이터 수집
            market_data = self._collect_market_data()
            if not market_data:
                self.logger.warning("시장 데이터 수집 실패")
                return None

            # 변동성 분석
            volatility = self._calculate_volatility(market_data)

            # 추세 강도 분석
            trend_strength = self._calculate_trend_strength(market_data)

            # 거래량 프로파일
            volume_profile = self._analyze_volume_profile(market_data)

            # 지지/저항 강도
            support_resistance = self._analyze_support_resistance(market_data)

            # 모멘텀 점수
            momentum_score = self._calculate_momentum_score(market_data)

            # 시장 상황 분류
            market_condition = self._classify_market_condition(
                volatility, trend_strength, volume_profile, momentum_score
            )

            # 신뢰도 계산
            confidence = self._calculate_analysis_confidence(market_data)

            analysis = MarketAnalysis(
                timestamp=datetime.now(),
                condition=market_condition,
                volatility=volatility,
                trend_strength=trend_strength,
                volume_profile=volume_profile,
                support_resistance_strength=support_resistance,
                momentum_score=momentum_score,
                confidence=confidence
            )

            # 이력에 추가
            with self._lock:
                self.market_analysis_history.append(analysis)
                # 최근 100개만 유지
                if len(self.market_analysis_history) > 100:
                    self.market_analysis_history = self.market_analysis_history[-100:]

            self.logger.info(
                f"시장 분석 완료: {market_condition.value}, 신뢰도: {confidence:.3f}")
            return analysis

        except Exception as e:
            self.logger.error(f"시장 분석 오류: {e}")
            return None

    def generate_optimization_recommendations(self,
                                              market_analysis: MarketAnalysis) -> List[OptimizationRecommendation]:
        """최적화 권장사항 생성"""
        recommendations = []

        try:
            # 1. 거래 주기 최적화
            trading_interval_rec = self._optimize_trading_interval(
                market_analysis)
            if trading_interval_rec:
                recommendations.append(trading_interval_rec)

            # 2. 신뢰도 임계값 최적화
            confidence_threshold_rec = self._optimize_confidence_threshold(
                market_analysis)
            if confidence_threshold_rec:
                recommendations.append(confidence_threshold_rec)

            # 3. 리스크 한계 조정
            risk_limit_rec = self._optimize_risk_limits(market_analysis)
            if risk_limit_rec:
                recommendations.append(risk_limit_rec)

            # 4. 포지션 크기 최적화
            position_size_rec = self._optimize_position_size(market_analysis)
            if position_size_rec:
                recommendations.append(position_size_rec)

            # 5. 전략 민감도 조정
            sensitivity_rec = self._optimize_strategy_sensitivity(
                market_analysis)
            if sensitivity_rec:
                recommendations.append(sensitivity_rec)

            # 신뢰도순 정렬
            recommendations.sort(key=lambda x: x.confidence, reverse=True)

            self.logger.info(f"최적화 권장사항 {len(recommendations)}개 생성")
            return recommendations

        except Exception as e:
            self.logger.error(f"최적화 권장사항 생성 오류: {e}")
            return []

    def apply_optimization_recommendations(self,
                                           recommendations: List[OptimizationRecommendation]) -> Dict[str, bool]:
        """최적화 권장사항 적용"""
        results = {}

        for rec in recommendations:
            try:
                if rec.confidence < self.min_confidence_for_change:
                    self.logger.info(f"신뢰도 부족으로 {rec.parameter.value} 변경 건너뜀")
                    results[rec.parameter.value] = False
                    continue

                success = self._apply_single_recommendation(rec)
                results[rec.parameter.value] = success

                if success:
                    self.logger.info(
                        f"{rec.parameter.value} 최적화 적용: {rec.current_value} → {rec.recommended_value}")
                else:
                    self.logger.warning(f"{rec.parameter.value} 최적화 적용 실패")

            except Exception as e:
                self.logger.error(f"권장사항 적용 오류 ({rec.parameter.value}): {e}")
                results[rec.parameter.value] = False

        return results

    def auto_optimize(self) -> Dict[str, Any]:
        """자동 최적화 실행"""
        try:
            self.logger.info("자동 최적화 시작")

            # 1. 시장 분석
            market_analysis = self.analyze_market_condition()
            if not market_analysis:
                return {'success': False, 'message': '시장 분석 실패'}

            # 2. 최적화 권장사항 생성
            recommendations = self.generate_optimization_recommendations(
                market_analysis)
            if not recommendations:
                return {'success': True, 'message': '최적화 권장사항 없음', 'market_condition': market_analysis.condition.value}

            # 3. 권장사항 적용
            application_results = self.apply_optimization_recommendations(
                recommendations)

            # 4. 결과 정리
            applied_count = sum(
                1 for success in application_results.values() if success)

            # 5. 이력에 추가
            with self._lock:
                self.optimization_history.extend(recommendations)
                # 최근 50개만 유지
                if len(self.optimization_history) > 50:
                    self.optimization_history = self.optimization_history[-50:]

            result = {
                'success': True,
                'market_condition': market_analysis.condition.value,
                'market_confidence': market_analysis.confidence,
                'total_recommendations': len(recommendations),
                'applied_recommendations': applied_count,
                'application_results': application_results,
                # 상위 3개만
                'recommendations': [rec.to_dict() for rec in recommendations[:3]]
            }

            self.logger.info(
                f"자동 최적화 완료: {applied_count}/{len(recommendations)} 적용")
            return result

        except Exception as e:
            self.logger.error(f"자동 최적화 오류: {e}")
            return {'success': False, 'message': f'자동 최적화 오류: {str(e)}'}

    def _collect_market_data(self) -> Optional[Dict]:
        """시장 데이터 수집"""
        try:
            from core.upbit_api import UpbitAPI
            api = UpbitAPI()

            # 다양한 시간대 캔들 데이터 수집
            candles_1h = api.get_candles(
                'KRW-BTC', minutes=60, count=24)  # 24시간
            candles_5m = api.get_candles(
                'KRW-BTC', minutes=5, count=288)  # 24시간 5분봉

            if not candles_1h or not candles_5m:
                return None

            # 현재가 정보
            ticker = api._make_request(
                'GET', '/v1/ticker', {'markets': 'KRW-BTC'})
            current_price = float(ticker[0]['trade_price']) if ticker and len(
                ticker) > 0 else None

            return {
                'candles_1h': candles_1h,
                'candles_5m': candles_5m,
                'current_price': current_price,
                'timestamp': datetime.now()
            }

        except Exception as e:
            self.logger.error(f"시장 데이터 수집 오류: {e}")
            return None

    def _calculate_volatility(self, market_data: Dict) -> float:
        """변동성 계산"""
        try:
            candles = market_data['candles_1h']
            if not candles or len(candles) < 10:
                return 0.5  # 기본값

            # 가격 변화율 계산
            prices = [float(candle['trade_price']) for candle in candles]
            returns = []

            for i in range(1, len(prices)):
                return_rate = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(return_rate)

            # 표준편차로 변동성 측정
            volatility = np.std(returns) if len(returns) > 1 else 0

            # 0-1 범위로 정규화 (일반적으로 일일 변동성 5% 이상은 높은 변동성)
            normalized_volatility = min(volatility / 0.05, 1.0)

            return normalized_volatility

        except Exception as e:
            self.logger.error(f"변동성 계산 오류: {e}")
            return 0.5

    def _calculate_trend_strength(self, market_data: Dict) -> float:
        """추세 강도 계산"""
        try:
            candles = market_data['candles_1h']
            if not candles or len(candles) < 10:
                return 0.5

            prices = [float(candle['trade_price']) for candle in candles]

            # 선형 회귀를 통한 추세 강도
            x = np.arange(len(prices))
            y = np.array(prices)

            # 회귀 계수 계산
            correlation = np.corrcoef(x, y)[0, 1]
            trend_strength = abs(correlation)  # 0-1 범위

            return trend_strength

        except Exception as e:
            self.logger.error(f"추세 강도 계산 오류: {e}")
            return 0.5

    def _analyze_volume_profile(self, market_data: Dict) -> float:
        """거래량 프로파일 분석"""
        try:
            candles = market_data['candles_5m']
            if not candles or len(candles) < 50:
                return 0.5

            volumes = [float(candle['candle_acc_trade_volume'])
                       for candle in candles[-50:]]

            # 최근 거래량 vs 평균 거래량
            recent_volume = np.mean(volumes[-10:])
            avg_volume = np.mean(volumes)

            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1

            # 0-1 범위로 정규화 (2배 이상은 높은 거래량)
            normalized_volume = min(volume_ratio / 2.0, 1.0)

            return normalized_volume

        except Exception as e:
            self.logger.error(f"거래량 프로파일 분석 오류: {e}")
            return 0.5

    def _analyze_support_resistance(self, market_data: Dict) -> float:
        """지지/저항 강도 분석"""
        try:
            candles = market_data['candles_1h']
            if not candles or len(candles) < 20:
                return 0.5

            highs = [float(candle['high_price']) for candle in candles]
            lows = [float(candle['low_price']) for candle in candles]

            # 가격 범위 분석
            price_range = max(highs) - min(lows)
            current_price = market_data.get(
                'current_price', (max(highs) + min(lows)) / 2)

            # 현재가가 범위의 중간에 가까울수록 지지/저항이 강함
            mid_price = (max(highs) + min(lows)) / 2
            distance_from_mid = abs(
                current_price - mid_price) / (price_range / 2) if price_range > 0 else 0

            support_resistance_strength = 1 - min(distance_from_mid, 1.0)

            return support_resistance_strength

        except Exception as e:
            self.logger.error(f"지지/저항 분석 오류: {e}")
            return 0.5

    def _calculate_momentum_score(self, market_data: Dict) -> float:
        """모멘텀 점수 계산"""
        try:
            candles = market_data['candles_1h']
            if not candles or len(candles) < 14:
                return 0.5

            closes = [float(candle['trade_price']) for candle in candles]

            # RSI 계산
            gains = []
            losses = []

            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            if len(gains) >= 14:
                avg_gain = np.mean(gains[-14:])
                avg_loss = np.mean(losses[-14:])

                rs = avg_gain / avg_loss if avg_loss > 0 else 100
                rsi = 100 - (100 / (1 + rs))

                # RSI를 0-1 범위로 정규화
                momentum_score = rsi / 100
            else:
                momentum_score = 0.5

            return momentum_score

        except Exception as e:
            self.logger.error(f"모멘텀 점수 계산 오류: {e}")
            return 0.5

    def _classify_market_condition(self, volatility: float, trend_strength: float,
                                   volume_profile: float, momentum_score: float) -> MarketCondition:
        """시장 상황 분류"""

        # 고변동성 체크
        if volatility > 0.7:
            return MarketCondition.HIGH_VOLATILITY

        # 저변동성 체크
        if volatility < 0.3:
            return MarketCondition.LOW_VOLATILITY

        # 강한 추세 체크
        if trend_strength > 0.7:
            if momentum_score > 0.6:
                return MarketCondition.BULL_MARKET
            elif momentum_score < 0.4:
                return MarketCondition.BEAR_MARKET
            else:
                return MarketCondition.TRENDING

        # 약한 추세 (횡보)
        if trend_strength < 0.3:
            return MarketCondition.SIDEWAYS

        # 박스권 거래
        if volume_profile < 0.4:
            return MarketCondition.RANGE_BOUND

        # 기본값
        return MarketCondition.SIDEWAYS

    def _calculate_analysis_confidence(self, market_data: Dict) -> float:
        """분석 신뢰도 계산"""
        confidence_factors = []

        # 데이터 충분성
        candles_1h_count = len(market_data.get('candles_1h', []))
        candles_5m_count = len(market_data.get('candles_5m', []))

        data_sufficiency = min(
            (candles_1h_count / 24 + candles_5m_count / 288) / 2, 1.0)
        confidence_factors.append(data_sufficiency)

        # 현재가 정보 가용성
        has_current_price = market_data.get('current_price') is not None
        confidence_factors.append(1.0 if has_current_price else 0.5)

        # 데이터 최신성
        timestamp = market_data.get('timestamp', datetime.now())
        data_age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        freshness = max(1 - (data_age_hours / 24), 0.3)  # 24시간 이상 오래되면 최소 신뢰도
        confidence_factors.append(freshness)

        return np.mean(confidence_factors)

    def _optimize_trading_interval(self, market_analysis: MarketAnalysis) -> Optional[OptimizationRecommendation]:
        """거래 주기 최적화"""
        try:
            current_interval = config_manager.get_config(
                'trading.trade_interval_minutes', 10)

            # 시장 상황에 따른 최적 주기 결정
            if market_analysis.condition == MarketCondition.HIGH_VOLATILITY:
                recommended_interval = max(
                    self.min_trading_interval, current_interval // 2)  # 빠른 거래
                reason = "고변동성 시장에서 빠른 대응을 위해 거래 주기 단축"
                improvement = 15.0
            elif market_analysis.condition == MarketCondition.LOW_VOLATILITY:
                recommended_interval = min(
                    self.max_trading_interval, current_interval * 2)  # 느린 거래
                reason = "저변동성 시장에서 과도한 거래 방지를 위해 거래 주기 연장"
                improvement = 10.0
            elif market_analysis.condition in [MarketCondition.BULL_MARKET, MarketCondition.BEAR_MARKET]:
                recommended_interval = max(self.min_trading_interval, int(
                    current_interval * 0.8))  # 약간 빠르게
                reason = "강한 추세 시장에서 트렌드 추종을 위해 거래 주기 단축"
                improvement = 12.0
            else:
                # 변화 불필요
                return None

            if abs(recommended_interval - current_interval) < 2:  # 2분 미만 차이는 무시
                return None

            return OptimizationRecommendation(
                parameter=OptimizationParameter.TRADING_INTERVAL,
                current_value=current_interval,
                recommended_value=recommended_interval,
                reason=reason,
                expected_improvement=improvement,
                confidence=market_analysis.confidence * 0.8,  # 보수적 신뢰도
                market_condition=market_analysis.condition,
                timestamp=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"거래 주기 최적화 오류: {e}")
            return None

    def _optimize_confidence_threshold(self, market_analysis: MarketAnalysis) -> Optional[OptimizationRecommendation]:
        """신뢰도 임계값 최적화"""
        try:
            current_threshold = config_manager.get_config(
                'independent_strategies.buy_threshold', 0.6)

            # 시장 상황에 따른 임계값 조정
            if market_analysis.condition == MarketCondition.HIGH_VOLATILITY:
                recommended_threshold = min(
                    current_threshold + 0.1, 0.8)  # 더 엄격하게
                reason = "고변동성 시장에서 거래 신뢰도 임계값 상향 조정"
                improvement = 8.0
            elif market_analysis.condition == MarketCondition.LOW_VOLATILITY:
                recommended_threshold = max(
                    current_threshold - 0.1, 0.4)  # 더 관대하게
                reason = "저변동성 시장에서 거래 기회 확대를 위해 임계값 하향 조정"
                improvement = 6.0
            else:
                return None

            if abs(recommended_threshold - current_threshold) < 0.05:
                return None

            return OptimizationRecommendation(
                parameter=OptimizationParameter.CONFIDENCE_THRESHOLD,
                current_value=current_threshold,
                recommended_value=recommended_threshold,
                reason=reason,
                expected_improvement=improvement,
                confidence=market_analysis.confidence * 0.7,
                market_condition=market_analysis.condition,
                timestamp=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"신뢰도 임계값 최적화 오류: {e}")
            return None

    def _optimize_risk_limits(self, market_analysis: MarketAnalysis) -> Optional[OptimizationRecommendation]:
        """리스크 한계 최적화"""
        # 구현 예정
        return None

    def _optimize_position_size(self, market_analysis: MarketAnalysis) -> Optional[OptimizationRecommendation]:
        """포지션 크기 최적화"""
        # 구현 예정
        return None

    def _optimize_strategy_sensitivity(self, market_analysis: MarketAnalysis) -> Optional[OptimizationRecommendation]:
        """전략 민감도 최적화"""
        # 구현 예정
        return None

    def _apply_single_recommendation(self, recommendation: OptimizationRecommendation) -> bool:
        """단일 권장사항 적용"""
        try:
            if recommendation.parameter == OptimizationParameter.TRADING_INTERVAL:
                return config_manager.update_config(
                    'trading.trade_interval_minutes',
                    recommendation.recommended_value
                )
            elif recommendation.parameter == OptimizationParameter.CONFIDENCE_THRESHOLD:
                # 매수/매도 임계값 동시 업데이트
                buy_success = config_manager.update_config(
                    'independent_strategies.buy_threshold',
                    recommendation.recommended_value
                )
                sell_success = config_manager.update_config(
                    'independent_strategies.sell_threshold',
                    -recommendation.recommended_value
                )
                return buy_success and sell_success

            # 다른 파라미터들은 추후 구현
            return False

        except Exception as e:
            self.logger.error(f"권장사항 적용 오류: {e}")
            return False

    def get_market_analysis_history(self, hours: int = 24) -> List[Dict]:
        """시장 분석 이력 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_analyses = [
            analysis.to_dict() for analysis in self.market_analysis_history
            if analysis.timestamp >= cutoff_time
        ]

        return recent_analyses

    def get_optimization_summary(self) -> Dict[str, Any]:
        """최적화 요약 정보"""
        try:
            recent_optimizations = self.optimization_history[-10:] if self.optimization_history else [
            ]
            recent_market_analyses = self.market_analysis_history[-5:] if self.market_analysis_history else [
            ]

            # 최근 시장 상황 요약
            if recent_market_analyses:
                latest_analysis = recent_market_analyses[-1]
                avg_volatility = np.mean(
                    [a.volatility for a in recent_market_analyses])
                avg_trend_strength = np.mean(
                    [a.trend_strength for a in recent_market_analyses])
            else:
                latest_analysis = None
                avg_volatility = 0
                avg_trend_strength = 0

            return {
                'latest_market_condition': latest_analysis.condition.value if latest_analysis else 'unknown',
                'market_confidence': latest_analysis.confidence if latest_analysis else 0,
                'avg_volatility_24h': avg_volatility,
                'avg_trend_strength_24h': avg_trend_strength,
                'recent_optimizations': len(recent_optimizations),
                'optimization_categories': list(set([opt.parameter.value for opt in recent_optimizations])),
                'last_optimization_time': recent_optimizations[-1].timestamp.isoformat() if recent_optimizations else None,
                'current_trading_interval': config_manager.get_config('trading.trade_interval_minutes', 10),
                'current_confidence_threshold': config_manager.get_config('independent_strategies.buy_threshold', 0.6)
            }

        except Exception as e:
            self.logger.error(f"최적화 요약 생성 오류: {e}")
            return {}


# 전역 인스턴스
adaptive_trading_optimizer = AdaptiveTradingOptimizer()
