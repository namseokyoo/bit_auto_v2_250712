"""
전략 성능 모니터링 및 분석 시스템
Strategy Performance Monitoring and Analysis System
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json

@dataclass
class StrategyMetrics:
    """전략 성과 지표"""
    strategy_id: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    risk_reward_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    recovery_factor: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_holding_time_hours: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

class PerformanceMonitor:
    """전략 성능 모니터링 시스템"""
    
    def __init__(self, db_path: str = "data/performance.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('PerformanceMonitor')
        
        # 데이터베이스 초기화
        self._initialize_database()
        
        # 메모리 캐시
        self.metrics_cache: Dict[str, StrategyMetrics] = {}
        
    def _initialize_database(self):
        """데이터베이스 테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 거래 기록 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                action TEXT NOT NULL,  -- 'buy' or 'sell'
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0,
                pnl REAL DEFAULT 0,
                pnl_percent REAL DEFAULT 0,
                confidence REAL,
                reasoning TEXT,
                order_id TEXT,
                status TEXT DEFAULT 'pending'  -- 'pending', 'executed', 'cancelled'
            )
        """)
        
        # 전략 성과 메트릭 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                metrics_json TEXT NOT NULL,
                UNIQUE(strategy_id, timestamp)
            )
        """)
        
        # 포지션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                entry_timestamp INTEGER NOT NULL,
                exit_timestamp INTEGER,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                side TEXT NOT NULL,  -- 'long' or 'short'
                pnl REAL DEFAULT 0,
                pnl_percent REAL DEFAULT 0,
                status TEXT DEFAULT 'open'  -- 'open' or 'closed'
            )
        """)
        
        # A/B 테스트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                strategy_a TEXT NOT NULL,
                strategy_b TEXT NOT NULL,
                start_timestamp INTEGER NOT NULL,
                end_timestamp INTEGER,
                winner TEXT,
                confidence_level REAL,
                metrics_json TEXT
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id, status)")
        
        conn.commit()
        conn.close()
        
        self.logger.info("성능 모니터링 데이터베이스 초기화 완료")
    
    def record_trade(self, strategy_id: str, action: str, price: float, 
                    quantity: float, amount: float, confidence: float = None,
                    reasoning: str = None, order_id: str = None) -> int:
        """거래 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO trades 
            (strategy_id, timestamp, action, price, quantity, amount, confidence, reasoning, order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_id, timestamp, action, price, quantity, amount,
            confidence, reasoning, order_id, 'pending'
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 캐시 업데이트
        self._update_metrics_cache(strategy_id)
        
        return trade_id
    
    def update_trade_status(self, trade_id: int, status: str, pnl: float = None):
        """거래 상태 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "UPDATE trades SET status = ?"
        params = [status]
        
        if pnl is not None:
            query += ", pnl = ?, pnl_percent = ?"
            # PnL 퍼센트 계산을 위해 거래 정보 조회
            cursor.execute("SELECT amount FROM trades WHERE id = ?", (trade_id,))
            amount = cursor.fetchone()[0]
            pnl_percent = (pnl / amount * 100) if amount > 0 else 0
            params.extend([pnl, pnl_percent])
        
        query += " WHERE id = ?"
        params.append(trade_id)
        
        cursor.execute(query, params)
        conn.commit()
        conn.close()
    
    def open_position(self, strategy_id: str, entry_price: float, 
                     quantity: float, side: str = 'long') -> int:
        """포지션 오픈"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO positions 
            (strategy_id, entry_timestamp, entry_price, quantity, side, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            strategy_id, timestamp, entry_price, quantity, side, 'open'
        ))
        
        position_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return position_id
    
    def close_position(self, position_id: int, exit_price: float) -> float:
        """포지션 클로즈"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 포지션 정보 조회
        cursor.execute("""
            SELECT entry_price, quantity, side 
            FROM positions 
            WHERE id = ? AND status = 'open'
        """, (position_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return 0
        
        entry_price, quantity, side = result
        exit_timestamp = int(datetime.now().timestamp())
        
        # PnL 계산
        if side == 'long':
            pnl = (exit_price - entry_price) * quantity
        else:  # short
            pnl = (entry_price - exit_price) * quantity
        
        pnl_percent = (pnl / (entry_price * quantity)) * 100
        
        # 포지션 업데이트
        cursor.execute("""
            UPDATE positions 
            SET exit_timestamp = ?, exit_price = ?, pnl = ?, pnl_percent = ?, status = ?
            WHERE id = ?
        """, (
            exit_timestamp, exit_price, pnl, pnl_percent, 'closed', position_id
        ))
        
        conn.commit()
        conn.close()
        
        return pnl
    
    def calculate_metrics(self, strategy_id: str, days: int = 30) -> StrategyMetrics:
        """전략 성과 지표 계산"""
        conn = sqlite3.connect(self.db_path)
        
        # 기간 설정
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        
        # 완료된 포지션 조회
        positions_df = pd.read_sql_query("""
            SELECT * FROM positions 
            WHERE strategy_id = ? 
            AND status = 'closed'
            AND exit_timestamp BETWEEN ? AND ?
            ORDER BY exit_timestamp
        """, conn, params=(strategy_id, start_timestamp, end_timestamp))
        
        conn.close()
        
        metrics = StrategyMetrics(strategy_id=strategy_id)
        
        if positions_df.empty:
            return metrics
        
        # 기본 통계
        metrics.total_trades = len(positions_df)
        metrics.winning_trades = len(positions_df[positions_df['pnl'] > 0])
        metrics.losing_trades = len(positions_df[positions_df['pnl'] < 0])
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        
        # PnL 통계
        metrics.total_pnl = positions_df['pnl'].sum()
        metrics.total_pnl_percent = positions_df['pnl_percent'].sum()
        
        winning_trades = positions_df[positions_df['pnl'] > 0]
        losing_trades = positions_df[positions_df['pnl'] < 0]
        
        metrics.avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
        metrics.avg_loss = abs(losing_trades['pnl'].mean()) if not losing_trades.empty else 0
        
        # 리스크/리워드 비율
        if metrics.avg_loss > 0:
            metrics.risk_reward_ratio = metrics.avg_win / metrics.avg_loss
        
        # Profit Factor
        total_wins = winning_trades['pnl'].sum() if not winning_trades.empty else 0
        total_losses = abs(losing_trades['pnl'].sum()) if not losing_trades.empty else 0
        metrics.profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Expectancy
        if metrics.total_trades > 0:
            metrics.expectancy = (
                metrics.win_rate * metrics.avg_win - 
                (1 - metrics.win_rate) * metrics.avg_loss
            )
        
        # 최대 드로우다운
        cumulative_pnl = positions_df['pnl'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        metrics.max_drawdown = drawdown.min()
        
        # 드로우다운 퍼센트
        if running_max.max() > 0:
            metrics.max_drawdown_percent = (metrics.max_drawdown / running_max.max()) * 100
        
        # 샤프 비율 (연간화)
        if not positions_df.empty:
            daily_returns = positions_df.set_index(
                pd.to_datetime(positions_df['exit_timestamp'], unit='s')
            )['pnl_percent'].resample('D').sum()
            
            if len(daily_returns) > 1 and daily_returns.std() > 0:
                metrics.sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365)
        
        # 소르티노 비율 (하방 리스크만 고려)
        if not positions_df.empty:
            negative_returns = daily_returns[daily_returns < 0]
            if len(negative_returns) > 0:
                downside_std = negative_returns.std()
                if downside_std > 0:
                    metrics.sortino_ratio = (daily_returns.mean() / downside_std) * np.sqrt(365)
        
        # Calmar Ratio
        if metrics.max_drawdown_percent != 0:
            annual_return = metrics.total_pnl_percent * (365 / days)
            metrics.calmar_ratio = annual_return / abs(metrics.max_drawdown_percent)
        
        # 연속 승/패
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for pnl in positions_df['pnl']:
            if pnl > 0:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    current_streak = 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    current_streak = -1
                max_loss_streak = max(max_loss_streak, abs(current_streak))
        
        metrics.max_consecutive_wins = max_win_streak
        metrics.max_consecutive_losses = max_loss_streak
        
        # 평균 보유 시간
        holding_times = (positions_df['exit_timestamp'] - positions_df['entry_timestamp']) / 3600
        metrics.avg_holding_time_hours = holding_times.mean()
        
        # 캐시 업데이트
        self.metrics_cache[strategy_id] = metrics
        
        # 데이터베이스에 저장
        self._save_metrics_to_db(metrics)
        
        return metrics
    
    def _save_metrics_to_db(self, metrics: StrategyMetrics):
        """메트릭을 데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        metrics_dict = {
            'total_trades': metrics.total_trades,
            'win_rate': metrics.win_rate,
            'total_pnl': metrics.total_pnl,
            'sharpe_ratio': metrics.sharpe_ratio,
            'max_drawdown_percent': metrics.max_drawdown_percent,
            'profit_factor': metrics.profit_factor,
            'expectancy': metrics.expectancy
        }
        
        cursor.execute("""
            INSERT OR REPLACE INTO strategy_metrics 
            (strategy_id, timestamp, metrics_json)
            VALUES (?, ?, ?)
        """, (
            metrics.strategy_id,
            timestamp,
            json.dumps(metrics_dict)
        ))
        
        conn.commit()
        conn.close()
    
    def _update_metrics_cache(self, strategy_id: str):
        """메트릭 캐시 업데이트"""
        # 최근 30일 메트릭 재계산
        self.calculate_metrics(strategy_id, days=30)
    
    def get_all_strategies_metrics(self, days: int = 30) -> Dict[str, StrategyMetrics]:
        """모든 전략의 성과 지표"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 모든 전략 ID 조회
        cursor.execute("SELECT DISTINCT strategy_id FROM positions")
        strategies = cursor.fetchall()
        conn.close()
        
        all_metrics = {}
        for (strategy_id,) in strategies:
            all_metrics[strategy_id] = self.calculate_metrics(strategy_id, days)
        
        return all_metrics
    
    def get_strategy_comparison(self, strategy_ids: List[str], days: int = 30) -> pd.DataFrame:
        """전략 비교 테이블"""
        comparison_data = []
        
        for strategy_id in strategy_ids:
            metrics = self.calculate_metrics(strategy_id, days)
            comparison_data.append({
                'Strategy': strategy_id,
                'Win Rate': f"{metrics.win_rate:.1%}",
                'Total PnL': f"${metrics.total_pnl:,.0f}",
                'Sharpe Ratio': f"{metrics.sharpe_ratio:.2f}",
                'Max DD': f"{metrics.max_drawdown_percent:.1f}%",
                'Profit Factor': f"{metrics.profit_factor:.2f}",
                'Trades': metrics.total_trades
            })
        
        return pd.DataFrame(comparison_data)
    
    def start_ab_test(self, test_id: str, strategy_a: str, strategy_b: str) -> int:
        """A/B 테스트 시작"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO ab_tests 
            (test_id, strategy_a, strategy_b, start_timestamp)
            VALUES (?, ?, ?, ?)
        """, (test_id, strategy_a, strategy_b, timestamp))
        
        ab_test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.logger.info(f"A/B 테스트 시작: {test_id} ({strategy_a} vs {strategy_b})")
        
        return ab_test_id
    
    def evaluate_ab_test(self, ab_test_id: int, confidence_level: float = 0.95) -> Dict:
        """A/B 테스트 평가"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # A/B 테스트 정보 조회
        cursor.execute("""
            SELECT test_id, strategy_a, strategy_b, start_timestamp
            FROM ab_tests
            WHERE id = ?
        """, (ab_test_id,))
        
        test_info = cursor.fetchone()
        if not test_info:
            conn.close()
            return {}
        
        test_id, strategy_a, strategy_b, start_timestamp = test_info
        
        # 각 전략의 성과 계산
        days_elapsed = (datetime.now().timestamp() - start_timestamp) / 86400
        metrics_a = self.calculate_metrics(strategy_a, int(days_elapsed))
        metrics_b = self.calculate_metrics(strategy_b, int(days_elapsed))
        
        # 승자 결정 (샤프 비율 기준)
        winner = strategy_a if metrics_a.sharpe_ratio > metrics_b.sharpe_ratio else strategy_b
        
        result = {
            'test_id': test_id,
            'strategy_a': {
                'id': strategy_a,
                'sharpe_ratio': metrics_a.sharpe_ratio,
                'win_rate': metrics_a.win_rate,
                'total_pnl': metrics_a.total_pnl
            },
            'strategy_b': {
                'id': strategy_b,
                'sharpe_ratio': metrics_b.sharpe_ratio,
                'win_rate': metrics_b.win_rate,
                'total_pnl': metrics_b.total_pnl
            },
            'winner': winner,
            'confidence_level': confidence_level,
            'days_elapsed': days_elapsed
        }
        
        # 결과 저장
        cursor.execute("""
            UPDATE ab_tests 
            SET end_timestamp = ?, winner = ?, confidence_level = ?, metrics_json = ?
            WHERE id = ?
        """, (
            int(datetime.now().timestamp()),
            winner,
            confidence_level,
            json.dumps(result),
            ab_test_id
        ))
        
        conn.commit()
        conn.close()
        
        return result

# 사용 예시
if __name__ == "__main__":
    monitor = PerformanceMonitor()
    
    # 거래 기록
    trade_id = monitor.record_trade(
        strategy_id="h1",
        action="buy",
        price=50000000,
        quantity=0.001,
        amount=50000,
        confidence=0.75,
        reasoning="EMA Golden Cross"
    )
    
    # 포지션 오픈/클로즈
    position_id = monitor.open_position("h1", 50000000, 0.001, "long")
    pnl = monitor.close_position(position_id, 51000000)
    
    # 메트릭 계산
    metrics = monitor.calculate_metrics("h1", days=30)
    print(f"Strategy h1 - Win Rate: {metrics.win_rate:.1%}, Sharpe: {metrics.sharpe_ratio:.2f}")