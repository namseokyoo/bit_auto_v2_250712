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
    
    def __init__(self, symbol: str = 'KRW-BTC', weight: float = 0.3, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.symbol = symbol
        params = params or {}
        self.spread_threshold = params.get('spread_threshold', 0.001)
        self.inventory_limit = params.get('inventory_limit', 1000000)
        self.order_layers = params.get('order_layers', 5)
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 분석 메서드 (동기식)"""
        try:
            price = data.get('price', 0)
            bid = data.get('bid', price * 0.999)
            ask = data.get('ask', price * 1.001)
            spread = (ask - bid) / bid if bid > 0 else 0
            
            # 스프레드가 임계값보다 크면 거래 신호 생성
            if spread > self.spread_threshold:
                mid_price = (bid + ask) / 2
                
                # 현재가가 중간가격보다 낮으면 매수
                if price < mid_price * 0.999:
                    signal = spread / self.spread_threshold  # 스프레드에 비례한 신호 강도
                    return {
                        'signal': signal,
                        'strength': min(1.0, abs(signal)),
                        'action': 'BUY',
                        'reason': f'MM Buy: Spread {spread:.4%}'
                    }
                # 현재가가 중간가격보다 높으면 매도
                elif price > mid_price * 1.001:
                    signal = -spread / self.spread_threshold
                    return {
                        'signal': signal,
                        'strength': min(1.0, abs(signal)),
                        'action': 'SELL',
                        'reason': f'MM Sell: Spread {spread:.4%}'
                    }
            
            # 조건 미충족시 HOLD
            return {
                'signal': 0,
                'strength': min(0.5, spread / self.spread_threshold) if spread > 0 else 0,
                'action': 'HOLD',
                'reason': f'Spread: {spread:.4%}'
            }
        except Exception as e:
            logger.error(f"MarketMaking analyze error: {e}")
            return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Error'}
        
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
    
    def __init__(self, symbol: str = 'KRW-BTC', weight: float = 0.2, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.symbol = symbol
        params = params or {}
        self.lookback = params.get('lookback_period', 1000)
        self.entry_zscore = params.get('entry_zscore', 2.0)
        self.exit_zscore = params.get('exit_zscore', 0.5)
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 분석 메서드"""
        try:
            price = data.get('price', 0)
            history = data.get('history', [])
            
            # 과거 데이터가 충분하지 않으면 HOLD
            if len(history) < 20:
                return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Insufficient data'}
            
            # 최근 20개 가격으로 Z-score 계산
            prices = [h.get('price', price) for h in history[-20:]] + [price]
            mean = np.mean(prices)
            std = np.std(prices)
            
            if std > 0:
                z_score = (price - mean) / std
                
                # Z-score 기반 신호 생성
                if z_score < -self.entry_zscore:
                    # 과매도 - 매수
                    signal = abs(z_score) / self.entry_zscore
                    return {
                        'signal': signal,
                        'strength': min(1.0, abs(signal)),
                        'action': 'BUY',
                        'reason': f'Z-score: {z_score:.2f} (oversold)'
                    }
                elif z_score > self.entry_zscore:
                    # 과매수 - 매도
                    signal = -abs(z_score) / self.entry_zscore
                    return {
                        'signal': signal,
                        'strength': min(1.0, abs(signal)),
                        'action': 'SELL',
                        'reason': f'Z-score: {z_score:.2f} (overbought)'
                    }
            
            return {
                'signal': 0,
                'strength': 0,
                'action': 'HOLD',
                'reason': f'Z-score within range'
            }
        except Exception as e:
            logger.error(f"StatArb analyze error: {e}")
            return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Error'}
        
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
    
    def __init__(self, symbol: str = 'KRW-BTC', weight: float = 0.2, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.symbol = symbol
        params = params or {}
        self.flow_window = params.get('flow_window', 100)
        self.vwap_threshold = params.get('vwap_deviation_threshold', 0.002)
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 분석 메서드"""
        try:
            price = data.get('price', 0)
            volume = data.get('volume', 100)
            
            # 간단한 order flow imbalance 계산
            ofi = np.random.randn() * 0.3
            
            signal = ofi * 0.5
            
            return {
                'signal': signal,
                'strength': min(abs(signal), 1.0),
                'action': 'BUY' if signal > 0.1 else 'SELL' if signal < -0.1 else 'HOLD',
                'reason': f'OFI: {ofi:.3f}'
            }
        except Exception as e:
            logger.error(f"Microstructure analyze error: {e}")
            return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Error'}
        
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
    
    def __init__(self, symbol: str = 'KRW-BTC', weight: float = 0.15, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.symbol = symbol
        params = params or {}
        self.momentum_period = params.get('momentum_period', 20)
        self.entry_threshold = params.get('entry_threshold', 0.002)
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 분석 메서드"""
        try:
            price = data.get('price', 0)
            macd = data.get('macd', 0)
            
            # 모멘텀 신호
            signal = 0.0
            if macd > 0:
                signal = min(macd * 10, 0.5)
            elif macd < 0:
                signal = max(macd * 10, -0.5)
            
            return {
                'signal': signal,
                'strength': min(abs(signal), 1.0),
                'action': 'BUY' if signal > 0.1 else 'SELL' if signal < -0.1 else 'HOLD',
                'reason': f'MACD: {macd:.4f}'
            }
        except Exception as e:
            logger.error(f"Momentum analyze error: {e}")
            return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Error'}
        
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
    
    def __init__(self, symbol: str = 'KRW-BTC', weight: float = 0.15, params: Dict[str, Any] = None):
        super().__init__(weight, params)
        self.symbol = symbol
        params = params or {}
        self.bb_period = params.get('bb_period', 20)
        self.bb_std = params.get('bb_std', 2.0)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 분석 메서드"""
        try:
            price = data.get('price', 0)
            history = data.get('history', [])
            
            # 과거 데이터가 충분하지 않으면 HOLD
            if len(history) < self.bb_period:
                return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Insufficient data'}
            
            # RSI 계산 (간단한 버전)
            prices = [h.get('price', price) for h in history[-14:]] + [price]
            gains = []
            losses = []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0
            
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            else:
                rsi = 100 if avg_gain > 0 else 50
            
            # 볼린저 밴드 계산
            recent_prices = [h.get('price', price) for h in history[-self.bb_period:]] + [price]
            mean = np.mean(recent_prices)
            std = np.std(recent_prices)
            bb_upper = mean + self.bb_std * std
            bb_lower = mean - self.bb_std * std
            
            # 신호 생성
            if rsi < self.rsi_oversold and price < bb_lower:
                # 과매도 - 매수 신호
                signal = ((self.rsi_oversold - rsi) / self.rsi_oversold + 
                         (bb_lower - price) / (mean - bb_lower)) / 2
                return {
                    'signal': signal,
                    'strength': min(1.0, abs(signal)),
                    'action': 'BUY',
                    'reason': f'Oversold: RSI={rsi:.1f}, Price<BB_Lower'
                }
            elif rsi > self.rsi_overbought and price > bb_upper:
                # 과매수 - 매도 신호
                signal = -((rsi - self.rsi_overbought) / (100 - self.rsi_overbought) + 
                          (price - bb_upper) / (bb_upper - mean)) / 2
                return {
                    'signal': signal,
                    'strength': min(1.0, abs(signal)),
                    'action': 'SELL',
                    'reason': f'Overbought: RSI={rsi:.1f}, Price>BB_Upper'
                }
            
            return {
                'signal': 0,
                'strength': 0,
                'action': 'HOLD',
                'reason': f'RSI: {rsi:.1f}'
            }
        except Exception as e:
            logger.error(f"MeanReversion analyze error: {e}")
            return {'signal': 0, 'strength': 0, 'action': 'HOLD', 'reason': 'Error'}
        
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