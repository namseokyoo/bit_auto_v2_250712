"""
SQLite 데이터베이스 관리
거래 기록, 시장 데이터, 로그 저장
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import pandas as pd
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path: str = "data/trading_data.db"):
        self.db_path = db_path
        self.logger = self._setup_logger()
        
        # 데이터 디렉토리 생성
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 데이터베이스 초기화
        self.init_database()
        self.logger.info(f"데이터베이스 초기화 완료: {db_path}")

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('DatabaseManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """데이터베이스 테이블 초기화"""
        with self.get_connection() as conn:
            # 거래 기록 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT NOT NULL,
                    order_id TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    amount REAL NOT NULL,
                    fees REAL DEFAULT 0,
                    pnl REAL,
                    status TEXT DEFAULT 'open',
                    reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 시장 데이터 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    timeframe TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp, timeframe)
                )
            ''')

            # 전략 성능 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT NOT NULL,
                    date DATE NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    avg_return REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(strategy_id, date)
                )
            ''')

            # 시스템 로그 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 설정 변경 이력 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    changed_by TEXT DEFAULT 'system',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 분석 이력 테이블 (자동 거래 분석 결과 저장)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    result TEXT NOT NULL,
                    executed BOOLEAN DEFAULT FALSE,
                    action TEXT,
                    confidence REAL,
                    price REAL,
                    reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 인덱스 생성
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_history(timestamp)')

            conn.commit()

    def insert_trade(self, trade_data: Dict) -> int:
        """거래 기록 삽입"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO trades (
                    strategy_id, order_id, symbol, side, entry_time, exit_time,
                    entry_price, exit_price, quantity, amount, fees, pnl, status, reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('strategy_id'),
                trade_data.get('order_id'),
                trade_data.get('symbol', 'KRW-BTC'),
                trade_data.get('side'),
                trade_data.get('entry_time'),
                trade_data.get('exit_time'),
                trade_data.get('entry_price'),
                trade_data.get('exit_price'),
                trade_data.get('quantity'),
                trade_data.get('amount'),
                trade_data.get('fees', 0),
                trade_data.get('pnl'),
                trade_data.get('status', 'open'),
                trade_data.get('reasoning')
            ))
            conn.commit()
            return cursor.lastrowid

    def update_trade(self, trade_id: int, update_data: Dict):
        """거래 기록 업데이트"""
        set_clauses = []
        values = []
        
        for key, value in update_data.items():
            if key in ['exit_time', 'exit_price', 'pnl', 'status']:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        if set_clauses:
            values.append(trade_id)
            query = f"UPDATE trades SET {', '.join(set_clauses)} WHERE id = ?"
            
            with self.get_connection() as conn:
                conn.execute(query, values)
                conn.commit()

    def get_trades(self, strategy_id: str = None, start_date: datetime = None, 
                  end_date: datetime = None, status: str = None) -> List[Dict]:
        """거래 기록 조회"""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY entry_time DESC"
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def insert_market_data(self, market_data: Dict):
        """시장 데이터 삽입"""
        with self.get_connection() as conn:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO market_data (
                        symbol, timestamp, open_price, high_price, low_price, 
                        close_price, volume, timeframe
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    market_data.get('symbol', 'KRW-BTC'),
                    market_data.get('timestamp'),
                    market_data.get('open_price'),
                    market_data.get('high_price'),
                    market_data.get('low_price'),
                    market_data.get('close_price'),
                    market_data.get('volume'),
                    market_data.get('timeframe', '1h')
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # 중복 데이터는 무시

    def get_market_data(self, symbol: str = 'KRW-BTC', timeframe: str = '1h', 
                       limit: int = 100) -> pd.DataFrame:
        """시장 데이터 조회"""
        query = '''
            SELECT * FROM market_data 
            WHERE symbol = ? AND timeframe = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        '''
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)
            return df

    def insert_log(self, level: str, module: str, message: str, details: str = None):
        """시스템 로그 삽입"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO system_logs (level, module, message, details)
                VALUES (?, ?, ?, ?)
            ''', (level, module, message, details))
            conn.commit()

    def get_logs(self, level: str = None, module: str = None, 
                start_time: datetime = None, limit: int = 1000) -> List[Dict]:
        """시스템 로그 조회"""
        query = "SELECT * FROM system_logs WHERE 1=1"
        params = []
        
        if level:
            query += " AND level = ?"
            params.append(level)
        
        if module:
            query += " AND module = ?"
            params.append(module)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_strategy_performance(self, strategy_id: str, performance_data: Dict):
        """전략 성능 업데이트"""
        today = datetime.now().date()
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO strategy_performance (
                    strategy_id, date, total_trades, winning_trades, total_pnl,
                    max_drawdown, win_rate, avg_return, sharpe_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                strategy_id,
                today,
                performance_data.get('total_trades', 0),
                performance_data.get('winning_trades', 0),
                performance_data.get('total_pnl', 0),
                performance_data.get('max_drawdown', 0),
                performance_data.get('win_rate', 0),
                performance_data.get('avg_return', 0),
                performance_data.get('sharpe_ratio', 0)
            ))
            conn.commit()

    def get_strategy_performance(self, strategy_id: str = None, 
                               days: int = 30) -> List[Dict]:
        """전략 성능 조회"""
        start_date = datetime.now().date() - timedelta(days=days)
        
        query = "SELECT * FROM strategy_performance WHERE date >= ?"
        params = [start_date]
        
        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        
        query += " ORDER BY date DESC"
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def log_config_change(self, config_key: str, old_value: str, 
                         new_value: str, changed_by: str = 'system'):
        """설정 변경 이력 저장"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO config_history (config_key, old_value, new_value, changed_by)
                VALUES (?, ?, ?, ?)
            ''', (config_key, old_value, new_value, changed_by))
            conn.commit()

    def insert_analysis(self, analysis_data: Dict) -> int:
        """분석 결과 삽입"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO analysis_history (
                    timestamp, result, executed, action, confidence, price, reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                analysis_data.get('timestamp'),
                analysis_data.get('result'),
                analysis_data.get('executed', False),
                analysis_data.get('action'),
                analysis_data.get('confidence'),
                analysis_data.get('price'),
                analysis_data.get('reasoning')
            ))
            conn.commit()
            return cursor.lastrowid

    def get_latest_analysis(self, limit: int = 10) -> List[Dict]:
        """최근 분석 결과 조회"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM analysis_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_dashboard_data(self) -> Dict:
        """대시보드용 데이터 조회"""
        with self.get_connection() as conn:
            # 총 거래 수
            total_trades = conn.execute("SELECT COUNT(*) as count FROM trades").fetchone()['count']
            
            # 오늘 거래 수
            today = datetime.now().date()
            today_trades = conn.execute(
                "SELECT COUNT(*) as count FROM trades WHERE DATE(entry_time) = ?", 
                (today,)
            ).fetchone()['count']
            
            # 총 수익/손실
            total_pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) as total FROM trades WHERE status = 'closed'"
            ).fetchone()['total']
            
            # 승률
            winning_trades = conn.execute(
                "SELECT COUNT(*) as count FROM trades WHERE status = 'closed' AND pnl > 0"
            ).fetchone()['count']
            
            closed_trades = conn.execute(
                "SELECT COUNT(*) as count FROM trades WHERE status = 'closed'"
            ).fetchone()['count']
            
            win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0
            
            # 최근 거래들
            recent_trades = conn.execute('''
                SELECT strategy_id, symbol, side, entry_price, pnl, entry_time, status
                FROM trades 
                ORDER BY entry_time DESC 
                LIMIT 10
            ''').fetchall()
            
            return {
                'total_trades': total_trades,
                'today_trades': today_trades,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'recent_trades': [dict(trade) for trade in recent_trades]
            }

    def cleanup_old_data(self, days: int = 90):
        """오래된 데이터 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with self.get_connection() as conn:
            # 오래된 로그 삭제
            conn.execute("DELETE FROM system_logs WHERE timestamp < ?", (cutoff_date,))
            
            # 오래된 시장 데이터 삭제 (거래 데이터는 보존)
            conn.execute("DELETE FROM market_data WHERE timestamp < ?", (cutoff_date,))
            
            conn.commit()
            self.logger.info(f"{days}일 이전 데이터 정리 완료")

    def backup_database(self, backup_path: str = None):
        """데이터베이스 백업"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"data/backup/trading_data_{timestamp}.db"
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        with self.get_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
        
        self.logger.info(f"데이터베이스 백업 완료: {backup_path}")
        return backup_path

# 전역 데이터베이스 인스턴스
db = DatabaseManager()

# 사용 예시
if __name__ == "__main__":
    # 테스트 데이터 삽입
    test_trade = {
        'strategy_id': 'h1',
        'order_id': 'test_001',
        'symbol': 'KRW-BTC',
        'side': 'buy',
        'entry_time': datetime.now(),
        'entry_price': 50000000,
        'quantity': 0.001,
        'amount': 50000,
        'reasoning': '테스트 거래'
    }
    
    trade_id = db.insert_trade(test_trade)
    print(f"거래 기록 생성: {trade_id}")
    
    # 거래 조회
    trades = db.get_trades(strategy_id='h1')
    print(f"전략 h1 거래 수: {len(trades)}")
    
    # 대시보드 데이터
    dashboard = db.get_dashboard_data()
    print(f"대시보드 데이터: {dashboard}")
    
    # 백업
    backup_file = db.backup_database()
    print(f"백업 파일: {backup_file}")