"""
전략 실행 결과 누적 추적 시스템
모든 전략 실행 결과를 데이터베이스에 저장하고 분석
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from config.config_manager import config_manager


@dataclass
class StrategyExecution:
    """전략 실행 기록"""
    execution_time: datetime
    strategy_tier: str  # 'scalping', 'trend', 'macro'
    strategy_id: str
    signal_action: str  # 'buy', 'sell', 'hold'
    confidence: float
    strength: float
    reasoning: str
    market_regime: str
    indicators: Dict[str, Any]
    trade_executed: bool = False
    trade_id: Optional[int] = None
    pnl: float = 0.0
    execution_duration: float = 0.0  # 실행 시간 (ms)
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['execution_time'] = self.execution_time.isoformat()
        data['indicators'] = json.dumps(self.indicators)
        return data


@dataclass
class StrategyPerformanceMetrics:
    """전략 성과 지표"""
    strategy_tier: str
    strategy_id: str
    total_executions: int
    signals_generated: int
    trades_executed: int
    success_rate: float
    avg_confidence: float
    avg_pnl: float
    total_pnl: float
    avg_execution_time: float
    last_execution: datetime
    
    
class StrategyExecutionTracker:
    """전략 실행 추적기"""
    
    def __init__(self, db_path: str = "data/strategy_executions.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('StrategyExecutionTracker')
        self._init_database()
        
    def _init_database(self):
        """데이터베이스 초기화"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # 전략 실행 기록 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS strategy_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_time TEXT NOT NULL,
                    strategy_tier TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    signal_action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    strength REAL,
                    reasoning TEXT,
                    market_regime TEXT,
                    indicators TEXT,  -- JSON
                    trade_executed BOOLEAN DEFAULT FALSE,
                    trade_id INTEGER,
                    pnl REAL DEFAULT 0,
                    execution_duration REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_execution_time 
                ON strategy_executions(execution_time)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_strategy 
                ON strategy_executions(strategy_tier, strategy_id)
            ''')
            
            # 전략 성과 요약 테이블 (캐시용)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS strategy_performance_cache (
                    id INTEGER PRIMARY KEY,
                    strategy_tier TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_executions INTEGER DEFAULT 0,
                    signals_generated INTEGER DEFAULT 0,
                    trades_executed INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0,
                    avg_confidence REAL DEFAULT 0,
                    avg_pnl REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    avg_execution_time REAL DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(strategy_tier, strategy_id, date)
                )
            ''')
            
            conn.commit()
            self.logger.info("전략 실행 추적 데이터베이스 초기화 완료")
    
    def record_execution(self, execution: StrategyExecution) -> bool:
        """전략 실행 기록 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                data = execution.to_dict()
                
                conn.execute('''
                    INSERT INTO strategy_executions 
                    (execution_time, strategy_tier, strategy_id, signal_action, 
                     confidence, strength, reasoning, market_regime, indicators,
                     trade_executed, trade_id, pnl, execution_duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['execution_time'], data['strategy_tier'], data['strategy_id'],
                    data['signal_action'], data['confidence'], data['strength'],
                    data['reasoning'], data['market_regime'], data['indicators'],
                    data['trade_executed'], data['trade_id'], data['pnl'],
                    data['execution_duration']
                ))
                
                conn.commit()
                
                # 일일 성과 캐시 업데이트
                self._update_daily_cache(execution)
                
                return True
                
        except Exception as e:
            self.logger.error(f"전략 실행 기록 저장 오류: {e}")
            return False
    
    def _update_daily_cache(self, execution: StrategyExecution):
        """일일 성과 캐시 업데이트"""
        try:
            date_str = execution.execution_time.date().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # 해당 날짜의 기존 캐시 조회
                cursor = conn.execute('''
                    SELECT total_executions, signals_generated, trades_executed,
                           total_pnl, avg_execution_time
                    FROM strategy_performance_cache 
                    WHERE strategy_tier = ? AND strategy_id = ? AND date = ?
                ''', (execution.strategy_tier, execution.strategy_id, date_str))
                
                row = cursor.fetchone()
                
                if row:
                    # 기존 캐시 업데이트
                    total_executions, signals_generated, trades_executed, total_pnl, avg_execution_time = row
                    
                    new_total_executions = total_executions + 1
                    new_signals_generated = signals_generated + (1 if execution.signal_action != 'hold' else 0)
                    new_trades_executed = trades_executed + (1 if execution.trade_executed else 0)
                    new_total_pnl = total_pnl + execution.pnl
                    new_avg_execution_time = ((avg_execution_time * total_executions) + execution.execution_duration) / new_total_executions
                    
                    # 성공률 계산
                    success_rate = new_trades_executed / new_signals_generated if new_signals_generated > 0 else 0
                    
                    # 평균 신뢰도 계산 (오늘 실행된 모든 기록에서)
                    cursor = conn.execute('''
                        SELECT AVG(confidence) FROM strategy_executions 
                        WHERE strategy_tier = ? AND strategy_id = ? 
                        AND date(execution_time) = ?
                    ''', (execution.strategy_tier, execution.strategy_id, date_str))
                    
                    avg_confidence = cursor.fetchone()[0] or 0
                    avg_pnl = new_total_pnl / new_trades_executed if new_trades_executed > 0 else 0
                    
                    conn.execute('''
                        UPDATE strategy_performance_cache 
                        SET total_executions = ?, signals_generated = ?, trades_executed = ?,
                            success_rate = ?, avg_confidence = ?, avg_pnl = ?, total_pnl = ?,
                            avg_execution_time = ?, last_updated = ?
                        WHERE strategy_tier = ? AND strategy_id = ? AND date = ?
                    ''', (new_total_executions, new_signals_generated, new_trades_executed,
                          success_rate, avg_confidence, avg_pnl, new_total_pnl,
                          new_avg_execution_time, datetime.now().isoformat(),
                          execution.strategy_tier, execution.strategy_id, date_str))
                else:
                    # 새 캐시 생성
                    signals_generated = 1 if execution.signal_action != 'hold' else 0
                    trades_executed = 1 if execution.trade_executed else 0
                    success_rate = trades_executed / signals_generated if signals_generated > 0 else 0
                    avg_pnl = execution.pnl if trades_executed > 0 else 0
                    
                    conn.execute('''
                        INSERT INTO strategy_performance_cache 
                        (strategy_tier, strategy_id, date, total_executions, signals_generated,
                         trades_executed, success_rate, avg_confidence, avg_pnl, total_pnl,
                         avg_execution_time, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (execution.strategy_tier, execution.strategy_id, date_str,
                          1, signals_generated, trades_executed, success_rate,
                          execution.confidence, avg_pnl, execution.pnl,
                          execution.execution_duration, datetime.now().isoformat()))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"일일 캐시 업데이트 오류: {e}")
    
    def get_strategy_performance(self, strategy_tier: str = None, 
                               strategy_id: str = None,
                               days: int = 30) -> List[Dict]:
        """전략 성과 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
                
                query = '''
                    SELECT strategy_tier, strategy_id, date, total_executions,
                           signals_generated, trades_executed, success_rate,
                           avg_confidence, avg_pnl, total_pnl, avg_execution_time
                    FROM strategy_performance_cache
                    WHERE date >= ?
                '''
                params = [start_date]
                
                if strategy_tier:
                    query += ' AND strategy_tier = ?'
                    params.append(strategy_tier)
                
                if strategy_id:
                    query += ' AND strategy_id = ?'
                    params.append(strategy_id)
                
                query += ' ORDER BY date DESC, strategy_tier, strategy_id'
                
                cursor = conn.execute(query, params)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'strategy_tier': row[0],
                        'strategy_id': row[1],
                        'date': row[2],
                        'total_executions': row[3],
                        'signals_generated': row[4],
                        'trades_executed': row[5],
                        'success_rate': row[6],
                        'avg_confidence': row[7],
                        'avg_pnl': row[8],
                        'total_pnl': row[9],
                        'avg_execution_time': row[10]
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"전략 성과 조회 오류: {e}")
            return []
    
    def get_execution_history(self, strategy_tier: str = None,
                            strategy_id: str = None,
                            hours: int = 24,
                            limit: int = 100) -> List[Dict]:
        """전략 실행 이력 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
                
                query = '''
                    SELECT execution_time, strategy_tier, strategy_id, signal_action,
                           confidence, strength, reasoning, market_regime, indicators,
                           trade_executed, trade_id, pnl, execution_duration
                    FROM strategy_executions
                    WHERE execution_time >= ?
                '''
                params = [start_time]
                
                if strategy_tier:
                    query += ' AND strategy_tier = ?'
                    params.append(strategy_tier)
                
                if strategy_id:
                    query += ' AND strategy_id = ?'
                    params.append(strategy_id)
                
                query += ' ORDER BY execution_time DESC LIMIT ?'
                params.append(limit)
                
                cursor = conn.execute(query, params)
                
                results = []
                for row in cursor.fetchall():
                    indicators = json.loads(row[8]) if row[8] else {}
                    
                    results.append({
                        'execution_time': row[0],
                        'strategy_tier': row[1],
                        'strategy_id': row[2],
                        'signal_action': row[3],
                        'confidence': row[4],
                        'strength': row[5],
                        'reasoning': row[6],
                        'market_regime': row[7],
                        'indicators': indicators,
                        'trade_executed': bool(row[9]),
                        'trade_id': row[10],
                        'pnl': row[11],
                        'execution_duration': row[12]
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"전략 실행 이력 조회 오류: {e}")
            return []
    
    def get_strategy_summary(self, days: int = 7) -> Dict[str, Any]:
        """전략 요약 통계"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
                
                # 계층별 요약
                cursor = conn.execute('''
                    SELECT strategy_tier,
                           SUM(total_executions) as total_executions,
                           SUM(signals_generated) as total_signals,
                           SUM(trades_executed) as total_trades,
                           AVG(success_rate) as avg_success_rate,
                           AVG(avg_confidence) as avg_confidence,
                           SUM(total_pnl) as total_pnl,
                           AVG(avg_execution_time) as avg_execution_time
                    FROM strategy_performance_cache
                    WHERE date >= ?
                    GROUP BY strategy_tier
                ''', (start_date,))
                
                tier_summary = {}
                for row in cursor.fetchall():
                    tier_summary[row[0]] = {
                        'total_executions': row[1],
                        'total_signals': row[2],
                        'total_trades': row[3],
                        'avg_success_rate': row[4],
                        'avg_confidence': row[5],
                        'total_pnl': row[6],
                        'avg_execution_time': row[7]
                    }
                
                # 전체 요약
                cursor = conn.execute('''
                    SELECT SUM(total_executions), SUM(signals_generated), 
                           SUM(trades_executed), AVG(success_rate),
                           AVG(avg_confidence), SUM(total_pnl)
                    FROM strategy_performance_cache
                    WHERE date >= ?
                ''', (start_date,))
                
                row = cursor.fetchone()
                overall_summary = {
                    'total_executions': row[0] or 0,
                    'total_signals': row[1] or 0,
                    'total_trades': row[2] or 0,
                    'avg_success_rate': row[3] or 0,
                    'avg_confidence': row[4] or 0,
                    'total_pnl': row[5] or 0
                }
                
                return {
                    'period_days': days,
                    'overall': overall_summary,
                    'by_tier': tier_summary
                }
                
        except Exception as e:
            self.logger.error(f"전략 요약 통계 조회 오류: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 90):
        """오래된 데이터 정리"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # 오래된 실행 기록 삭제
                cursor = conn.execute('''
                    DELETE FROM strategy_executions WHERE execution_time < ?
                ''', (cutoff_date,))
                
                deleted_executions = cursor.rowcount
                
                # 오래된 캐시 삭제
                cutoff_date_str = (datetime.now() - timedelta(days=days)).date().isoformat()
                cursor = conn.execute('''
                    DELETE FROM strategy_performance_cache WHERE date < ?
                ''', (cutoff_date_str,))
                
                deleted_cache = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(f"오래된 데이터 정리: 실행기록 {deleted_executions}개, 캐시 {deleted_cache}개 삭제")
                
        except Exception as e:
            self.logger.error(f"데이터 정리 오류: {e}")


# 전역 인스턴스
execution_tracker = StrategyExecutionTracker()
