"""
시장 체제 감지 시스템 (Market Regime Detection)
다양한 기술적 지표를 종합하여 현재 시장 체제를 판단
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from core.upbit_api import UpbitAPI


class MarketRegime(Enum):
    """시장 체제 열거형"""
    BULL_MARKET = "bull_market"          # 상승장
    BEAR_MARKET = "bear_market"          # 하락장
    SIDEWAYS = "sideways"                # 횡보장
    HIGH_VOLATILITY = "high_volatility"  # 고변동성
    LOW_VOLATILITY = "low_volatility"    # 저변동성
    TRENDING_UP = "trending_up"          # 상승 트렌드
    TRENDING_DOWN = "trending_down"      # 하락 트렌드
    UNKNOWN = "unknown"                  # 불명확


@dataclass
class RegimeMetrics:
    """체제 판단을 위한 지표들"""
    # 트렌드 지표
    ema_9: float
    ema_21: float
    ema_50: float
    ema_200: float
    price_vs_ema50: float  # 가격이 EMA50 대비 몇 % 위/아래
    price_vs_ema200: float
    
    # 모멘텀 지표
    rsi: float
    macd_histogram: float
    macd_signal: float
    
    # 변동성 지표
    atr: float
    bb_width: float  # 볼린저 밴드 폭
    price_range: float  # 최근 N일 가격 범위
    
    # 거래량 지표
    volume_ratio: float  # 평균 거래량 대비 현재 거래량
    volume_trend: float  # 거래량 추세
    
    # 추가 지표
    stochastic_k: float
    williams_r: float


@dataclass
class RegimeResult:
    """체제 감지 결과"""
    primary_regime: MarketRegime
    secondary_regime: Optional[MarketRegime]
    confidence: float  # 0.0 ~ 1.0
    metrics: RegimeMetrics
    regime_scores: Dict[MarketRegime, float]  # 각 체제별 점수
    timestamp: datetime
    reasoning: str  # 판단 근거


class RegimeDetector:
    """시장 체제 감지기"""
    
    def __init__(self, upbit_api: UpbitAPI):
        self.upbit_api = upbit_api
        self.logger = logging.getLogger('RegimeDetector')
        
        # 체제 판단 임계값들
        self.thresholds = {
            'trend_strength': 0.02,      # 트렌드 강도 임계값 (2%)
            'volatility_high': 0.03,     # 고변동성 임계값 (3%)
            'volatility_low': 0.01,       # 저변동성 임계값 (1%)
            'volume_surge': 1.5,         # 거래량 급증 임계값
            'rsi_overbought': 70,        # RSI 과매수
            'rsi_oversold': 30,          # RSI 과매도
            'confidence_min': 0.6        # 최소 신뢰도
        }
        
        self.logger.info("RegimeDetector 초기화 완료")
    
    def detect_regime(self, market: str = "KRW-BTC") -> Optional[RegimeResult]:
        """현재 시장 체제 감지"""
        try:
            # 시장 데이터 수집
            metrics = self._collect_metrics(market)
            if not metrics:
                self.logger.error("지표 수집 실패")
                return None
            
            # 체제별 점수 계산
            regime_scores = self._calculate_regime_scores(metrics)
            
            # 최종 체제 결정
            primary_regime, secondary_regime, confidence = self._determine_regime(regime_scores)
            
            # 판단 근거 생성
            reasoning = self._generate_reasoning(primary_regime, regime_scores, metrics)
            
            result = RegimeResult(
                primary_regime=primary_regime,
                secondary_regime=secondary_regime,
                confidence=confidence,
                metrics=metrics,
                regime_scores=regime_scores,
                timestamp=datetime.now(),
                reasoning=reasoning
            )
            
            self.logger.info(f"체제 감지 완료: {primary_regime.value} (신뢰도: {confidence:.3f})")
            return result
            
        except Exception as e:
            self.logger.error(f"체제 감지 오류: {e}")
            return None
    
    def _collect_metrics(self, market: str) -> Optional[RegimeMetrics]:
        """시장 지표 수집"""
        try:
            # 다양한 시간프레임 데이터 수집
            candles_1h = self.upbit_api.get_candles(market, minutes=60, count=200)
            candles_4h = self.upbit_api.get_candles(market, minutes=240, count=100)
            candles_1d = self.upbit_api.get_candles(market, minutes=1440, count=50)
            
            if not all([candles_1h, candles_4h, candles_1d]):
                self.logger.error("캔들 데이터 수집 실패")
                return None
            
            # DataFrame 변환
            df_1h = pd.DataFrame(candles_1h)
            df_4h = pd.DataFrame(candles_4h)
            df_1d = pd.DataFrame(candles_1d)
            
            # 가격 정렬 (오래된 것부터)
            df_1h = df_1h.sort_values('candle_date_time_kst').reset_index(drop=True)
            df_4h = df_4h.sort_values('candle_date_time_kst').reset_index(drop=True)
            df_1d = df_1d.sort_values('candle_date_time_kst').reset_index(drop=True)
            
            # 현재 가격
            current_price = df_1h.iloc[-1]['trade_price']
            
            # 이동평균선 계산
            ema_9 = self._calculate_ema(df_1h['trade_price'], 9)
            ema_21 = self._calculate_ema(df_1h['trade_price'], 21)
            ema_50 = self._calculate_ema(df_1h['trade_price'], 50)
            ema_200 = self._calculate_ema(df_1h['trade_price'], 200)
            
            # RSI 계산
            rsi = self._calculate_rsi(df_1h['trade_price'], 14)
            
            # MACD 계산
            macd_line, macd_signal, macd_histogram = self._calculate_macd(df_1h['trade_price'])
            
            # ATR 계산
            atr = self._calculate_atr(df_1h, 14)
            
            # 볼린저 밴드 계산
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df_1h['trade_price'], 20, 2)
            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]
            
            # Stochastic 계산
            stoch_k, stoch_d = self._calculate_stochastic(df_1h, 14, 3)
            
            # Williams %R 계산
            williams_r = self._calculate_williams_r(df_1h, 14)
            
            # 거래량 분석
            volume_ratio = self._calculate_volume_ratio(df_1h['candle_acc_trade_volume'])
            volume_trend = self._calculate_volume_trend(df_1h['candle_acc_trade_volume'])
            
            # 가격 범위 계산
            price_range = self._calculate_price_range(df_1h['trade_price'], 20)
            
            return RegimeMetrics(
                ema_9=ema_9.iloc[-1],
                ema_21=ema_21.iloc[-1],
                ema_50=ema_50.iloc[-1],
                ema_200=ema_200.iloc[-1],
                price_vs_ema50=(current_price - ema_50.iloc[-1]) / ema_50.iloc[-1],
                price_vs_ema200=(current_price - ema_200.iloc[-1]) / ema_200.iloc[-1],
                rsi=rsi.iloc[-1],
                macd_histogram=macd_histogram.iloc[-1],
                macd_signal=macd_signal.iloc[-1],
                atr=atr.iloc[-1],
                bb_width=bb_width,
                price_range=price_range,
                volume_ratio=volume_ratio,
                volume_trend=volume_trend,
                stochastic_k=stoch_k.iloc[-1],
                williams_r=williams_r.iloc[-1]
            )
            
        except Exception as e:
            self.logger.error(f"지표 수집 오류: {e}")
            return None
    
    def _calculate_regime_scores(self, metrics: RegimeMetrics) -> Dict[MarketRegime, float]:
        """체제별 점수 계산"""
        scores = {}
        
        # 상승장 점수
        bull_score = 0
        if metrics.price_vs_ema50 > 0.02:  # 가격이 EMA50 위 2% 이상
            bull_score += 0.3
        if metrics.price_vs_ema200 > 0.05:  # 가격이 EMA200 위 5% 이상
            bull_score += 0.3
        if metrics.ema_9 > metrics.ema_21 > metrics.ema_50:  # EMA 정렬
            bull_score += 0.2
        if metrics.macd_histogram > 0:  # MACD 히스토그램 양수
            bull_score += 0.1
        if metrics.volume_ratio > 1.2:  # 거래량 증가
            bull_score += 0.1
        scores[MarketRegime.BULL_MARKET] = min(bull_score, 1.0)
        
        # 하락장 점수
        bear_score = 0
        if metrics.price_vs_ema50 < -0.02:  # 가격이 EMA50 아래 2% 이상
            bear_score += 0.3
        if metrics.price_vs_ema200 < -0.05:  # 가격이 EMA200 아래 5% 이상
            bear_score += 0.3
        if metrics.ema_9 < metrics.ema_21 < metrics.ema_50:  # EMA 역정렬
            bear_score += 0.2
        if metrics.macd_histogram < 0:  # MACD 히스토그램 음수
            bear_score += 0.1
        if metrics.volume_ratio > 1.2:  # 거래량 증가
            bear_score += 0.1
        scores[MarketRegime.BEAR_MARKET] = min(bear_score, 1.0)
        
        # 횡보장 점수
        sideways_score = 0
        if abs(metrics.price_vs_ema50) < 0.01:  # 가격이 EMA50 근처
            sideways_score += 0.4
        if abs(metrics.price_vs_ema200) < 0.02:  # 가격이 EMA200 근처
            sideways_score += 0.3
        if metrics.volume_ratio < 1.0:  # 거래량 감소
            sideways_score += 0.3
        scores[MarketRegime.SIDEWAYS] = min(sideways_score, 1.0)
        
        # 고변동성 점수
        high_vol_score = 0
        if metrics.atr > self.thresholds['volatility_high']:
            high_vol_score += 0.4
        if metrics.bb_width > 0.1:  # 볼린저 밴드 폭이 넓음
            high_vol_score += 0.3
        if metrics.price_range > 0.05:  # 가격 범위가 넓음
            high_vol_score += 0.3
        scores[MarketRegime.HIGH_VOLATILITY] = min(high_vol_score, 1.0)
        
        # 저변동성 점수
        low_vol_score = 0
        if metrics.atr < self.thresholds['volatility_low']:
            low_vol_score += 0.4
        if metrics.bb_width < 0.05:  # 볼린저 밴드 폭이 좁음
            low_vol_score += 0.3
        if metrics.price_range < 0.02:  # 가격 범위가 좁음
            low_vol_score += 0.3
        scores[MarketRegime.LOW_VOLATILITY] = min(low_vol_score, 1.0)
        
        # 상승 트렌드 점수
        trend_up_score = 0
        if metrics.ema_9 > metrics.ema_21:
            trend_up_score += 0.3
        if metrics.macd_signal > 0:
            trend_up_score += 0.3
        if metrics.rsi > 50:
            trend_up_score += 0.2
        if metrics.stochastic_k > 50:
            trend_up_score += 0.2
        scores[MarketRegime.TRENDING_UP] = min(trend_up_score, 1.0)
        
        # 하락 트렌드 점수
        trend_down_score = 0
        if metrics.ema_9 < metrics.ema_21:
            trend_down_score += 0.3
        if metrics.macd_signal < 0:
            trend_down_score += 0.3
        if metrics.rsi < 50:
            trend_down_score += 0.2
        if metrics.stochastic_k < 50:
            trend_down_score += 0.2
        scores[MarketRegime.TRENDING_DOWN] = min(trend_down_score, 1.0)
        
        return scores
    
    def _determine_regime(self, scores: Dict[MarketRegime, float]) -> Tuple[MarketRegime, Optional[MarketRegime], float]:
        """최종 체제 결정"""
        # 가장 높은 점수의 체제를 주요 체제로 선택
        primary_regime = max(scores, key=scores.get)
        primary_score = scores[primary_regime]
        
        # 두 번째로 높은 점수의 체제를 보조 체제로 선택 (임계값 이상인 경우)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        secondary_regime = None
        if len(sorted_scores) > 1 and sorted_scores[1][1] > 0.3:
            secondary_regime = sorted_scores[1][0]
        
        # 신뢰도 계산 (주요 체제 점수 기반)
        confidence = primary_score
        
        # 신뢰도가 너무 낮으면 UNKNOWN으로 설정
        if confidence < self.thresholds['confidence_min']:
            primary_regime = MarketRegime.UNKNOWN
            confidence = 0.0
        
        return primary_regime, secondary_regime, confidence
    
    def _generate_reasoning(self, regime: MarketRegime, scores: Dict[MarketRegime, float], metrics: RegimeMetrics) -> str:
        """판단 근거 생성"""
        reasoning_parts = []
        
        if regime == MarketRegime.BULL_MARKET:
            reasoning_parts.append("강한 상승 트렌드 감지")
            if metrics.price_vs_ema50 > 0.02:
                reasoning_parts.append(f"가격이 EMA50 위 {metrics.price_vs_ema50*100:.1f}%")
            if metrics.volume_ratio > 1.2:
                reasoning_parts.append(f"거래량 {metrics.volume_ratio:.1f}배 증가")
                
        elif regime == MarketRegime.BEAR_MARKET:
            reasoning_parts.append("강한 하락 트렌드 감지")
            if metrics.price_vs_ema50 < -0.02:
                reasoning_parts.append(f"가격이 EMA50 아래 {abs(metrics.price_vs_ema50)*100:.1f}%")
            if metrics.volume_ratio > 1.2:
                reasoning_parts.append(f"거래량 {metrics.volume_ratio:.1f}배 증가")
                
        elif regime == MarketRegime.HIGH_VOLATILITY:
            reasoning_parts.append("고변동성 시장 감지")
            reasoning_parts.append(f"ATR: {metrics.atr:.3f}, BB폭: {metrics.bb_width:.3f}")
            
        elif regime == MarketRegime.LOW_VOLATILITY:
            reasoning_parts.append("저변동성 시장 감지")
            reasoning_parts.append(f"ATR: {metrics.atr:.3f}, BB폭: {metrics.bb_width:.3f}")
            
        elif regime == MarketRegime.SIDEWAYS:
            reasoning_parts.append("횡보장 감지")
            reasoning_parts.append(f"가격 변동폭: {metrics.price_range:.3f}")
            
        else:
            reasoning_parts.append("체제 불명확")
        
        return " | ".join(reasoning_parts)
    
    # 기술적 지표 계산 메서드들
    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """지수이동평균 계산"""
        return prices.ewm(span=period).mean()
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: pd.Series, fast=12, slow=26, signal=9):
        """MACD 계산"""
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        macd_signal = self._calculate_ema(macd_line, signal)
        macd_histogram = macd_line - macd_signal
        return macd_line, macd_signal, macd_histogram
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """ATR 계산"""
        high = df['high_price']
        low = df['low_price']
        close = df['trade_price']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int, std_dev: float):
        """볼린저 밴드 계산"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int, d_period: int):
        """Stochastic 계산"""
        low_min = df['low_price'].rolling(window=k_period).min()
        high_max = df['high_price'].rolling(window=k_period).max()
        k_percent = 100 * ((df['trade_price'] - low_min) / (high_max - low_min))
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    
    def _calculate_williams_r(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Williams %R 계산"""
        high_max = df['high_price'].rolling(window=period).max()
        low_min = df['low_price'].rolling(window=period).min()
        williams_r = -100 * ((high_max - df['trade_price']) / (high_max - low_min))
        return williams_r
    
    def _calculate_volume_ratio(self, volumes: pd.Series) -> float:
        """거래량 비율 계산 (현재 거래량 / 평균 거래량)"""
        current_volume = volumes.iloc[-1]
        avg_volume = volumes.tail(20).mean()
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    
    def _calculate_volume_trend(self, volumes: pd.Series) -> float:
        """거래량 추세 계산"""
        recent_avg = volumes.tail(5).mean()
        older_avg = volumes.tail(20).head(15).mean()
        return (recent_avg - older_avg) / older_avg if older_avg > 0 else 0.0
    
    def _calculate_price_range(self, prices: pd.Series, period: int) -> float:
        """가격 범위 계산 (최근 N일간 최고가-최저가)"""
        recent_prices = prices.tail(period)
        return (recent_prices.max() - recent_prices.min()) / recent_prices.mean()
