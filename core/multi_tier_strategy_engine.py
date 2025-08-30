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


class StrategyTier(Enum):
    """전략 계층"""
    SCALPING = "5m"      # 5분 스캘핑 레이어
    TREND = "1h"         # 1시간 트렌드 레이어  
    MACRO = "1d"         # 1일 매크로 레이어


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
    """5분 스캘핑 계층"""
    
    def __init__(self):
        self.logger = logging.getLogger('ScalpingLayer')
        self.timeframe = '5m'
        
    def analyze(self) -> List[TierSignal]:
        """5분 스캘핑 신호 생성"""
        signals = []
        
        try:
            # 5분 캔들 데이터 조회
            df = candle_collector.get_dataframe('5m', 50)
            if df is None or len(df) < 20:
                self.logger.warning("5분 캔들 데이터 부족")
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
            # RSI 계산
            rsi = self._calculate_rsi(df['close'], 5)
            stoch_k, stoch_d = self._calculate_stochastic(df, 5, 3)
            volume_ma = df['volume'].rolling(10).mean()
            
            latest_rsi = rsi.iloc[-1]
            latest_stoch_k = stoch_k.iloc[-1] if not pd.isna(stoch_k.iloc[-1]) else 50
            latest_volume = df['volume'].iloc[-1]
            avg_volume = volume_ma.iloc[-1] if not pd.isna(volume_ma.iloc[-1]) else df['volume'].mean()
            
            # 신호 조건
            oversold_bounce = latest_rsi < 25 and latest_stoch_k < 20
            volume_surge = latest_volume > avg_volume * 1.5
            
            if oversold_bounce and volume_surge:
                confidence = min(0.9, (30 - latest_rsi) / 10 + 0.3)
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
            overbought_decline = latest_rsi > 75 and latest_stoch_k > 80
            if overbought_decline and volume_surge:
                confidence = min(0.9, (latest_rsi - 70) / 10 + 0.3)
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
            # 볼린저밴드 계산
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df['close'], 20, 2)
            bb_width = (bb_upper - bb_lower) / bb_middle
            
            # MACD 계산
            macd, macd_signal, _ = self._calculate_macd(df['close'], 5, 13, 3)
            
            latest_close = df['close'].iloc[-1]
            latest_bb_width = bb_width.iloc[-1]
            latest_macd = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
            latest_macd_signal = macd_signal.iloc[-1] if not pd.isna(macd_signal.iloc[-1]) else 0
            
            # 밴드 수축 후 돌파
            bb_width_ma = bb_width.rolling(10).mean()
            is_squeeze = latest_bb_width < bb_width_ma.iloc[-1] * 0.8
            
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
            # 최근 고점/저점 계산
            highs = df['high'].rolling(5).max()
            lows = df['low'].rolling(5).min()
            
            latest_close = df['close'].iloc[-1]
            latest_high = df['high'].iloc[-1]
            latest_low = df['low'].iloc[-1]
            
            # 지지선 근처에서의 반등
            recent_lows = lows.tail(20).dropna()
            if len(recent_lows) > 0:
                support_level = recent_lows.min()
                distance_to_support = (latest_close - support_level) / support_level
                
                # 지지선 근처 (1% 이내) + 반전 캔들
                if 0 < distance_to_support < 0.01:
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
            recent_highs = highs.tail(20).dropna()
            if len(recent_highs) > 0:
                resistance_level = recent_highs.max()
                distance_to_resistance = (resistance_level - latest_close) / latest_close
                
                # 저항선 근처 (1% 이내) + 반전 캔들
                if 0 < distance_to_resistance < 0.01:
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
    """1시간 트렌드 필터 계층"""
    
    def __init__(self):
        self.logger = logging.getLogger('TrendFilterLayer')
        self.timeframe = '1h'
        
    def analyze(self) -> Dict[str, Any]:
        """1시간 트렌드 필터 분석"""
        try:
            # 1시간 캔들 데이터 조회
            df = candle_collector.get_dataframe('1h', 100)
            if df is None or len(df) < 50:
                self.logger.warning("1시간 캔들 데이터 부족")
                return {'trend': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
            
            # 1. EMA 트렌드 필터
            ema_trend = self._ema_trend_analysis(df)
            
            # 2. VWAP 포지션 분석
            vwap_position = self._vwap_analysis(df)
            
            # 3. 모멘텀 강도 측정
            momentum_strength = self._momentum_analysis(df)
            
            # 통합 분석
            trend_score = (ema_trend['score'] + vwap_position['score'] + momentum_strength['score']) / 3
            
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
                'momentum_strength': momentum_strength,
                'volatility': self._calculate_volatility(df)
            }
            
        except Exception as e:
            self.logger.error(f"트렌드 필터 분석 오류: {e}")
            return {'trend': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
    
    def _ema_trend_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """EMA 트렌드 분석"""
        try:
            ema12 = df['close'].ewm(span=12).mean()
            ema26 = df['close'].ewm(span=26).mean()
            ema50 = df['close'].ewm(span=50).mean()
            
            latest_price = df['close'].iloc[-1]
            latest_ema12 = ema12.iloc[-1]
            latest_ema26 = ema26.iloc[-1]
            latest_ema50 = ema50.iloc[-1]
            
            # EMA 정렬 점수 계산
            if latest_ema12 > latest_ema26 > latest_ema50 and latest_price > latest_ema12:
                score = 1.0  # 강한 상승 트렌드
            elif latest_ema12 < latest_ema26 < latest_ema50 and latest_price < latest_ema12:
                score = -1.0  # 강한 하락 트렌드
            elif latest_ema12 > latest_ema26 and latest_price > latest_ema26:
                score = 0.5  # 약한 상승 트렌드
            elif latest_ema12 < latest_ema26 and latest_price < latest_ema26:
                score = -0.5  # 약한 하락 트렌드
            else:
                score = 0.0  # 중립
            
            return {
                'score': score,
                'ema12': latest_ema12,
                'ema26': latest_ema26,
                'ema50': latest_ema50,
                'price_vs_ema12': (latest_price - latest_ema12) / latest_ema12
            }
            
        except Exception as e:
            self.logger.error(f"EMA 트렌드 분석 오류: {e}")
            return {'score': 0.0}
    
    def _vwap_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """VWAP 분석"""
        try:
            # VWAP 계산 (단순화된 버전)
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            
            latest_price = df['close'].iloc[-1]
            latest_vwap = vwap.iloc[-1]
            
            # VWAP 대비 위치 점수
            price_vs_vwap = (latest_price - latest_vwap) / latest_vwap
            
            if price_vs_vwap > 0.02:
                score = 1.0  # VWAP 위 2% 이상
            elif price_vs_vwap > 0.005:
                score = 0.5  # VWAP 위 0.5~2%
            elif price_vs_vwap < -0.02:
                score = -1.0  # VWAP 아래 2% 이상
            elif price_vs_vwap < -0.005:
                score = -0.5  # VWAP 아래 0.5~2%
            else:
                score = 0.0  # VWAP 근처
            
            return {
                'score': score,
                'vwap': latest_vwap,
                'price_vs_vwap': price_vs_vwap
            }
            
        except Exception as e:
            self.logger.error(f"VWAP 분석 오류: {e}")
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
    """1일 매크로 방향성 계층"""
    
    def __init__(self):
        self.logger = logging.getLogger('MacroDirectionLayer')
        self.timeframe = '1d'
        
    def analyze(self) -> Dict[str, Any]:
        """매크로 방향성 분석"""
        try:
            # 1일 캔들 데이터 조회
            df = candle_collector.get_dataframe('1d', 200)
            if df is None or len(df) < 50:
                self.logger.warning("일일 캔들 데이터 부족")
                return {'direction': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
            
            # 1. 장기 트렌드 정렬
            trend_alignment = self._trend_alignment_analysis(df)
            
            # 2. 변동성 체제 분석
            volatility_regime = self._volatility_regime_analysis(df)
            
            # 3. 시장 구조 분석
            market_structure = self._market_structure_analysis(df)
            
            # 통합 방향성 결정
            macro_score = (trend_alignment['score'] + market_structure['score']) / 2
            
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
                if regime == MarketRegime.BULLISH:
                    regime = MarketRegime.HIGH_VOLATILITY
                elif regime == MarketRegime.BEARISH:
                    regime = MarketRegime.HIGH_VOLATILITY
            
            return {
                'direction': direction,
                'strength': abs(macro_score),
                'regime': regime,
                'trend_alignment': trend_alignment,
                'volatility_regime': volatility_regime,
                'market_structure': market_structure
            }
            
        except Exception as e:
            self.logger.error(f"매크로 분석 오류: {e}")
            return {'direction': 'neutral', 'strength': 0.5, 'regime': MarketRegime.SIDEWAYS}
    
    def _trend_alignment_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """트렌드 정렬 분석"""
        try:
            sma20 = df['close'].rolling(20).mean()
            sma50 = df['close'].rolling(50).mean()
            sma200 = df['close'].rolling(200).mean()
            
            latest_price = df['close'].iloc[-1]
            latest_sma20 = sma20.iloc[-1]
            latest_sma50 = sma50.iloc[-1] 
            latest_sma200 = sma200.iloc[-1] if not pd.isna(sma200.iloc[-1]) else latest_sma50
            
            # 트렌드 정렬 점수
            if latest_price > latest_sma20 > latest_sma50 > latest_sma200:
                score = 1.0  # 완벽한 상승 정렬
            elif latest_price < latest_sma20 < latest_sma50 < latest_sma200:
                score = -1.0  # 완벽한 하락 정렬
            elif latest_price > latest_sma50 > latest_sma200:
                score = 0.7  # 부분 상승 정렬
            elif latest_price < latest_sma50 < latest_sma200:
                score = -0.7  # 부분 하락 정렬
            elif latest_price > latest_sma200:
                score = 0.3  # 약한 상승
            elif latest_price < latest_sma200:
                score = -0.3  # 약한 하락
            else:
                score = 0.0  # 중립
            
            return {
                'score': score,
                'sma20': latest_sma20,
                'sma50': latest_sma50,
                'sma200': latest_sma200,
                'price_vs_sma200': (latest_price - latest_sma200) / latest_sma200
            }
            
        except Exception as e:
            self.logger.error(f"트렌드 정렬 분석 오류: {e}")
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
        
        # 가중치 설정
        self.tier_weights = {
            StrategyTier.SCALPING: 0.4,
            StrategyTier.TREND: 0.35,
            StrategyTier.MACRO: 0.25
        }
        
    def analyze(self) -> MultiTierDecision:
        """다층 전략 통합 분석"""
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
            
            return decision
            
        except Exception as e:
            self.logger.error(f"다층 전략 분석 오류: {e}")
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


# 전역 인스턴스
multi_tier_engine = MultiTierStrategyEngine()
