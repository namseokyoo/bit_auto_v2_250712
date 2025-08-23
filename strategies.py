"""
퀀트 트레이딩 전략 모듈
5개 핵심 전략 구현
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """거래 신호"""
    timestamp: float
    strategy: str
    action: str  # BUY, SELL, HOLD
    strength: float  # 0.0 ~ 1.0
    price: float
    reason: str


class BaseStrategy(ABC):
    """전략 기본 클래스"""
    
    def __init__(self, weight: float = 0.2, params: Dict[str, Any] = None):
        self.weight = weight
        self.params = params or {}
        self.position = None
        self.trades = []
        
    @abstractmethod
    async def generate_signal(self, market_data: List) -> Optional[Signal]:
        """신호 생성 (추상 메서드)"""
        pass
        
    def calculate_indicators(self, prices: pd.Series) -> Dict[str, Any]:
        """기술적 지표 계산"""
        indicators = {}
        
        # 이동평균
        indicators['ma_20'] = prices.rolling(20).mean().iloc[-1]
        indicators['ma_50'] = prices.rolling(50).mean().iloc[-1]
        
        # RSI
        indicators['rsi'] = self.calculate_rsi(prices)
        
        # 볼린저 밴드
        bb_period = 20
        bb_std = 2
        ma = prices.rolling(bb_period).mean()
        std = prices.rolling(bb_period).std()
        indicators['bb_upper'] = (ma + bb_std * std).iloc[-1]
        indicators['bb_lower'] = (ma - bb_std * std).iloc[-1]
        indicators['bb_middle'] = ma.iloc[-1]
        
        # MACD
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicators['macd'] = macd.iloc[-1]
        indicators['macd_signal'] = signal.iloc[-1]
        indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
        
        return indicators
        
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
        

class MarketMakingStrategy(BaseStrategy):
    """마켓 메이킹 전략"""
    
    def __init__(self, weight: float = 0.3, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.spread_threshold = params.get('spread_threshold', 0.001)
        self.inventory_limit = params.get('inventory_limit', 1000000)
        self.order_layers = params.get('order_layers', 5)
        
    async def generate_signal(self, market_data: List) -> Optional[Signal]:
        """마켓 메이킹 신호 생성"""
        try:
            if len(market_data) < 100:
                return None
                
            # 최근 데이터로 DataFrame 생성
            df = pd.DataFrame([{
                'price': d.price,
                'bid': d.bid,
                'ask': d.ask,
                'spread': d.spread,
                'timestamp': d.timestamp
            } for d in market_data[-100:]])
            
            current_price = df['price'].iloc[-1]
            current_bid = df['bid'].iloc[-1]
            current_ask = df['ask'].iloc[-1]
            spread = current_ask - current_bid
            spread_percent = spread / current_price
            
            # 변동성 계산
            volatility = df['price'].pct_change().std()
            
            # 스프레드가 충분히 넓고 변동성이 낮을 때
            if spread_percent > self.spread_threshold and volatility < 0.01:
                # 중간 가격 계산
                mid_price = (current_bid + current_ask) / 2
                
                # 현재가가 중간 가격보다 낮으면 매수
                strength = min(1.0, spread_percent / self.spread_threshold)
                
                if current_price < mid_price * 0.999:
                    return Signal(
                        timestamp=market_data[-1].timestamp,
                        strategy='market_making',
                        action='BUY',
                        strength=strength,
                        price=current_price,
                        reason=f"Market making buy: spread {spread_percent:.3%}"
                    )
                # 현재가가 중간 가격보다 높으면 매도
                elif current_price > mid_price * 1.001:
                    return Signal(
                        timestamp=market_data[-1].timestamp,
                        strategy='market_making',
                        action='SELL',
                        strength=strength,
                        price=current_price,
                        reason=f"Market making sell: spread {spread_percent:.3%}"
                    )
                else:
                    # 조건 미충족시에도 신호 강도 반환 (HOLD)
                    return Signal(
                        timestamp=market_data[-1].timestamp,
                        strategy='market_making',
                        action='HOLD',
                        strength=strength,
                        price=current_price,
                        reason=f"Spread: {spread_percent:.3%}, volatility: {volatility:.3f}"
                    )
            else:
                # 스프레드가 좁거나 변동성이 높은 경우에도 신호 반환
                strength = min(1.0, spread_percent / self.spread_threshold) if spread_percent > 0 else 0
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='market_making',
                    action='HOLD',
                    strength=strength,
                    price=current_price,
                    reason=f"Spread: {spread_percent:.3%}, volatility: {volatility:.3f}"
                )
                    
        except Exception as e:
            logger.error(f"Market making strategy error: {e}")
            
        return None
        

class StatisticalArbitrageStrategy(BaseStrategy):
    """통계적 차익거래 전략"""
    
    def __init__(self, weight: float = 0.2, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.lookback = params.get('lookback_period', 1000)
        self.entry_zscore = params.get('entry_zscore', 2.0)
        self.exit_zscore = params.get('exit_zscore', 0.5)
        
    async def generate_signal(self, market_data: List) -> Optional[Signal]:
        """통계적 차익거래 신호 생성"""
        try:
            if len(market_data) < self.lookback:
                return None
                
            # 가격 데이터 추출
            prices = pd.Series([d.price for d in market_data[-self.lookback:]])
            
            # 로그 수익률 계산
            log_returns = np.log(prices / prices.shift(1)).dropna()
            
            # 평균 회귀 테스트 (Augmented Dickey-Fuller)
            # 간단한 버전: Z-score 계산
            mean = prices.mean()
            std = prices.std()
            current_price = prices.iloc[-1]
            zscore = (current_price - mean) / std
            
            # Z-score 기반 신호 - 항상 강도를 계산하여 반환
            strength = min(1.0, abs(zscore) / 3)
            
            if zscore < -self.entry_zscore:
                # 과매도 - 매수 신호
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='stat_arb',
                    action='BUY',
                    strength=strength,
                    price=current_price,
                    reason=f"Statistical arbitrage: Z-score {zscore:.2f} (oversold)"
                )
            elif zscore > self.entry_zscore:
                # 과매수 - 매도 신호
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='stat_arb',
                    action='SELL',
                    strength=strength,
                    price=current_price,
                    reason=f"Statistical arbitrage: Z-score {zscore:.2f} (overbought)"
                )
            else:
                # 조건 미충족시에도 신호 강도 반환 (HOLD)
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='stat_arb',
                    action='HOLD',
                    strength=strength,
                    price=current_price,
                    reason=f"Z-score: {zscore:.2f} (threshold: {self.entry_zscore})"
                )
                
        except Exception as e:
            logger.error(f"Statistical arbitrage strategy error: {e}")
            
        return None
        

class MicrostructureStrategy(BaseStrategy):
    """시장 미시구조 전략"""
    
    def __init__(self, weight: float = 0.2, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.flow_window = params.get('flow_window', 100)
        self.vwap_threshold = params.get('vwap_deviation_threshold', 0.002)
        
    async def generate_signal(self, market_data: List) -> Optional[Signal]:
        """마이크로구조 신호 생성"""
        try:
            if len(market_data) < self.flow_window:
                return None
                
            # 최근 데이터로 DataFrame 생성
            df = pd.DataFrame([{
                'price': d.price,
                'volume': d.volume if d.volume > 0 else 1,
                'bid': d.bid,
                'ask': d.ask,
                'spread': d.spread
            } for d in market_data[-self.flow_window:]])
            
            # VWAP 계산
            df['pv'] = df['price'] * df['volume']
            vwap = df['pv'].sum() / df['volume'].sum()
            
            current_price = df['price'].iloc[-1]
            
            # Order Flow Imbalance 계산
            # 간단한 버전: bid-ask 스프레드 변화
            spread_change = df['spread'].diff().mean()
            
            # VWAP 대비 현재가 편차
            vwap_deviation = (current_price - vwap) / vwap
            
            # 신호 생성 - 항상 강도를 계산하여 반환
            strength = min(1.0, abs(vwap_deviation) / self.vwap_threshold)
            
            if vwap_deviation < -self.vwap_threshold and spread_change < 0:
                # VWAP보다 낮고 스프레드 감소 - 매수
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='microstructure',
                    action='BUY',
                    strength=strength,
                    price=current_price,
                    reason=f"Microstructure: VWAP deviation {vwap_deviation:.3%}"
                )
            elif vwap_deviation > self.vwap_threshold and spread_change > 0:
                # VWAP보다 높고 스프레드 증가 - 매도
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='microstructure',
                    action='SELL',
                    strength=strength,
                    price=current_price,
                    reason=f"Microstructure: VWAP deviation {vwap_deviation:.3%}"
                )
            else:
                # 조건 미충족시에도 신호 강도 반환 (HOLD)
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='microstructure',
                    action='HOLD',
                    strength=strength,
                    price=current_price,
                    reason=f"VWAP dev: {vwap_deviation:.3%}, spread change: {spread_change:.5f}"
                )
                
        except Exception as e:
            logger.error(f"Microstructure strategy error: {e}")
            
        return None
        

class MomentumScalpingStrategy(BaseStrategy):
    """모멘텀 스캘핑 전략"""
    
    def __init__(self, weight: float = 0.15, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.momentum_period = params.get('momentum_period', 20)
        self.entry_threshold = params.get('entry_threshold', 0.002)
        
    async def generate_signal(self, market_data: List) -> Optional[Signal]:
        """모멘텀 스캘핑 신호 생성"""
        try:
            if len(market_data) < self.momentum_period:
                return None
                
            # 가격 데이터 추출
            prices = pd.Series([d.price for d in market_data[-self.momentum_period:]])
            
            # 로그 수익률 계산
            returns = np.log(prices / prices.shift(1)).dropna()
            
            # 가중 모멘텀 계산 (최근 데이터에 더 높은 가중치)
            weights = np.exp(np.linspace(-1, 0, len(returns)))
            weights /= weights.sum()
            weighted_momentum = np.dot(returns, weights)
            
            # 볼륨 확인 (실제로는 볼륨 데이터 필요)
            # 여기서는 스프레드로 대체
            avg_spread = np.mean([d.spread for d in market_data[-10:]])
            volume_surge = avg_spread < 0.001  # 스프레드가 좁으면 거래량 많다고 가정
            
            # 신호 생성 - 항상 강도를 계산하여 반환
            strength = min(1.0, abs(weighted_momentum) / (self.entry_threshold * 2))
            
            if weighted_momentum > self.entry_threshold and volume_surge:
                # 강한 상승 모멘텀
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='momentum_scalping',
                    action='BUY',
                    strength=strength,
                    price=market_data[-1].price,
                    reason=f"Momentum scalping: momentum {weighted_momentum:.4f}"
                )
            elif weighted_momentum < -self.entry_threshold and volume_surge:
                # 강한 하락 모멘텀
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='momentum_scalping',
                    action='SELL',
                    strength=strength,
                    price=market_data[-1].price,
                    reason=f"Momentum scalping: momentum {weighted_momentum:.4f}"
                )
            else:
                # 조건 미충족시에도 신호 강도 반환 (HOLD)
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='momentum_scalping',
                    action='HOLD',
                    strength=strength,
                    price=market_data[-1].price,
                    reason=f"Momentum: {weighted_momentum:.4f} (threshold: {self.entry_threshold})"
                )
                
        except Exception as e:
            logger.error(f"Momentum scalping strategy error: {e}")
            
        return None
        

class MeanReversionStrategy(BaseStrategy):
    """평균 회귀 전략"""
    
    def __init__(self, weight: float = 0.15, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.bb_period = params.get('bb_period', 20)
        self.bb_std = params.get('bb_std', 2.0)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        
    async def generate_signal(self, market_data: List) -> Optional[Signal]:
        """평균 회귀 신호 생성"""
        try:
            if len(market_data) < max(self.bb_period, 14):  # RSI needs 14
                return None
                
            # 가격 데이터 추출
            prices = pd.Series([d.price for d in market_data[-50:]])
            
            # 지표 계산
            indicators = self.calculate_indicators(prices)
            
            current_price = prices.iloc[-1]
            rsi = indicators['rsi']
            bb_upper = indicators['bb_upper']
            bb_lower = indicators['bb_lower']
            
            # 신호 생성 - 항상 강도를 계산하여 반환
            # BB 위치 계산 (0: 하단, 0.5: 중간, 1.0: 상단)
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5
            # RSI 정규화 (0-1 범위)
            rsi_normalized = rsi / 100
            
            if current_price < bb_lower and rsi < self.rsi_oversold:
                # 볼린저 밴드 하단 이탈 + RSI 과매도
                strength = ((self.rsi_oversold - rsi) / self.rsi_oversold) * 0.5 + \
                          ((bb_lower - current_price) / bb_lower) * 0.5
                          
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='mean_reversion',
                    action='BUY',
                    strength=min(1.0, strength),
                    price=current_price,
                    reason=f"Mean reversion: RSI {rsi:.1f}, below BB lower"
                )
            elif current_price > bb_upper and rsi > self.rsi_overbought:
                # 볼린저 밴드 상단 이탈 + RSI 과매수
                strength = ((rsi - self.rsi_overbought) / (100 - self.rsi_overbought)) * 0.5 + \
                          ((current_price - bb_upper) / bb_upper) * 0.5
                          
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='mean_reversion',
                    action='SELL',
                    strength=min(1.0, strength),
                    price=current_price,
                    reason=f"Mean reversion: RSI {rsi:.1f}, above BB upper"
                )
            else:
                # 조건 미충족시에도 신호 강도 반환 (HOLD)
                # 강도는 BB 위치와 RSI를 조합하여 계산
                if bb_position < 0.5:  # 하단 근처
                    strength = (0.5 - bb_position) * 0.5 + (0.5 - rsi_normalized) * 0.5
                else:  # 상단 근처
                    strength = (bb_position - 0.5) * 0.5 + (rsi_normalized - 0.5) * 0.5
                    
                return Signal(
                    timestamp=market_data[-1].timestamp,
                    strategy='mean_reversion',
                    action='HOLD',
                    strength=max(0, min(1.0, abs(strength))),
                    price=current_price,
                    reason=f"RSI: {rsi:.1f}, BB position: {bb_position:.2f}"
                )
                
        except Exception as e:
            logger.error(f"Mean reversion strategy error: {e}")
            
        return None


class RiskManager:
    """리스크 관리 클래스"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.positions = {}
        self.daily_pnl = 0
        self.max_drawdown = 0
        
    def check_position_limit(self, current_position: float, new_order: float) -> bool:
        """포지션 한도 체크"""
        max_position = self.config.get('max_position', 10000000)
        return (current_position + new_order) <= max_position
        
    def check_daily_loss_limit(self) -> bool:
        """일일 손실 한도 체크"""
        max_daily_loss = self.config.get('max_daily_loss_percent', 5.0)
        return self.daily_pnl > -(max_daily_loss / 100)
        
    def calculate_position_size_kelly(self, win_rate: float, win_loss_ratio: float) -> float:
        """Kelly Criterion으로 포지션 크기 계산"""
        if win_loss_ratio <= 0:
            return 0.01
            
        # Kelly formula: f = (p * b - q) / b
        # where p = win_rate, q = 1-p, b = win_loss_ratio
        q = 1 - win_rate
        kelly_fraction = (win_rate * win_loss_ratio - q) / win_loss_ratio
        
        # 안전을 위해 Kelly의 25%만 사용
        safe_fraction = max(0.01, min(kelly_fraction * 0.25, 0.1))
        
        return safe_fraction
        
    def calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """Value at Risk 계산"""
        if len(returns) < 30:
            return 0
            
        # Parametric VaR
        mean = returns.mean()
        std = returns.std()
        
        # Z-score for confidence level
        z_score = stats.norm.ppf(1 - confidence)
        
        var = mean + z_score * std
        
        return abs(var)
        
    def calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """샤프 비율 계산"""
        if len(returns) < 30:
            return 0
            
        # 연율화
        daily_rf = risk_free_rate / 365
        excess_returns = returns - daily_rf
        
        if excess_returns.std() == 0:
            return 0
            
        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(365)
        
        return sharpe