"""
독립 전략 구현체들
기존 MultiTierStrategyEngine에서 분리된 개별 전략들
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

from core.independent_strategy_engine import IndependentStrategy, StrategyVote, StrategySignal


class RSIMomentumStrategy(IndependentStrategy):
    """RSI 모멘텀 전략"""
    
    def __init__(self):
        super().__init__(
            strategy_id="rsi_momentum",
            strategy_name="RSI 모멘텀 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'rsi_period': 14,
            'oversold': 30,
            'overbought': 70,
            'stoch_k_period': 14,
            'stoch_d_period': 3,
            'momentum_threshold': 0.02,
            'volume_threshold': 1.5,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """RSI 모멘텀 분석"""
        try:
            # 5분 캔들 사용
            candles = market_data.get('candles_5m')
            if not candles or len(candles) < 50:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족 (최소 50개 캔들 필요)", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # 지표 계산
            rsi = self._calculate_rsi(df['close'], config['rsi_period'])
            stoch_k, stoch_d = self._calculate_stochastic(df, config['stoch_k_period'], config['stoch_d_period'])
            
            if len(rsi) < 2 or len(stoch_k) < 2:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "지표 계산 실패", {}
                )
            
            # 최신 값들
            latest_rsi = rsi.iloc[-1]
            latest_stoch_k = stoch_k.iloc[-1]
            latest_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            
            # 모멘텀 체크
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            strong_momentum = abs(price_change) > config['momentum_threshold']
            
            # 거래량 급증
            volume_surge = latest_volume > avg_volume * config['volume_threshold']
            
            indicators = {
                'rsi': latest_rsi,
                'stoch_k': latest_stoch_k,
                'volume_ratio': latest_volume / avg_volume,
                'price_change': price_change
            }
            
            # 매수 신호: 과매도 반등
            oversold_bounce = (latest_rsi < config['oversold'] and 
                             latest_stoch_k < 20)
            
            if oversold_bounce and volume_surge and strong_momentum:
                confidence = min(0.9, (config['oversold'] - latest_rsi) / 10 + 0.3)
                strength = (latest_volume / avg_volume - 1) * 0.5 + confidence * 0.5
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    min(strength, 1.0),
                    f"RSI 과매도 반등 + 거래량 급증 (RSI:{latest_rsi:.1f}, Vol:{latest_volume/avg_volume:.1f}x)",
                    indicators
                )
            
            # 매도 신호: 과매수 하락
            overbought_decline = (latest_rsi > config['overbought'] and 
                                latest_stoch_k > 80)
            
            if overbought_decline and volume_surge and strong_momentum:
                confidence = min(0.9, (latest_rsi - config['overbought']) / 10 + 0.3)
                strength = (latest_volume / avg_volume - 1) * 0.5 + confidence * 0.5
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    min(strength, 1.0),
                    f"RSI 과매수 하락 + 거래량 급증 (RSI:{latest_rsi:.1f}, Vol:{latest_volume/avg_volume:.1f}x)",
                    indicators
                )
            
            # 중립 상황
            neutral_confidence = 0.1 if strong_momentum else 0.05
            return self._create_vote(
                StrategySignal.HOLD,
                neutral_confidence,
                0.1,
                f"중립 상황 (RSI:{latest_rsi:.1f}, 거래량 정상)",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"RSI 모멘텀 전략 분석 오류: {e}")
            return self._create_vote(
                StrategySignal.HOLD, 0.0, 0.0, f"분석 오류: {e}", {}
            )
    
    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """캔들 데이터를 DataFrame으로 변환"""
        data = []
        for candle in candles:
            data.append({
                'open': float(candle['opening_price']),
                'high': float(candle['high_price']),
                'low': float(candle['low_price']),
                'close': float(candle['trade_price']),
                'volume': float(candle['candle_acc_trade_volume'])
            })
        return pd.DataFrame(data)
    
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


class BollingerBandStrategy(IndependentStrategy):
    """볼린저밴드 수축/확장 전략"""
    
    def __init__(self):
        super().__init__(
            strategy_id="bollinger_squeeze",
            strategy_name="볼린저밴드 수축/확장 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'bb_period': 20,
            'bb_std': 2.0,
            'squeeze_threshold': 0.01,
            'macd_fast': 5,
            'macd_slow': 13,
            'macd_signal': 3,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """볼린저밴드 분석"""
        try:
            # 5분 캔들 사용
            candles = market_data.get('candles_5m')
            if not candles or len(candles) < 50:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # 볼린저밴드 계산
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
                df['close'], config['bb_period'], config['bb_std']
            )
            bb_width = (bb_upper - bb_lower) / bb_middle
            
            # MACD 계산
            macd, macd_signal, macd_histogram = self._calculate_macd(
                df['close'], config['macd_fast'], config['macd_slow'], config['macd_signal']
            )
            
            if bb_width.isna().all() or macd.isna().all():
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "지표 계산 실패", {}
                )
            
            # 최신 값들
            latest_close = df['close'].iloc[-1]
            latest_bb_width = bb_width.iloc[-1]
            latest_bb_upper = bb_upper.iloc[-1]
            latest_bb_lower = bb_lower.iloc[-1]
            latest_macd = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
            latest_macd_signal = macd_signal.iloc[-1] if not pd.isna(macd_signal.iloc[-1]) else 0
            
            # 밴드 수축 확인
            bb_width_ma = bb_width.rolling(10).mean()
            is_squeeze = latest_bb_width < bb_width_ma.iloc[-1] * (1 - config['squeeze_threshold'])
            
            # 볼린저밴드 포지션
            bb_position = (latest_close - latest_bb_lower) / (latest_bb_upper - latest_bb_lower)
            
            indicators = {
                'bb_width': latest_bb_width,
                'bb_position': bb_position,
                'macd': latest_macd,
                'macd_signal': latest_macd_signal,
                'is_squeeze': float(is_squeeze)
            }
            
            # 상향 돌파 (매수)
            if (latest_close > latest_bb_upper and 
                latest_macd > latest_macd_signal and 
                is_squeeze):
                
                confidence = min(0.8, bb_position * 0.6 + 0.2)
                strength = min(1.0, (latest_macd - latest_macd_signal) * 10 + 0.4)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"볼린저밴드 상향돌파 + MACD 상승 (위치:{bb_position:.2f})",
                    indicators
                )
            
            # 하향 돌파 (매도)
            elif (latest_close < latest_bb_lower and 
                  latest_macd < latest_macd_signal and 
                  is_squeeze):
                
                confidence = min(0.8, (1 - bb_position) * 0.6 + 0.2)
                strength = min(1.0, (latest_macd_signal - latest_macd) * 10 + 0.4)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"볼린저밴드 하향돌파 + MACD 하락 (위치:{bb_position:.2f})",
                    indicators
                )
            
            # 중립
            neutral_confidence = 0.15 if is_squeeze else 0.05
            return self._create_vote(
                StrategySignal.HOLD,
                neutral_confidence,
                0.1,
                f"밴드 내 움직임 (수축:{is_squeeze}, 위치:{bb_position:.2f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"볼린저밴드 전략 분석 오류: {e}")
            return self._create_vote(
                StrategySignal.HOLD, 0.0, 0.0, f"분석 오류: {e}", {}
            )
    
    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """캔들 데이터를 DataFrame으로 변환"""
        data = []
        for candle in candles:
            data.append({
                'open': float(candle['opening_price']),
                'high': float(candle['high_price']),
                'low': float(candle['low_price']),
                'close': float(candle['trade_price']),
                'volume': float(candle['candle_acc_trade_volume'])
            })
        return pd.DataFrame(data)
    
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


class SupportResistanceStrategy(IndependentStrategy):
    """지지/저항 반등 전략"""
    
    def __init__(self):
        super().__init__(
            strategy_id="support_resistance",
            strategy_name="지지/저항 반등 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'lookback_period': 20,
            'touch_tolerance': 0.005,
            'pattern_threshold': 0.3,
            'min_touches': 2,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """지지/저항 분석"""
        try:
            # 15분 캔들 사용 (더 안정적인 지지/저항)
            candles = market_data.get('candles_15m')
            if not candles or len(candles) < 50:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # 지지/저항 레벨 계산
            support_level, resistance_level = self._find_support_resistance(df, config['lookback_period'])
            
            latest_close = df['close'].iloc[-1]
            latest_high = df['high'].iloc[-1]
            latest_low = df['low'].iloc[-1]
            
            # 캔들 패턴 분석
            hammer_strength = self._detect_hammer_pattern(df.iloc[-1])
            shooting_star_strength = self._detect_shooting_star_pattern(df.iloc[-1])
            
            indicators = {
                'support_level': support_level,
                'resistance_level': resistance_level,
                'current_price': latest_close,
                'hammer_strength': hammer_strength,
                'shooting_star_strength': shooting_star_strength
            }
            
            # 지지선 근처에서 반등 (매수)
            if support_level > 0:
                distance_to_support = (latest_close - support_level) / support_level
                
                if (0 < distance_to_support < config['touch_tolerance'] and 
                    hammer_strength > config['pattern_threshold']):
                    
                    confidence = 0.75
                    strength = min(1.0, (config['touch_tolerance'] - distance_to_support) * 100 + hammer_strength)
                    
                    indicators['distance_to_support'] = distance_to_support
                    
                    return self._create_vote(
                        StrategySignal.BUY,
                        confidence,
                        strength,
                        f"지지선 반등 + 해머 패턴 (지지:{support_level:,.0f}, 거리:{distance_to_support:.3f})",
                        indicators
                    )
            
            # 저항선 근처에서 거부 (매도)
            if resistance_level > 0:
                distance_to_resistance = (resistance_level - latest_close) / latest_close
                
                if (0 < distance_to_resistance < config['touch_tolerance'] and 
                    shooting_star_strength > config['pattern_threshold']):
                    
                    confidence = 0.75
                    strength = min(1.0, (config['touch_tolerance'] - distance_to_resistance) * 100 + shooting_star_strength)
                    
                    indicators['distance_to_resistance'] = distance_to_resistance
                    
                    return self._create_vote(
                        StrategySignal.SELL,
                        confidence,
                        strength,
                        f"저항선 거부 + 유성 패턴 (저항:{resistance_level:,.0f}, 거리:{distance_to_resistance:.3f})",
                        indicators
                    )
            
            # 중립
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"지지/저항선과 거리 있음 (현재:{latest_close:,.0f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"지지/저항 전략 분석 오류: {e}")
            return self._create_vote(
                StrategySignal.HOLD, 0.0, 0.0, f"분석 오류: {e}", {}
            )
    
    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """캔들 데이터를 DataFrame으로 변환"""
        data = []
        for candle in candles:
            data.append({
                'open': float(candle['opening_price']),
                'high': float(candle['high_price']),
                'low': float(candle['low_price']),
                'close': float(candle['trade_price']),
                'volume': float(candle['candle_acc_trade_volume'])
            })
        return pd.DataFrame(data)
    
    def _find_support_resistance(self, df: pd.DataFrame, lookback: int) -> Tuple[float, float]:
        """지지/저항 레벨 찾기"""
        try:
            # 최근 N개 봉의 고점/저점
            recent_highs = df['high'].tail(lookback)
            recent_lows = df['low'].tail(lookback)
            
            # 지지선: 최근 저점들의 최솟값
            support_level = recent_lows.min()
            
            # 저항선: 최근 고점들의 최댓값
            resistance_level = recent_highs.max()
            
            return support_level, resistance_level
            
        except Exception as e:
            self.logger.error(f"지지/저항 레벨 계산 오류: {e}")
            return 0.0, 0.0
    
    def _detect_hammer_pattern(self, candle: pd.Series) -> float:
        """해머 패턴 강도 계산 (0.0 ~ 1.0)"""
        try:
            open_price = candle['open']
            high_price = candle['high']
            low_price = candle['low']
            close_price = candle['close']
            
            body_size = abs(close_price - open_price)
            total_range = high_price - low_price
            
            if total_range == 0:
                return 0.0
            
            # 해머 조건: 작은 몸통 + 긴 아래꼬리 + 짧은 위꼬리
            lower_shadow = min(open_price, close_price) - low_price
            upper_shadow = high_price - max(open_price, close_price)
            
            # 강도 계산
            body_ratio = body_size / total_range
            lower_shadow_ratio = lower_shadow / total_range
            upper_shadow_ratio = upper_shadow / total_range
            
            # 해머 패턴 점수
            if (body_ratio < 0.3 and 
                lower_shadow_ratio > 0.6 and 
                upper_shadow_ratio < 0.1 and 
                close_price > open_price):  # 상승 해머
                return min(1.0, lower_shadow_ratio + (0.3 - body_ratio))
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _detect_shooting_star_pattern(self, candle: pd.Series) -> float:
        """유성 패턴 강도 계산 (0.0 ~ 1.0)"""
        try:
            open_price = candle['open']
            high_price = candle['high']
            low_price = candle['low']
            close_price = candle['close']
            
            body_size = abs(close_price - open_price)
            total_range = high_price - low_price
            
            if total_range == 0:
                return 0.0
            
            # 유성 조건: 작은 몸통 + 긴 위꼬리 + 짧은 아래꼬리
            lower_shadow = min(open_price, close_price) - low_price
            upper_shadow = high_price - max(open_price, close_price)
            
            # 강도 계산
            body_ratio = body_size / total_range
            lower_shadow_ratio = lower_shadow / total_range
            upper_shadow_ratio = upper_shadow / total_range
            
            # 유성 패턴 점수
            if (body_ratio < 0.3 and 
                upper_shadow_ratio > 0.6 and 
                lower_shadow_ratio < 0.1 and 
                close_price < open_price):  # 하락 유성
                return min(1.0, upper_shadow_ratio + (0.3 - body_ratio))
            
            return 0.0
            
        except Exception:
            return 0.0
