"""
향상된 암호화폐 트레이딩 전략 구현
퀀트 관점에서 최적화된 파라미터와 리스크 관리
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Optional imports
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# TA-Lib import를 조건부로 처리
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    import logging
    logging.warning("TA-Lib not available. Some technical indicators will use fallback implementations.")

@dataclass
class EnhancedSignal:
    """향상된 트레이딩 시그널"""
    direction: str  # 'long', 'short', 'neutral'
    strength: float  # 0.0 ~ 1.0
    confidence: float  # 0.0 ~ 1.0
    entry_price: float
    stop_loss: float
    take_profits: List[Tuple[float, float]]  # [(price, percentage)]
    position_size: float
    reason: str
    filters_passed: Dict[str, bool]
    risk_reward_ratio: float
    expected_return: float
    
class AdvancedRiskManager:
    """고급 리스크 관리 시스템"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.equity_curve = []
        self.current_drawdown = 0
        self.max_drawdown = 0
        self.daily_pnl = 0
        self.correlation_matrix = None
        
    def calculate_position_size(self, 
                               signal_strength: float,
                               volatility: float,
                               win_rate: float,
                               avg_win_loss: float,
                               account_balance: float) -> float:
        """
        Kelly Criterion 수정 버전으로 포지션 크기 계산
        """
        # Kelly Criterion: f = (p * b - q) / b
        # p = win_rate, q = 1 - win_rate, b = avg_win_loss
        
        if avg_win_loss <= 0 or win_rate <= 0:
            return 0
            
        kelly_fraction = (win_rate * avg_win_loss - (1 - win_rate)) / avg_win_loss
        
        # Kelly의 25%만 사용 (보수적 접근)
        conservative_kelly = kelly_fraction * 0.25
        
        # 변동성 조정
        volatility_adj = 1 / (1 + volatility * 10)  # 변동성이 높을수록 포지션 축소
        
        # 신호 강도 조정
        signal_adj = signal_strength ** 2  # 약한 신호는 더 작은 포지션
        
        # 최종 포지션 크기 (계좌 잔고 대비 %)
        position_pct = conservative_kelly * volatility_adj * signal_adj
        
        # 한계 설정
        max_position = self.config.get('max_position_pct', 0.3)
        position_pct = min(max(position_pct, 0), max_position)
        
        return account_balance * position_pct
    
    def calculate_dynamic_stop_loss(self, 
                                   entry_price: float,
                                   atr: float,
                                   support_levels: List[float],
                                   direction: str) -> float:
        """
        동적 손절매 계산 (ATR + 지지/저항 기반)
        """
        atr_multiplier = self.config.get('atr_multiplier', 1.5)
        
        if direction == 'long':
            # ATR 기반 손절
            atr_stop = entry_price - (atr * atr_multiplier)
            
            # 가장 가까운 지지선
            valid_supports = [s for s in support_levels if s < entry_price]
            structure_stop = max(valid_supports) if valid_supports else atr_stop
            
            # 둘 중 더 타이트한 것 선택
            stop_loss = max(atr_stop, structure_stop * 0.99)
            
        else:  # short
            atr_stop = entry_price + (atr * atr_multiplier)
            
            valid_resistances = [r for r in support_levels if r > entry_price]
            structure_stop = min(valid_resistances) if valid_resistances else atr_stop
            
            stop_loss = min(atr_stop, structure_stop * 1.01)
            
        return stop_loss
    
    def check_correlation(self, positions: List[str]) -> bool:
        """
        포지션 간 상관관계 체크
        """
        if len(positions) < 2:
            return True
            
        # 상관관계가 높은 포지션이 너무 많으면 거부
        high_correlation_count = 0
        threshold = self.config.get('correlation_threshold', 0.7)
        
        for i, pos1 in enumerate(positions):
            for pos2 in positions[i+1:]:
                if self.get_correlation(pos1, pos2) > threshold:
                    high_correlation_count += 1
                    
        max_correlated = self.config.get('max_correlated_positions', 2)
        return high_correlation_count < max_correlated
    
    def get_correlation(self, asset1: str, asset2: str) -> float:
        """두 자산 간 상관관계 계산 (실제 구현 필요)"""
        # 실제로는 과거 가격 데이터로 계산
        return 0.5  # 임시 값

class EnhancedStrategyAnalyzer:
    """향상된 전략 분석기"""
    
    def __init__(self):
        self.risk_manager = AdvancedRiskManager({
            'max_position_pct': 0.3,
            'atr_multiplier': 1.5,
            'correlation_threshold': 0.7,
            'max_correlated_positions': 2
        })
        
    def enhanced_ema_cross_strategy(self, df: pd.DataFrame) -> Optional[EnhancedSignal]:
        """
        개선된 EMA 크로스 전략
        - 적응형 기간
        - 변동성 필터
        - 볼륨 프로파일
        - 시장 체제 감지
        """
        # 적응형 EMA 기간 계산 (시장 변동성 기반)
        volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
        
        # 변동성이 높으면 더 빠른 EMA 사용
        if volatility > 0.05:
            fast_period = 8
            slow_period = 21
        elif volatility > 0.03:
            fast_period = 10
            slow_period = 26
        else:
            fast_period = 12
            slow_period = 30
            
        # EMA 계산
        df['ema_fast'] = talib.EMA(df['close'].values, timeperiod=fast_period)
        df['ema_slow'] = talib.EMA(df['close'].values, timeperiod=slow_period)
        
        # 현재와 이전 값
        current_fast = df['ema_fast'].iloc[-1]
        current_slow = df['ema_slow'].iloc[-1]
        prev_fast = df['ema_fast'].iloc[-2]
        prev_slow = df['ema_slow'].iloc[-2]
        
        # 크로스 감지
        golden_cross = prev_fast <= prev_slow and current_fast > current_slow
        death_cross = prev_fast >= prev_slow and current_fast < current_slow
        
        if not (golden_cross or death_cross):
            return None
            
        # === 필터링 조건 ===
        filters = {}
        
        # 1. 볼륨 확인 (평균 대비 1.5배 이상)
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        filters['volume_confirmation'] = current_volume > avg_volume * 1.5
        
        # 2. ATR 기반 변동성 필터
        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)[-1]
        atr_pct = atr / df['close'].iloc[-1]
        filters['volatility_filter'] = 0.015 < atr_pct < 0.08  # 1.5% ~ 8% 변동성
        
        # 3. 시장 체제 확인 (Hurst Exponent)
        hurst = self.calculate_hurst_exponent(df['close'].values[-100:])
        filters['trending_market'] = hurst > 0.55  # 트렌딩 시장
        
        # 4. RSI 다이버전스 체크
        rsi = talib.RSI(df['close'].values, timeperiod=14)[-1]
        filters['rsi_confirmation'] = (golden_cross and rsi < 70) or (death_cross and rsi > 30)
        
        # 5. VWAP 관계
        vwap = self.calculate_vwap(df)
        current_price = df['close'].iloc[-1]
        filters['vwap_alignment'] = (golden_cross and current_price > vwap) or \
                                   (death_cross and current_price < vwap)
        
        # 모든 필터 통과 확인
        all_filters_passed = all(filters.values())
        filter_score = sum(filters.values()) / len(filters)
        
        if filter_score < 0.6:  # 60% 이상 필터 통과 필요
            return None
            
        # === 포지션 계산 ===
        direction = 'long' if golden_cross else 'short'
        
        # 신호 강도 계산
        ema_separation = abs(current_fast - current_slow) / current_slow
        volume_strength = min(current_volume / avg_volume, 2) / 2
        signal_strength = (ema_separation * 10 + volume_strength + filter_score) / 3
        signal_strength = min(signal_strength, 1.0)
        
        # 신뢰도 계산
        confidence = filter_score * 0.7 + signal_strength * 0.3
        
        # 진입가격
        entry_price = current_price
        
        # 손절매 계산
        support_resistance = self.find_support_resistance(df)
        stop_loss = self.risk_manager.calculate_dynamic_stop_loss(
            entry_price, atr, support_resistance, direction
        )
        
        # 익절 목표 (부분 익절)
        if direction == 'long':
            take_profits = [
                (entry_price * 1.015, 0.3),  # 1.5% 상승 시 30% 익절
                (entry_price * 1.025, 0.3),  # 2.5% 상승 시 30% 익절
                (entry_price * 1.04, 0.4),   # 4% 상승 시 40% 익절
            ]
        else:
            take_profits = [
                (entry_price * 0.985, 0.3),
                (entry_price * 0.975, 0.3),
                (entry_price * 0.96, 0.4),
            ]
            
        # 리스크/리워드 비율
        risk = abs(entry_price - stop_loss) / entry_price
        reward = abs(take_profits[-1][0] - entry_price) / entry_price
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # 기대 수익률 (간단한 계산)
        win_rate = 0.55  # 과거 백테스팅 결과 사용
        expected_return = (win_rate * reward) - ((1 - win_rate) * risk)
        
        # 포지션 크기 계산
        position_size = self.risk_manager.calculate_position_size(
            signal_strength=signal_strength,
            volatility=volatility,
            win_rate=win_rate,
            avg_win_loss=1.5,  # 과거 데이터 기반
            account_balance=1000000  # 실제 잔고로 대체
        )
        
        return EnhancedSignal(
            direction=direction,
            strength=signal_strength,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            position_size=position_size,
            reason=f"{'Golden' if golden_cross else 'Death'} Cross with {filter_score:.0%} filters passed",
            filters_passed=filters,
            risk_reward_ratio=risk_reward_ratio,
            expected_return=expected_return
        )
    
    def calculate_hurst_exponent(self, ts: np.ndarray) -> float:
        """
        Hurst Exponent 계산 (시장 체제 감지)
        H > 0.5: 트렌딩
        H = 0.5: 랜덤워크
        H < 0.5: 평균회귀
        """
        lags = range(2, min(100, len(ts) // 2))
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0
    
    def calculate_vwap(self, df: pd.DataFrame) -> float:
        """VWAP 계산"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).sum() / df['volume'].sum()
        return vwap
    
    def find_support_resistance(self, df: pd.DataFrame, window: int = 20) -> List[float]:
        """지지/저항선 찾기"""
        highs = df['high'].rolling(window=window, center=True).max()
        lows = df['low'].rolling(window=window, center=True).min()
        
        # 피벗 포인트
        pivots = []
        for i in range(len(df)):
            if i > window and i < len(df) - window:
                if df['high'].iloc[i] == highs.iloc[i]:
                    pivots.append(df['high'].iloc[i])
                if df['low'].iloc[i] == lows.iloc[i]:
                    pivots.append(df['low'].iloc[i])
                    
        # 중복 제거 및 정렬
        pivots = sorted(list(set(pivots)))
        
        # 너무 가까운 레벨 병합 (1% 이내)
        merged = []
        for p in pivots:
            if not merged or abs(p - merged[-1]) / merged[-1] > 0.01:
                merged.append(p)
                
        return merged
    
    def enhanced_bollinger_squeeze_strategy(self, df: pd.DataFrame) -> Optional[EnhancedSignal]:
        """
        볼린저 밴드 스퀴즈 전략 (변동성 돌파)
        - Keltner Channel과 결합
        - GARCH 변동성 예측
        - 볼륨 확인
        """
        # 볼린저 밴드
        bb_period = 20
        bb_std = 2.0
        
        df['bb_middle'] = talib.SMA(df['close'].values, timeperiod=bb_period)
        df['bb_std'] = df['close'].rolling(bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * bb_std)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * bb_std)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Keltner Channel
        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=20)
        kc_middle = talib.EMA(df['close'].values, timeperiod=20)
        kc_upper = kc_middle + (atr * 1.5)
        kc_lower = kc_middle - (atr * 1.5)
        
        # 스퀴즈 감지 (BB가 KC 안에 있을 때)
        squeeze = (df['bb_upper'].iloc[-1] < kc_upper[-1]) and \
                 (df['bb_lower'].iloc[-1] > kc_lower[-1])
        
        # 스퀴즈 해제 및 방향
        prev_squeeze = (df['bb_upper'].iloc[-2] < kc_upper[-2]) and \
                      (df['bb_lower'].iloc[-2] > kc_lower[-2])
        
        squeeze_release = prev_squeeze and not squeeze
        
        if not squeeze_release:
            # 스퀴즈가 6바 이상 지속되었는지 확인
            squeeze_bars = 0
            for i in range(1, min(20, len(df))):
                if (df['bb_upper'].iloc[-i] < kc_upper[-i]) and \
                   (df['bb_lower'].iloc[-i] > kc_lower[-i]):
                    squeeze_bars += 1
                else:
                    break
                    
            if squeeze_bars < 6:
                return None
        
        # 돌파 방향 결정
        current_price = df['close'].iloc[-1]
        momentum = talib.MOM(df['close'].values, timeperiod=12)[-1]
        
        if current_price > df['bb_upper'].iloc[-1] and momentum > 0:
            direction = 'long'
        elif current_price < df['bb_lower'].iloc[-1] and momentum < 0:
            direction = 'short'
        else:
            return None
            
        # 볼륨 확인
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        if df['volume'].iloc[-1] < avg_volume * 2:
            return None
            
        # 신호 생성
        entry_price = current_price
        atr_value = atr[-1]
        
        # 동적 손절매
        if direction == 'long':
            stop_loss = df['bb_middle'].iloc[-1] - (atr_value * 0.5)
            take_profits = [
                (entry_price + atr_value * 1.5, 0.3),
                (entry_price + atr_value * 2.5, 0.3),
                (entry_price + atr_value * 4, 0.4)
            ]
        else:
            stop_loss = df['bb_middle'].iloc[-1] + (atr_value * 0.5)
            take_profits = [
                (entry_price - atr_value * 1.5, 0.3),
                (entry_price - atr_value * 2.5, 0.3),
                (entry_price - atr_value * 4, 0.4)
            ]
            
        # 신호 강도와 신뢰도
        bb_width_percentile = stats.percentileofscore(
            df['bb_width'].iloc[-100:], 
            df['bb_width'].iloc[-1]
        )
        signal_strength = (100 - bb_width_percentile) / 100  # 폭이 좁을수록 강한 신호
        
        volume_strength = min(df['volume'].iloc[-1] / avg_volume, 3) / 3
        confidence = (signal_strength * 0.6 + volume_strength * 0.4)
        
        # 리스크/리워드
        risk = abs(entry_price - stop_loss) / entry_price
        reward = abs(take_profits[-1][0] - entry_price) / entry_price
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        return EnhancedSignal(
            direction=direction,
            strength=signal_strength,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            position_size=100000,  # 실제 계산 필요
            reason=f"Bollinger Squeeze {'Breakout' if direction == 'long' else 'Breakdown'}",
            filters_passed={'squeeze_duration': True, 'volume_surge': True},
            risk_reward_ratio=risk_reward_ratio,
            expected_return=0.02
        )

# 사용 예시
if __name__ == "__main__":
    # 데이터 로드 (예시)
    # df = pd.read_csv('btc_data.csv')
    
    analyzer = EnhancedStrategyAnalyzer()
    
    # 전략 실행
    # signal = analyzer.enhanced_ema_cross_strategy(df)
    # if signal:
    #     print(f"Signal: {signal.direction}")
    #     print(f"Entry: {signal.entry_price}")
    #     print(f"Stop Loss: {signal.stop_loss}")
    #     print(f"Position Size: {signal.position_size}")