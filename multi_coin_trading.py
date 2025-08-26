"""
멀티 코인 트레이딩 시스템
BTC, ETH, SOL, XRP, DOGE 동시 거래
"""

import asyncio
import pyupbit
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import yaml
import redis
import json
from dataclasses import dataclass, asdict
from collections import defaultdict
import sqlite3

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class CoinConfig:
    """코인별 설정"""
    symbol: str
    allocation: float  # 자금 배분 비율
    strategy_weights: Dict[str, float]  # 전략 가중치
    min_order_size: float
    max_position: float
    volatility_adjustment: float  # 변동성 조정 계수
    
    def to_dict(self):
        return asdict(self)


class MultiCoinTrader:
    """멀티 코인 트레이더"""
    
    # 거래 대상 코인 설정
    COIN_CONFIGS = {
        'KRW-BTC': CoinConfig(
            symbol='KRW-BTC',
            allocation=0.30,  # 30%
            strategy_weights={
                'market_making': 0.3,
                'statistical_arbitrage': 0.2,
                'microstructure': 0.2,
                'momentum_scalping': 0.15,
                'mean_reversion': 0.15
            },
            min_order_size=5000,
            max_position=3000000,
            volatility_adjustment=1.0
        ),
        'KRW-ETH': CoinConfig(
            symbol='KRW-ETH',
            allocation=0.25,  # 25%
            strategy_weights={
                'market_making': 0.25,
                'statistical_arbitrage': 0.25,
                'microstructure': 0.15,
                'momentum_scalping': 0.20,
                'mean_reversion': 0.15
            },
            min_order_size=5000,
            max_position=2500000,
            volatility_adjustment=1.2
        ),
        'KRW-SOL': CoinConfig(
            symbol='KRW-SOL',
            allocation=0.20,  # 20%
            strategy_weights={
                'market_making': 0.2,
                'statistical_arbitrage': 0.15,
                'microstructure': 0.15,
                'momentum_scalping': 0.30,  # 고변동성 활용
                'mean_reversion': 0.20
            },
            min_order_size=5000,
            max_position=2000000,
            volatility_adjustment=1.5
        ),
        'KRW-XRP': CoinConfig(
            symbol='KRW-XRP',
            allocation=0.15,  # 15%
            strategy_weights={
                'market_making': 0.25,
                'statistical_arbitrage': 0.20,
                'microstructure': 0.15,
                'momentum_scalping': 0.25,
                'mean_reversion': 0.15
            },
            min_order_size=5000,
            max_position=1500000,
            volatility_adjustment=1.3
        ),
        'KRW-DOGE': CoinConfig(
            symbol='KRW-DOGE',
            allocation=0.10,  # 10%
            strategy_weights={
                'market_making': 0.15,
                'statistical_arbitrage': 0.10,
                'microstructure': 0.10,
                'momentum_scalping': 0.40,  # 극고변동성
                'mean_reversion': 0.25
            },
            min_order_size=5000,
            max_position=1000000,
            volatility_adjustment=2.0
        )
    }
    
    def __init__(self, config_path='config/config.yaml'):
        self.config = self._load_config(config_path)
        self.upbit = self._init_upbit()
        self.redis_client = self._init_redis()
        self.db = self._init_database()
        
        # 코인별 상태 추적
        self.coin_states = {}
        self.positions = defaultdict(float)
        self.daily_pnl = defaultdict(float)
        
        # 전략 모듈 (각 코인에 대해 독립적으로 실행)
        self.strategies = {}
        
        # 성능 추적
        self.performance_tracker = PerformanceTracker()
        
    def _load_config(self, config_path):
        """설정 파일 로드"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _init_upbit(self):
        """Upbit API 초기화"""
        import os
        from dotenv import load_dotenv
        load_dotenv('config/.env')
        
        return pyupbit.Upbit(
            os.getenv('UPBIT_ACCESS_KEY'),
            os.getenv('UPBIT_SECRET_KEY')
        )
    
    def _init_redis(self):
        """Redis 초기화"""
        try:
            r = redis.Redis(
                host=self.config['redis']['host'],
                port=self.config['redis']['port'],
                db=self.config['redis']['db'],
                decode_responses=True
            )
            r.ping()
            return r
        except:
            logger.warning("Redis not available")
            return None
    
    def _init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect('data/multi_coin.db')
        cursor = conn.cursor()
        
        # 멀티 코인 거래 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                coin TEXT,
                strategy TEXT,
                side TEXT,
                price REAL,
                quantity REAL,
                amount REAL,
                fee REAL,
                pnl REAL,
                signal_strength REAL,
                market_conditions TEXT
            )
        ''')
        
        # 포지션 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                coin TEXT PRIMARY KEY,
                quantity REAL,
                avg_price REAL,
                current_value REAL,
                unrealized_pnl REAL,
                last_updated DATETIME
            )
        ''')
        
        conn.commit()
        return conn
    
    async def initialize(self):
        """초기화 및 상태 복원"""
        
        logger.info("Initializing multi-coin trading system...")
        
        # 각 코인별 전략 초기화
        for symbol, config in self.COIN_CONFIGS.items():
            self.strategies[symbol] = CoinStrategyManager(
                symbol=symbol,
                config=config,
                upbit=self.upbit
            )
            
            # 현재 포지션 확인
            balance = self.upbit.get_balance(symbol.split('-')[1])
            if balance > 0:
                self.positions[symbol] = balance
                logger.info(f"{symbol}: Current position {balance}")
        
        # 이전 상태 복원
        self._restore_state()
        
        logger.info("Multi-coin system initialized")
    
    async def run(self):
        """메인 실행 루프"""
        
        await self.initialize()
        
        logger.info("Starting multi-coin trading...")
        
        while True:
            try:
                # 모든 코인 동시 처리
                tasks = []
                
                for symbol in self.COIN_CONFIGS.keys():
                    tasks.append(self.process_coin(symbol))
                
                # 병렬 실행
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 결과 처리
                for symbol, result in zip(self.COIN_CONFIGS.keys(), results):
                    if isinstance(result, Exception):
                        logger.error(f"{symbol}: {result}")
                
                # 포트폴리오 리밸런싱 체크
                await self.check_rebalancing()
                
                # 리스크 관리
                await self.check_risk_limits()
                
                # 성능 추적
                self.performance_tracker.update(self.positions, self.daily_pnl)
                
                # 대기
                await asyncio.sleep(self.config['trading']['interval'])
                
            except KeyboardInterrupt:
                logger.info("Stopping multi-coin trading...")
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(5)
    
    async def process_coin(self, symbol: str):
        """개별 코인 처리"""
        
        try:
            config = self.COIN_CONFIGS[symbol]
            strategy_manager = self.strategies[symbol]
            
            # 1. 시장 데이터 수집
            market_data = await self.collect_market_data(symbol)
            
            # 2. 전략 실행
            signal = await strategy_manager.generate_signal(market_data)
            
            # 3. 신호 검증
            if self.validate_signal(symbol, signal):
                
                # 4. 포지션 크기 계산
                position_size = self.calculate_position_size(
                    symbol, 
                    signal,
                    config
                )
                
                # 5. 주문 실행
                if position_size > config.min_order_size:
                    order = await self.execute_order(
                        symbol,
                        signal,
                        position_size
                    )
                    
                    # 6. 거래 기록
                    if order:
                        self.record_trade(symbol, signal, order)
                        
                        # Redis에 상태 업데이트
                        self.update_redis_state(symbol, signal, order)
            
            return True
            
        except Exception as e:
            logger.error(f"{symbol} processing error: {e}")
            raise
    
    async def collect_market_data(self, symbol: str) -> Dict:
        """시장 데이터 수집"""
        
        # 현재가
        current_price = self.upbit.get_current_price(symbol)
        
        # 호가창
        orderbook = pyupbit.get_orderbook(symbol)
        
        # OHLCV
        ohlcv = pyupbit.get_ohlcv(symbol, interval='minute1', count=100)
        
        # 기술 지표 계산
        indicators = self.calculate_indicators(ohlcv)
        
        # 시장 상태
        market_state = self.analyze_market_state(ohlcv, orderbook)
        
        return {
            'symbol': symbol,
            'price': current_price,
            'orderbook': orderbook,
            'ohlcv': ohlcv,
            'indicators': indicators,
            'market_state': market_state,
            'timestamp': datetime.now()
        }
    
    def calculate_indicators(self, ohlcv: pd.DataFrame) -> Dict:
        """기술 지표 계산"""
        
        if ohlcv is None or len(ohlcv) < 20:
            return {}
        
        indicators = {}
        
        # 이동평균
        indicators['sma_20'] = ohlcv['close'].rolling(20).mean().iloc[-1]
        indicators['ema_10'] = ohlcv['close'].ewm(span=10).mean().iloc[-1]
        
        # RSI
        indicators['rsi'] = self.calculate_rsi(ohlcv['close'])
        
        # Bollinger Bands
        bb = self.calculate_bollinger_bands(ohlcv['close'])
        indicators.update(bb)
        
        # Volume indicators
        indicators['volume_ratio'] = ohlcv['volume'].iloc[-1] / ohlcv['volume'].rolling(20).mean().iloc[-1]
        
        # Volatility
        indicators['volatility'] = ohlcv['close'].pct_change().rolling(20).std().iloc[-1]
        
        return indicators
    
    def calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return (100 - 100 / (1 + rs)).iloc[-1]
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """볼린저 밴드 계산"""
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        
        return {
            'bb_upper': (sma + std_dev * std).iloc[-1],
            'bb_middle': sma.iloc[-1],
            'bb_lower': (sma - std_dev * std).iloc[-1],
            'bb_position': (prices.iloc[-1] - (sma - std_dev * std).iloc[-1]) / (2 * std_dev * std).iloc[-1]
        }
    
    def analyze_market_state(self, ohlcv: pd.DataFrame, orderbook: Dict) -> Dict:
        """시장 상태 분석"""
        
        if ohlcv is None or len(ohlcv) < 20:
            return {'trend': 'unknown', 'volatility': 'unknown'}
        
        # 추세 판단
        sma_20 = ohlcv['close'].rolling(20).mean()
        sma_50 = ohlcv['close'].rolling(50).mean() if len(ohlcv) >= 50 else sma_20
        
        if sma_20.iloc[-1] > sma_50.iloc[-1]:
            trend = 'bullish'
        elif sma_20.iloc[-1] < sma_50.iloc[-1]:
            trend = 'bearish'
        else:
            trend = 'sideways'
        
        # 변동성 레벨
        volatility = ohlcv['close'].pct_change().rolling(20).std().iloc[-1]
        
        if volatility < 0.01:
            vol_level = 'low'
        elif volatility < 0.03:
            vol_level = 'medium'
        else:
            vol_level = 'high'
        
        # 호가창 불균형
        if orderbook:
            bid_volume = sum([order[1] for order in orderbook[0]['orderbook_units'][:5]])
            ask_volume = sum([order[1] for order in orderbook[0]['orderbook_units'][:5]])
            
            imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
        else:
            imbalance = 0
        
        return {
            'trend': trend,
            'volatility': vol_level,
            'volatility_value': volatility,
            'orderbook_imbalance': imbalance
        }
    
    def validate_signal(self, symbol: str, signal: Dict) -> bool:
        """신호 검증"""
        
        if not signal:
            return False
        
        # 신호 강도 체크
        if signal.get('strength', 0) < self.config['trading']['signal_threshold']:
            return False
        
        # 포지션 한도 체크
        config = self.COIN_CONFIGS[symbol]
        current_position_value = self.positions.get(symbol, 0) * self.upbit.get_current_price(symbol)
        
        if current_position_value >= config.max_position:
            logger.warning(f"{symbol}: Position limit reached")
            return False
        
        # 일일 손실 한도 체크
        if self.daily_pnl[symbol] < -config.max_position * 0.05:  # 5% 손실
            logger.warning(f"{symbol}: Daily loss limit reached")
            return False
        
        return True
    
    def calculate_position_size(self, symbol: str, signal: Dict, config: CoinConfig) -> float:
        """포지션 크기 계산"""
        
        # 기본 크기
        base_size = config.max_position * config.allocation
        
        # 신호 강도 조정
        signal_adjustment = min(signal.get('strength', 0.5) * 2, 1.5)
        
        # 변동성 조정
        volatility = signal.get('market_data', {}).get('indicators', {}).get('volatility', 0.02)
        vol_adjustment = 1 / (1 + volatility * config.volatility_adjustment * 10)
        
        # 켈리 기준 (간단화)
        win_rate = self.performance_tracker.get_win_rate(symbol)
        if win_rate > 0:
            kelly_factor = min((win_rate - 0.5) * 2, 0.25)  # 최대 25% 켈리
        else:
            kelly_factor = 0.05  # 초기값
        
        # 최종 크기
        position_size = base_size * signal_adjustment * vol_adjustment * kelly_factor
        
        # 최소/최대 제한
        position_size = max(config.min_order_size, min(position_size, config.max_position))
        
        return round(position_size, -3)  # 1000원 단위
    
    async def execute_order(self, symbol: str, signal: Dict, size: float) -> Optional[Dict]:
        """주문 실행"""
        
        try:
            if signal['action'] == 'BUY':
                order = self.upbit.buy_market_order(symbol, size)
            elif signal['action'] == 'SELL':
                # 보유 수량 확인
                coin = symbol.split('-')[1]
                balance = self.upbit.get_balance(coin)
                
                if balance > 0:
                    order = self.upbit.sell_market_order(symbol, balance)
                else:
                    logger.warning(f"{symbol}: No balance to sell")
                    return None
            else:
                return None
            
            logger.info(f"{symbol}: Order executed - {signal['action']} {size:,.0f} KRW")
            
            return order
            
        except Exception as e:
            logger.error(f"{symbol}: Order execution failed - {e}")
            return None
    
    def record_trade(self, symbol: str, signal: Dict, order: Dict):
        """거래 기록"""
        
        cursor = self.db.cursor()
        
        cursor.execute('''
            INSERT INTO trades (
                coin, strategy, side, price, quantity, amount, 
                fee, pnl, signal_strength, market_conditions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol,
            signal.get('strategy', 'unknown'),
            signal['action'],
            order.get('price', 0),
            order.get('executed_volume', 0),
            order.get('executed_funds', 0),
            order.get('paid_fee', 0),
            0,  # PnL은 나중에 계산
            signal.get('strength', 0),
            json.dumps(signal.get('market_state', {}))
        ))
        
        self.db.commit()
    
    def update_redis_state(self, symbol: str, signal: Dict, order: Dict):
        """Redis 상태 업데이트"""
        
        if not self.redis_client:
            return
        
        state = {
            'symbol': symbol,
            'last_trade': datetime.now().isoformat(),
            'action': signal['action'],
            'price': order.get('price', 0),
            'signal_strength': signal.get('strength', 0),
            'position': self.positions.get(symbol, 0)
        }
        
        self.redis_client.hset(f"coin:{symbol}", mapping=state)
        self.redis_client.expire(f"coin:{symbol}", 3600)  # 1시간
    
    async def check_rebalancing(self):
        """포트폴리오 리밸런싱 체크"""
        
        # 총 자산 계산
        total_value = 0
        current_allocations = {}
        
        for symbol in self.COIN_CONFIGS.keys():
            coin = symbol.split('-')[1]
            balance = self.upbit.get_balance(coin)
            price = self.upbit.get_current_price(symbol)
            
            value = balance * price if balance and price else 0
            total_value += value
            current_allocations[symbol] = value
        
        # KRW 잔고 추가
        krw_balance = self.upbit.get_balance('KRW')
        total_value += krw_balance
        
        if total_value == 0:
            return
        
        # 목표 대비 편차 체크
        needs_rebalancing = False
        
        for symbol, config in self.COIN_CONFIGS.items():
            current_pct = current_allocations.get(symbol, 0) / total_value
            target_pct = config.allocation
            
            # 10% 이상 편차시 리밸런싱
            if abs(current_pct - target_pct) > 0.1:
                needs_rebalancing = True
                logger.info(f"{symbol}: Allocation drift - Current: {current_pct:.2%}, Target: {target_pct:.2%}")
        
        if needs_rebalancing:
            logger.info("Portfolio rebalancing needed")
            # TODO: 리밸런싱 실행 로직
    
    async def check_risk_limits(self):
        """리스크 한도 체크"""
        
        # 일일 손실 체크
        total_daily_loss = sum(self.daily_pnl.values())
        max_daily_loss = self.config['risk_management']['limits']['max_daily_loss_percent']
        
        if total_daily_loss < -max_daily_loss * 100000:  # 임시 기준
            logger.warning(f"Daily loss limit approaching: {total_daily_loss:,.0f} KRW")
            
            # 거래 축소 또는 중단
            # TODO: 구현 필요
    
    def _restore_state(self):
        """이전 상태 복원"""
        
        cursor = self.db.cursor()
        
        # 오늘 PnL 계산
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT coin, SUM(pnl) 
            FROM trades 
            WHERE DATE(timestamp) = ?
            GROUP BY coin
        """, (today,))
        
        for coin, pnl in cursor.fetchall():
            self.daily_pnl[coin] = pnl or 0
    
    def _save_state(self):
        """현재 상태 저장"""
        
        cursor = self.db.cursor()
        
        for symbol, position in self.positions.items():
            price = self.upbit.get_current_price(symbol)
            
            cursor.execute('''
                INSERT OR REPLACE INTO positions 
                (coin, quantity, avg_price, current_value, unrealized_pnl, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                position,
                0,  # TODO: 평균 가격 계산
                position * price if price else 0,
                0,  # TODO: 미실현 손익 계산
                datetime.now()
            ))
        
        self.db.commit()


class CoinStrategyManager:
    """코인별 전략 관리자"""
    
    def __init__(self, symbol: str, config: CoinConfig, upbit):
        self.symbol = symbol
        self.config = config
        self.upbit = upbit
        
    async def generate_signal(self, market_data: Dict) -> Dict:
        """통합 신호 생성"""
        
        signals = []
        
        # 각 전략 실행
        for strategy_name, weight in self.config.strategy_weights.items():
            if weight > 0:
                signal = await self.run_strategy(strategy_name, market_data)
                if signal:
                    signal['weight'] = weight
                    signals.append(signal)
        
        # 신호 통합
        if not signals:
            return None
        
        # 가중 평균
        total_weight = sum(s['weight'] for s in signals)
        weighted_strength = sum(s['strength'] * s['weight'] for s in signals) / total_weight
        
        # 최종 액션 결정
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        sell_signals = [s for s in signals if s['action'] == 'SELL']
        
        if len(buy_signals) > len(sell_signals):
            action = 'BUY'
        elif len(sell_signals) > len(buy_signals):
            action = 'SELL'
        else:
            action = 'HOLD'
        
        return {
            'action': action,
            'strength': weighted_strength,
            'strategy': 'ensemble',
            'market_data': market_data,
            'component_signals': signals
        }
    
    async def run_strategy(self, strategy_name: str, market_data: Dict) -> Optional[Dict]:
        """개별 전략 실행"""
        
        if strategy_name == 'momentum_scalping':
            return self.momentum_scalping(market_data)
        elif strategy_name == 'mean_reversion':
            return self.mean_reversion(market_data)
        elif strategy_name == 'market_making':
            return self.market_making(market_data)
        # TODO: 다른 전략들 구현
        
        return None
    
    def momentum_scalping(self, market_data: Dict) -> Optional[Dict]:
        """모멘텀 스캘핑 전략"""
        
        indicators = market_data.get('indicators', {})
        
        if not indicators:
            return None
        
        # 모멘텀 판단
        current_price = market_data['price']
        ema_10 = indicators.get('ema_10', current_price)
        volume_ratio = indicators.get('volume_ratio', 1)
        
        signal = None
        
        # 상승 모멘텀
        if current_price > ema_10 * 1.002 and volume_ratio > 1.5:
            signal = {
                'action': 'BUY',
                'strength': min((current_price / ema_10 - 1) * 100, 1.0),
                'strategy': 'momentum_scalping'
            }
        # 하락 모멘텀
        elif current_price < ema_10 * 0.998 and volume_ratio > 1.5:
            signal = {
                'action': 'SELL',
                'strength': min((1 - current_price / ema_10) * 100, 1.0),
                'strategy': 'momentum_scalping'
            }
        
        return signal
    
    def mean_reversion(self, market_data: Dict) -> Optional[Dict]:
        """평균 회귀 전략"""
        
        indicators = market_data.get('indicators', {})
        
        if not indicators:
            return None
        
        rsi = indicators.get('rsi', 50)
        bb_position = indicators.get('bb_position', 0.5)
        
        signal = None
        
        # 과매도
        if rsi < 30 and bb_position < 0.2:
            signal = {
                'action': 'BUY',
                'strength': (30 - rsi) / 30 * (0.2 - bb_position) / 0.2,
                'strategy': 'mean_reversion'
            }
        # 과매수
        elif rsi > 70 and bb_position > 0.8:
            signal = {
                'action': 'SELL',
                'strength': (rsi - 70) / 30 * (bb_position - 0.8) / 0.2,
                'strategy': 'mean_reversion'
            }
        
        return signal
    
    def market_making(self, market_data: Dict) -> Optional[Dict]:
        """마켓 메이킹 전략"""
        
        orderbook = market_data.get('orderbook', {})
        
        if not orderbook:
            return None
        
        # 스프레드 계산
        if orderbook and len(orderbook) > 0 and 'orderbook_units' in orderbook[0]:
            units = orderbook[0]['orderbook_units']
            if units:
                bid = units[0]['bid_price']
                ask = units[0]['ask_price']
                spread = (ask - bid) / bid
                
                # 스프레드가 충분히 넓을 때
                if spread > 0.002:  # 0.2%
                    return {
                        'action': 'BUY',  # 또는 SELL
                        'strength': min(spread * 100, 1.0),
                        'strategy': 'market_making'
                    }
        
        return None


class PerformanceTracker:
    """성능 추적"""
    
    def __init__(self):
        self.trades = defaultdict(list)
        self.daily_stats = {}
        
    def update(self, positions: Dict, daily_pnl: Dict):
        """성능 업데이트"""
        
        self.daily_stats = {
            'timestamp': datetime.now(),
            'positions': dict(positions),
            'daily_pnl': dict(daily_pnl),
            'total_pnl': sum(daily_pnl.values())
        }
    
    def get_win_rate(self, symbol: str) -> float:
        """승률 계산"""
        
        if symbol not in self.trades or not self.trades[symbol]:
            return 0.5  # 기본값
        
        wins = sum(1 for trade in self.trades[symbol] if trade['pnl'] > 0)
        total = len(self.trades[symbol])
        
        return wins / total if total > 0 else 0.5


async def main():
    """메인 실행"""
    
    trader = MultiCoinTrader()
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())