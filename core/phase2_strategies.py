"""
Phase 2 추가 전략들
EMA, MACD, Stochastic, Williams %R, CCI, Volume, Price Action 전략
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

from core.independent_strategy_engine import IndependentStrategy, StrategyVote, StrategySignal


class EMACrossoverStrategy(IndependentStrategy):
    """EMA 크로스오버 전략 - 트렌드 추종"""
    
    def __init__(self):
        super().__init__(
            strategy_id="ema_crossover",
            strategy_name="EMA 크로스오버 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'fast_ema': 12,
            'slow_ema': 26,
            'signal_ema': 9,
            'trend_ema': 50,
            'volume_threshold': 1.2,
            'min_crossover_strength': 0.001,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """EMA 크로스오버 분석"""
        try:
            # 5분 캔들 사용
            candles = market_data.get('candles_5m')
            if not candles or len(candles) < 60:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족 (최소 60개 캔들 필요)", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # EMA 계산
            fast_ema = self._calculate_ema(df['close'], config['fast_ema'])
            slow_ema = self._calculate_ema(df['close'], config['slow_ema'])
            signal_ema = self._calculate_ema(fast_ema - slow_ema, config['signal_ema'])
            trend_ema = self._calculate_ema(df['close'], config['trend_ema'])
            
            if len(fast_ema) < 5 or len(slow_ema) < 5:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "EMA 계산 실패", {}
                )
            
            # 최신 값들
            current_fast = fast_ema.iloc[-1]
            current_slow = slow_ema.iloc[-1]
            prev_fast = fast_ema.iloc[-2]
            prev_slow = slow_ema.iloc[-2]
            current_price = df['close'].iloc[-1]
            current_trend = trend_ema.iloc[-1]
            current_signal = signal_ema.iloc[-1] if not pd.isna(signal_ema.iloc[-1]) else 0
            
            # 거래량 확인
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            volume_surge = current_volume > avg_volume * config['volume_threshold']
            
            # 크로스오버 감지
            bullish_crossover = (prev_fast <= prev_slow) and (current_fast > current_slow)
            bearish_crossover = (prev_fast >= prev_slow) and (current_fast < current_slow)
            
            # 크로스오버 강도 계산
            crossover_strength = abs(current_fast - current_slow) / current_price
            strong_crossover = crossover_strength > config['min_crossover_strength']
            
            # 트렌드 방향
            uptrend = current_price > current_trend
            downtrend = current_price < current_trend
            
            indicators = {
                'fast_ema': current_fast,
                'slow_ema': current_slow,
                'signal_ema': current_signal,
                'trend_ema': current_trend,
                'crossover_strength': crossover_strength,
                'volume_ratio': current_volume / avg_volume,
                'uptrend': uptrend
            }
            
            # 매수 신호: 상승 크로스오버 + 상승 트렌드
            if bullish_crossover and uptrend and strong_crossover:
                confidence = min(0.85, 0.5 + crossover_strength * 100)
                if volume_surge:
                    confidence += 0.1
                if current_signal > 0:  # MACD 신호선도 상승
                    confidence += 0.05
                
                strength = min(1.0, crossover_strength * 200 + 0.4)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"EMA 상승 크로스오버 (강도:{crossover_strength:.4f}, 상승트렌드)",
                    indicators
                )
            
            # 매도 신호: 하락 크로스오버 + 하락 트렌드  
            elif bearish_crossover and downtrend and strong_crossover:
                confidence = min(0.85, 0.5 + crossover_strength * 100)
                if volume_surge:
                    confidence += 0.1
                if current_signal < 0:  # MACD 신호선도 하락
                    confidence += 0.05
                
                strength = min(1.0, crossover_strength * 200 + 0.4)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"EMA 하락 크로스오버 (강도:{crossover_strength:.4f}, 하락트렌드)",
                    indicators
                )
            
            # 트렌드 지속
            elif current_fast > current_slow and uptrend:
                trend_strength = (current_fast - current_slow) / current_price
                confidence = min(0.3, trend_strength * 50)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    0.2,
                    f"상승 트렌드 지속 (EMA 순배열)",
                    indicators
                )
            
            elif current_fast < current_slow and downtrend:
                trend_strength = (current_slow - current_fast) / current_price
                confidence = min(0.3, trend_strength * 50)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    0.2,
                    f"하락 트렌드 지속 (EMA 역배열)",
                    indicators
                )
            
            # 중립 상황
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"EMA 중립 (fast/slow: {current_fast:.0f}/{current_slow:.0f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"EMA 크로스오버 전략 분석 오류: {e}")
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
    
    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """EMA(지수이동평균) 계산"""
        return prices.ewm(span=period, adjust=False).mean()


class MACDStrategy(IndependentStrategy):
    """MACD 신호 전략 - 모멘텀 전환점 포착"""
    
    def __init__(self):
        super().__init__(
            strategy_id="macd_signal",
            strategy_name="MACD 신호 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9,
            'histogram_threshold': 0.0001,
            'signal_crossover_strength': 0.0005,
            'zero_line_threshold': 0.0002,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """MACD 신호 분석"""
        try:
            # 15분 캔들 사용 (더 안정적인 MACD 신호)
            candles = market_data.get('candles_15m')
            if not candles or len(candles) < 50:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # MACD 계산
            macd_line, signal_line, histogram = self._calculate_macd(
                df['close'], 
                config['fast_period'], 
                config['slow_period'], 
                config['signal_period']
            )
            
            if len(macd_line) < 5:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "MACD 계산 실패", {}
                )
            
            # 최신 값들
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_histogram = histogram.iloc[-1]
            prev_macd = macd_line.iloc[-2]
            prev_signal = signal_line.iloc[-2]
            prev_histogram = histogram.iloc[-2]
            current_price = df['close'].iloc[-1]
            
            # 거래량 확인
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(10).mean()
            volume_ratio = current_volume / avg_volume
            
            indicators = {
                'macd_line': current_macd,
                'signal_line': current_signal,
                'histogram': current_histogram,
                'volume_ratio': volume_ratio,
                'macd_above_zero': current_macd > 0,
                'signal_above_zero': current_signal > 0
            }
            
            # 신호선 크로스오버 감지
            bullish_signal_cross = (prev_macd <= prev_signal) and (current_macd > current_signal)
            bearish_signal_cross = (prev_macd >= prev_signal) and (current_macd < current_signal)
            
            # 제로라인 크로스오버 감지
            macd_above_zero = current_macd > config['zero_line_threshold']
            macd_below_zero = current_macd < -config['zero_line_threshold']
            
            # 히스토그램 모멘텀
            histogram_increasing = current_histogram > prev_histogram
            histogram_decreasing = current_histogram < prev_histogram
            
            # 크로스오버 강도
            crossover_strength = abs(current_macd - current_signal) / current_price
            
            # 매수 신호 조건들
            if bullish_signal_cross and crossover_strength > config['signal_crossover_strength']:
                confidence = 0.7
                strength = 0.6
                
                # 추가 확인 요소들
                if macd_above_zero:
                    confidence += 0.1
                    reasoning = "MACD 상승 크로스오버 (제로라인 위)"
                else:
                    reasoning = "MACD 상승 크로스오버 (제로라인 아래)"
                
                if histogram_increasing:
                    confidence += 0.05
                    strength += 0.1
                
                if volume_ratio > 1.2:
                    confidence += 0.05
                    strength += 0.1
                
                return self._create_vote(
                    StrategySignal.BUY,
                    min(confidence, 0.9),
                    min(strength, 1.0),
                    reasoning + f" (강도:{crossover_strength:.4f})",
                    indicators
                )
            
            # 매도 신호 조건들
            elif bearish_signal_cross and crossover_strength > config['signal_crossover_strength']:
                confidence = 0.7
                strength = 0.6
                
                # 추가 확인 요소들
                if macd_below_zero:
                    confidence += 0.1
                    reasoning = "MACD 하락 크로스오버 (제로라인 아래)"
                else:
                    reasoning = "MACD 하락 크로스오버 (제로라인 위)"
                
                if histogram_decreasing:
                    confidence += 0.05
                    strength += 0.1
                
                if volume_ratio > 1.2:
                    confidence += 0.05
                    strength += 0.1
                
                return self._create_vote(
                    StrategySignal.SELL,
                    min(confidence, 0.9),
                    min(strength, 1.0),
                    reasoning + f" (강도:{crossover_strength:.4f})",
                    indicators
                )
            
            # 약한 신호들
            elif current_macd > current_signal and macd_above_zero and histogram_increasing:
                # 상승 모멘텀 지속
                momentum_strength = (current_macd - current_signal) / current_price
                confidence = min(0.4, momentum_strength * 1000)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    0.3,
                    f"MACD 상승 모멘텀 지속",
                    indicators
                )
            
            elif current_macd < current_signal and macd_below_zero and histogram_decreasing:
                # 하락 모멘텀 지속
                momentum_strength = (current_signal - current_macd) / current_price
                confidence = min(0.4, momentum_strength * 1000)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    0.3,
                    f"MACD 하락 모멘텀 지속",
                    indicators
                )
            
            # 중립 상황
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"MACD 중립 (MACD:{current_macd:.4f}, Signal:{current_signal:.4f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"MACD 전략 분석 오류: {e}")
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
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 계산"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram


class StochasticStrategy(IndependentStrategy):
    """Stochastic 오실레이터 전략 - 과매수/과매도 정밀 감지"""
    
    def __init__(self):
        super().__init__(
            strategy_id="stochastic_oscillator",
            strategy_name="Stochastic 오실레이터 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'k_period': 14,
            'd_period': 3,
            'smooth_k': 3,
            'overbought': 80,
            'oversold': 20,
            'crossover_threshold': 5,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """Stochastic 분석"""
        try:
            # 5분 캔들 사용
            candles = market_data.get('candles_5m')
            if not candles or len(candles) < 50:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # Stochastic 계산
            k_percent, d_percent = self._calculate_stochastic(
                df, config['k_period'], config['d_period'], config['smooth_k']
            )
            
            if len(k_percent) < 5:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "Stochastic 계산 실패", {}
                )
            
            # 최신 값들
            current_k = k_percent.iloc[-1]
            current_d = d_percent.iloc[-1]
            prev_k = k_percent.iloc[-2]
            prev_d = d_percent.iloc[-2]
            
            indicators = {
                'stoch_k': current_k,
                'stoch_d': current_d,
                'overbought': current_k > config['overbought'],
                'oversold': current_k < config['oversold']
            }
            
            # 크로스오버 감지
            bullish_cross = (prev_k <= prev_d) and (current_k > current_d)
            bearish_cross = (prev_k >= prev_d) and (current_k < current_d)
            
            # 크로스오버 강도
            crossover_strength = abs(current_k - current_d)
            strong_crossover = crossover_strength > config['crossover_threshold']
            
            # 매수 신호: 과매도 구간에서 상승 크로스오버
            if (bullish_cross and current_k < config['oversold'] + 10 and 
                strong_crossover):
                
                confidence = min(0.8, (config['oversold'] + 10 - min(current_k, current_d)) / 20 + 0.4)
                strength = min(1.0, crossover_strength / 20 + 0.3)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"Stochastic 과매도 반등 (K:{current_k:.1f}, D:{current_d:.1f})",
                    indicators
                )
            
            # 매도 신호: 과매수 구간에서 하락 크로스오버
            elif (bearish_cross and current_k > config['overbought'] - 10 and 
                  strong_crossover):
                
                confidence = min(0.8, (max(current_k, current_d) - config['overbought'] + 10) / 20 + 0.4)
                strength = min(1.0, crossover_strength / 20 + 0.3)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"Stochastic 과매수 하락 (K:{current_k:.1f}, D:{current_d:.1f})",
                    indicators
                )
            
            # 약한 신호들
            elif current_k < config['oversold'] and current_k > prev_k:
                # 과매도에서 반등 시작
                return self._create_vote(
                    StrategySignal.BUY,
                    0.3,
                    0.2,
                    f"Stochastic 과매도 반등 시작 (K:{current_k:.1f})",
                    indicators
                )
            
            elif current_k > config['overbought'] and current_k < prev_k:
                # 과매수에서 하락 시작
                return self._create_vote(
                    StrategySignal.SELL,
                    0.3,
                    0.2,
                    f"Stochastic 과매수 하락 시작 (K:{current_k:.1f})",
                    indicators
                )
            
            # 중립
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"Stochastic 중립 (K:{current_k:.1f}, D:{current_d:.1f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"Stochastic 전략 분석 오류: {e}")
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
    
    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, 
                             d_period: int = 3, smooth_k: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Stochastic 계산"""
        # Fast %K 계산
        lowest_low = df['low'].rolling(k_period).min()
        highest_high = df['high'].rolling(k_period).max()
        fast_k = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
        
        # Slow %K 계산 (Fast %K의 이동평균)
        slow_k = fast_k.rolling(smooth_k).mean()
        
        # %D 계산 (Slow %K의 이동평균)
        d_percent = slow_k.rolling(d_period).mean()
        
        return slow_k, d_percent


class WilliamsRStrategy(IndependentStrategy):
    """Williams %R 전략 - 단기 반전 신호"""
    
    def __init__(self):
        super().__init__(
            strategy_id="williams_r",
            strategy_name="Williams %R 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'period': 14,
            'overbought': -20,
            'oversold': -80,
            'signal_threshold': 5,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """Williams %R 분석"""
        try:
            # 5분 캔들 사용
            candles = market_data.get('candles_5m')
            if not candles or len(candles) < 30:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # Williams %R 계산
            williams_r = self._calculate_williams_r(df, config['period'])
            
            if len(williams_r) < 5:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "Williams %R 계산 실패", {}
                )
            
            # 최신 값들
            current_wr = williams_r.iloc[-1]
            prev_wr = williams_r.iloc[-2]
            
            indicators = {
                'williams_r': current_wr,
                'overbought': current_wr > config['overbought'],
                'oversold': current_wr < config['oversold']
            }
            
            # 과매도에서 반등
            if (current_wr < config['oversold'] and 
                current_wr > prev_wr and 
                (current_wr - prev_wr) > config['signal_threshold']):
                
                reversal_strength = (current_wr - prev_wr) / 10
                confidence = min(0.75, (config['oversold'] - current_wr) / 30 + 0.3)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    min(1.0, reversal_strength + 0.3),
                    f"Williams %R 과매도 반등 ({current_wr:.1f})",
                    indicators
                )
            
            # 과매수에서 하락
            elif (current_wr > config['overbought'] and 
                  current_wr < prev_wr and 
                  (prev_wr - current_wr) > config['signal_threshold']):
                
                reversal_strength = (prev_wr - current_wr) / 10
                confidence = min(0.75, (current_wr - config['overbought']) / 30 + 0.3)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    min(1.0, reversal_strength + 0.3),
                    f"Williams %R 과매수 하락 ({current_wr:.1f})",
                    indicators
                )
            
            # 중립
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"Williams %R 중립 ({current_wr:.1f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"Williams %R 전략 분석 오류: {e}")
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
    
    def _calculate_williams_r(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Williams %R 계산"""
        highest_high = df['high'].rolling(period).max()
        lowest_low = df['low'].rolling(period).min()
        williams_r = -100 * (highest_high - df['close']) / (highest_high - lowest_low)
        return williams_r


class CCIStrategy(IndependentStrategy):
    """CCI(Commodity Channel Index) 전략 - 사이클 분석"""
    
    def __init__(self):
        super().__init__(
            strategy_id="cci_oscillator",
            strategy_name="CCI 오실레이터 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'period': 20,
            'overbought': 100,
            'oversold': -100,
            'extreme_overbought': 200,
            'extreme_oversold': -200,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """CCI 분석"""
        try:
            # 15분 캔들 사용
            candles = market_data.get('candles_15m')
            if not candles or len(candles) < 30:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # CCI 계산
            cci = self._calculate_cci(df, config['period'])
            
            if len(cci) < 5:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "CCI 계산 실패", {}
                )
            
            # 최신 값들
            current_cci = cci.iloc[-1]
            prev_cci = cci.iloc[-2]
            
            indicators = {
                'cci': current_cci,
                'overbought': current_cci > config['overbought'],
                'oversold': current_cci < config['oversold'],
                'extreme_overbought': current_cci > config['extreme_overbought'],
                'extreme_oversold': current_cci < config['extreme_oversold']
            }
            
            # 극단적 과매도에서 반등
            if (current_cci < config['extreme_oversold'] and 
                current_cci > prev_cci):
                
                confidence = min(0.9, abs(current_cci) / 300 + 0.4)
                strength = min(1.0, (current_cci - prev_cci) / 20 + 0.5)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"CCI 극단적 과매도 반등 ({current_cci:.1f})",
                    indicators
                )
            
            # 극단적 과매수에서 하락
            elif (current_cci > config['extreme_overbought'] and 
                  current_cci < prev_cci):
                
                confidence = min(0.9, current_cci / 300 + 0.4)
                strength = min(1.0, (prev_cci - current_cci) / 20 + 0.5)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"CCI 극단적 과매수 하락 ({current_cci:.1f})",
                    indicators
                )
            
            # 일반 과매도 반등
            elif (config['oversold'] < current_cci < config['oversold'] + 50 and 
                  current_cci > prev_cci):
                
                confidence = 0.4
                strength = 0.3
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"CCI 과매도 반등 ({current_cci:.1f})",
                    indicators
                )
            
            # 일반 과매수 하락
            elif (config['overbought'] - 50 < current_cci < config['overbought'] and 
                  current_cci < prev_cci):
                
                confidence = 0.4
                strength = 0.3
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"CCI 과매수 하락 ({current_cci:.1f})",
                    indicators
                )
            
            # 중립
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"CCI 중립 ({current_cci:.1f})",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"CCI 전략 분석 오류: {e}")
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
    
    def _calculate_cci(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """CCI 계산"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma = typical_price.rolling(period).mean()
        mean_deviation = typical_price.rolling(period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )
        cci = (typical_price - sma) / (0.015 * mean_deviation)
        return cci


class VolumeSurgeStrategy(IndependentStrategy):
    """Volume 급증 감지 전략 - 거래량 기반 돌파 신호"""
    
    def __init__(self):
        super().__init__(
            strategy_id="volume_surge",
            strategy_name="거래량 급증 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'volume_threshold': 2.0,
            'price_movement_threshold': 0.01,
            'volume_avg_period': 20,
            'surge_duration': 3,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """거래량 급증 분석"""
        try:
            # 5분 캔들 사용
            candles = market_data.get('candles_5m')
            if not candles or len(candles) < 30:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # 거래량 분석
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(config['volume_avg_period']).mean()
            volume_ratio = current_volume / avg_volume
            
            # 가격 변동 분석
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            price_change = (current_price - prev_price) / prev_price
            
            # 최근 N개 봉의 거래량 급증 확인
            recent_volumes = df['volume'].tail(config['surge_duration'])
            recent_avg = recent_volumes.mean()
            sustained_surge = recent_avg > avg_volume * (config['volume_threshold'] * 0.8)
            
            indicators = {
                'volume_ratio': volume_ratio,
                'price_change': price_change,
                'avg_volume': avg_volume,
                'current_volume': current_volume,
                'sustained_surge': sustained_surge
            }
            
            # 거래량 급증 + 상승 돌파
            if (volume_ratio > config['volume_threshold'] and 
                price_change > config['price_movement_threshold']):
                
                confidence = min(0.8, (volume_ratio - 1) * 0.2 + 0.4)
                if sustained_surge:
                    confidence += 0.1
                
                strength = min(1.0, volume_ratio * 0.2 + abs(price_change) * 20)
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"거래량 급증 상승 돌파 (거래량:{volume_ratio:.1f}x, 가격:{price_change:.2%})",
                    indicators
                )
            
            # 거래량 급증 + 하락 돌파
            elif (volume_ratio > config['volume_threshold'] and 
                  price_change < -config['price_movement_threshold']):
                
                confidence = min(0.8, (volume_ratio - 1) * 0.2 + 0.4)
                if sustained_surge:
                    confidence += 0.1
                
                strength = min(1.0, volume_ratio * 0.2 + abs(price_change) * 20)
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"거래량 급증 하락 돌파 (거래량:{volume_ratio:.1f}x, 가격:{price_change:.2%})",
                    indicators
                )
            
            # 중간 신호들
            elif volume_ratio > config['volume_threshold'] * 0.7:
                weak_confidence = min(0.3, (volume_ratio - 1) * 0.1)
                
                if price_change > 0:
                    return self._create_vote(
                        StrategySignal.BUY,
                        weak_confidence,
                        0.2,
                        f"거래량 증가 상승 ({volume_ratio:.1f}x)",
                        indicators
                    )
                elif price_change < 0:
                    return self._create_vote(
                        StrategySignal.SELL,
                        weak_confidence,
                        0.2,
                        f"거래량 증가 하락 ({volume_ratio:.1f}x)",
                        indicators
                    )
            
            # 중립
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                f"거래량 정상 ({volume_ratio:.1f}x)",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"거래량 급증 전략 분석 오류: {e}")
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


class PriceActionStrategy(IndependentStrategy):
    """Price Action 패턴 전략 - 캔들 패턴 종합 분석"""
    
    def __init__(self):
        super().__init__(
            strategy_id="price_action",
            strategy_name="Price Action 패턴 전략"
        )
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            'pattern_threshold': 0.6,
            'body_ratio_threshold': 0.3,
            'shadow_ratio_threshold': 0.6,
            'engulfing_threshold': 1.2,
            'enabled': True
        }
    
    def analyze(self, market_data: Dict[str, Any], config: Dict[str, Any]) -> StrategyVote:
        """Price Action 패턴 분석"""
        try:
            # 15분 캔들 사용 (더 의미있는 패턴)
            candles = market_data.get('candles_15m')
            if not candles or len(candles) < 10:
                return self._create_vote(
                    StrategySignal.HOLD, 0.0, 0.0, "데이터 부족", {}
                )
            
            # DataFrame 변환
            df = self._candles_to_dataframe(candles)
            
            # 최근 3개 캔들 분석
            current_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            prev2_candle = df.iloc[-3] if len(df) > 2 else None
            
            indicators = {}
            
            # 1. 강세 패턴 감지
            bullish_patterns = []
            
            # 해머/도지 패턴
            hammer_strength = self._detect_hammer(current_candle)
            if hammer_strength > config['pattern_threshold']:
                bullish_patterns.append(('hammer', hammer_strength))
                indicators['hammer_strength'] = hammer_strength
            
            # 강세 잠식형
            if prev2_candle is not None:
                engulfing_strength = self._detect_bullish_engulfing(prev_candle, current_candle)
                if engulfing_strength > config['engulfing_threshold']:
                    bullish_patterns.append(('bullish_engulfing', engulfing_strength))
                    indicators['bullish_engulfing'] = engulfing_strength
            
            # 아침별/샛별 패턴
            if prev2_candle is not None:
                morning_star = self._detect_morning_star(prev2_candle, prev_candle, current_candle)
                if morning_star > config['pattern_threshold']:
                    bullish_patterns.append(('morning_star', morning_star))
                    indicators['morning_star'] = morning_star
            
            # 2. 약세 패턴 감지
            bearish_patterns = []
            
            # 유성/도지 패턴
            shooting_star_strength = self._detect_shooting_star(current_candle)
            if shooting_star_strength > config['pattern_threshold']:
                bearish_patterns.append(('shooting_star', shooting_star_strength))
                indicators['shooting_star'] = shooting_star_strength
            
            # 약세 잠식형
            if prev2_candle is not None:
                bearish_engulfing = self._detect_bearish_engulfing(prev_candle, current_candle)
                if bearish_engulfing > config['engulfing_threshold']:
                    bearish_patterns.append(('bearish_engulfing', bearish_engulfing))
                    indicators['bearish_engulfing'] = bearish_engulfing
            
            # 저녁별 패턴
            if prev2_candle is not None:
                evening_star = self._detect_evening_star(prev2_candle, prev_candle, current_candle)
                if evening_star > config['pattern_threshold']:
                    bearish_patterns.append(('evening_star', evening_star))
                    indicators['evening_star'] = evening_star
            
            # 3. 패턴 종합 평가
            if bullish_patterns:
                total_strength = sum(strength for _, strength in bullish_patterns)
                confidence = min(0.8, total_strength * 0.3 + 0.2)
                strength = min(1.0, total_strength * 0.4)
                
                pattern_names = [name for name, _ in bullish_patterns]
                
                return self._create_vote(
                    StrategySignal.BUY,
                    confidence,
                    strength,
                    f"강세 Price Action 패턴: {', '.join(pattern_names)}",
                    indicators
                )
            
            elif bearish_patterns:
                total_strength = sum(strength for _, strength in bearish_patterns)
                confidence = min(0.8, total_strength * 0.3 + 0.2)
                strength = min(1.0, total_strength * 0.4)
                
                pattern_names = [name for name, _ in bearish_patterns]
                
                return self._create_vote(
                    StrategySignal.SELL,
                    confidence,
                    strength,
                    f"약세 Price Action 패턴: {', '.join(pattern_names)}",
                    indicators
                )
            
            # 중립
            return self._create_vote(
                StrategySignal.HOLD,
                0.1,
                0.1,
                "뚜렷한 Price Action 패턴 없음",
                indicators
            )
            
        except Exception as e:
            self.logger.error(f"Price Action 전략 분석 오류: {e}")
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
    
    def _detect_hammer(self, candle: pd.Series) -> float:
        """해머 패턴 감지"""
        try:
            body_size = abs(candle['close'] - candle['open'])
            total_range = candle['high'] - candle['low']
            lower_shadow = min(candle['open'], candle['close']) - candle['low']
            upper_shadow = candle['high'] - max(candle['open'], candle['close'])
            
            if total_range == 0:
                return 0.0
            
            body_ratio = body_size / total_range
            lower_shadow_ratio = lower_shadow / total_range
            upper_shadow_ratio = upper_shadow / total_range
            
            # 해머 조건: 작은 몸통 + 긴 아래꼬리 + 짧은 위꼬리
            if (body_ratio < 0.3 and 
                lower_shadow_ratio > 0.6 and 
                upper_shadow_ratio < 0.1):
                return lower_shadow_ratio + (0.3 - body_ratio)
            
            return 0.0
        except:
            return 0.0
    
    def _detect_shooting_star(self, candle: pd.Series) -> float:
        """유성 패턴 감지"""
        try:
            body_size = abs(candle['close'] - candle['open'])
            total_range = candle['high'] - candle['low']
            lower_shadow = min(candle['open'], candle['close']) - candle['low']
            upper_shadow = candle['high'] - max(candle['open'], candle['close'])
            
            if total_range == 0:
                return 0.0
            
            body_ratio = body_size / total_range
            lower_shadow_ratio = lower_shadow / total_range
            upper_shadow_ratio = upper_shadow / total_range
            
            # 유성 조건: 작은 몸통 + 긴 위꼬리 + 짧은 아래꼬리
            if (body_ratio < 0.3 and 
                upper_shadow_ratio > 0.6 and 
                lower_shadow_ratio < 0.1):
                return upper_shadow_ratio + (0.3 - body_ratio)
            
            return 0.0
        except:
            return 0.0
    
    def _detect_bullish_engulfing(self, prev_candle: pd.Series, current_candle: pd.Series) -> float:
        """강세 잠식형 패턴 감지"""
        try:
            # 이전 캔들: 음봉, 현재 캔들: 양봉
            prev_bearish = prev_candle['close'] < prev_candle['open']
            current_bullish = current_candle['close'] > current_candle['open']
            
            if not (prev_bearish and current_bullish):
                return 0.0
            
            # 현재 캔들이 이전 캔들을 완전히 잠식
            engulfs = (current_candle['open'] < prev_candle['close'] and 
                      current_candle['close'] > prev_candle['open'])
            
            if engulfs:
                # 잠식 강도 계산
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                current_body = abs(current_candle['close'] - current_candle['open'])
                engulf_ratio = current_body / prev_body if prev_body > 0 else 0
                return min(2.0, engulf_ratio)
            
            return 0.0
        except:
            return 0.0
    
    def _detect_bearish_engulfing(self, prev_candle: pd.Series, current_candle: pd.Series) -> float:
        """약세 잠식형 패턴 감지"""
        try:
            # 이전 캔들: 양봉, 현재 캔들: 음봉
            prev_bullish = prev_candle['close'] > prev_candle['open']
            current_bearish = current_candle['close'] < current_candle['open']
            
            if not (prev_bullish and current_bearish):
                return 0.0
            
            # 현재 캔들이 이전 캔들을 완전히 잠식
            engulfs = (current_candle['open'] > prev_candle['close'] and 
                      current_candle['close'] < prev_candle['open'])
            
            if engulfs:
                # 잠식 강도 계산
                prev_body = abs(prev_candle['close'] - prev_candle['open'])
                current_body = abs(current_candle['close'] - current_candle['open'])
                engulf_ratio = current_body / prev_body if prev_body > 0 else 0
                return min(2.0, engulf_ratio)
            
            return 0.0
        except:
            return 0.0
    
    def _detect_morning_star(self, first: pd.Series, second: pd.Series, third: pd.Series) -> float:
        """아침별 패턴 감지"""
        try:
            # 첫 번째: 긴 음봉
            first_bearish = first['close'] < first['open']
            first_body = abs(first['close'] - first['open'])
            
            # 두 번째: 작은 몸통 (도지/스피닝탑)
            second_small = abs(second['close'] - second['open']) < first_body * 0.3
            
            # 세 번째: 긴 양봉
            third_bullish = third['close'] > third['open']
            third_body = abs(third['close'] - third['open'])
            
            if first_bearish and second_small and third_bullish:
                # 갭 확인
                gap_down = second['high'] < first['close']
                gap_up = third['open'] > second['high']
                
                if gap_down and gap_up:
                    return min(1.5, (first_body + third_body) / (first['high'] - first['low']) * 2)
            
            return 0.0
        except:
            return 0.0
    
    def _detect_evening_star(self, first: pd.Series, second: pd.Series, third: pd.Series) -> float:
        """저녁별 패턴 감지"""
        try:
            # 첫 번째: 긴 양봉
            first_bullish = first['close'] > first['open']
            first_body = abs(first['close'] - first['open'])
            
            # 두 번째: 작은 몸통 (도지/스피닝탑)
            second_small = abs(second['close'] - second['open']) < first_body * 0.3
            
            # 세 번째: 긴 음봉
            third_bearish = third['close'] < third['open']
            third_body = abs(third['close'] - third['open'])
            
            if first_bullish and second_small and third_bearish:
                # 갭 확인
                gap_up = second['low'] > first['close']
                gap_down = third['open'] < second['low']
                
                if gap_up and gap_down:
                    return min(1.5, (first_body + third_body) / (first['high'] - first['low']) * 2)
            
            return 0.0
        except:
            return 0.0
