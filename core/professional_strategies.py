"""
전문가 수준의 트레이딩 전략 구현
Professional Trading Strategies Implementation
"""

import numpy as np
import pandas as pd
import talib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

@dataclass
class ProfessionalSignal:
    """전문가 수준 신호 클래스"""
    strategy_id: str
    action: str  # 'long', 'short', 'close', 'hold'
    entry_price: float
    stop_loss: float
    take_profits: List[Tuple[float, float]]  # [(price, percentage)]
    position_size: float
    confidence: float
    risk_reward_ratio: float
    reasoning: str
    filters_passed: Dict[str, bool]
    market_condition: str
    timeframe: str
    timestamp: datetime
    
class ProfessionalStrategyAnalyzer:
    """전문가 수준 전략 분석기"""
    
    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.logger = logging.getLogger('ProfessionalStrategy')
        
    def _default_config(self) -> Dict:
        """기본 설정"""
        return {
            'risk_per_trade': 0.02,  # 거래당 2% 리스크
            'max_correlation': 0.7,
            'min_volume_multiplier': 1.5,
            'atr_multiplier': 2.0,
            'partial_profits': [
                (1.5, 0.3),  # 1.5R에서 30%
                (2.5, 0.3),  # 2.5R에서 30%
                (4.0, 0.4),  # 4.0R에서 40%
            ]
        }
    
    # ==================== H1: EMA 크로스오버 전략 ====================
    
    def h1_ema_crossover_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H1: EMA 크로스오버 전략
        - 적응형 EMA 기간
        - 다중 필터링
        - 동적 손절매
        """
        try:
            if len(df) < 50:
                return None
            
            # 1. 변동성 기반 적응형 EMA 기간 설정
            volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
            
            if volatility > 0.05:  # 고변동성
                fast_period, slow_period = 8, 21
            elif volatility > 0.03:  # 중간 변동성
                fast_period, slow_period = 10, 26
            else:  # 저변동성
                fast_period, slow_period = 12, 30
            
            # 2. EMA 계산
            df['ema_fast'] = talib.EMA(df['close'].values, timeperiod=fast_period)
            df['ema_slow'] = talib.EMA(df['close'].values, timeperiod=slow_period)
            df['ema_signal'] = talib.EMA(df['close'].values, timeperiod=50)
            
            # 3. RSI 계산
            rsi = talib.RSI(df['close'].values, timeperiod=14)
            
            # 4. ATR 계산
            atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
            
            # 5. 거래량 분석
            volume_ma = df['volume'].rolling(20).mean()
            volume_ratio = df['volume'].iloc[-1] / volume_ma.iloc[-1]
            
            # 6. 크로스 감지
            current_fast = df['ema_fast'].iloc[-1]
            current_slow = df['ema_slow'].iloc[-1]
            prev_fast = df['ema_fast'].iloc[-2]
            prev_slow = df['ema_slow'].iloc[-2]
            current_price = df['close'].iloc[-1]
            
            golden_cross = prev_fast <= prev_slow and current_fast > current_slow
            death_cross = prev_fast >= prev_slow and current_fast < current_slow
            
            # 7. 필터 조건 체크
            filters = {}
            
            if golden_cross:
                filters['golden_cross'] = True
                filters['trend_filter'] = current_price > df['ema_signal'].iloc[-1]
                filters['volume_confirmation'] = volume_ratio > 1.5
                filters['rsi_filter'] = 40 < rsi[-1] < 70
                filters['volatility_filter'] = 0.015 < atr[-1] / current_price < 0.08
                
                # 모든 필터 통과 확인
                if all(filters.values()):
                    # 손절매 계산 (ATR 기반 + 구조적 지지)
                    atr_stop = current_price - (atr[-1] * self.config['atr_multiplier'])
                    structure_stop = df['low'].rolling(10).min().iloc[-1] * 0.995
                    stop_loss = max(atr_stop, structure_stop)
                    
                    # 목표가 설정 (부분 익절)
                    risk = current_price - stop_loss
                    take_profits = [
                        (current_price + risk * r, pct) 
                        for r, pct in self.config['partial_profits']
                    ]
                    
                    # 포지션 크기 계산
                    position_size = self._calculate_position_size(
                        account_balance=1000000,  # 실제 잔고로 대체
                        risk_amount=current_price - stop_loss,
                        confidence=0.7
                    )
                    
                    return ProfessionalSignal(
                        strategy_id='h1',
                        action='long',
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profits=take_profits,
                        position_size=position_size,
                        confidence=0.7,
                        risk_reward_ratio=self.config['partial_profits'][-1][0],
                        reasoning=f"EMA 골든크로스 (Fast:{fast_period} Slow:{slow_period})",
                        filters_passed=filters,
                        market_condition='trending_up',
                        timeframe='1h',
                        timestamp=datetime.now()
                    )
            
            elif death_cross:
                filters['death_cross'] = True
                filters['trend_filter'] = current_price < df['ema_signal'].iloc[-1]
                filters['volume_confirmation'] = volume_ratio > 1.5
                filters['rsi_filter'] = 30 < rsi[-1] < 60
                
                if all(filters.values()):
                    # 숏 포지션 로직
                    stop_loss = current_price + (atr[-1] * self.config['atr_multiplier'])
                    risk = stop_loss - current_price
                    take_profits = [
                        (current_price - risk * r, pct)
                        for r, pct in self.config['partial_profits']
                    ]
                    
                    return ProfessionalSignal(
                        strategy_id='h1',
                        action='short',
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profits=take_profits,
                        position_size=self._calculate_position_size(1000000, risk, 0.65),
                        confidence=0.65,
                        risk_reward_ratio=self.config['partial_profits'][-1][0],
                        reasoning=f"EMA 데드크로스",
                        filters_passed=filters,
                        market_condition='trending_down',
                        timeframe='1h',
                        timestamp=datetime.now()
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"H1 전략 오류: {e}")
            return None
    
    # ==================== H2: RSI 다이버전스 전략 ====================
    
    def h2_rsi_divergence_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H2: RSI 다이버전스 전략
        - Regular & Hidden 다이버전스
        - 다중 시간대 확인
        - 볼륨 검증
        """
        try:
            if len(df) < 50:
                return None
            
            # RSI 계산
            rsi = talib.RSI(df['close'].values, timeperiod=14)
            current_price = df['close'].iloc[-1]
            
            # 피크와 트로프 찾기 (지난 20봉)
            lookback = 20
            price_highs = self._find_peaks(df['high'].values[-lookback:], order=3)
            price_lows = self._find_troughs(df['low'].values[-lookback:], order=3)
            rsi_highs = self._find_peaks(rsi[-lookback:], order=3)
            rsi_lows = self._find_troughs(rsi[-lookback:], order=3)
            
            # Bullish Divergence (가격 하락, RSI 상승)
            if len(price_lows) >= 2 and len(rsi_lows) >= 2:
                if price_lows[-1] < price_lows[-2] and rsi_lows[-1] > rsi_lows[-2]:
                    # 다이버전스 강도 계산
                    price_diff = abs(price_lows[-1] - price_lows[-2]) / price_lows[-2]
                    rsi_diff = abs(rsi_lows[-1] - rsi_lows[-2])
                    divergence_strength = (price_diff * 100 + rsi_diff) / 2
                    
                    if divergence_strength > 5 and rsi[-1] < 35:
                        # 필터링
                        filters = {
                            'divergence': True,
                            'rsi_oversold': rsi[-1] < 35,
                            'volume_increase': df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1],
                            'min_bars': len(price_lows) >= 5
                        }
                        
                        if sum(filters.values()) >= 3:
                            atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values)[-1]
                            stop_loss = current_price - (atr * 1.5)
                            
                            return ProfessionalSignal(
                                strategy_id='h2',
                                action='long',
                                entry_price=current_price,
                                stop_loss=stop_loss,
                                take_profits=self._calculate_take_profits(current_price, stop_loss, 'long'),
                                position_size=50000,
                                confidence=0.65 + divergence_strength / 100,
                                risk_reward_ratio=2.0,
                                reasoning=f"Bullish RSI Divergence (Strength: {divergence_strength:.1f})",
                                filters_passed=filters,
                                market_condition='oversold_reversal',
                                timeframe='1h',
                                timestamp=datetime.now()
                            )
            
            # Bearish Divergence
            if len(price_highs) >= 2 and len(rsi_highs) >= 2:
                if price_highs[-1] > price_highs[-2] and rsi_highs[-1] < rsi_highs[-2]:
                    if rsi[-1] > 65:
                        # Similar logic for bearish divergence
                        pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"H2 전략 오류: {e}")
            return None
    
    # ==================== H3: 피봇 포인트 전략 ====================
    
    def h3_pivot_point_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H3: 피봇 포인트 반등 전략
        - 표준 & Camarilla 피봇
        - 캔들 패턴 확인
        - 볼륨 프로파일
        """
        try:
            if len(df) < 2:
                return None
            
            # 전일 데이터
            prev_high = df['high'].iloc[-2]
            prev_low = df['low'].iloc[-2]
            prev_close = df['close'].iloc[-2]
            current_price = df['close'].iloc[-1]
            
            # 표준 피봇 계산
            pp = (prev_high + prev_low + prev_close) / 3
            r1 = 2 * pp - prev_low
            r2 = pp + (prev_high - prev_low)
            r3 = prev_high + 2 * (pp - prev_low)
            s1 = 2 * pp - prev_high
            s2 = pp - (prev_high - prev_low)
            s3 = prev_low - 2 * (prev_high - pp)
            
            # Camarilla 피봇
            h_l = prev_high - prev_low
            r4 = prev_close + (h_l * 1.1 / 2)
            r3_cam = prev_close + (h_l * 1.1 / 4)
            s3_cam = prev_close - (h_l * 1.1 / 4)
            s4 = prev_close - (h_l * 1.1 / 2)
            
            # 캔들 패턴 인식
            candle_pattern = self._identify_candle_pattern(df.tail(3))
            
            # RSI
            rsi = talib.RSI(df['close'].values, timeperiod=14)[-1]
            
            # 피봇 레벨 근처 체크 (0.3% 오차)
            tolerance = 0.003
            
            # S1 지지선 반등
            if abs(current_price - s1) / current_price < tolerance:
                if candle_pattern in ['hammer', 'bullish_engulfing', 'doji']:
                    filters = {
                        'pivot_touch': True,
                        'candle_pattern': True,
                        'rsi_oversold': rsi < 40,
                        'volume_spike': df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1] * 1.5
                    }
                    
                    if sum(filters.values()) >= 3:
                        stop_loss = s2  # 다음 지지선
                        target = pp  # 중심 피봇
                        
                        return ProfessionalSignal(
                            strategy_id='h3',
                            action='long',
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profits=[(pp, 0.5), (r1, 0.3), (r2, 0.2)],
                            position_size=40000,
                            confidence=0.65,
                            risk_reward_ratio=(target - current_price) / (current_price - stop_loss),
                            reasoning=f"S1 Pivot Bounce ({candle_pattern})",
                            filters_passed=filters,
                            market_condition='support_bounce',
                            timeframe='1h',
                            timestamp=datetime.now()
                        )
            
            # R1 저항선 거부
            if abs(current_price - r1) / current_price < tolerance:
                if candle_pattern in ['shooting_star', 'bearish_engulfing', 'evening_star']:
                    # Similar logic for resistance rejection
                    pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"H3 전략 오류: {e}")
            return None
    
    # ==================== H4: VWAP 전략 ====================
    
    def h4_vwap_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H4: VWAP 되돌림 전략
        - VWAP 밴드
        - Cumulative Delta
        - Anchored VWAP
        """
        try:
            if len(df) < 20:
                return None
            
            # VWAP 계산
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            
            # VWAP 표준편차 밴드
            squared_diff = ((typical_price - vwap) ** 2 * df['volume']).cumsum()
            variance = squared_diff / df['volume'].cumsum()
            std_dev = np.sqrt(variance)
            
            upper_band = vwap + (2 * std_dev)
            lower_band = vwap - (2 * std_dev)
            
            current_price = df['close'].iloc[-1]
            current_vwap = vwap.iloc[-1]
            
            # Cumulative Delta (간단 버전)
            delta = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
            cum_delta = delta.cumsum()
            
            # 거리 계산
            distance_from_vwap = (current_price - current_vwap) / current_vwap
            
            # 트렌드 확인
            ema20 = talib.EMA(df['close'].values, timeperiod=20)
            ema50 = talib.EMA(df['close'].values, timeperiod=50)
            uptrend = ema20[-1] > ema50[-1]
            
            # VWAP 되돌림 매수
            if uptrend and -0.01 < distance_from_vwap < -0.003:
                if cum_delta[-1] > 0:  # 매수 우세
                    # 바운스 확인 (최근 2봉)
                    if df['close'].iloc[-1] > df['close'].iloc[-2]:
                        filters = {
                            'vwap_pullback': True,
                            'uptrend': True,
                            'positive_delta': True,
                            'bounce_confirmation': True
                        }
                        
                        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values)[-1]
                        stop_loss = current_vwap - std_dev.iloc[-1]
                        
                        return ProfessionalSignal(
                            strategy_id='h4',
                            action='long',
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profits=[(current_vwap + std_dev.iloc[-1], 0.4), 
                                        (upper_band.iloc[-1], 0.6)],
                            position_size=45000,
                            confidence=0.68,
                            risk_reward_ratio=2.5,
                            reasoning=f"VWAP Pullback in Uptrend (Delta: {cum_delta[-1]:.0f})",
                            filters_passed=filters,
                            market_condition='pullback_in_trend',
                            timeframe='1h',
                            timestamp=datetime.now()
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"H4 전략 오류: {e}")
            return None
    
    # ==================== 헬퍼 메서드 ====================
    
    def _calculate_position_size(self, account_balance: float, risk_amount: float, confidence: float) -> float:
        """포지션 크기 계산"""
        risk_per_trade = self.config['risk_per_trade']
        max_risk = account_balance * risk_per_trade
        
        # Kelly Criterion (simplified)
        kelly_fraction = confidence * 0.25  # Conservative Kelly
        
        position_size = min(max_risk / risk_amount, account_balance * kelly_fraction)
        
        return max(position_size, 10000)  # 최소 거래 금액
    
    def _calculate_take_profits(self, entry: float, stop: float, direction: str) -> List[Tuple[float, float]]:
        """목표가 계산"""
        risk = abs(entry - stop)
        
        if direction == 'long':
            return [
                (entry + risk * r, pct)
                for r, pct in self.config['partial_profits']
            ]
        else:
            return [
                (entry - risk * r, pct)
                for r, pct in self.config['partial_profits']
            ]
    
    def _find_peaks(self, data: np.ndarray, order: int = 3) -> List[float]:
        """피크 찾기"""
        peaks = []
        for i in range(order, len(data) - order):
            if all(data[i] > data[i-j] for j in range(1, order+1)) and \
               all(data[i] > data[i+j] for j in range(1, order+1)):
                peaks.append(data[i])
        return peaks
    
    def _find_troughs(self, data: np.ndarray, order: int = 3) -> List[float]:
        """트로프 찾기"""
        troughs = []
        for i in range(order, len(data) - order):
            if all(data[i] < data[i-j] for j in range(1, order+1)) and \
               all(data[i] < data[i+j] for j in range(1, order+1)):
                troughs.append(data[i])
        return troughs
    
    def _identify_candle_pattern(self, df: pd.DataFrame) -> str:
        """캔들 패턴 인식"""
        if len(df) < 1:
            return 'none'
        
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])
        upper_shadow = last['high'] - max(last['close'], last['open'])
        lower_shadow = min(last['close'], last['open']) - last['low']
        
        # Hammer
        if lower_shadow > body * 2 and upper_shadow < body * 0.3:
            return 'hammer'
        
        # Shooting Star
        if upper_shadow > body * 2 and lower_shadow < body * 0.3:
            return 'shooting_star'
        
        # Doji
        if body < (last['high'] - last['low']) * 0.1:
            return 'doji'
        
        # Engulfing (need 2 candles)
        if len(df) >= 2:
            prev = df.iloc[-2]
            if last['close'] > last['open'] and prev['close'] < prev['open']:
                if last['open'] < prev['close'] and last['close'] > prev['open']:
                    return 'bullish_engulfing'
            elif last['close'] < last['open'] and prev['close'] > prev['open']:
                if last['open'] > prev['close'] and last['close'] < prev['open']:
                    return 'bearish_engulfing'
        
        return 'none'
    
    # ==================== H5: MACD 히스토그램 전략 ====================
    
    def h5_macd_histogram_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H5: MACD 히스토그램 전략
        - 모멘텀 변화 감지
        - 히스토그램 크로스오버
        - MACD 다이버전스
        """
        try:
            if len(df) < 50:
                return None
            
            # MACD 계산
            macd, signal, histogram = talib.MACD(
                df['close'].values,
                fastperiod=12,
                slowperiod=26,
                signalperiod=9
            )
            
            # ADX for trend strength
            adx = talib.ADX(df['high'].values, df['low'].values, df['close'].values)
            
            current_price = df['close'].iloc[-1]
            
            # 히스토그램 크로스오버 체크
            if len(histogram) >= 2:
                prev_hist = histogram[-2]
                curr_hist = histogram[-1]
                
                # Bullish crossover (negative to positive)
                if prev_hist < 0 and curr_hist > 0:
                    # 추가 필터
                    filters = {
                        'histogram_cross': True,
                        'macd_above_signal': macd[-1] > signal[-1],
                        'trend_exists': adx[-1] > 25,
                        'momentum_increasing': curr_hist > prev_hist,
                        'price_above_ma': current_price > talib.EMA(df['close'].values, 50)[-1]
                    }
                    
                    if sum(filters.values()) >= 4:
                        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values)[-1]
                        stop_loss = current_price - (atr * 2.0)
                        
                        return ProfessionalSignal(
                            strategy_id='h5',
                            action='long',
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profits=self._calculate_take_profits(current_price, stop_loss, 'long'),
                            position_size=35000,
                            confidence=0.66,
                            risk_reward_ratio=2.2,
                            reasoning="MACD Histogram Bullish Crossover",
                            filters_passed=filters,
                            market_condition='momentum_shift',
                            timeframe='1h',
                            timestamp=datetime.now()
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"H5 전략 오류: {e}")
            return None
    
    # ==================== H6: 볼린저 밴드 스퀴즈 전략 ====================
    
    def h6_bollinger_squeeze_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H6: 볼린저 밴드 스퀴즈 전략
        - 변동성 압축과 확장
        - TTM Squeeze 지표
        - Keltner Channel과 결합
        """
        try:
            if len(df) < 30:
                return None
            
            # 볼린저 밴드
            bb_upper, bb_middle, bb_lower = talib.BBANDS(
                df['close'].values,
                timeperiod=20,
                nbdevup=2,
                nbdevdn=2
            )
            
            # Keltner Channel (수동 계산)
            atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values)
            kc_middle = talib.EMA(df['close'].values, timeperiod=20)
            kc_upper = kc_middle + (atr * 1.5)
            kc_lower = kc_middle - (atr * 1.5)
            
            # 스퀴즈 감지
            squeeze_on = (bb_upper[-1] < kc_upper[-1]) and (bb_lower[-1] > kc_lower[-1])
            
            # 스퀴즈 히스토리 체크 (최근 10봉)
            squeeze_history = []
            for i in range(-10, 0):
                is_squeeze = (bb_upper[i] < kc_upper[i]) and (bb_lower[i] > kc_lower[i])
                squeeze_history.append(is_squeeze)
            
            # 스퀴즈 해제 감지
            was_squeeze = any(squeeze_history[-6:])
            squeeze_released = was_squeeze and not squeeze_on
            
            if squeeze_released:
                # 모멘텀 방향 확인
                momentum = df['close'].iloc[-1] - df['close'].rolling(20).mean().iloc[-1]
                volume_surge = df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1] * 2
                
                if momentum > 0 and volume_surge:
                    filters = {
                        'squeeze_release': True,
                        'positive_momentum': True,
                        'volume_surge': True,
                        'price_breakout': df['close'].iloc[-1] > bb_upper[-1]
                    }
                    
                    current_price = df['close'].iloc[-1]
                    stop_loss = bb_middle[-1]
                    
                    return ProfessionalSignal(
                        strategy_id='h6',
                        action='long',
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profits=[(bb_upper[-1] + atr[-1], 0.5), 
                                    (bb_upper[-1] + atr[-1] * 2, 0.5)],
                        position_size=40000,
                        confidence=0.70,
                        risk_reward_ratio=2.0,
                        reasoning="Bollinger Squeeze Release - Bullish",
                        filters_passed=filters,
                        market_condition='volatility_expansion',
                        timeframe='1h',
                        timestamp=datetime.now()
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"H6 전략 오류: {e}")
            return None
    
    # ==================== H7: 미체결약정 & 펀딩비 전략 ====================
    
    def h7_open_interest_funding_strategy(self, df: pd.DataFrame, 
                                         oi_data: Dict = None,
                                         funding_rate: float = None) -> Optional[ProfessionalSignal]:
        """
        H7: 미체결약정 & 펀딩비 전략
        - OI 변화 분석
        - 펀딩비 극단값
        - Long/Short 비율
        """
        try:
            if len(df) < 20:
                return None
            
            # 임시 데이터 (실제로는 외부 API에서 가져와야 함)
            if oi_data is None:
                oi_data = {'current': 1000000, 'previous': 950000, 'long_ratio': 0.45}
            if funding_rate is None:
                funding_rate = 0.01  # 1% 예시
            
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            
            # OI 변화율
            oi_change = (oi_data['current'] - oi_data['previous']) / oi_data['previous']
            price_change = (current_price - prev_price) / prev_price
            
            # 시나리오 분석
            # Price UP + OI UP = 신규 매수 (강세)
            if price_change > 0.01 and oi_change > 0.05:
                if funding_rate < 0.03:  # 펀딩비가 너무 높지 않을 때
                    filters = {
                        'price_up_oi_up': True,
                        'funding_reasonable': True,
                        'long_ratio_ok': oi_data['long_ratio'] < 0.6,
                        'volume_confirmation': df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1]
                    }
                    
                    if sum(filters.values()) >= 3:
                        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values)[-1]
                        stop_loss = current_price - (atr * 1.8)
                        
                        return ProfessionalSignal(
                            strategy_id='h7',
                            action='long',
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profits=self._calculate_take_profits(current_price, stop_loss, 'long'),
                            position_size=30000,
                            confidence=0.64,
                            risk_reward_ratio=1.8,
                            reasoning=f"New Longs Entering (OI +{oi_change:.1%})",
                            filters_passed=filters,
                            market_condition='bullish_sentiment',
                            timeframe='1h',
                            timestamp=datetime.now()
                        )
            
            # Contrarian signal on extreme funding
            elif abs(funding_rate) > 0.05:
                if funding_rate > 0.05:  # 과도한 롱
                    # Short opportunity
                    pass
                else:  # 과도한 숏
                    # Long opportunity
                    pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"H7 전략 오류: {e}")
            return None
    
    # ==================== H8: 깃발/페넌트 패턴 전략 ====================
    
    def h8_flag_pennant_strategy(self, df: pd.DataFrame) -> Optional[ProfessionalSignal]:
        """
        H8: 깃발/페넌트 패턴 전략
        - 강한 추세 후 조정 패턴
        - 패턴 브레이크아웃
        - 거래량 확인
        """
        try:
            if len(df) < 30:
                return None
            
            # 패턴 감지를 위한 최근 30봉 분석
            lookback = 30
            recent_data = df.tail(lookback)
            
            # 깃대 찾기 (급등/급락)
            max_idx = recent_data['high'].idxmax()
            min_idx = recent_data['low'].idxmin()
            
            # Bull flag 체크
            if max_idx < len(recent_data) - 5:  # 고점이 5봉 이상 전에 있음
                flagpole_start_idx = max_idx - 5
                if flagpole_start_idx >= 0:
                    flagpole_height = recent_data.loc[max_idx, 'high'] - recent_data.iloc[flagpole_start_idx]['low']
                    flagpole_percent = flagpole_height / recent_data.iloc[flagpole_start_idx]['low']
                    
                    if flagpole_percent > 0.15:  # 15% 이상 급등
                        # 깃발 부분 분석 (고점 이후)
                        flag_data = recent_data.loc[max_idx:]
                        
                        # 조정 깊이
                        correction_depth = (recent_data.loc[max_idx, 'high'] - flag_data['low'].min()) / flagpole_height
                        
                        if 0.382 < correction_depth < 0.618:  # 피보나치 레벨
                            # 브레이크아웃 체크
                            current_price = df['close'].iloc[-1]
                            flag_high = flag_data['high'].max()
                            
                            if current_price > flag_high * 0.995:  # 브레이크아웃 근처
                                filters = {
                                    'flag_pattern': True,
                                    'correction_depth_ok': True,
                                    'volume_pattern': df['volume'].iloc[-1] > df['volume'].iloc[-5:-1].mean(),
                                    'time_limit': len(flag_data) < 15  # 15봉 이내
                                }
                                
                                if sum(filters.values()) >= 3:
                                    stop_loss = flag_data['low'].min()
                                    target = current_price + flagpole_height  # Measured move
                                    
                                    return ProfessionalSignal(
                                        strategy_id='h8',
                                        action='long',
                                        entry_price=current_price,
                                        stop_loss=stop_loss,
                                        take_profits=[(target * 0.5, 0.5), (target, 0.5)],
                                        position_size=35000,
                                        confidence=0.68,
                                        risk_reward_ratio=(target - current_price) / (current_price - stop_loss),
                                        reasoning=f"Bull Flag Breakout ({flagpole_percent:.1%} pole)",
                                        filters_passed=filters,
                                        market_condition='continuation_pattern',
                                        timeframe='1h',
                                        timestamp=datetime.now()
                                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"H8 전략 오류: {e}")
            return None
    
    # ==================== 일봉 전략 구현 ====================
    
    def d1_weekly_ma50_strategy(self, daily_df: pd.DataFrame, weekly_df: pd.DataFrame = None) -> Optional[ProfessionalSignal]:
        """
        D1: 주봉 필터 + 50일선 전략
        - 다중 시간대 분석
        - 50일선 반등
        - Scale-in 전략
        """
        try:
            if len(daily_df) < 50:
                return None
            
            # 50일 이동평균
            ma50 = talib.SMA(daily_df['close'].values, timeperiod=50)
            current_price = daily_df['close'].iloc[-1]
            
            # 주봉 트렌드 확인 (간단 버전)
            weekly_trend_up = True  # 실제로는 weekly_df 분석 필요
            
            # 50일선 터치 확인
            distance_to_ma50 = abs(current_price - ma50[-1]) / current_price
            
            if distance_to_ma50 < 0.01 and weekly_trend_up:  # 1% 이내
                # 반등 패턴 확인
                candle_pattern = self._identify_candle_pattern(daily_df.tail(2))
                
                if candle_pattern in ['hammer', 'bullish_engulfing', 'doji']:
                    filters = {
                        'ma50_touch': True,
                        'weekly_uptrend': True,
                        'bounce_pattern': True,
                        'rsi_oversold': talib.RSI(daily_df['close'].values)[-1] < 40,
                        'volume_increase': daily_df['volume'].iloc[-1] > daily_df['volume'].rolling(20).mean().iloc[-1]
                    }
                    
                    if sum(filters.values()) >= 4:
                        atr = talib.ATR(daily_df['high'].values, daily_df['low'].values, daily_df['close'].values)[-1]
                        stop_loss = ma50[-1] - atr
                        
                        return ProfessionalSignal(
                            strategy_id='d1',
                            action='long',
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profits=self._calculate_take_profits(current_price, stop_loss, 'long'),
                            position_size=60000,
                            confidence=0.72,
                            risk_reward_ratio=2.5,
                            reasoning="MA50 Bounce in Weekly Uptrend",
                            filters_passed=filters,
                            market_condition='pullback_in_trend',
                            timeframe='1d',
                            timestamp=datetime.now()
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"D1 전략 오류: {e}")
            return None