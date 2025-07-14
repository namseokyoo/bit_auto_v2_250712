"""
실제 기술적 분석 기반 전략 신호 생성 모듈
랜덤 요소를 제거하고 실제 시장 데이터와 기술적 지표를 사용
"""

from datetime import datetime
from typing import Dict, Optional, List
import logging
from dataclasses import dataclass

from core.upbit_api import UpbitAPI
from core.technical_indicators import TechnicalIndicators
from core.signal_manager import TradingSignal

@dataclass
class StrategyConfig:
    """전략 설정"""
    min_confidence: float = 0.5
    max_confidence: float = 0.9
    base_amount: float = 50000

class RealStrategySignals:
    def __init__(self, api: UpbitAPI):
        self.api = api
        self.indicators = TechnicalIndicators()
        self.config = StrategyConfig()
        self.logger = logging.getLogger('RealStrategySignals')
        
        # 캐시된 데이터 (성능 최적화)
        self._candle_cache = {}
        self._cache_time = {}
        self.cache_duration = 60  # 1분 캐시
    
    def _get_candles_cached(self, timeframe: str, interval: int, count: int = 100) -> Optional[List[Dict]]:
        """캐시된 캔들 데이터 조회"""
        cache_key = f"{timeframe}_{interval}_{count}"
        current_time = datetime.now().timestamp()
        
        # 캐시 확인
        if (cache_key in self._candle_cache and 
            cache_key in self._cache_time and 
            current_time - self._cache_time[cache_key] < self.cache_duration):
            return self._candle_cache[cache_key]
        
        # 새로 데이터 조회
        candles = self.api.get_candles("KRW-BTC", timeframe, interval, count)
        if candles:
            self._candle_cache[cache_key] = candles
            self._cache_time[cache_key] = current_time
        
        return candles
    
    def generate_ema_cross_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """EMA 골든/데드크로스 전략"""
        try:
            # 1시간 캔들 데이터 조회
            candles = self._get_candles_cached("minutes", 60, 150)
            if not candles or len(candles) < 50:
                return self._create_hold_signal("ema_cross", "데이터 부족")
            
            # EMA 12, 26 계산
            ema12 = self.indicators.calculate_ema(candles, 12)
            ema26 = self.indicators.calculate_ema(candles, 26)
            
            if len(ema12) < 2 or len(ema26) < 2:
                return self._create_hold_signal("ema_cross", "EMA 계산 불가")
            
            # 현재와 이전 EMA 값
            current_ema12 = ema12[-1]
            current_ema26 = ema26[-1]
            prev_ema12 = ema12[-2]
            prev_ema26 = ema26[-2]
            
            current_price = float(candles[-1]['trade_price'])
            
            # 골든크로스/데드크로스 감지
            current_cross = current_ema12 - current_ema26
            prev_cross = prev_ema12 - prev_ema26
            
            # 4시간 EMA 50으로 필터링
            h4_candles = self._get_candles_cached("minutes", 240, 60)
            if h4_candles:
                ema50_h4 = self.indicators.calculate_ema(h4_candles, 50)
                if ema50_h4:
                    h4_filter = current_price > ema50_h4[-1]
                else:
                    h4_filter = True
            else:
                h4_filter = True
            
            # 거래량 확인
            recent_volumes = [float(c['candle_acc_trade_volume']) for c in candles[-10:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            current_volume = float(candles[-1]['candle_acc_trade_volume'])
            volume_surge = current_volume > avg_volume * 1.5
            
            # 신호 생성
            if prev_cross <= 0 and current_cross > 0 and h4_filter and volume_surge:
                # 골든크로스
                confidence = min(0.85, 0.6 + (current_cross / current_ema26 * 10))
                return TradingSignal(
                    strategy_id="ema_cross",
                    action="buy",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=self.config.base_amount,
                    reasoning=f"EMA 골든크로스 감지 (EMA12: {current_ema12:,.0f}, EMA26: {current_ema26:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            elif prev_cross >= 0 and current_cross < 0 and not h4_filter:
                # 데드크로스
                confidence = min(0.75, 0.6 + abs(current_cross / current_ema26 * 10))
                return TradingSignal(
                    strategy_id="ema_cross",
                    action="sell",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"EMA 데드크로스 감지 (EMA12: {current_ema12:,.0f}, EMA26: {current_ema26:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            else:
                return self._create_hold_signal("ema_cross", f"명확한 크로스 신호 없음 (차이: {current_cross:+.0f})")
                
        except Exception as e:
            self.logger.error(f"EMA 크로스 신호 생성 오류: {e}")
            return self._create_hold_signal("ema_cross", f"계산 오류: {str(e)}")
    
    def generate_rsi_divergence_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """RSI 다이버전스 전략"""
        try:
            # 1시간 캔들 데이터
            candles = self._get_candles_cached("minutes", 60, 100)
            if not candles or len(candles) < 50:
                return self._create_hold_signal("rsi_divergence", "데이터 부족")
            
            # RSI 계산
            rsi_values = self.indicators.calculate_rsi(candles, 14)
            if len(rsi_values) < 20:
                return self._create_hold_signal("rsi_divergence", "RSI 계산 불가")
            
            current_rsi = rsi_values[-1]
            current_price = float(candles[-1]['trade_price'])
            
            # 지지/저항선 분석
            sr_data = self.indicators.detect_support_resistance(candles)
            
            # RSI 과매도/과매수 조건
            oversold_threshold = 30
            overbought_threshold = 70
            
            if current_rsi < oversold_threshold and sr_data.get('nearest_support'):
                # 과매도 + 지지선 근처
                support_distance = abs(current_price - sr_data['nearest_support']) / current_price
                if support_distance < 0.02:  # 2% 이내
                    confidence = min(0.8, 0.5 + (oversold_threshold - current_rsi) / 100)
                    return TradingSignal(
                        strategy_id="rsi_divergence",
                        action="buy",
                        confidence=confidence,
                        price=current_price,
                        suggested_amount=self.config.base_amount,
                        reasoning=f"RSI 과매도 + 지지선 근처 (RSI: {current_rsi:.1f}, 지지선: {sr_data['nearest_support']:,.0f})",
                        timestamp=datetime.now(),
                        timeframe="1h"
                    )
            
            elif current_rsi > overbought_threshold and sr_data.get('nearest_resistance'):
                # 과매수 + 저항선 근처
                resistance_distance = abs(sr_data['nearest_resistance'] - current_price) / current_price
                if resistance_distance < 0.02:  # 2% 이내
                    confidence = min(0.8, 0.5 + (current_rsi - overbought_threshold) / 100)
                    return TradingSignal(
                        strategy_id="rsi_divergence", 
                        action="sell",
                        confidence=confidence,
                        price=current_price,
                        suggested_amount=0,
                        reasoning=f"RSI 과매수 + 저항선 근처 (RSI: {current_rsi:.1f}, 저항선: {sr_data['nearest_resistance']:,.0f})",
                        timestamp=datetime.now(),
                        timeframe="1h"
                    )
            
            return self._create_hold_signal("rsi_divergence", f"중립 구간 (RSI: {current_rsi:.1f})")
            
        except Exception as e:
            self.logger.error(f"RSI 다이버전스 신호 생성 오류: {e}")
            return self._create_hold_signal("rsi_divergence", f"계산 오류: {str(e)}")
    
    def generate_vwap_pullback_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """VWAP 되돌림 전략"""
        try:
            # 15분 캔들 데이터
            candles = self._get_candles_cached("minutes", 15, 96)  # 24시간 분량
            if not candles or len(candles) < 50:
                return self._create_hold_signal("vwap_pullback", "데이터 부족")
            
            # VWAP 계산
            vwap = self.indicators.calculate_vwap(candles)
            current_price = float(candles[-1]['trade_price'])
            
            # 1시간 EMA 20으로 트렌드 확인
            h1_candles = self._get_candles_cached("minutes", 60, 50)
            if h1_candles:
                ema20 = self.indicators.calculate_ema(h1_candles, 20)
                if ema20 and len(ema20) >= 2:
                    trend_up = ema20[-1] > ema20[-2]
                else:
                    trend_up = True
            else:
                trend_up = True
            
            # VWAP 대비 가격 위치
            vwap_distance = (current_price - vwap) / vwap
            
            # 15분 RSI
            rsi_15m = self.indicators.calculate_rsi(candles, 14)
            current_rsi_15m = rsi_15m[-1] if rsi_15m else 50
            
            if trend_up and vwap_distance < -0.002 and current_rsi_15m >= 50:
                # 상승 트렌드 + VWAP 하단 + RSI 중립 이상
                confidence = min(0.75, 0.5 + abs(vwap_distance) * 100)
                return TradingSignal(
                    strategy_id="vwap_pullback",
                    action="buy", 
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=self.config.base_amount,
                    reasoning=f"VWAP 하단 지지 반등 (현재: {current_price:,.0f}, VWAP: {vwap:,.0f}, 차이: {vwap_distance:.2%})",
                    timestamp=datetime.now(),
                    timeframe="15m"
                )
            
            elif not trend_up and vwap_distance > 0.002 and current_rsi_15m <= 50:
                # 하락 트렌드 + VWAP 상단 + RSI 중립 이하
                confidence = min(0.75, 0.5 + vwap_distance * 100)
                return TradingSignal(
                    strategy_id="vwap_pullback",
                    action="sell",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"VWAP 상단 저항 (현재: {current_price:,.0f}, VWAP: {vwap:,.0f}, 차이: {vwap_distance:.2%})",
                    timestamp=datetime.now(),
                    timeframe="15m"
                )
            
            return self._create_hold_signal("vwap_pullback", f"VWAP 중심선 근처 (차이: {vwap_distance:.2%})")
            
        except Exception as e:
            self.logger.error(f"VWAP 되돌림 신호 생성 오류: {e}")
            return self._create_hold_signal("vwap_pullback", f"계산 오류: {str(e)}")
    
    def generate_macd_zero_cross_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """MACD 제로크로스 전략"""
        try:
            # 1시간 캔들 데이터
            candles = self._get_candles_cached("minutes", 60, 100)
            if not candles or len(candles) < 60:
                return self._create_hold_signal("macd_zero_cross", "데이터 부족")
            
            # MACD 계산
            macd_data = self.indicators.calculate_macd(candles, 12, 26, 9)
            if not macd_data:
                return self._create_hold_signal("macd_zero_cross", "MACD 계산 불가")
            
            current_macd = macd_data['macd']
            current_histogram = macd_data['histogram']
            current_price = float(candles[-1]['trade_price'])
            
            # 1시간 EMA 50으로 필터링
            ema50 = self.indicators.calculate_ema(candles, 50)
            if ema50:
                price_above_ema50 = current_price > ema50[-1]
            else:
                price_above_ema50 = True
            
            # MACD 히스토그램이 0선 위에 있고 상승 중
            if current_histogram > 0 and price_above_ema50:
                # 히스토그램 기울기 확인
                if len(macd_data.get('histogram_line', [])) >= 2:
                    histogram_slope = macd_data['histogram_line'][-1] - macd_data['histogram_line'][-2]
                    if histogram_slope > 0:
                        confidence = min(0.8, 0.6 + current_histogram / current_price * 1000000)
                        return TradingSignal(
                            strategy_id="macd_zero_cross",
                            action="buy",
                            confidence=confidence,
                            price=current_price,
                            suggested_amount=self.config.base_amount,
                            reasoning=f"MACD 히스토그램 상승 (히스토그램: {current_histogram:.0f}, MACD: {current_macd:.0f})",
                            timestamp=datetime.now(),
                            timeframe="1h"
                        )
            
            elif current_histogram < 0 and not price_above_ema50:
                # 히스토그램이 0선 아래에 있고 하락 중
                if len(macd_data.get('histogram_line', [])) >= 2:
                    histogram_slope = macd_data['histogram_line'][-1] - macd_data['histogram_line'][-2]
                    if histogram_slope < 0:
                        confidence = min(0.8, 0.6 + abs(current_histogram) / current_price * 1000000)
                        return TradingSignal(
                            strategy_id="macd_zero_cross",
                            action="sell",
                            confidence=confidence,
                            price=current_price,
                            suggested_amount=0,
                            reasoning=f"MACD 히스토그램 하락 (히스토그램: {current_histogram:.0f}, MACD: {current_macd:.0f})",
                            timestamp=datetime.now(),
                            timeframe="1h"
                        )
            
            return self._create_hold_signal("macd_zero_cross", f"MACD 신호 약함 (히스토그램: {current_histogram:.0f})")
            
        except Exception as e:
            self.logger.error(f"MACD 제로크로스 신호 생성 오류: {e}")
            return self._create_hold_signal("macd_zero_cross", f"계산 오류: {str(e)}")
    
    def generate_bollinger_band_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """볼린저 밴드 전략"""
        try:
            # 1시간 캔들 데이터
            candles = self._get_candles_cached("minutes", 60, 80)
            if not candles or len(candles) < 50:
                return self._create_hold_signal("bollinger_band_strategy", "데이터 부족")
            
            # 볼린저 밴드 계산
            bb_data = self.indicators.calculate_bollinger_bands(candles, 20, 2)
            if not bb_data:
                return self._create_hold_signal("bollinger_band_strategy", "볼린저 밴드 계산 불가")
            
            current_price = bb_data['current_price']
            upper_band = bb_data['upper']
            lower_band = bb_data['lower']
            middle_band = bb_data['middle']
            position = bb_data['position']
            
            # ADX로 트렌드 강도 확인 (간단한 버전)
            price_changes = [abs(float(candles[i]['trade_price']) - float(candles[i-1]['trade_price'])) 
                           for i in range(1, min(15, len(candles)))]
            avg_change = sum(price_changes) / len(price_changes)
            trending = avg_change > current_price * 0.01  # 1% 이상 변동성
            
            # RSI로 추가 확인
            rsi_values = self.indicators.calculate_rsi(candles, 14)
            current_rsi = rsi_values[-1] if rsi_values else 50
            
            if position == 'lower' and not trending and current_rsi < 40:
                # 레인징 시장에서 하단 밴드 터치 + RSI 낮음
                confidence = min(0.8, 0.6 + (lower_band - current_price) / current_price * 100)
                return TradingSignal(
                    strategy_id="bollinger_band_strategy",
                    action="buy",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=self.config.base_amount,
                    reasoning=f"볼린저 밴드 하단 반등 (현재: {current_price:,.0f}, 하단: {lower_band:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            elif position == 'upper' and not trending and current_rsi > 60:
                # 레인징 시장에서 상단 밴드 터치 + RSI 높음
                confidence = min(0.8, 0.6 + (current_price - upper_band) / current_price * 100)
                return TradingSignal(
                    strategy_id="bollinger_band_strategy",
                    action="sell",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"볼린저 밴드 상단 저항 (현재: {current_price:,.0f}, 상단: {upper_band:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            elif trending and position == 'upper':
                # 트렌딩 시장에서 상단 밴드 라이딩
                confidence = 0.65
                return TradingSignal(
                    strategy_id="bollinger_band_strategy",
                    action="hold",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"트렌딩 시장 - 상단 밴드 라이딩 중 (현재: {position})",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._create_hold_signal("bollinger_band_strategy", f"중간대 위치 (위치: {position})")
            
        except Exception as e:
            self.logger.error(f"볼린저 밴드 신호 생성 오류: {e}")
            return self._create_hold_signal("bollinger_band_strategy", f"계산 오류: {str(e)}")
    
    def generate_pivot_points_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """피봇 포인트 지지/저항 반등 전략"""
        try:
            # 일봉 데이터로 피봇 포인트 계산
            daily_candles = self._get_candles_cached("days", 1, 30)
            if not daily_candles or len(daily_candles) < 5:
                return self._create_hold_signal("pivot_points", "일봉 데이터 부족")
            
            # 어제 데이터로 오늘의 피봇 포인트 계산
            yesterday = daily_candles[-2]  # 어제 데이터
            high = float(yesterday['high_price'])
            low = float(yesterday['low_price'])
            close = float(yesterday['trade_price'])
            
            # 표준 피봇 포인트 계산
            pivot = (high + low + close) / 3
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)
            
            # 현재가
            current_price = float(daily_candles[-1]['trade_price'])
            
            # 15분봉으로 캔들스틱 패턴 확인
            candles_15m = self._get_candles_cached("minutes", 15, 20)
            if candles_15m and len(candles_15m) >= 4:
                # 단순한 반전 패턴 감지 (연속 하락 후 상승 시작)
                recent_closes = [float(c['trade_price']) for c in candles_15m[-4:]]
                bullish_pattern = (recent_closes[0] > recent_closes[1] > recent_closes[2] and 
                                 recent_closes[3] > recent_closes[2])
                bearish_pattern = (recent_closes[0] < recent_closes[1] < recent_closes[2] and 
                                 recent_closes[3] < recent_closes[2])
            else:
                bullish_pattern = False
                bearish_pattern = False
            
            # 지지선 근처에서 매수 신호
            s1_distance = abs(current_price - s1) / current_price
            s2_distance = abs(current_price - s2) / current_price
            
            if (s1_distance < 0.005 or s2_distance < 0.005) and current_price < pivot and bullish_pattern:
                # S1 또는 S2 근처에서 강세 패턴
                confidence = min(0.8, 0.6 + (1 - min(s1_distance, s2_distance)) * 20)
                return TradingSignal(
                    strategy_id="pivot_points",
                    action="buy",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=self.config.base_amount,
                    reasoning=f"피봇 지지선 반등 (현재: {current_price:,.0f}, S1: {s1:,.0f}, S2: {s2:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="15m"
                )
            
            # 저항선 근처에서 매도 신호
            r1_distance = abs(r1 - current_price) / current_price
            r2_distance = abs(r2 - current_price) / current_price
            
            if (r1_distance < 0.005 or r2_distance < 0.005) and current_price > pivot and bearish_pattern:
                # R1 또는 R2 근처에서 약세 패턴
                confidence = min(0.8, 0.6 + (1 - min(r1_distance, r2_distance)) * 20)
                return TradingSignal(
                    strategy_id="pivot_points",
                    action="sell",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"피봇 저항선 반발 (현재: {current_price:,.0f}, R1: {r1:,.0f}, R2: {r2:,.0f})",
                    timestamp=datetime.now(),
                    timeframe="15m"
                )
            
            return self._create_hold_signal("pivot_points", f"피봇 중립구간 (PP: {pivot:,.0f})")
            
        except Exception as e:
            self.logger.error(f"피봇 포인트 신호 생성 오류: {e}")
            return self._create_hold_signal("pivot_points", f"계산 오류: {str(e)}")
    
    def generate_open_interest_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """미체결 약정 증감 전략 (업비트는 현물이므로 거래량 기반으로 대체)"""
        try:
            # 1시간 캔들로 거래량 분석
            candles = self._get_candles_cached("minutes", 60, 50)
            if not candles or len(candles) < 20:
                return self._create_hold_signal("open_interest", "거래량 데이터 부족")
            
            # 거래량 및 가격 데이터 추출
            volumes = [float(c['candle_acc_trade_volume']) for c in candles]
            prices = [float(c['trade_price']) for c in candles]
            
            current_price = prices[-1]
            current_volume = volumes[-1]
            
            # 평균 거래량 계산
            avg_volume_10 = sum(volumes[-10:]) / 10
            avg_volume_20 = sum(volumes[-20:]) / 20
            
            # 가격 변화율
            price_change_1h = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
            price_change_4h = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
            
            # 거래량 급증 여부
            volume_surge = current_volume > avg_volume_20 * 1.5
            
            # 가격 상승 + 거래량 증가 = 매수 신호
            if price_change_1h > 0.01 and price_change_4h > 0.02 and volume_surge:
                # 상승 + 거래량 증가
                confidence = min(0.8, 0.6 + price_change_4h * 10)
                return TradingSignal(
                    strategy_id="open_interest",
                    action="buy",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=self.config.base_amount,
                    reasoning=f"가격상승+거래량급증 (4h: {price_change_4h:.2%}, 거래량: {current_volume/avg_volume_20:.1f}배)",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            # 가격 하락 + 거래량 증가 = 매도 신호 
            elif price_change_1h < -0.01 and price_change_4h < -0.02 and volume_surge:
                # 하락 + 거래량 증가
                confidence = min(0.8, 0.6 + abs(price_change_4h) * 10)
                return TradingSignal(
                    strategy_id="open_interest",
                    action="sell",
                    confidence=confidence,
                    price=current_price,
                    suggested_amount=0,
                    reasoning=f"가격하락+거래량급증 (4h: {price_change_4h:.2%}, 거래량: {current_volume/avg_volume_20:.1f}배)",
                    timestamp=datetime.now(),
                    timeframe="1h"
                )
            
            return self._create_hold_signal("open_interest", f"거래량 변화 없음 (비율: {current_volume/avg_volume_20:.1f}배)")
            
        except Exception as e:
            self.logger.error(f"거래량 분석 신호 생성 오류: {e}")
            return self._create_hold_signal("open_interest", f"계산 오류: {str(e)}")
    
    def generate_flag_pennant_signal(self, strategy: Dict) -> Optional[TradingSignal]:
        """깃발/페넌트 패턴 돌파 전략"""
        try:
            # 1시간 캔들로 패턴 분석
            candles = self._get_candles_cached("minutes", 60, 100)
            if not candles or len(candles) < 50:
                return self._create_hold_signal("flag_pennant", "패턴 분석 데이터 부족")
            
            # 가격 및 거래량 데이터
            highs = [float(c['high_price']) for c in candles]
            lows = [float(c['low_price']) for c in candles]
            closes = [float(c['trade_price']) for c in candles]
            volumes = [float(c['candle_acc_trade_volume']) for c in candles]
            
            current_price = closes[-1]
            current_volume = volumes[-1]
            
            # 최근 20개 봉에서 flagpole 찾기 (급격한 가격 변동)
            flagpole_strength = 0
            flagpole_direction = None
            
            for i in range(-20, -5):
                if i + 10 < len(closes):
                    price_move = (closes[i + 5] - closes[i]) / closes[i]
                    if abs(price_move) > 0.05:  # 5% 이상 움직임
                        flagpole_strength = abs(price_move)
                        flagpole_direction = "up" if price_move > 0 else "down"
                        break
            
            if not flagpole_direction:
                return self._create_hold_signal("flag_pennant", "명확한 flagpole 없음")
            
            # 최근 10개 봉에서 횡보 구간 확인 (consolidation)
            recent_highs = highs[-10:]
            recent_lows = lows[-10:]
            consolidation_range = (max(recent_highs) - min(recent_lows)) / current_price
            
            # 거래량 확인
            avg_volume = sum(volumes[-20:-10]) / 10  # flagpole 구간 평균 거래량
            current_volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # 20일 이동평균 계산
            ma20 = sum(closes[-20:]) / 20
            
            # 깃발 패턴 돌파 확인
            if (consolidation_range < 0.03 and  # 3% 이내 횡보
                flagpole_strength > 0.05):     # 5% 이상 flagpole
                
                if flagpole_direction == "up":
                    # 상승 깃발 패턴
                    resistance_level = max(recent_highs)
                    if (current_price > resistance_level * 1.002 and  # 저항선 돌파
                        current_volume_ratio > 1.5 and               # 거래량 증가
                        current_price > ma20):                       # 20일선 위
                        
                        confidence = min(0.85, 0.6 + flagpole_strength + (current_volume_ratio - 1) * 0.1)
                        return TradingSignal(
                            strategy_id="flag_pennant",
                            action="buy",
                            confidence=confidence,
                            price=current_price,
                            suggested_amount=self.config.base_amount * 1.2,  # 패턴 돌파시 더 큰 포지션
                            reasoning=f"상승 깃발 돌파 (flagpole: {flagpole_strength:.2%}, 거래량: {current_volume_ratio:.1f}배)",
                            timestamp=datetime.now(),
                            timeframe="1h"
                        )
                
                elif flagpole_direction == "down":
                    # 하락 깃발 패턴  
                    support_level = min(recent_lows)
                    if (current_price < support_level * 0.998 and    # 지지선 이탈
                        current_volume_ratio > 1.5 and               # 거래량 증가
                        current_price < ma20):                       # 20일선 아래
                        
                        confidence = min(0.85, 0.6 + flagpole_strength + (current_volume_ratio - 1) * 0.1)
                        return TradingSignal(
                            strategy_id="flag_pennant",
                            action="sell",
                            confidence=confidence,
                            price=current_price,
                            suggested_amount=0,
                            reasoning=f"하락 깃발 이탈 (flagpole: {flagpole_strength:.2%}, 거래량: {current_volume_ratio:.1f}배)",
                            timestamp=datetime.now(),
                            timeframe="1h"
                        )
            
            return self._create_hold_signal("flag_pennant", f"패턴 형성 중 ({flagpole_direction} flagpole {flagpole_strength:.1%})")
            
        except Exception as e:
            self.logger.error(f"깃발/페넌트 패턴 신호 생성 오류: {e}")
            return self._create_hold_signal("flag_pennant", f"계산 오류: {str(e)}")
    
    def _create_hold_signal(self, strategy_id: str, reason: str, confidence: float = None) -> TradingSignal:
        """홀드 신호 생성"""
        try:
            current_price = 0
            market_data = self.api.get_market_data("KRW-BTC")
            if market_data:
                current_price = market_data.price
        except:
            current_price = 0
        
        # 전략별 다른 기본 신뢰도 설정
        if confidence is None:
            confidence_map = {
                "ema_cross": 0.3,
                "rsi_divergence": 0.4,
                "vwap_pullback": 0.35,
                "macd_zero_cross": 0.3,
                "bollinger_band_strategy": 0.4,
                "pivot_points": 0.35,
                "open_interest": 0.3,
                "flag_pennant": 0.25
            }
            confidence = confidence_map.get(strategy_id, 0.3)
        
        return TradingSignal(
            strategy_id=strategy_id,
            action="hold",
            confidence=confidence,
            price=current_price,
            suggested_amount=0,
            reasoning=reason,
            timestamp=datetime.now(),
            timeframe="1h"
        )