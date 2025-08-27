#!/usr/bin/env python3
"""
고급 백테스트 엔진
- 과거 데이터로 전략 성능 검증
- 수수료 및 슬리피지 반영
- 상세한 성과 메트릭 계산
"""

import os
import sys
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
import pyupbit
from dataclasses import dataclass, asdict
import yaml

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Trade:
    """거래 기록"""
    timestamp: datetime
    symbol: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: float
    fee: float
    slippage: float
    pnl: float = 0.0
    strategy: str = ""
    signal_strength: float = 0.0

@dataclass
class BacktestResult:
    """백테스트 결과"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    recovery_factor: float
    trades_per_day: float
    total_fees: float
    total_slippage: float
    net_pnl: float
    roi: float
    daily_returns: List[float]
    equity_curve: List[float]
    trades: List[Trade]

class BacktestEngine:
    """백테스트 엔진"""
    
    def __init__(self, initial_capital: float = 1_000_000):
        """
        Args:
            initial_capital: 초기 자본금 (원화)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.position = 0  # 현재 보유 수량
        self.avg_entry_price = 0  # 평균 진입가
        
        # 수수료 및 슬리피지 설정
        self.MAKER_FEE = 0.0005  # 0.05% - Upbit 메이커 수수료
        self.TAKER_FEE = 0.0005  # 0.05% - Upbit 테이커 수수료
        self.SLIPPAGE_RATE = 0.001  # 0.1% - 예상 슬리피지
        
        # 거래 기록
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
        self.daily_returns: List[float] = []
        
        # 성과 메트릭
        self.max_equity = initial_capital
        self.max_drawdown = 0
        self.total_fees = 0
        self.total_slippage = 0
        
        # 데이터베이스
        self.db_path = "data/backtest_results.db"
        self._init_database()
        
    def _init_database(self):
        """백테스트 결과 저장용 데이터베이스 초기화"""
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 백테스트 세션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                initial_capital REAL NOT NULL,
                final_capital REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                total_pnl REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                parameters TEXT,
                result_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 개별 거래 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                fee REAL NOT NULL,
                slippage REAL NOT NULL,
                pnl REAL NOT NULL,
                strategy TEXT,
                signal_strength REAL,
                FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
            )
        """)
        
        conn.commit()
        conn.close()
        
    def calculate_slippage(self, price: float, side: str, volume: float = None) -> float:
        """
        슬리피지 계산
        
        Args:
            price: 신호 가격
            side: 'buy' or 'sell'
            volume: 거래량 (클수록 슬리피지 증가)
        
        Returns:
            슬리피지 적용된 실제 체결 예상 가격
        """
        # 기본 슬리피지
        slippage_mult = self.SLIPPAGE_RATE
        
        # 거래량이 클수록 슬리피지 증가
        if volume and volume > 1_000_000:  # 100만원 이상
            slippage_mult *= (1 + volume / 10_000_000)  # 1000만원당 100% 증가
            
        if side == 'buy':
            # 매수 시 더 비싸게 체결
            actual_price = price * (1 + slippage_mult)
        else:
            # 매도 시 더 싸게 체결
            actual_price = price * (1 - slippage_mult)
            
        return actual_price
    
    def calculate_fee(self, amount: float, is_maker: bool = False) -> float:
        """
        거래 수수료 계산
        
        Args:
            amount: 거래 금액
            is_maker: 메이커 주문 여부
        
        Returns:
            수수료 금액
        """
        fee_rate = self.MAKER_FEE if is_maker else self.TAKER_FEE
        return amount * fee_rate
    
    def execute_trade(self, 
                     timestamp: datetime,
                     symbol: str,
                     side: str,
                     signal_price: float,
                     quantity: float,
                     strategy: str = "",
                     signal_strength: float = 0.0,
                     is_maker: bool = False) -> Optional[Trade]:
        """
        거래 실행 시뮬레이션
        
        Args:
            timestamp: 거래 시간
            symbol: 거래 심볼
            side: 'buy' or 'sell'
            signal_price: 신호 가격
            quantity: 거래 수량
            strategy: 전략 이름
            signal_strength: 신호 강도
            is_maker: 메이커 주문 여부
        
        Returns:
            Trade 객체 또는 None (실패 시)
        """
        # 거래 금액 계산
        amount = signal_price * quantity
        
        # 슬리피지 적용
        actual_price = self.calculate_slippage(signal_price, side, amount)
        actual_amount = actual_price * quantity
        
        # 수수료 계산
        fee = self.calculate_fee(actual_amount, is_maker)
        slippage_cost = abs(actual_amount - amount)
        
        # 거래 가능 여부 확인
        if side == 'buy':
            total_cost = actual_amount + fee
            if total_cost > self.current_capital:
                logger.warning(f"자금 부족: 필요 {total_cost:,.0f}, 보유 {self.current_capital:,.0f}")
                return None
                
            # 매수 실행
            self.current_capital -= total_cost
            old_position = self.position
            self.position += quantity
            
            # 평균 진입가 업데이트
            if old_position > 0:
                self.avg_entry_price = (
                    (self.avg_entry_price * old_position + actual_price * quantity) 
                    / self.position
                )
            else:
                self.avg_entry_price = actual_price
                
            pnl = 0  # 매수 시 PnL은 0
            
        else:  # sell
            if self.position <= 0:
                logger.warning("매도할 포지션이 없습니다")
                return None
                
            if quantity > self.position:
                quantity = self.position  # 보유 수량만큼만 매도
                
            # 매도 실행
            revenue = actual_amount - fee
            self.current_capital += revenue
            
            # PnL 계산
            pnl = (actual_price - self.avg_entry_price) * quantity - fee
            
            # 포지션 업데이트
            self.position -= quantity
            if self.position == 0:
                self.avg_entry_price = 0
                
        # 거래 기록
        trade = Trade(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            price=actual_price,
            quantity=quantity,
            fee=fee,
            slippage=slippage_cost,
            pnl=pnl,
            strategy=strategy,
            signal_strength=signal_strength
        )
        
        self.trades.append(trade)
        
        # 자산 업데이트
        total_equity = self.current_capital + self.position * actual_price
        self.equity_curve.append(total_equity)
        
        # 통계 업데이트
        self.total_fees += fee
        self.total_slippage += slippage_cost
        
        # 최대 자산 및 낙폭 업데이트
        if total_equity > self.max_equity:
            self.max_equity = total_equity
        drawdown = self.max_equity - total_equity
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            
        return trade
    
    def calculate_metrics(self) -> BacktestResult:
        """백테스트 성과 지표 계산"""
        if not self.trades:
            return self._empty_result()
            
        # 기본 통계
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl <= 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # PnL 계산
        total_pnl = sum(t.pnl for t in self.trades)
        avg_trade_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # 승/패 평균
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl <= 0]
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        # Profit Factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # 수익률
        final_equity = self.equity_curve[-1] if self.equity_curve else self.initial_capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        # 일별 수익률 계산
        if len(self.equity_curve) > 1:
            equity_series = pd.Series(self.equity_curve)
            daily_returns = equity_series.pct_change().dropna().tolist()
        else:
            daily_returns = []
            
        # Sharpe Ratio (연율화)
        if daily_returns:
            daily_returns_array = np.array(daily_returns)
            avg_daily_return = np.mean(daily_returns_array)
            std_daily_return = np.std(daily_returns_array)
            sharpe_ratio = (avg_daily_return / std_daily_return * np.sqrt(365)) if std_daily_return > 0 else 0
        else:
            sharpe_ratio = 0
            
        # Sortino Ratio (하방 리스크만 고려)
        if daily_returns:
            negative_returns = [r for r in daily_returns if r < 0]
            if negative_returns:
                downside_std = np.std(negative_returns)
                sortino_ratio = (avg_daily_return / downside_std * np.sqrt(365)) if downside_std > 0 else 0
            else:
                sortino_ratio = float('inf') if avg_daily_return > 0 else 0
        else:
            sortino_ratio = 0
            
        # 최대 낙폭
        max_dd_percent = (self.max_drawdown / self.max_equity * 100) if self.max_equity > 0 else 0
        
        # Recovery Factor
        recovery_factor = total_pnl / self.max_drawdown if self.max_drawdown > 0 else 0
        
        # 거래 빈도
        if self.trades:
            first_trade = self.trades[0].timestamp
            last_trade = self.trades[-1].timestamp
            trading_days = (last_trade - first_trade).days or 1
            trades_per_day = total_trades / trading_days
        else:
            trades_per_day = 0
            
        # Net PnL (수수료와 슬리피지 차감)
        net_pnl = total_pnl - self.total_fees - self.total_slippage
        
        # ROI
        roi = net_pnl / self.initial_capital * 100
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate * 100,
            total_pnl=total_pnl,
            total_pnl_percent=total_return * 100,
            max_drawdown=self.max_drawdown,
            max_drawdown_percent=max_dd_percent,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            avg_trade_pnl=avg_trade_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            recovery_factor=recovery_factor,
            trades_per_day=trades_per_day,
            total_fees=self.total_fees,
            total_slippage=self.total_slippage,
            net_pnl=net_pnl,
            roi=roi,
            daily_returns=daily_returns,
            equity_curve=self.equity_curve,
            trades=self.trades
        )
    
    def _empty_result(self) -> BacktestResult:
        """빈 결과 반환"""
        return BacktestResult(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0, total_pnl=0, total_pnl_percent=0,
            max_drawdown=0, max_drawdown_percent=0,
            sharpe_ratio=0, sortino_ratio=0,
            avg_trade_pnl=0, avg_win=0, avg_loss=0,
            profit_factor=0, recovery_factor=0, trades_per_day=0,
            total_fees=0, total_slippage=0, net_pnl=0, roi=0,
            daily_returns=[], equity_curve=[self.initial_capital], trades=[]
        )
    
    def save_results(self, 
                    strategy: str, 
                    symbol: str,
                    period_start: datetime,
                    period_end: datetime,
                    parameters: Dict = None) -> int:
        """백테스트 결과를 데이터베이스에 저장"""
        result = self.calculate_metrics()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 세션 저장
        cursor.execute("""
            INSERT INTO backtest_sessions (
                timestamp, strategy, symbol, period_start, period_end,
                initial_capital, final_capital, total_trades, win_rate,
                total_pnl, max_drawdown, sharpe_ratio, parameters, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            strategy,
            symbol,
            period_start.isoformat(),
            period_end.isoformat(),
            self.initial_capital,
            self.equity_curve[-1] if self.equity_curve else self.initial_capital,
            result.total_trades,
            result.win_rate,
            result.total_pnl,
            result.max_drawdown,
            result.sharpe_ratio,
            json.dumps(parameters) if parameters else "{}",
            json.dumps(asdict(result), default=str)
        ))
        
        session_id = cursor.lastrowid
        
        # 개별 거래 저장
        for trade in self.trades:
            cursor.execute("""
                INSERT INTO backtest_trades (
                    session_id, timestamp, symbol, side, price, quantity,
                    fee, slippage, pnl, strategy, signal_strength
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                trade.timestamp.isoformat(),
                trade.symbol,
                trade.side,
                trade.price,
                trade.quantity,
                trade.fee,
                trade.slippage,
                trade.pnl,
                trade.strategy,
                trade.signal_strength
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"백테스트 결과 저장 완료 (Session ID: {session_id})")
        return session_id
    
    def print_summary(self):
        """백테스트 결과 요약 출력"""
        result = self.calculate_metrics()
        
        print("\n" + "="*60)
        print("📊 백테스트 결과 요약")
        print("="*60)
        
        print(f"\n💰 수익 성과:")
        print(f"  총 수익: ₩{result.net_pnl:,.0f}")
        print(f"  수익률: {result.roi:.2f}%")
        print(f"  초기 자본: ₩{self.initial_capital:,.0f}")
        print(f"  최종 자본: ₩{self.equity_curve[-1]:,.0f}")
        
        print(f"\n📈 거래 통계:")
        print(f"  총 거래: {result.total_trades}회")
        print(f"  승률: {result.win_rate:.1f}%")
        print(f"  평균 수익: ₩{result.avg_win:,.0f}")
        print(f"  평균 손실: ₩{result.avg_loss:,.0f}")
        print(f"  Profit Factor: {result.profit_factor:.2f}")
        
        print(f"\n📉 리스크 지표:")
        print(f"  최대 낙폭: {result.max_drawdown_percent:.2f}%")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio: {result.sortino_ratio:.2f}")
        
        print(f"\n💸 비용:")
        print(f"  총 수수료: ₩{result.total_fees:,.0f}")
        print(f"  총 슬리피지: ₩{result.total_slippage:,.0f}")
        print(f"  총 비용: ₩{result.total_fees + result.total_slippage:,.0f}")
        
        print("="*60)