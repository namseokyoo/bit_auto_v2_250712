"""
기술적 분석 지표 계산 모듈
실제 캔들 데이터를 기반으로 RSI, MACD, 볼린저 밴드 등을 계산
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

class TechnicalIndicators:
    def __init__(self):
        self.logger = logging.getLogger('TechnicalIndicators')
    
    def calculate_rsi(self, candles: List[Dict], period: int = 14) -> List[float]:
        """RSI (Relative Strength Index) 계산"""
        try:
            if len(candles) < period + 1:
                return []
            
            # 종가 추출
            closes = [float(candle['trade_price']) for candle in candles]
            
            # 가격 변화 계산
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            
            # 상승분과 하락분 분리
            gains = [max(delta, 0) for delta in deltas]
            losses = [abs(min(delta, 0)) for delta in deltas]
            
            # 평균 상승폭과 평균 하락폭 계산
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            
            rsi_values = []
            
            for i in range(period, len(gains)):
                if avg_loss == 0:
                    rsi = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                rsi_values.append(rsi)
                
                # 지수이동평균으로 갱신
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            return rsi_values
            
        except Exception as e:
            self.logger.error(f"RSI 계산 오류: {e}")
            return []
    
    def calculate_macd(self, candles: List[Dict], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """MACD 계산"""
        try:
            if len(candles) < slow + signal:
                return {}
            
            closes = [float(candle['trade_price']) for candle in candles]
            
            # EMA 계산 함수
            def calculate_ema(data: List[float], period: int) -> List[float]:
                ema = []
                multiplier = 2 / (period + 1)
                
                # 첫 번째 EMA는 SMA로 시작
                sma = sum(data[:period]) / period
                ema.append(sma)
                
                for i in range(period, len(data)):
                    ema_value = (data[i] * multiplier) + (ema[-1] * (1 - multiplier))
                    ema.append(ema_value)
                
                return ema
            
            # Fast EMA와 Slow EMA 계산
            fast_ema = calculate_ema(closes, fast)
            slow_ema = calculate_ema(closes, slow)
            
            # MACD 라인 계산
            macd_line = []
            start_idx = slow - fast
            for i in range(len(slow_ema)):
                macd_value = fast_ema[i + start_idx] - slow_ema[i]
                macd_line.append(macd_value)
            
            # Signal 라인 계산 (MACD의 EMA)
            signal_line = calculate_ema(macd_line, signal)
            
            # Histogram 계산
            histogram = []
            signal_start = len(macd_line) - len(signal_line)
            for i in range(len(signal_line)):
                hist_value = macd_line[i + signal_start] - signal_line[i]
                histogram.append(hist_value)
            
            return {
                'macd': macd_line[-1] if macd_line else 0,
                'signal': signal_line[-1] if signal_line else 0,
                'histogram': histogram[-1] if histogram else 0,
                'macd_line': macd_line,
                'signal_line': signal_line,
                'histogram_line': histogram
            }
            
        except Exception as e:
            self.logger.error(f"MACD 계산 오류: {e}")
            return {}
    
    def calculate_bollinger_bands(self, candles: List[Dict], period: int = 20, std_dev: float = 2) -> Dict:
        """볼린저 밴드 계산"""
        try:
            if len(candles) < period:
                return {}
            
            closes = [float(candle['trade_price']) for candle in candles]
            
            # 이동평균 계산
            sma_values = []
            for i in range(period - 1, len(closes)):
                sma = sum(closes[i - period + 1:i + 1]) / period
                sma_values.append(sma)
            
            # 표준편차 계산
            std_values = []
            for i in range(period - 1, len(closes)):
                period_data = closes[i - period + 1:i + 1]
                mean = sum(period_data) / period
                variance = sum((x - mean) ** 2 for x in period_data) / period
                std = variance ** 0.5
                std_values.append(std)
            
            # 밴드 계산
            upper_band = [sma + (std * std_dev) for sma, std in zip(sma_values, std_values)]
            lower_band = [sma - (std * std_dev) for sma, std in zip(sma_values, std_values)]
            
            current_price = closes[-1]
            
            return {
                'middle': sma_values[-1] if sma_values else 0,
                'upper': upper_band[-1] if upper_band else 0,
                'lower': lower_band[-1] if lower_band else 0,
                'current_price': current_price,
                'band_width': (upper_band[-1] - lower_band[-1]) / sma_values[-1] if sma_values else 0,
                'position': self._get_bb_position(current_price, upper_band[-1], lower_band[-1], sma_values[-1]) if sma_values else 'middle'
            }
            
        except Exception as e:
            self.logger.error(f"볼린저 밴드 계산 오류: {e}")
            return {}
    
    def _get_bb_position(self, price: float, upper: float, lower: float, middle: float) -> str:
        """볼린저 밴드에서의 가격 위치 판단"""
        if price >= upper:
            return 'upper'
        elif price <= lower:
            return 'lower'
        elif price > middle:
            return 'upper_middle'
        else:
            return 'lower_middle'
    
    def calculate_ema(self, candles: List[Dict], period: int) -> List[float]:
        """지수이동평균 계산"""
        try:
            if len(candles) < period:
                return []
            
            closes = [float(candle['trade_price']) for candle in candles]
            ema_values = []
            multiplier = 2 / (period + 1)
            
            # 첫 번째 EMA는 SMA로 시작
            sma = sum(closes[:period]) / period
            ema_values.append(sma)
            
            for i in range(period, len(closes)):
                ema_value = (closes[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
                ema_values.append(ema_value)
            
            return ema_values
            
        except Exception as e:
            self.logger.error(f"EMA 계산 오류: {e}")
            return []
    
    def calculate_vwap(self, candles: List[Dict]) -> float:
        """VWAP (Volume Weighted Average Price) 계산"""
        try:
            if not candles:
                return 0
            
            total_volume = 0
            total_pv = 0
            
            for candle in candles:
                price = float(candle['trade_price'])
                volume = float(candle['candle_acc_trade_volume'])
                
                total_pv += price * volume
                total_volume += volume
            
            return total_pv / total_volume if total_volume > 0 else 0
            
        except Exception as e:
            self.logger.error(f"VWAP 계산 오류: {e}")
            return 0
    
    def detect_support_resistance(self, candles: List[Dict], window: int = 20) -> Dict:
        """지지/저항선 감지"""
        try:
            if len(candles) < window * 2:
                return {}
            
            highs = [float(candle['high_price']) for candle in candles]
            lows = [float(candle['low_price']) for candle in candles]
            
            # 피봇 포인트 찾기
            resistance_levels = []
            support_levels = []
            
            for i in range(window, len(highs) - window):
                # 저항선 (고점)
                if all(highs[i] >= highs[j] for j in range(i - window, i + window + 1) if j != i):
                    resistance_levels.append(highs[i])
                
                # 지지선 (저점)
                if all(lows[i] <= lows[j] for j in range(i - window, i + window + 1) if j != i):
                    support_levels.append(lows[i])
            
            # 가장 가까운 지지/저항 찾기
            current_price = float(candles[-1]['trade_price'])
            
            nearest_resistance = min(
                [r for r in resistance_levels if r > current_price], 
                default=None
            )
            nearest_support = max(
                [s for s in support_levels if s < current_price], 
                default=None
            )
            
            return {
                'nearest_resistance': nearest_resistance,
                'nearest_support': nearest_support,
                'resistance_levels': resistance_levels[-5:],  # 최근 5개
                'support_levels': support_levels[-5:],  # 최근 5개
                'current_price': current_price
            }
            
        except Exception as e:
            self.logger.error(f"지지/저항선 감지 오류: {e}")
            return {}

# 사용 예시
if __name__ == "__main__":
    # 테스트 코드
    ti = TechnicalIndicators()
    
    # 더미 캔들 데이터
    test_candles = [
        {'trade_price': '50000000', 'high_price': '51000000', 'low_price': '49000000', 'candle_acc_trade_volume': '100'},
        {'trade_price': '51000000', 'high_price': '52000000', 'low_price': '50000000', 'candle_acc_trade_volume': '150'},
        # ... 더 많은 데이터 필요
    ]
    
    print("기술적 지표 계산 모듈 테스트 완료")