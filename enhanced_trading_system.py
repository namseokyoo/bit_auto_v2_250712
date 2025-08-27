#!/usr/bin/env python3
"""
Enhanced Quantum Trading System v3.1
목표: 일일 0.15% 수익 달성을 위한 안정적 트레이딩 시스템
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading

import pyupbit
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import redis
import yaml

# 환경 변수 로드
load_dotenv('config/.env')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/enhanced_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedTradingSystem:
    """하루 2% 수익을 목표로 하는 고빈도 트레이딩 시스템"""
    
    def __init__(self):
        self.access_key = os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if not self.access_key or not self.secret_key:
            logger.error("API keys not found")
            sys.exit(1)
            
        self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)
        
        # 거래 설정
        self.DAILY_TARGET_RETURN = 0.0015  # 0.15% 일일 목표 - 현실적 설정
        self.POSITION_SIZE_RATIO = 0.1   # 총 자산의 10%씩 사용
        self.STOP_LOSS = -0.002          # -0.2% 손절 - 더 보수적
        self.TAKE_PROFIT = 0.002         # +0.2% 익절 - 현실적 목표
        self.MAX_DAILY_LOSS = -0.02      # -2% 일일 최대 손실 - 엄격한 리스크 관리
        self.MIN_ORDER_SIZE = 5000        # 최소 주문 금액
        
        # 거래 상태
        self.is_running = True
        self.current_position = None
        self.daily_trades = []
        self.daily_pnl = 0
        self.total_trades_today = 0
        self.winning_trades_today = 0
        
        # Redis 연결
        try:
            self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis.ping()
            logger.info("Redis connected for enhanced trading")
        except:
            self.redis = None
            logger.warning("Redis not available")
            
        # 기술적 지표 설정
        self.indicators = {}
        
    def get_account_info(self) -> Dict:
        """현재 계좌 정보 조회"""
        try:
            balances = self.upbit.get_balances()
            
            total_krw = 0
            total_value = 0
            positions = {}
            
            for balance in balances:
                currency = balance['currency']
                amount = float(balance['balance'])
                locked = float(balance['locked'])
                
                if currency == 'KRW':
                    total_krw = amount + locked
                elif amount > 0:
                    symbol = f"KRW-{currency}"
                    try:
                        current_price = pyupbit.get_current_price(symbol)
                        if current_price:
                            value = amount * current_price
                            total_value += value
                            positions[currency] = {
                                'amount': amount,
                                'value': value,
                                'price': current_price
                            }
                    except:
                        pass
                        
            total_assets = total_krw + total_value
            
            return {
                'total_krw': total_krw,
                'total_value': total_value,
                'total_assets': total_assets,
                'positions': positions,
                'position_size': total_assets * self.POSITION_SIZE_RATIO,
                'daily_target': total_assets * self.DAILY_TARGET_RETURN
            }
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None
            
    def calculate_indicators(self, symbol: str, interval: str = "minute1") -> Dict:
        """기술적 지표 계산"""
        try:
            # 1분봉 데이터 가져오기
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=100)
            if df is None or len(df) < 20:
                return None
                
            # RSI 계산
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            sma20 = df['close'].rolling(window=20).mean()
            std20 = df['close'].rolling(window=20).std()
            upper_band = sma20 + (std20 * 2)
            lower_band = sma20 - (std20 * 2)
            
            # MACD
            ema12 = df['close'].ewm(span=12).mean()
            ema26 = df['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            
            # 변동성
            volatility = df['close'].pct_change().rolling(window=20).std()
            
            current_price = df['close'].iloc[-1]
            
            return {
                'price': current_price,
                'rsi': rsi.iloc[-1],
                'bb_upper': upper_band.iloc[-1],
                'bb_lower': lower_band.iloc[-1],
                'bb_middle': sma20.iloc[-1],
                'macd': macd.iloc[-1],
                'macd_signal': signal.iloc[-1],
                'volume': df['volume'].iloc[-1],
                'volatility': volatility.iloc[-1],
                'price_change': (current_price - df['close'].iloc[-2]) / df['close'].iloc[-2]
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate indicators: {e}")
            return None
            
    def get_order_book_imbalance(self, symbol: str) -> float:
        """주문북 불균형 계산"""
        try:
            orderbook = pyupbit.get_orderbook(symbol)
            if not orderbook:
                return 0
                
            # 매수/매도 호가 총량 계산
            total_bid_volume = sum([unit['size'] for unit in orderbook[0]['orderbook_units'][:5]])
            total_ask_volume = sum([unit['size'] for unit in orderbook[0]['orderbook_units'][5:10]])
            
            if total_bid_volume + total_ask_volume == 0:
                return 0
                
            # -1 ~ 1 사이의 값 (양수: 매수 우세, 음수: 매도 우세)
            imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)
            
            return imbalance
            
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return 0
            
    def generate_trading_signal(self, symbol: str) -> Tuple[str, float]:
        """거래 신호 생성 (고빈도 스캘핑)"""
        try:
            # 지표 계산
            indicators = self.calculate_indicators(symbol)
            if not indicators:
                return None, 0
                
            # 주문북 불균형
            order_imbalance = self.get_order_book_imbalance(symbol)
            
            signal_strength = 0
            signal_type = None
            
            # RSI 신호 (과매수/과매도)
            if indicators['rsi'] < 30:
                signal_strength += 0.3
                signal_type = 'buy'
            elif indicators['rsi'] > 70:
                signal_strength += 0.3
                signal_type = 'sell'
                
            # Bollinger Band 신호
            if indicators['price'] < indicators['bb_lower']:
                signal_strength += 0.2
                if not signal_type:
                    signal_type = 'buy'
            elif indicators['price'] > indicators['bb_upper']:
                signal_strength += 0.2
                if not signal_type:
                    signal_type = 'sell'
                    
            # MACD 신호
            if indicators['macd'] > indicators['macd_signal'] and indicators['macd'] < 0:
                signal_strength += 0.2
                if not signal_type:
                    signal_type = 'buy'
            elif indicators['macd'] < indicators['macd_signal'] and indicators['macd'] > 0:
                signal_strength += 0.2
                if not signal_type:
                    signal_type = 'sell'
                    
            # 주문북 신호
            if abs(order_imbalance) > 0.2:
                signal_strength += abs(order_imbalance) * 0.3
                if not signal_type:
                    signal_type = 'buy' if order_imbalance > 0 else 'sell'
                    
            # 최소 신호 강도 체크
            if signal_strength < 0.5:
                return None, 0
                
            # Redis에 신호 저장
            if self.redis:
                signal_data = {
                    'symbol': symbol,
                    'type': signal_type,
                    'strength': signal_strength,
                    'indicators': json.dumps(indicators, default=str),
                    'timestamp': datetime.now().isoformat()
                }
                self.redis.hset(f'signal:{symbol}', mapping=signal_data)
                self.redis.expire(f'signal:{symbol}', 300)  # 5분 후 만료
                
            return signal_type, signal_strength
            
        except Exception as e:
            logger.error(f"Failed to generate signal: {e}")
            return None, 0
            
    def execute_trade(self, symbol: str, signal_type: str, signal_strength: float) -> bool:
        """거래 실행"""
        try:
            account_info = self.get_account_info()
            if not account_info:
                return False
                
            # 일일 손실 한도 체크
            if self.daily_pnl <= self.MAX_DAILY_LOSS * account_info['total_assets']:
                logger.warning("Daily loss limit reached")
                return False
                
            # 포지션 크기 계산
            position_size = min(
                account_info['position_size'],
                account_info['total_krw'] * 0.9  # KRW의 90%까지만 사용
            )
            
            if position_size < self.MIN_ORDER_SIZE:
                logger.info("Insufficient balance for trading")
                return False
                
            current_price = pyupbit.get_current_price(symbol)
            
            if signal_type == 'buy' and not self.current_position:
                # 매수 주문
                quantity = position_size / current_price
                
                logger.info(f"Executing BUY: {symbol} qty={quantity:.8f} @ {current_price}")
                
                # 실제 주문 실행
                result = self.upbit.buy_market_order(symbol, position_size)
                
                if result:
                    self.current_position = {
                        'symbol': symbol,
                        'side': 'buy',
                        'entry_price': current_price,
                        'quantity': quantity,
                        'value': position_size,
                        'stop_loss': current_price * (1 + self.STOP_LOSS),
                        'take_profit': current_price * (1 + self.TAKE_PROFIT),
                        'entry_time': datetime.now()
                    }
                    
                    self.total_trades_today += 1
                    
                    logger.info(f"BUY order executed: {result}")
                    return True
                    
            elif signal_type == 'sell' and self.current_position:
                # 매도 주문
                logger.info(f"Executing SELL: {self.current_position['symbol']}")
                
                result = self.upbit.sell_market_order(
                    self.current_position['symbol'],
                    self.current_position['quantity']
                )
                
                if result:
                    # PnL 계산
                    pnl = (current_price - self.current_position['entry_price']) * \
                          self.current_position['quantity']
                    pnl_percent = ((current_price / self.current_position['entry_price']) - 1) * 100
                    
                    self.daily_pnl += pnl
                    
                    if pnl > 0:
                        self.winning_trades_today += 1
                        
                    # 거래 기록
                    trade_record = {
                        'symbol': self.current_position['symbol'],
                        'side': 'sell',
                        'entry_price': self.current_position['entry_price'],
                        'exit_price': current_price,
                        'quantity': self.current_position['quantity'],
                        'pnl': pnl,
                        'pnl_percent': pnl_percent,
                        'duration': (datetime.now() - self.current_position['entry_time']).seconds,
                        'timestamp': datetime.now()
                    }
                    
                    self.daily_trades.append(trade_record)
                    self.current_position = None
                    
                    logger.info(f"SELL order executed. PnL: {pnl:.0f} ({pnl_percent:.2f}%)")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            
        return False
        
    def check_stop_conditions(self) -> bool:
        """손절/익절 체크"""
        if not self.current_position:
            return False
            
        try:
            current_price = pyupbit.get_current_price(self.current_position['symbol'])
            
            # 손절 체크
            if current_price <= self.current_position['stop_loss']:
                logger.info("Stop loss triggered")
                self.execute_trade(self.current_position['symbol'], 'sell', 1.0)
                return True
                
            # 익절 체크
            if current_price >= self.current_position['take_profit']:
                logger.info("Take profit triggered")
                self.execute_trade(self.current_position['symbol'], 'sell', 1.0)
                return True
                
            # 시간 기반 청산 (5분 이상 보유)
            if (datetime.now() - self.current_position['entry_time']).seconds > 300:
                logger.info("Time-based exit triggered")
                self.execute_trade(self.current_position['symbol'], 'sell', 0.5)
                return True
                
        except Exception as e:
            logger.error(f"Failed to check stop conditions: {e}")
            
        return False
        
    def update_dashboard_stats(self):
        """대시보드 통계 업데이트"""
        try:
            if not self.redis:
                return
                
            account_info = self.get_account_info()
            
            stats = {
                'total_assets': account_info['total_assets'],
                'daily_pnl': self.daily_pnl,
                'daily_pnl_percent': (self.daily_pnl / account_info['total_assets']) * 100,
                'total_trades': self.total_trades_today,
                'winning_trades': self.winning_trades_today,
                'win_rate': (self.winning_trades_today / self.total_trades_today * 100) 
                           if self.total_trades_today > 0 else 0,
                'current_position': json.dumps(self.current_position, default=str) 
                                   if self.current_position else None,
                'target_achieved': self.daily_pnl >= account_info['daily_target'],
                'timestamp': datetime.now().isoformat()
            }
            
            self.redis.hset('trading:stats', mapping=stats)
            
        except Exception as e:
            logger.error(f"Failed to update dashboard stats: {e}")
            
    async def run_trading_cycle(self):
        """메인 거래 사이클 (1분마다 실행)"""
        symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-SOL']  # 거래할 코인
        
        while self.is_running:
            try:
                # 계좌 정보 확인
                account_info = self.get_account_info()
                if not account_info:
                    await asyncio.sleep(60)
                    continue
                    
                # 일일 목표 달성 체크
                if self.daily_pnl >= account_info['daily_target']:
                    logger.info(f"Daily target achieved! PnL: {self.daily_pnl:.0f}")
                    
                # 손절/익절 체크
                self.check_stop_conditions()
                
                # 포지션이 없을 때만 새로운 신호 찾기
                if not self.current_position:
                    for symbol in symbols:
                        signal_type, signal_strength = self.generate_trading_signal(symbol)
                        
                        if signal_type and signal_strength > 0.5:
                            logger.info(f"Signal detected: {symbol} {signal_type} strength={signal_strength:.2f}")
                            
                            if self.execute_trade(symbol, signal_type, signal_strength):
                                break  # 하나의 포지션만 진입
                                
                # 대시보드 통계 업데이트
                self.update_dashboard_stats()
                
                # 상태 로깅
                if self.total_trades_today > 0:
                    logger.info(f"Today: Trades={self.total_trades_today} " 
                               f"WinRate={self.winning_trades_today/self.total_trades_today*100:.1f}% "
                               f"PnL={self.daily_pnl:.0f}")
                    
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                logger.error(f"Trading cycle error: {e}")
                await asyncio.sleep(60)
                
    def reset_daily_stats(self):
        """일일 통계 리셋 (자정에 실행)"""
        self.daily_pnl = 0
        self.total_trades_today = 0
        self.winning_trades_today = 0
        self.daily_trades = []
        logger.info("Daily stats reset")
        
    def start(self):
        """시스템 시작"""
        logger.info("Enhanced Trading System v3.1 Starting...")
        logger.info("Target: 2% daily return")
        
        account_info = self.get_account_info()
        if account_info:
            logger.info(f"Total Assets: {account_info['total_assets']:,.0f}")
            logger.info(f"Daily Target: {account_info['daily_target']:,.0f}")
            logger.info(f"Position Size: {account_info['position_size']:,.0f}")
            
        # 비동기 이벤트 루프 실행
        asyncio.run(self.run_trading_cycle())

if __name__ == "__main__":
    system = EnhancedTradingSystem()
    
    try:
        system.start()
    except KeyboardInterrupt:
        logger.info("System stopped by user")
        system.is_running = False