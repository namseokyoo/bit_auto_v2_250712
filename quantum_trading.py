#!/usr/bin/env python3
"""
Quantum Trading System v3.0
고빈도 퀀트 트레이딩 시스템
"""

import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pyupbit
import redis
import yaml
from dotenv import load_dotenv

# 전략 클래스 import
from strategies import (
    MarketMakingStrategy,
    StatisticalArbitrageStrategy,
    MicrostructureStrategy,
    MomentumScalpingStrategy,
    MeanReversionStrategy
)

# 로깅 설정
import os
os.makedirs('logs', exist_ok=True)

# 로그 파일 경로
log_file = 'logs/quantum_trading.log'

# 파일 핸들러 생성
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# 루트 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

# urllib3와 다른 노이즈 로거들 비활성화
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

# 환경 변수 로드
load_dotenv('.env')

@dataclass
class MarketData:
    """시장 데이터"""
    timestamp: float
    symbol: str
    price: float
    volume: float
    bid: float
    ask: float
    spread: float
    
@dataclass
class Signal:
    """거래 신호"""
    timestamp: float
    strategy: str
    action: str  # BUY, SELL, HOLD
    strength: float  # 0.0 ~ 1.0
    price: float
    reason: str

@dataclass
class Position:
    """포지션 정보"""
    symbol: str
    side: str  # long, short
    entry_price: float
    current_price: float
    quantity: float
    pnl: float
    pnl_percent: float


class QuantumTradingSystem:
    """메인 트레이딩 시스템"""
    
    def __init__(self, config_path='config/config.yaml'):
        """시스템 초기화"""
        self.running = False
        self.config = self.load_config(config_path)
        self.setup_connections()
        self.init_data_structures()
        self.init_strategies()
        self.setup_signal_handlers()
        
    def load_config(self, config_path: str) -> dict:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)
            
    def setup_connections(self):
        """외부 서비스 연결 설정"""
        # Upbit API 연결
        access_key = os.getenv('UPBIT_ACCESS_KEY')
        secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if not access_key or not secret_key:
            logger.error("Upbit API keys not found in environment variables")
            sys.exit(1)
            
        self.upbit = pyupbit.Upbit(access_key, secret_key)
        
        # Redis 연결
        try:
            self.redis = redis.Redis(
                host=self.config.get('redis', {}).get('host', 'localhost'),
                port=self.config.get('redis', {}).get('port', 6379),
                decode_responses=True
            )
            self.redis.ping()
            logger.info("Redis connected successfully")
        except:
            logger.warning("Redis not available, using in-memory cache")
            self.redis = None
            
        # SQLite 데이터베이스
        self.init_database()
        
    def init_database(self):
        """데이터베이스 초기화"""
        self.db = sqlite3.connect('data/quantum.db', check_same_thread=False)
        cursor = self.db.cursor()
        
        # 거래 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                strategy_name TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                quantity REAL,
                fee REAL,
                pnl REAL
            )
        ''')
        
        # 신호 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                strategy_name TEXT,
                action TEXT,
                strength REAL,
                price REAL,
                reason TEXT
            )
        ''')
        
        # 성능 지표 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                timestamp DATETIME PRIMARY KEY,
                total_balance REAL,
                position_value REAL,
                daily_pnl REAL,
                win_rate REAL,
                sharpe_ratio REAL
            )
        ''')
        
        self.db.commit()
        logger.info("Database initialized")
        
    def init_data_structures(self):
        """데이터 구조 초기화"""
        self.market_data = deque(maxlen=10000)  # 최근 10000개 틱 데이터
        self.orderbook = deque(maxlen=1000)     # 오더북 스냅샷
        self.signals = deque(maxlen=100)        # 최근 신호
        self.positions = {}                     # 현재 포지션
        self.pending_orders = {}                # 대기 중인 주문
        
    def init_strategies(self):
        """전략 초기화"""
        from strategies import (
            MarketMakingStrategy,
            StatisticalArbitrageStrategy,
            MicrostructureStrategy,
            MomentumScalpingStrategy,
            MeanReversionStrategy
        )
        
        self.strategies = {}
        
        # 전략 설정 로드 및 초기화
        strategy_config = self.config.get('strategies', {})
        
        if strategy_config.get('market_making', {}).get('enabled', True):
            self.strategies['market_making'] = MarketMakingStrategy(
                weight=strategy_config['market_making'].get('weight', 0.3),
                params=strategy_config['market_making'].get('params', {})
            )
            
        if strategy_config.get('statistical_arbitrage', {}).get('enabled', True):
            self.strategies['stat_arb'] = StatisticalArbitrageStrategy(
                weight=strategy_config['statistical_arbitrage'].get('weight', 0.2),
                params=strategy_config['statistical_arbitrage'].get('params', {})
            )
            
        if strategy_config.get('microstructure', {}).get('enabled', True):
            self.strategies['microstructure'] = MicrostructureStrategy(
                weight=strategy_config['microstructure'].get('weight', 0.2),
                params=strategy_config['microstructure'].get('params', {})
            )
            
        if strategy_config.get('momentum_scalping', {}).get('enabled', True):
            self.strategies['momentum'] = MomentumScalpingStrategy(
                weight=strategy_config['momentum_scalping'].get('weight', 0.15),
                params=strategy_config['momentum_scalping'].get('params', {})
            )
            
        if strategy_config.get('mean_reversion', {}).get('enabled', True):
            self.strategies['mean_reversion'] = MeanReversionStrategy(
                weight=strategy_config['mean_reversion'].get('weight', 0.15),
                params=strategy_config['mean_reversion'].get('params', {})
            )
            
        # 전략별 가중치 로그 출력
        weights_info = []
        for name, strategy in self.strategies.items():
            weights_info.append(f"{name}: {strategy.weight*100:.0f}%")
        
        logger.info(f"Initialized {len(self.strategies)} strategies with weights: {', '.join(weights_info)}")
        
    def setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        # 백그라운드 실행을 위해 시그널 핸들러 비활성화
        # signal.signal(signal.SIGINT, self.shutdown)
        # signal.signal(signal.SIGTERM, self.shutdown)
        pass
        
    def shutdown(self, signum=None, frame=None):
        """종료 처리"""
        logger.info("Shutting down Quantum Trading System...")
        self.running = False
        
        # 모든 포지션 청산 (선택적)
        # if self.positions:
        #     logger.info("Closing all positions...")
        #     self.close_all_positions()
            
        # 데이터베이스 닫기
        if hasattr(self, 'db'):
            self.db.close()
            
        logger.info("Shutdown complete")
        # sys.exit(0) 제거 - 백그라운드에서 계속 실행
        
    async def collect_market_data(self):
        """시장 데이터 수집"""
        logger.info("Starting market data collection...")
        while self.running:
            try:
                symbol = self.config['trading']['symbol']
                
                # 현재가 조회
                ticker = pyupbit.get_current_price(symbol)
                orderbook = pyupbit.get_orderbook(symbol)
                
                if ticker and orderbook:
                    # orderbook이 딕셔너리 형태로 반환됨
                    if isinstance(orderbook, dict) and 'orderbook_units' in orderbook:
                        units = orderbook['orderbook_units']
                        if units and len(units) > 0:
                            bid = units[0]['bid_price']
                            ask = units[0]['ask_price']
                        else:
                            bid = ticker * 0.999
                            ask = ticker * 1.001
                    else:
                        # 기본값 설정
                        bid = ticker * 0.999
                        ask = ticker * 1.001
                    
                    market_data = MarketData(
                        timestamp=time.time(),
                        symbol=symbol,
                        price=ticker,
                        volume=0,  # Volume은 별도 API 필요
                        bid=bid,
                        ask=ask,
                        spread=(ask - bid) / bid if bid > 0 else 0
                    )
                    
                    self.market_data.append(market_data)
                    
                    # 수집된 데이터 로그 (처음 10개만)
                    if len(self.market_data) <= 10:
                        logger.info(f"Market data collected #{len(self.market_data)}: Price={ticker:,.0f}, Bid={bid:,.0f}, Ask={ask:,.0f}")
                    elif len(self.market_data) == 100:
                        logger.info("Collected 100 market data points, starting signal generation...")
                    
                    # Redis 캐시 업데이트
                    if self.redis:
                        self.redis.set(
                            f"market:{symbol}:latest",
                            json.dumps(asdict(market_data))
                        )
                        
            except Exception as e:
                logger.error(f"Error collecting market data: {e}")
                
            await asyncio.sleep(1)  # 1초마다 수집
            
    async def generate_signals(self):
        """전략별 신호 생성"""
        logger.info("Starting signal generation...")
        while self.running:
            try:
                if len(self.market_data) < 100:
                    if len(self.market_data) % 10 == 0:
                        logger.info(f"Waiting for market data... ({len(self.market_data)}/100)")
                    await asyncio.sleep(1)
                    continue
                    
                # 각 전략에서 신호 생성
                signals = []
                logger.info(f"Checking {len(self.strategies)} strategies for signals...")
                for name, strategy in self.strategies.items():
                    if hasattr(strategy, 'generate_signal'):
                        try:
                            signal = await strategy.generate_signal(
                                list(self.market_data)
                            )
                            if signal:
                                signal.strategy = name
                                signals.append(signal)
                                logger.info(f"Signal from {name}: {signal.action} with strength {signal.strength:.2f}")
                        except Exception as e:
                            logger.error(f"Error generating signal from {name}: {e}")
                            
                # 신호 집계 및 최종 결정
                if signals:
                    logger.info(f"Total {len(signals)} signals generated, aggregating...")
                    final_signal = self.aggregate_signals(signals)
                    if final_signal:
                        logger.info(f"Final signal: {final_signal.action} with strength {final_signal.strength:.2f}")
                        self.signals.append(final_signal)
                        await self.execute_signal(final_signal)
                else:
                    logger.debug("No signals generated in this cycle")
                        
            except Exception as e:
                logger.error(f"Error generating signals: {e}")
                
            await asyncio.sleep(self.config['trading']['interval'])
            
    def aggregate_signals(self, signals: List[Signal]) -> Optional[Signal]:
        """신호 집계 및 가중 평균"""
        if not signals:
            return None
            
        buy_score = 0
        sell_score = 0
        
        # 전략별 신호 정보 저장 - 모든 전략을 0으로 초기화
        strategy_signals = {}
        
        # 먼저 모든 전략을 0으로 초기화
        for name, strategy in self.strategies.items():
            strategy_signals[name] = {
                'action': 'HOLD',
                'raw_signal': 0.0,
                'weight': strategy.weight,
                'weighted_signal': 0.0
            }
        
        # 실제 신호가 있는 전략들 업데이트
        for signal in signals:
            strategy_weight = self.strategies[signal.strategy].weight
            
            # 전략별 원본 신호와 가중치 적용 신호 저장
            strategy_signals[signal.strategy] = {
                'action': signal.action,
                'raw_signal': signal.strength,
                'weight': strategy_weight,
                'weighted_signal': signal.strength * strategy_weight
            }
            
            if signal.action == 'BUY':
                buy_score += signal.strength * strategy_weight
            elif signal.action == 'SELL':
                sell_score += signal.strength * strategy_weight
        
        # Redis나 메모리에 전략별 신호 저장
        self.save_strategy_signals(strategy_signals, buy_score, sell_score)
                
        # 임계값 체크 (설정 파일에서 읽기)
        threshold = self.config.get('trading', {}).get('signal_threshold', 0.25)  # 기본값 0.25로 수정
        
        # 로그 추가하여 디버깅
        logger.info(f"Aggregating signals - Buy: {buy_score:.3f}, Sell: {sell_score:.3f}, Threshold: {threshold}")
        
        # 임계값을 넘는 신호만 처리
        if buy_score > threshold and buy_score > sell_score:
            logger.info(f"Buy signal passes threshold check: {buy_score:.3f} > {threshold}")
            return Signal(
                timestamp=time.time(),
                strategy='ensemble',
                action='BUY',
                strength=buy_score,
                price=self.market_data[-1].price,
                reason=f"Ensemble buy signal (score: {buy_score:.2f})"
            )
        elif sell_score > threshold and sell_score > buy_score:
            logger.info(f"Sell signal passes threshold check: {sell_score:.3f} > {threshold}")
            return Signal(
                timestamp=time.time(),
                strategy='ensemble',
                action='SELL',
                strength=sell_score,
                price=self.market_data[-1].price,
                reason=f"Ensemble sell signal (score: {sell_score:.2f})"
            )
        else:
            logger.info(f"No signal passes threshold. Buy: {buy_score:.3f}, Sell: {sell_score:.3f} < {threshold}")
            
        return None
    
    def save_strategy_signals(self, strategy_signals: dict, buy_score: float, sell_score: float):
        """전략별 신호를 Redis 또는 메모리에 저장"""
        try:
            # Redis에 저장 시도
            if self.redis:
                logger.info(f"Saving {len(strategy_signals)} strategy signals to Redis")
                # 전략별 신호 저장
                for strategy, data in strategy_signals.items():
                    key = f"signal:{strategy}"
                    self.redis.hset(key, mapping={
                        'action': str(data['action']),
                        'raw_signal': str(data['raw_signal']),
                        'weight': str(data['weight']),
                        'weighted_signal': str(data['weighted_signal']),
                        'timestamp': str(time.time())
                    })
                    logger.debug(f"Saved signal for {strategy}: {data}")
                
                # 최종 집계 신호 저장
                action = 'HOLD'
                if buy_score > sell_score and buy_score > self.config.get('trading', {}).get('signal_threshold', 0.25):
                    action = 'BUY'
                elif sell_score > buy_score and sell_score > self.config.get('trading', {}).get('signal_threshold', 0.25):
                    action = 'SELL'
                
                self.redis.hset("signal:aggregate", mapping={
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'action': action,
                    'timestamp': time.time()
                })
                
                # 최종 점수 저장
                self.redis.hset("signal:final", mapping={
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'timestamp': time.time()
                })
                
                # 1분 후 만료
                for strategy in strategy_signals.keys():
                    self.redis.expire(f"signal:{strategy}", 60)
                self.redis.expire("signal:final", 60)
            else:
                # 메모리에 저장 (클래스 변수 사용)
                self.latest_signals = {
                    'strategies': strategy_signals,
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.error(f"Error saving strategy signals: {e}")
        
    async def execute_signal(self, signal: Signal):
        """신호 실행"""
        try:
            symbol = self.config['trading']['symbol']
            logger.info(f"Executing signal: {signal.action} for {symbol}")
            
            # 리스크 체크
            if not self.check_risk_limits():
                logger.warning("Risk limits exceeded, skipping trade")
                return
                
            # 포지션 크기 계산
            position_size = self.calculate_position_size(signal)
            logger.info(f"Calculated position size: {position_size:,.0f} KRW")
            
            if signal.action == 'BUY':
                # 매수 주문
                logger.info(f"Placing BUY order for {position_size:,.0f} KRW")
                order = self.upbit.buy_market_order(symbol, position_size)
                logger.info(f"Buy order placed: {order}")
                
            elif signal.action == 'SELL':
                # 매도 주문
                balance = self.upbit.get_balance(symbol.split('-')[1])
                if balance > 0:
                    order = self.upbit.sell_market_order(symbol, balance)
                    logger.info(f"Sell order placed: {order}")
                    
            # 거래 기록
            self.record_trade(signal, position_size)
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            
    def check_risk_limits(self) -> bool:
        """리스크 한도 체크"""
        try:
            # 일일 손실 체크
            daily_pnl = self.get_daily_pnl()
            max_daily_loss = self.config['risk_management']['limits']['max_daily_loss_percent']
            
            if daily_pnl < -max_daily_loss:
                logger.warning(f"Daily loss limit exceeded: {daily_pnl:.2f}%")
                return False
                
            # 포지션 한도 체크
            total_position = sum(p.quantity * p.current_price for p in self.positions.values())
            max_position = self.config['trading']['limits']['max_position']
            
            if total_position >= max_position:
                logger.warning(f"Position limit exceeded: {total_position:,.0f} KRW")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
            
    def calculate_position_size(self, signal: Signal) -> float:
        """포지션 크기 계산 (Kelly Criterion)"""
        try:
            # Kelly fraction 계산
            win_rate = self.get_win_rate()
            avg_win = self.get_average_win()
            avg_loss = self.get_average_loss()
            
            if avg_loss == 0:
                kelly_fraction = 0.1  # 기본값
            else:
                win_loss_ratio = avg_win / abs(avg_loss)
                kelly_fraction = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
                
            # 안전을 위해 Kelly의 25%만 사용
            safe_fraction = max(0, min(kelly_fraction * 0.25, 0.1))
            
            # 잔고 조회
            balance = self.upbit.get_balance("KRW")
            
            # 포지션 크기 계산
            position_size = balance * safe_fraction * signal.strength
            
            # 최소/최대 제한
            min_order = self.config['trading']['limits']['min_order_size']
            max_order = self.config['trading']['limits']['max_order_size']
            
            return max(min_order, min(position_size, max_order))
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return self.config['trading']['limits']['min_order_size']
            
    def record_trade(self, signal: Signal, size: float):
        """거래 기록"""
        try:
            cursor = self.db.cursor()
            cursor.execute('''
                INSERT INTO trades (strategy_name, symbol, side, price, quantity)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                signal.strategy,
                self.config['trading']['symbol'],
                signal.action,
                signal.price,
                size
            ))
            self.db.commit()
            
            # 신호도 기록
            cursor.execute('''
                INSERT INTO signals (strategy_name, action, strength, price, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                signal.strategy,
                signal.action,
                signal.strength,
                signal.price,
                signal.reason
            ))
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
            
    def get_daily_pnl(self) -> float:
        """일일 손익률 계산"""
        try:
            cursor = self.db.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT SUM(pnl) FROM trades
                WHERE DATE(timestamp) = ?
            ''', (today,))
            
            result = cursor.fetchone()
            return result[0] if result[0] else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating daily PnL: {e}")
            return 0.0
            
    def get_win_rate(self) -> float:
        """승률 계산"""
        try:
            cursor = self.db.cursor()
            
            # 최근 100개 거래
            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
                FROM (SELECT * FROM trades ORDER BY id DESC LIMIT 100)
            ''')
            
            result = cursor.fetchone()
            if result and result[0] > 0:
                return result[1] / result[0]
            return 0.5  # 기본값
            
        except Exception as e:
            logger.error(f"Error calculating win rate: {e}")
            return 0.5
            
    def get_average_win(self) -> float:
        """평균 수익 계산"""
        try:
            cursor = self.db.cursor()
            
            cursor.execute('''
                SELECT AVG(pnl) FROM trades
                WHERE pnl > 0
                ORDER BY id DESC LIMIT 100
            ''')
            
            result = cursor.fetchone()
            return result[0] if result[0] else 0.01
            
        except Exception as e:
            logger.error(f"Error calculating average win: {e}")
            return 0.01
            
    def get_average_loss(self) -> float:
        """평균 손실 계산"""
        try:
            cursor = self.db.cursor()
            
            cursor.execute('''
                SELECT AVG(pnl) FROM trades
                WHERE pnl < 0
                ORDER BY id DESC LIMIT 100
            ''')
            
            result = cursor.fetchone()
            return result[0] if result[0] else -0.01
            
        except Exception as e:
            logger.error(f"Error calculating average loss: {e}")
            return -0.01
            
    def close_all_positions(self):
        """모든 포지션 청산"""
        try:
            symbol = self.config['trading']['symbol']
            balance = self.upbit.get_balance(symbol.split('-')[1])
            
            if balance > 0:
                order = self.upbit.sell_market_order(symbol, balance)
                logger.info(f"Closed all positions: {order}")
                
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
            
    async def update_metrics(self):
        """성능 지표 업데이트"""
        while self.running:
            try:
                # 잔고 조회
                total_balance = self.upbit.get_balance("KRW")
                
                # 메트릭 계산
                metrics = {
                    'timestamp': datetime.now(),
                    'total_balance': total_balance,
                    'position_value': sum(p.quantity * p.current_price for p in self.positions.values()),
                    'daily_pnl': self.get_daily_pnl(),
                    'win_rate': self.get_win_rate(),
                    'sharpe_ratio': 0  # TODO: 샤프 비율 계산 구현
                }
                
                # 데이터베이스 저장
                cursor = self.db.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO metrics 
                    (timestamp, total_balance, position_value, daily_pnl, win_rate, sharpe_ratio)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    metrics['timestamp'],
                    metrics['total_balance'],
                    metrics['position_value'],
                    metrics['daily_pnl'],
                    metrics['win_rate'],
                    metrics['sharpe_ratio']
                ))
                self.db.commit()
                
                # Redis 캐시 업데이트
                if self.redis:
                    self.redis.set('metrics:latest', json.dumps(metrics, default=str))
                    
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                
            await asyncio.sleep(60)  # 1분마다 업데이트
            
    async def run(self):
        """메인 실행 루프"""
        logger.info("Starting Quantum Trading System...")
        self.running = True
        
        # 모든 비동기 태스크 시작
        tasks = [
            asyncio.create_task(self.collect_market_data()),
            asyncio.create_task(self.generate_signals()),
            asyncio.create_task(self.update_metrics()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.running = False
            for task in tasks:
                task.cancel()
                

def main():
    """메인 함수"""
    # 드라이런 모드 체크
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        logger.info("Running in DRY RUN mode (no real trades)")
        os.environ['TRADING_MODE'] = 'dry_run'
    
    # 시스템 시작
    system = QuantumTradingSystem()
    
    try:
        asyncio.run(system.run())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()