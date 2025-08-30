"""
다층 전략 엔진 (Multi-Tier Strategy Engine)
5분/1시간/1일 계층으로 구성된 통합 전략 시스템
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd

from core.candle_data_collector import candle_collector
from core.upbit_api import UpbitAPI
from core.signal_manager import TradingSignal, MarketCondition
from config.config_manager import config_manager
from core.strategy_execution_tracker import execution_tracker, StrategyExecution


class StrategyTier(Enum):
    """전략 계층"""
    SCALPING = "scalping"    # 스캘핑 레이어 (설정된 거래 주기)
    TREND = "trend"          # 트렌드 레이어 (거래 주기 * 6배)  
    MACRO = "macro"          # 매크로 레이어 (일일)


class MarketRegime(Enum):
    """시장 체제"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_vol"
    LOW_VOLATILITY = "low_vol"


@dataclass
class TierSignal:
    """계층별 신호"""
    tier: StrategyTier
    strategy_id: str
    action: str  # 'buy', 'sell', 'hold'
    confidence: float  # 0.0 ~ 1.0
    strength: float  # 신호 강도
    reasoning: str
    indicators: Dict[str, float]
    timestamp: datetime
    
    def to_trading_signal(self, price: float, amount: float) -> TradingSignal:
        """TradingSignal로 변환"""
        return TradingSignal(
            strategy_id=f"{self.tier.value}_{self.strategy_id}",
            action=self.action,
            confidence=self.confidence,
            price=price,
            suggested_amount=amount,
            reasoning=self.reasoning,
            timestamp=self.timestamp,
            timeframe=self.tier.value
        )


@dataclass
class MultiTierDecision:
    """다층 통합 결정"""
    final_action: str
    confidence: float
    tier_contributions: Dict[StrategyTier, float]
    market_regime: MarketRegime
    reasoning: str
    risk_score: float
    suggested_amount: float
    timestamp: datetime


class ScalpingLayer:
    """스캘핑 계층 (설정된 거래 주기 기반)"""
    
    def __init__(self):
        self.logger = logging.getLogger('ScalpingLayer')
        # 설정에서 거래 주기 가져오기
        self.trade_interval = config_manager.get_config('trading.trade_interval_minutes', 10)
        self.timeframe = f'{self.trade_interval}m' if self.trade_interval <= 60 else f'{self.trade_interval//60}h'
        
    def analyze(self) -> List[TierSignal]:
        """스캘핑 신호 생성 (설정된 주기 기반)"""
        signals = []
        
        try:
            # 설정된 주기의 캔들 데이터 조회
            df = candle_collector.get_dataframe(self.timeframe, 100)
            if df is None or len(df) < 20:
                self.logger.warning(f"{self.timeframe} 캔들 데이터 부족")
                return signals
            
            # 1. RSI 모멘텀 스캘핑
            rsi_signal = self._rsi_momentum_strategy(df)
            if rsi_signal:
                signals.append(rsi_signal)
            
            # 2. 볼린저밴드 수축/확장
            bb_signal = self._bollinger_squeeze_strategy(df)
            if bb_signal:
                signals.append(bb_signal)
                
            # 3. 지지/저항 반등
            sr_signal = self._support_resistance_strategy(df)
            if sr_signal:
                signals.append(sr_signal)
            
        except Exception as e:
            self.logger.error(f"스캘핑 분석 오류: {e}")
        
        return signals
    
    def _rsi_momentum_strategy(self, df: pd.DataFrame) -> Optional[TierSignal]:
        """RSI 모멘텀 스캘핑 전략"""
        try:
            # 설정값 로드
            config = config_manager.get_config('strategies.scalping_strategies.rsi_momentum', {})
            if not config.get('enabled', True):
                return None
            
            rsi_period = config.get('rsi_period', 14)
            oversold = config.get('oversold', 30)
            overbought = config.get('overbought', 70)
            momentum_threshold = config.get('momentum_threshold', 0.002)
            
            # RSI 계산
            rsi = self._calculate_rsi(df['close'], rsi_period)
            stoch_k, stoch_d = self._calculate_stochastic(df, 5, 3)
            volume_ma = df['volume'].rolling(10).mean()
            
            latest_rsi = rsi.iloc[-1]
            latest_stoch_k = stoch_k.iloc[-1] if not pd.isna(stoch_k.iloc[-1]) else 50
            latest_volume = df['volume'].iloc[-1]
            avg_volume = volume_ma.iloc[-1] if not pd.isna(volume_ma.iloc[-1]) else df['volume'].mean()
            
            # 가격 모멘텀 확인
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            strong_momentum = abs(price_change) > momentum_threshold
            
            # 신호 조건
            oversold_bounce = latest_rsi < oversold and latest_stoch_k < 20
            volume_surge = latest_volume > avg_volume * 1.5
            
            if oversold_bounce and volume_surge and strong_momentum:
                confidence = min(0.9, (oversold - latest_rsi) / 10 + 0.3)
                strength = (latest_volume / avg_volume - 1) * 0.5 + confidence * 0.5
                
                return TierSignal(
                    tier=StrategyTier.SCALPING,
                    strategy_id="rsi_momentum",
                    action="buy",
                    confidence=confidence,
                    strength=strength,
                    reasoning=f"RSI 과매도 반등 + 거래량 급증 (RSI:{latest_rsi:.1f}, Vol:{latest_volume/avg_volume:.1f}x)",
                    indicators={
                        'rsi': latest_rsi,
                        'stoch_k': latest_stoch_k,
                        'volume_ratio': latest_volume / avg_volume
                    },
                    timestamp=datetime.now()
                )
            
            # 매도 신호
            overbought_decline = latest_rsi > overbought and latest_stoch_k > 80
            if overbought_decline and volume_surge and strong_momentum:
                confidence = min(0.9, (latest_rsi - overbought) / 10 + 0.3)
                strength = (latest_volume / avg_volume - 1) * 0.5 + confidence * 0.5
                
                return TierSignal(
                    tier=StrategyTier.SCALPING,
                    strategy_id="rsi_momentum",
                    action="sell",
                    confidence=confidence,
                    strength=strength,
                    reasoning=f"RSI 과매수 하락 + 거래량 급증 (RSI:{latest_rsi:.1f}, Vol:{latest_volume/avg_volume:.1f}x)",
                    indicators={
                        'rsi': latest_rsi,
                        'stoch_k': latest_stoch_k,
                        'volume_ratio': latest_volume / avg_volume
                    },
                    timestamp=datetime.now()
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"RSI 모멘텀 전략 오류: {e}")
            return None
    
    def _bollinger_squeeze_strategy(self, df: pd.DataFrame) -> Optional[TierSignal]:
        """볼린저밴드 수축/확장 전략"""
        try:
            # 설정값 로드
            config = config_manager.get_config('strategies.scalping_strategies.bollinger_squeeze', {})
            if not config.get('enabled', True):
                return None
            
            bb_period = config.get('bb_period', 20)
            bb_std = config.get('bb_std', 2.0)
            squeeze_threshold = config.get('squeeze_threshold', 0.01)
            
            # 볼린저밴드 계산
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df['close'], bb_period, bb_std)
            bb_width = (bb_upper - bb_lower) / bb_middle
            
            # MACD 계산
            macd, macd_signal, _ = self._calculate_macd(df['close'], 5, 13, 3)
            
            latest_close = df['close'].iloc[-1]
            latest_bb_width = bb_width.iloc[-1]
            latest_macd = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
            latest_macd_signal = macd_signal.iloc[-1] if not pd.isna(macd_signal.iloc[-1]) else 0
            
            # 밴드 수축 후 돌파 (설정값 적용)
            bb_width_ma = bb_width.rolling(10).mean()
            is_squeeze = latest_bb_width < bb_width_ma.iloc[-1] * (1 - squeeze_threshold)
            
            # 상향 돌파
            upper_breakout = latest_close > bb_upper.iloc[-1]
            macd_bullish = latest_macd > latest_macd_signal
            
            if is_squeeze and upper_breakout and macd_bullish:
                confidence = 0.8
                strength = min(1.0, abs(latest_macd - latest_macd_signal) / abs(latest_macd) + 0.4)
                
                return TierSignal(
                    tier=StrategyTier.SCALPING,
                    strategy_id="bollinger_squeeze",
                    action="buy",
                    confidence=confidence,
                    strength=strength,
                    reasoning=f"볼린저밴드 수축 후 상향 돌파 + MACD 상승 (Width:{latest_bb_width:.4f})",
                    indicators={
                        'bb_width': latest_bb_width,
                        'macd': latest_macd,
                        'price_vs_upper': (latest_close - bb_upper.iloc[-1]) / bb_upper.iloc[-1]
                    },
                    timestamp=datetime.now()
                )
            
            # 하향 돌파
            lower_breakout = latest_close < bb_lower.iloc[-1]
            macd_bearish = latest_macd < latest_macd_signal
            
            if is_squeeze and lower_breakout and macd_bearish:
                confidence = 0.8
                strength = min(1.0, abs(latest_macd - latest_macd_signal) / abs(latest_macd) + 0.4)
                
                return TierSignal(
                    tier=StrategyTier.SCALPING,
                    strategy_id="bollinger_squeeze",
                    action="sell",
                    confidence=confidence,
                    strength=strength,
                    reasoning=f"볼린저밴드 수축 후 하향 돌파 + MACD 하락 (Width:{latest_bb_width:.4f})",
                    indicators={
                        'bb_width': latest_bb_width,
                        'macd': latest_macd,
                        'price_vs_lower': (latest_close - bb_lower.iloc[-1]) / bb_lower.iloc[-1]
                    },
                    timestamp=datetime.now()
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"볼린저밴드 전략 오류: {e}")
            return None
    
    def _support_resistance_strategy(self, df: pd.DataFrame) -> Optional[TierSignal]:
        """지지/저항 반등 전략"""
        try:
            # 설정값 로드
            config = config_manager.get_config('strategies.scalping_strategies.support_resistance', {})
            if not config.get('enabled', True):
                return None
            
            lookback_period = config.get('lookback_period', 20)
            touch_tolerance = config.get('touch_tolerance', 0.005)
            
            # 최근 고점/저점 계산
            highs = df['high'].rolling(5).max()
            lows = df['low'].rolling(5).min()
            
            latest_close = df['close'].iloc[-1]
            latest_high = df['high'].iloc[-1]
            latest_low = df['low'].iloc[-1]
            
            # 지지선 근처에서의 반등
            recent_lows = lows.tail(lookback_period).dropna()
            if len(recent_lows) > 0:
                support_level = recent_lows.min()
                distance_to_support = (latest_close - support_level) / support_level
                
                # 지지선 근처 (설정값 이내) + 반전 캔들
                if 0 < distance_to_support < touch_tolerance:
                    # 해머/도지 캔들 패턴 체크
                    body_size = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
                    total_range = df['high'].iloc[-1] - df['low'].iloc[-1]
                    hammer_pattern = body_size < total_range * 0.3 and latest_close > df['open'].iloc[-1]
                    
                    if hammer_pattern:
                        confidence = 0.75
                        strength = min(1.0, (0.01 - distance_to_support) * 100 + 0.5)
                        
                        return TierSignal(
                            tier=StrategyTier.SCALPING,
                            strategy_id="support_resistance",
                            action="buy",
                            confidence=confidence,
                            strength=strength,
                            reasoning=f"지지선 반등 + 해머 패턴 (지지:{support_level:,.0f}, 거리:{distance_to_support:.3f})",
                            indicators={
                                'support_level': support_level,
                                'distance_to_support': distance_to_support,
                                'pattern_strength': body_size / total_range
                            },
                            timestamp=datetime.now()
                        )
            
            # 저항선 근처에서의 거부
            recent_highs = highs.tail(lookback_period).dropna()
            if len(recent_highs) > 0:
                resistance_level = recent_highs.max()
                distance_to_resistance = (resistance_level - latest_close) / latest_close
                
                # 저항선 근처 (설정값 이내) + 반전 캔들
                if 0 < distance_to_resistance < touch_tolerance:
                    # 유성/도지 캔들 패턴 체크
                    body_size = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
                    total_range = df['high'].iloc[-1] - df['low'].iloc[-1]
                    shooting_star = body_size < total_range * 0.3 and latest_close < df['open'].iloc[-1]
                    
                    if shooting_star:
                        confidence = 0.75
                        strength = min(1.0, (0.01 - distance_to_resistance) * 100 + 0.5)
                        
                        return TierSignal(
                            tier=StrategyTier.SCALPING,
                            strategy_id="support_resistance",
                            action="sell",
                            confidence=confidence,
                            strength=strength,
                            reasoning=f"저항선 거부 + 유성 패턴 (저항:{resistance_level:,.0f}, 거리:{distance_to_resistance:.3f})",
                            indicators={
                                'resistance_level': resistance_level,
                                'distance_to_resistance': distance_to_resistance,
                                'pattern_strength': body_size / total_range
                            },
                            timestamp=datetime.now()
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"지지/저항 전략 오류: {e}")
            return None
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """스토캐스틱 계산"""
        lowest_low = df['low'].rolling(k_period).min()
        highest_high = df['high'].rolling(k_period).max()
        k_percent = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
        d_percent = k_percent.rolling(d_period).mean()
        return k_percent, d_percent
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저밴드 계산"""
        middle = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 계산"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram


class TrendFilterLayer:
    """트렌드 필터 계층 (거래 주기 * 6배)"""
    
    def __init__(self):
        self.logger = logging.getLogger('TrendFilterLayer')
        # 설정에서 거래 주기의 6배로 트렌드 분석
        self.trade_interval = config_manager.get_config('trading.trade_interval_minutes', 10)
        self.trend_interval = self.trade_interval * 6
        self.timeframe = f'{self.trend_interval}m' if self.trend_interval <= 60 else f'{self.trend_interval//60}h'
        
    def analyze(self) -> Dict[str, Any]:
        """트렌드 필터 분석 (설정된 주기 * 6배)"""
        try:
            # 트렌드 분석용 캔들 데이터 조회
            df = candle_collector.get_dataframe(self.timeframe, 100)
            if df is None or len(df) < 50:
                self.logger.warning(f"{self.timeframe} 캔들 데이터 부족")
                return {'trend': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
            
            # 1. EMA 트렌드 필터 (개선됨)
            ema_trend = self._enhanced_ema_trend_analysis(df)
            
            # 2. VWAP 포지션 분석 (개선됨) 
            vwap_position = self._enhanced_vwap_analysis(df)
            
            # 3. 피보나치 되돌림 전략 (새로 추가)
            fibonacci_signal = self._fibonacci_retracement_analysis(df)
            
            # 통합 분석
            trend_score = (ema_trend['score'] + vwap_position['score'] + fibonacci_signal['score']) / 3
            
            if trend_score > 0.6:
                trend = 'bullish'
                regime = MarketRegime.BULLISH
            elif trend_score < -0.6:
                trend = 'bearish'
                regime = MarketRegime.BEARISH
            else:
                trend = 'neutral'
                regime = MarketRegime.SIDEWAYS
            
            return {
                'trend': trend,
                'strength': abs(trend_score),
                'regime': regime,
                'ema_trend': ema_trend,
                'vwap_position': vwap_position,
                'fibonacci_signal': fibonacci_signal,
                'volatility': self._calculate_volatility(df)
            }
            
        except Exception as e:
            self.logger.error(f"트렌드 필터 분석 오류: {e}")
            return {'trend': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
    
    def _enhanced_ema_trend_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """개선된 EMA 트렌드 분석"""
        try:
            # 다중 EMA와 기울기 분석
            ema9 = df['close'].ewm(span=9).mean()
            ema21 = df['close'].ewm(span=21).mean()
            ema50 = df['close'].ewm(span=50).mean()
            ema200 = df['close'].ewm(span=200).mean()
            
            latest_price = df['close'].iloc[-1]
            latest_ema9 = ema9.iloc[-1]
            latest_ema21 = ema21.iloc[-1]
            latest_ema50 = ema50.iloc[-1]
            latest_ema200 = ema200.iloc[-1] if not pd.isna(ema200.iloc[-1]) else latest_ema50
            
            # EMA 기울기 계산 (최근 5개 캔들)
            ema21_slope = (ema21.iloc[-1] - ema21.iloc[-5]) / ema21.iloc[-5] if len(ema21) >= 5 else 0
            ema50_slope = (ema50.iloc[-1] - ema50.iloc[-5]) / ema50.iloc[-5] if len(ema50) >= 5 else 0
            
            # 점수 계산
            alignment_score = 0
            slope_score = 0
            position_score = 0
            
            # 1. EMA 정렬 점수
            if latest_ema9 > latest_ema21 > latest_ema50 > latest_ema200:
                alignment_score = 1.0  # 완벽한 상승 정렬
            elif latest_ema9 < latest_ema21 < latest_ema50 < latest_ema200:
                alignment_score = -1.0  # 완벽한 하락 정렬
            elif latest_ema9 > latest_ema21 > latest_ema50:
                alignment_score = 0.7  # 부분 상승 정렬
            elif latest_ema9 < latest_ema21 < latest_ema50:
                alignment_score = -0.7  # 부분 하락 정렬
            
            # 2. 기울기 점수
            if ema21_slope > 0.001 and ema50_slope > 0.001:
                slope_score = 1.0  # 강한 상승 기울기
            elif ema21_slope < -0.001 and ema50_slope < -0.001:
                slope_score = -1.0  # 강한 하락 기울기
            elif ema21_slope > 0:
                slope_score = 0.5  # 약한 상승 기울기
            elif ema21_slope < 0:
                slope_score = -0.5  # 약한 하락 기울기
            
            # 3. 가격 위치 점수
            if latest_price > latest_ema9:
                position_score = 0.5
            elif latest_price < latest_ema9:
                position_score = -0.5
            
            # 최종 점수 (가중 평균)
            final_score = (alignment_score * 0.5 + slope_score * 0.3 + position_score * 0.2)
            
            return {
                'score': final_score,
                'ema9': latest_ema9,
                'ema21': latest_ema21,
                'ema50': latest_ema50,
                'ema200': latest_ema200,
                'ema21_slope': ema21_slope,
                'ema50_slope': ema50_slope,
                'alignment_score': alignment_score,
                'slope_score': slope_score,
                'position_score': position_score
            }
            
        except Exception as e:
            self.logger.error(f"개선된 EMA 트렌드 분석 오류: {e}")
            return {'score': 0.0}
    
    def _enhanced_vwap_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """개선된 VWAP 분석"""
        try:
            # 다중 기간 VWAP 계산
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            
            # 단기 VWAP (최근 20개)
            recent_data = df.tail(20)
            recent_typical = (recent_data['high'] + recent_data['low'] + recent_data['close']) / 3
            short_vwap = (recent_typical * recent_data['volume']).sum() / recent_data['volume'].sum()
            
            # 장기 VWAP (전체)
            long_vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            latest_long_vwap = long_vwap.iloc[-1]
            
            latest_price = df['close'].iloc[-1]
            
            # VWAP 기울기 계산
            vwap_slope = 0
            if len(long_vwap) >= 5:
                vwap_slope = (long_vwap.iloc[-1] - long_vwap.iloc[-5]) / long_vwap.iloc[-5]
            
            # 거래량 가중 분석
            recent_volume = df['volume'].tail(10).mean()
            avg_volume = df['volume'].mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # 점수 계산
            position_score = 0
            slope_score = 0
            volume_score = 0
            
            # 1. VWAP 위치 점수
            short_vs_long = (short_vwap - latest_long_vwap) / latest_long_vwap
            price_vs_short = (latest_price - short_vwap) / short_vwap
            price_vs_long = (latest_price - latest_long_vwap) / latest_long_vwap
            
            if price_vs_short > 0.01 and price_vs_long > 0.01:
                position_score = 1.0  # 강한 상승 포지션
            elif price_vs_short < -0.01 and price_vs_long < -0.01:
                position_score = -1.0  # 강한 하락 포지션
            elif price_vs_short > 0.005:
                position_score = 0.5  # 약한 상승 포지션
            elif price_vs_short < -0.005:
                position_score = -0.5  # 약한 하락 포지션
            
            # 2. VWAP 기울기 점수
            if vwap_slope > 0.002:
                slope_score = 1.0  # 상승 기울기
            elif vwap_slope < -0.002:
                slope_score = -1.0  # 하락 기울기
            elif vwap_slope > 0:
                slope_score = 0.3  # 약한 상승
            elif vwap_slope < 0:
                slope_score = -0.3  # 약한 하락
            
            # 3. 거래량 점수
            if volume_ratio > 1.5:
                volume_score = 1.0  # 높은 거래량
            elif volume_ratio > 1.2:
                volume_score = 0.5  # 평균 이상 거래량
            elif volume_ratio < 0.7:
                volume_score = -0.5  # 낮은 거래량
            
            # 최종 점수
            final_score = (position_score * 0.5 + slope_score * 0.3 + volume_score * 0.2)
            
            return {
                'score': final_score,
                'short_vwap': short_vwap,
                'long_vwap': latest_long_vwap,
                'price_vs_short_vwap': price_vs_short,
                'price_vs_long_vwap': price_vs_long,
                'vwap_slope': vwap_slope,
                'volume_ratio': volume_ratio,
                'position_score': position_score,
                'slope_score': slope_score,
                'volume_score': volume_score
            }
            
        except Exception as e:
            self.logger.error(f"개선된 VWAP 분석 오류: {e}")
            return {'score': 0.0}
    
    def _fibonacci_retracement_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """피보나치 되돌림 전략"""
        try:
            # 최근 스윙 고점/저점 찾기 (20개 캔들 기준)
            lookback = min(20, len(df))
            recent_data = df.tail(lookback)
            
            swing_high = recent_data['high'].max()
            swing_low = recent_data['low'].min()
            swing_range = swing_high - swing_low
            
            if swing_range == 0:
                return {'score': 0.0}
            
            # 피보나치 레벨 계산
            fib_levels = {
                '23.6': swing_high - (swing_range * 0.236),
                '38.2': swing_high - (swing_range * 0.382), 
                '50.0': swing_high - (swing_range * 0.500),
                '61.8': swing_high - (swing_range * 0.618),
                '78.6': swing_high - (swing_range * 0.786)
            }
            
            latest_price = df['close'].iloc[-1]
            latest_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(10).mean()
            
            # 현재 가격이 어느 피보나치 레벨 근처인지 확인
            score = 0.0
            support_level = None
            resistance_level = None
            tolerance = swing_range * 0.02  # 2% 허용오차
            
            for level_name, level_price in fib_levels.items():
                if abs(latest_price - level_price) <= tolerance:
                    # 피보나치 레벨 근처에서의 반응 분석
                    if latest_price > level_price:
                        # 지지선으로 작용하는 경우
                        support_level = level_name
                        # 거래량 증가와 함께 반등하면 매수 신호
                        if latest_volume > avg_volume * 1.2:
                            score = float(level_name.replace('.', '')) / 100  # 레벨에 따른 신뢰도
                        else:
                            score = 0.3
                    else:
                        # 저항선으로 작용하는 경우
                        resistance_level = level_name
                        # 거래량 증가와 함께 하락하면 매도 신호
                        if latest_volume > avg_volume * 1.2:
                            score = -float(level_name.replace('.', '')) / 100
                        else:
                            score = -0.3
                    break
            
            # 트렌드 방향 고려
            sma20 = df['close'].tail(20).mean()
            if latest_price > sma20:  # 상승 트렌드
                if support_level:
                    score *= 1.2  # 상승 트렌드에서 지지선 반등은 더 강함
                elif resistance_level:
                    score *= 0.8  # 상승 트렌드에서 저항선은 약함
            else:  # 하락 트렌드
                if resistance_level:
                    score *= 1.2  # 하락 트렌드에서 저항선 거부는 더 강함
                elif support_level:
                    score *= 0.8  # 하락 트렌드에서 지지선은 약함
            
            return {
                'score': max(-1.0, min(1.0, score)),  # -1 ~ 1 범위로 제한
                'swing_high': swing_high,
                'swing_low': swing_low,
                'fib_levels': fib_levels,
                'current_level': support_level or resistance_level,
                'support_level': support_level,
                'resistance_level': resistance_level,
                'volume_ratio': latest_volume / avg_volume if avg_volume > 0 else 1,
                'trend_bias': 'up' if latest_price > sma20 else 'down'
            }
            
        except Exception as e:
            self.logger.error(f"피보나치 되돌림 분석 오류: {e}")
            return {'score': 0.0}
    
    def _momentum_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """모멘텀 분석"""
        try:
            # RSI, MACD, Stochastic RSI 계산
            rsi = self._calculate_rsi(df['close'], 14)
            macd, macd_signal, _ = self._calculate_macd(df['close'])
            
            latest_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            latest_macd = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
            latest_macd_signal = macd_signal.iloc[-1] if not pd.isna(macd_signal.iloc[-1]) else 0
            
            # 모멘텀 점수 계산
            rsi_score = 0
            if latest_rsi > 60:
                rsi_score = (latest_rsi - 60) / 20  # 0~1
            elif latest_rsi < 40:
                rsi_score = (latest_rsi - 40) / 20  # -1~0
            
            macd_score = 1 if latest_macd > latest_macd_signal else -1
            
            momentum_score = (rsi_score + macd_score) / 2
            
            return {
                'score': momentum_score,
                'rsi': latest_rsi,
                'macd': latest_macd,
                'macd_signal': latest_macd_signal
            }
            
        except Exception as e:
            self.logger.error(f"모멘텀 분석 오류: {e}")
            return {'score': 0.0}
    
    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """변동성 계산"""
        try:
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(24)  # 일일 변동성으로 환산
            return volatility
        except:
            return 0.02  # 기본값
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 계산"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram


class MacroDirectionLayer:
    """매크로 방향성 계층 (일일 기준)"""
    
    def __init__(self):
        self.logger = logging.getLogger('MacroDirectionLayer')
        self.timeframe = '1d'  # 매크로는 항상 일일 기준
        
    def analyze(self) -> Dict[str, Any]:
        """매크로 방향성 분석 (3개 전략)"""
        try:
            # 일일 캔들 데이터 조회
            df = candle_collector.get_dataframe('1d', 200)
            if df is None or len(df) < 50:
                self.logger.warning("일일 캔들 데이터 부족")
                return {'direction': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
            
            # 1. 장기 트렌드 정렬 (개선됨)
            trend_alignment = self._enhanced_trend_alignment_analysis(df)
            
            # 2. 거래량 프로파일 분석 (새로 추가)
            volume_profile = self._volume_profile_analysis(df)
            
            # 3. 시장 강도 지수 (새로 추가)
            market_strength = self._market_strength_index(df)
            
            # 변동성 체제 분석 (보조 지표)
            volatility_regime = self._volatility_regime_analysis(df)
            
            # 통합 방향성 결정
            macro_score = (trend_alignment['score'] + volume_profile['score'] + market_strength['score']) / 3
            
            if macro_score > 0.6:
                direction = 'bullish'
                regime = MarketRegime.BULLISH
            elif macro_score < -0.6:
                direction = 'bearish' 
                regime = MarketRegime.BEARISH
            else:
                direction = 'neutral'
                regime = MarketRegime.SIDEWAYS
            
            # 변동성 체제 반영
            if volatility_regime['high_volatility']:
                regime = MarketRegime.HIGH_VOLATILITY
            elif volatility_regime['low_volatility']:
                regime = MarketRegime.LOW_VOLATILITY
            
            return {
                'direction': direction,
                'strength': abs(macro_score),
                'regime': regime,
                'trend_alignment': trend_alignment,
                'volume_profile': volume_profile,
                'market_strength': market_strength,
                'volatility_regime': volatility_regime
            }
            
        except Exception as e:
            self.logger.error(f"매크로 분석 오류: {e}")
            return {'direction': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
    
    def _enhanced_trend_alignment_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """개선된 장기 트렌드 정렬 분석"""
        try:
            # 다중 이동평균과 기울기 분석
            sma20 = df['close'].rolling(20).mean()
            sma50 = df['close'].rolling(50).mean()
            sma100 = df['close'].rolling(100).mean()
            sma200 = df['close'].rolling(200).mean()
            
            latest_price = df['close'].iloc[-1]
            latest_sma20 = sma20.iloc[-1]
            latest_sma50 = sma50.iloc[-1] 
            latest_sma100 = sma100.iloc[-1] if not pd.isna(sma100.iloc[-1]) else latest_sma50
            latest_sma200 = sma200.iloc[-1] if not pd.isna(sma200.iloc[-1]) else latest_sma100
            
            # 이동평균 기울기 계산 (최근 5일)
            sma20_slope = (sma20.iloc[-1] - sma20.iloc[-5]) / sma20.iloc[-5] if len(sma20) >= 5 else 0
            sma50_slope = (sma50.iloc[-1] - sma50.iloc[-5]) / sma50.iloc[-5] if len(sma50) >= 5 else 0
            sma200_slope = (sma200.iloc[-1] - sma200.iloc[-5]) / sma200.iloc[-5] if len(sma200) >= 5 else 0
            
            # 점수 계산
            alignment_score = 0
            slope_score = 0
            position_score = 0
            
            # 1. 이동평균 정렬 점수
            if latest_price > latest_sma20 > latest_sma50 > latest_sma100 > latest_sma200:
                alignment_score = 1.0  # 완벽한 상승 정렬
            elif latest_price < latest_sma20 < latest_sma50 < latest_sma100 < latest_sma200:
                alignment_score = -1.0  # 완벽한 하락 정렬
            elif latest_price > latest_sma50 > latest_sma200:
                alignment_score = 0.6  # 부분 상승 정렬
            elif latest_price < latest_sma50 < latest_sma200:
                alignment_score = -0.6  # 부분 하락 정렬
            elif latest_price > latest_sma200:
                alignment_score = 0.3  # 약한 상승
            elif latest_price < latest_sma200:
                alignment_score = -0.3  # 약한 하락
            
            # 2. 기울기 점수 (장기 모멘텀)
            if sma20_slope > 0.005 and sma50_slope > 0.002 and sma200_slope > 0.001:
                slope_score = 1.0  # 강한 상승 모멘텀
            elif sma20_slope < -0.005 and sma50_slope < -0.002 and sma200_slope < -0.001:
                slope_score = -1.0  # 강한 하락 모멘텀
            elif sma20_slope > 0 and sma50_slope > 0:
                slope_score = 0.5  # 약한 상승 모멘텀
            elif sma20_slope < 0 and sma50_slope < 0:
                slope_score = -0.5  # 약한 하락 모멘텀
            
            # 3. 가격 위치 점수 (지지/저항 역할)
            distance_from_sma200 = (latest_price - latest_sma200) / latest_sma200
            if distance_from_sma200 > 0.1:  # 10% 이상 위
                position_score = 1.0
            elif distance_from_sma200 > 0.05:  # 5-10% 위
                position_score = 0.5
            elif distance_from_sma200 < -0.1:  # 10% 이상 아래
                position_score = -1.0
            elif distance_from_sma200 < -0.05:  # 5-10% 아래
                position_score = -0.5
            
            # 최종 점수 (가중 평균)
            final_score = (alignment_score * 0.5 + slope_score * 0.3 + position_score * 0.2)
            
            return {
                'score': final_score,
                'sma20': latest_sma20,
                'sma50': latest_sma50,
                'sma100': latest_sma100,
                'sma200': latest_sma200,
                'sma20_slope': sma20_slope,
                'sma50_slope': sma50_slope,
                'sma200_slope': sma200_slope,
                'alignment_score': alignment_score,
                'slope_score': slope_score,
                'position_score': position_score,
                'distance_from_sma200': distance_from_sma200
            }
            
        except Exception as e:
            self.logger.error(f"개선된 트렌드 정렬 분석 오류: {e}")
            return {'score': 0.0}
    
    def _volume_profile_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """거래량 프로파일 분석"""
        try:
            # 최근 30일 거래량 분석
            recent_data = df.tail(30)
            
            # 가격대별 거래량 분포 계산
            price_range = recent_data['high'].max() - recent_data['low'].min()
            price_bins = 20  # 20개 구간으로 분할
            bin_size = price_range / price_bins
            
            volume_profile = {}
            for i, row in recent_data.iterrows():
                # 각 캔들의 가격 범위를 여러 구간으로 나누어 거래량 분배
                candle_range = row['high'] - row['low']
                if candle_range > 0:
                    # 단순화: 평균 가격 기준으로 거래량 할당
                    avg_price = (row['high'] + row['low'] + row['close']) / 3
                    price_bin = int((avg_price - recent_data['low'].min()) / bin_size)
                    price_bin = max(0, min(price_bins - 1, price_bin))  # 범위 제한
                    
                    if price_bin not in volume_profile:
                        volume_profile[price_bin] = 0
                    volume_profile[price_bin] += row['volume']
            
            if not volume_profile:
                return {'score': 0.0}
            
            # POC (Point of Control) 찾기 - 가장 거래량이 많은 가격대
            max_volume_bin = max(volume_profile.keys(), key=lambda k: volume_profile[k])
            poc_price = recent_data['low'].min() + (max_volume_bin + 0.5) * bin_size
            
            # Value Area 계산 (총 거래량의 70%)
            total_volume = sum(volume_profile.values())
            target_volume = total_volume * 0.7
            
            # POC 주변에서 확장하며 Value Area 찾기
            sorted_bins = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
            value_area_volume = 0
            value_area_bins = []
            
            for bin_idx, volume in sorted_bins:
                value_area_volume += volume
                value_area_bins.append(bin_idx)
                if value_area_volume >= target_volume:
                    break
            
            if value_area_bins:
                value_area_high = recent_data['low'].min() + (max(value_area_bins) + 1) * bin_size
                value_area_low = recent_data['low'].min() + min(value_area_bins) * bin_size
            else:
                value_area_high = value_area_low = poc_price
            
            # 현재 가격과 POC, Value Area 비교
            current_price = df['close'].iloc[-1]
            
            # 점수 계산
            score = 0.0
            
            # 1. POC 대비 위치
            poc_distance = (current_price - poc_price) / poc_price
            
            # 2. Value Area 내 위치
            in_value_area = value_area_low <= current_price <= value_area_high
            
            # 3. 거래량 증가 추세
            recent_volume = recent_data['volume'].tail(5).mean()
            avg_volume = recent_data['volume'].mean()
            volume_trend = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # 점수 산정
            if in_value_area:
                # Value Area 내에서는 중립적
                if volume_trend > 1.2:
                    score = 0.3 if poc_distance > 0 else -0.3  # 거래량 증가 시 방향성 부여
                else:
                    score = 0.1 if poc_distance > 0 else -0.1
            else:
                # Value Area 밖에서는 평균회귀 성향
                if current_price > value_area_high:
                    # 고가권 - 하락 압력
                    score = -0.5 if volume_trend > 1.2 else -0.3
                elif current_price < value_area_low:
                    # 저가권 - 상승 압력
                    score = 0.5 if volume_trend > 1.2 else 0.3
            
            return {
                'score': score,
                'poc_price': poc_price,
                'value_area_high': value_area_high,
                'value_area_low': value_area_low,
                'current_vs_poc': poc_distance,
                'in_value_area': in_value_area,
                'volume_trend': volume_trend,
                'total_volume': total_volume
            }
            
        except Exception as e:
            self.logger.error(f"거래량 프로파일 분석 오류: {e}")
            return {'score': 0.0}
    
    def _market_strength_index(self, df: pd.DataFrame) -> Dict[str, float]:
        """시장 강도 지수 (커스텀 지표)"""
        try:
            # 여러 강도 지표를 조합한 커스텀 지수
            
            # 1. 상승/하락 일수 비율 (최근 20일)
            recent_data = df.tail(20)
            up_days = (recent_data['close'] > recent_data['open']).sum()
            down_days = (recent_data['close'] < recent_data['open']).sum()
            up_down_ratio = up_days / (up_days + down_days) if (up_days + down_days) > 0 else 0.5
            
            # 2. 평균 캔들 실체 크기 (변동성 고려)
            body_sizes = abs(recent_data['close'] - recent_data['open']) / recent_data['open']
            avg_body_size = body_sizes.mean()
            
            # 3. 거래량 가중 상승률
            price_changes = recent_data['close'].pct_change().fillna(0)
            volume_weights = recent_data['volume'] / recent_data['volume'].sum()
            volume_weighted_return = (price_changes * volume_weights).sum()
            
            # 4. High-Low 스프레드 (시장 참여도)
            hl_spreads = (recent_data['high'] - recent_data['low']) / recent_data['close']
            avg_hl_spread = hl_spreads.mean()
            
            # 5. 연속 상승/하락 패턴
            consecutive_pattern = 0
            current_direction = 1 if recent_data['close'].iloc[-1] > recent_data['open'].iloc[-1] else -1
            
            for i in range(len(recent_data) - 2, -1, -1):
                day_direction = 1 if recent_data['close'].iloc[i] > recent_data['open'].iloc[i] else -1
                if day_direction == current_direction:
                    consecutive_pattern += 1
                else:
                    break
            
            consecutive_pattern *= current_direction  # 방향 고려
            
            # 점수 계산
            strength_components = {
                'up_down_bias': (up_down_ratio - 0.5) * 2,  # -1 ~ 1
                'volatility_strength': min(1.0, avg_body_size * 50),  # 변동성 강도
                'volume_momentum': max(-1.0, min(1.0, volume_weighted_return * 100)),  # 거래량 가중 모멘텀
                'market_participation': min(1.0, avg_hl_spread * 20),  # 시장 참여도
                'pattern_momentum': max(-1.0, min(1.0, consecutive_pattern * 0.2))  # 연속 패턴
            }
            
            # 가중 평균으로 최종 점수 계산
            weights = {
                'up_down_bias': 0.3,
                'volatility_strength': 0.2,
                'volume_momentum': 0.25,
                'market_participation': 0.15,
                'pattern_momentum': 0.1
            }
            
            final_score = sum(strength_components[k] * weights[k] for k in strength_components)
            
            return {
                'score': final_score,
                'up_down_ratio': up_down_ratio,
                'avg_body_size': avg_body_size,
                'volume_weighted_return': volume_weighted_return,
                'avg_hl_spread': avg_hl_spread,
                'consecutive_pattern': consecutive_pattern,
                'components': strength_components
            }
            
        except Exception as e:
            self.logger.error(f"시장 강도 지수 계산 오류: {e}")
            return {'score': 0.0}
    
    def _volatility_regime_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """변동성 체제 분석"""
        try:
            # ATR 계산
            atr = self._calculate_atr(df, 14)
            atr_ma = atr.rolling(30).mean()
            
            latest_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
            avg_atr = atr_ma.iloc[-1] if not pd.isna(atr_ma.iloc[-1]) else latest_atr
            
            # 변동성 체제 분류
            volatility_ratio = latest_atr / avg_atr if avg_atr > 0 else 1
            high_volatility = volatility_ratio > 1.5
            low_volatility = volatility_ratio < 0.7
            
            return {
                'atr': latest_atr,
                'atr_ratio': volatility_ratio,
                'high_volatility': high_volatility,
                'low_volatility': low_volatility
            }
            
        except Exception as e:
            self.logger.error(f"변동성 분석 오류: {e}")
            return {'high_volatility': False, 'low_volatility': False}
    
    def _market_structure_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """시장 구조 분석"""
        try:
            # 최근 고점/저점 분석
            highs = df['high'].rolling(10).max()
            lows = df['low'].rolling(10).min()
            
            # 최근 30일간의 고점/저점 트렌드
            recent_highs = highs.tail(30)
            recent_lows = lows.tail(30)
            
            # 고점 상승/하락 추세
            high_trend = 0
            if len(recent_highs) >= 20:
                high_slope = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
                high_trend = np.tanh(high_slope / recent_highs.mean() * 1000)  # 정규화
            
            # 저점 상승/하락 추세  
            low_trend = 0
            if len(recent_lows) >= 20:
                low_slope = np.polyfit(range(len(recent_lows)), recent_lows, 1)[0]
                low_trend = np.tanh(low_slope / recent_lows.mean() * 1000)  # 정규화
            
            # 시장 구조 점수 (고점과 저점이 모두 상승하면 강세)
            structure_score = (high_trend + low_trend) / 2
            
            return {
                'score': structure_score,
                'high_trend': high_trend,
                'low_trend': low_trend
            }
            
        except Exception as e:
            self.logger.error(f"시장 구조 분석 오류: {e}")
            return {'score': 0.0}
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATR 계산"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        return atr


class MultiTierStrategyEngine:
    """다층 전략 통합 엔진"""
    
    def __init__(self):
        self.logger = logging.getLogger('MultiTierStrategyEngine')
        
        # 계층별 엔진
        self.scalping_layer = ScalpingLayer()
        self.trend_filter = TrendFilterLayer()
        self.macro_direction = MacroDirectionLayer()
        
        # 가중치 설정 (설정 파일에서 로드)
        self.tier_weights = {
            StrategyTier.SCALPING: config_manager.get_config('strategies.tier_weights.scalping', 0.4),
            StrategyTier.TREND: config_manager.get_config('strategies.tier_weights.trend', 0.35),
            StrategyTier.MACRO: config_manager.get_config('strategies.tier_weights.macro', 0.25)
        }
        
    def analyze(self) -> MultiTierDecision:
        """다층 전략 통합 분석"""
        start_time = datetime.now()
        
        try:
            # 각 계층 분석 실행
            scalping_signals = self.scalping_layer.analyze()
            trend_analysis = self.trend_filter.analyze()
            macro_analysis = self.macro_direction.analyze()
            
            # 시장 체제 결정
            market_regime = self._determine_market_regime(trend_analysis, macro_analysis)
            
            # 체제별 가중치 조정
            adjusted_weights = self._adjust_weights_by_regime(market_regime)
            
            # 신호 통합
            decision = self._integrate_signals(
                scalping_signals, 
                trend_analysis, 
                macro_analysis, 
                adjusted_weights,
                market_regime
            )
            
            # 실행 추적
            execution_duration = (datetime.now() - start_time).total_seconds() * 1000
            self._track_strategy_executions(
                scalping_signals, trend_analysis, macro_analysis,
                execution_duration, market_regime.value, decision
            )
            
            return decision
            
        except Exception as e:
            self.logger.error(f"다층 전략 분석 오류: {e}")
            execution_duration = (datetime.now() - start_time).total_seconds() * 1000
            self._track_error_execution(str(e), execution_duration)
            return self._create_hold_decision(MarketRegime.SIDEWAYS)
    
    def _determine_market_regime(self, trend_analysis: Dict, macro_analysis: Dict) -> MarketRegime:
        """시장 체제 결정"""
        try:
            # 변동성 우선 체크
            if trend_analysis.get('volatility', 0) > 0.05:  # 높은 변동성
                return MarketRegime.HIGH_VOLATILITY
            elif trend_analysis.get('volatility', 0) < 0.01:  # 낮은 변동성
                return MarketRegime.LOW_VOLATILITY
            
            # 트렌드 기반 체제 결정
            macro_regime = macro_analysis.get('regime', MarketRegime.SIDEWAYS)
            trend_regime = trend_analysis.get('regime', MarketRegime.SIDEWAYS)
            
            # 두 계층이 일치하면 해당 체제
            if macro_regime == trend_regime:
                return macro_regime
            
            # 불일치시 매크로를 우선시 (장기가 단기보다 우선)
            return macro_regime
            
        except Exception as e:
            self.logger.error(f"시장 체제 결정 오류: {e}")
            return MarketRegime.SIDEWAYS
    
    def _adjust_weights_by_regime(self, regime: MarketRegime) -> Dict[StrategyTier, float]:
        """체제별 가중치 조정"""
        base_weights = self.tier_weights.copy()
        
        if regime == MarketRegime.HIGH_VOLATILITY:
            # 고변동성: 스캘핑 가중치 증가
            base_weights[StrategyTier.SCALPING] = 0.5
            base_weights[StrategyTier.TREND] = 0.3
            base_weights[StrategyTier.MACRO] = 0.2
        elif regime == MarketRegime.LOW_VOLATILITY:
            # 저변동성: 매크로 가중치 증가
            base_weights[StrategyTier.SCALPING] = 0.3
            base_weights[StrategyTier.TREND] = 0.3
            base_weights[StrategyTier.MACRO] = 0.4
        elif regime in [MarketRegime.BULLISH, MarketRegime.BEARISH]:
            # 트렌드 시장: 트렌드 가중치 증가
            base_weights[StrategyTier.SCALPING] = 0.3
            base_weights[StrategyTier.TREND] = 0.4
            base_weights[StrategyTier.MACRO] = 0.3
        
        return base_weights
    
    def _integrate_signals(self, scalping_signals: List[TierSignal], 
                          trend_analysis: Dict, macro_analysis: Dict,
                          weights: Dict, regime: MarketRegime) -> MultiTierDecision:
        """신호 통합"""
        try:
            # 스캘핑 레이어 점수 계산
            scalping_score = 0
            scalping_reasoning = []
            
            for signal in scalping_signals:
                signal_weight = signal.confidence * signal.strength
                if signal.action == 'buy':
                    scalping_score += signal_weight
                elif signal.action == 'sell':
                    scalping_score -= signal_weight
                
                scalping_reasoning.append(f"{signal.strategy_id}: {signal.action} ({signal.confidence:.2f})")
            
            # 스캘핑 점수 정규화 (최대 3개 신호 가정)
            scalping_score = np.tanh(scalping_score / 3)
            
            # 트렌드 레이어 점수
            trend_score = 0
            trend_strength = trend_analysis.get('strength', 0.5)
            if trend_analysis.get('trend') == 'bullish':
                trend_score = trend_strength
            elif trend_analysis.get('trend') == 'bearish':
                trend_score = -trend_strength
            
            # 매크로 레이어 점수
            macro_score = 0
            macro_strength = macro_analysis.get('strength', 0.5)
            if macro_analysis.get('direction') == 'bullish':
                macro_score = macro_strength
            elif macro_analysis.get('direction') == 'bearish':
                macro_score = -macro_strength
            
            # 가중 평균 계산
            final_score = (
                scalping_score * weights[StrategyTier.SCALPING] +
                trend_score * weights[StrategyTier.TREND] +
                macro_score * weights[StrategyTier.MACRO]
            )
            
            # 최종 결정
            if final_score > 0.3:
                final_action = 'buy'
                confidence = min(0.95, abs(final_score) + 0.2)
            elif final_score < -0.3:
                final_action = 'sell'
                confidence = min(0.95, abs(final_score) + 0.2)
            else:
                final_action = 'hold'
                confidence = 0.5
            
            # 리스크 점수 계산
            risk_score = self._calculate_risk_score(regime, trend_analysis, macro_analysis)
            
            # 포지션 크기 결정
            base_amount = config_manager.get_config('trading.max_trade_amount', 100000)
            risk_adjusted_amount = base_amount * confidence * (1 - risk_score)
            
            # 추론 생성
            reasoning_parts = []
            if scalping_reasoning:
                reasoning_parts.append(f"스캘핑: {', '.join(scalping_reasoning[:2])}")
            reasoning_parts.append(f"트렌드: {trend_analysis.get('trend', 'neutral')} ({trend_strength:.2f})")
            reasoning_parts.append(f"매크로: {macro_analysis.get('direction', 'neutral')} ({macro_strength:.2f})")
            reasoning_parts.append(f"체제: {regime.value}")
            
            reasoning = " | ".join(reasoning_parts)
            
            return MultiTierDecision(
                final_action=final_action,
                confidence=confidence,
                tier_contributions={
                    StrategyTier.SCALPING: scalping_score * weights[StrategyTier.SCALPING],
                    StrategyTier.TREND: trend_score * weights[StrategyTier.TREND],
                    StrategyTier.MACRO: macro_score * weights[StrategyTier.MACRO]
                },
                market_regime=regime,
                reasoning=reasoning,
                risk_score=risk_score,
                suggested_amount=risk_adjusted_amount,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"신호 통합 오류: {e}")
            return self._create_hold_decision(regime)
    
    def _calculate_risk_score(self, regime: MarketRegime, trend_analysis: Dict, macro_analysis: Dict) -> float:
        """리스크 점수 계산 (0~1, 높을수록 위험)"""
        try:
            base_risk = 0.3
            
            # 변동성 기반 리스크
            volatility = trend_analysis.get('volatility', 0.02)
            volatility_risk = min(0.4, volatility * 20)  # 변동성 2% = 리스크 0.4
            
            # 체제별 리스크
            regime_risk = {
                MarketRegime.HIGH_VOLATILITY: 0.4,
                MarketRegime.LOW_VOLATILITY: 0.1,
                MarketRegime.BULLISH: 0.2,
                MarketRegime.BEARISH: 0.3,
                MarketRegime.SIDEWAYS: 0.25
            }.get(regime, 0.3)
            
            total_risk = min(0.8, base_risk + volatility_risk + regime_risk) / 3
            return total_risk
            
        except Exception as e:
            self.logger.error(f"리스크 점수 계산 오류: {e}")
            return 0.5
    
    def _create_hold_decision(self, regime: MarketRegime) -> MultiTierDecision:
        """홀드 결정 생성"""
        return MultiTierDecision(
            final_action='hold',
            confidence=0.5,
            tier_contributions={
                StrategyTier.SCALPING: 0.0,
                StrategyTier.TREND: 0.0,
                StrategyTier.MACRO: 0.0
            },
            market_regime=regime,
            reasoning="분석 오류 또는 신호 부족으로 홀드",
            risk_score=0.5,
            suggested_amount=0,
            timestamp=datetime.now()
        )
    
    def _track_strategy_executions(self, scalping_signals, trend_analysis, macro_analysis,
                                 execution_duration, market_regime, decision):
        """전략 실행 추적"""
        try:
            execution_time = datetime.now()
            
            # 스캘핑 전략들 추적
            for signal in scalping_signals:
                execution = StrategyExecution(
                    execution_time=execution_time,
                    strategy_tier='scalping',
                    strategy_id=getattr(signal, 'strategy_id', 'unknown'),
                    signal_action=getattr(signal, 'action', 'hold'),
                    confidence=getattr(signal, 'confidence', 0.5),
                    strength=getattr(signal, 'strength', 0.5),
                    reasoning=getattr(signal, 'reasoning', ''),
                    market_regime=market_regime,
                    indicators=getattr(signal, 'indicators', {}),
                    execution_duration=execution_duration
                )
                execution_tracker.record_execution(execution)
            
            # 트렌드 전략들 추적
            for strategy_name, analysis in trend_analysis.items():
                if isinstance(analysis, dict) and 'score' in analysis:
                    action = 'buy' if analysis['score'] > 0.3 else 'sell' if analysis['score'] < -0.3 else 'hold'
                    execution = StrategyExecution(
                        execution_time=execution_time,
                        strategy_tier='trend',
                        strategy_id=strategy_name,
                        signal_action=action,
                        confidence=abs(analysis['score']),
                        strength=abs(analysis['score']),
                        reasoning=f"트렌드 분석 점수: {analysis['score']:.3f}",
                        market_regime=market_regime,
                        indicators=analysis,
                        execution_duration=execution_duration
                    )
                    execution_tracker.record_execution(execution)
            
            # 매크로 전략들 추적
            for strategy_name, analysis in macro_analysis.items():
                if isinstance(analysis, dict) and 'score' in analysis:
                    action = 'buy' if analysis['score'] > 0.3 else 'sell' if analysis['score'] < -0.3 else 'hold'
                    execution = StrategyExecution(
                        execution_time=execution_time,
                        strategy_tier='macro',
                        strategy_id=strategy_name,
                        signal_action=action,
                        confidence=abs(analysis['score']),
                        strength=abs(analysis['score']),
                        reasoning=f"매크로 분석 점수: {analysis['score']:.3f}",
                        market_regime=market_regime,
                        indicators=analysis,
                        execution_duration=execution_duration
                    )
                    execution_tracker.record_execution(execution)
            
            # 통합 결정 추적
            execution = StrategyExecution(
                execution_time=execution_time,
                strategy_tier='integrated',
                strategy_id='multi_tier_decision',
                signal_action=decision.final_action,
                confidence=decision.confidence,
                strength=decision.confidence,
                reasoning=decision.reasoning,
                market_regime=market_regime,
                indicators={
                    'tier_contributions': decision.tier_contributions,
                    'risk_score': decision.risk_score,
                    'suggested_amount': decision.suggested_amount
                },
                execution_duration=execution_duration
            )
            execution_tracker.record_execution(execution)
            
        except Exception as e:
            self.logger.error(f"전략 실행 추적 오류: {e}")
    
    def _track_error_execution(self, error_message, execution_duration):
        """오류 실행 추적"""
        try:
            execution = StrategyExecution(
                execution_time=datetime.now(),
                strategy_tier='error',
                strategy_id='analysis_error',
                signal_action='hold',
                confidence=0.0,
                strength=0.0,
                reasoning=f"분석 오류: {error_message}",
                market_regime='unknown',
                indicators={'error': error_message},
                execution_duration=execution_duration
            )
            execution_tracker.record_execution(execution)
            
        except Exception as e:
            self.logger.error(f"오류 실행 추적 실패: {e}")


# 전역 인스턴스
multi_tier_engine = MultiTierStrategyEngine()
