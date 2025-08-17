"""
신호 기록 시스템 - 모든 분석 결과를 누적 저장
Signal Recording System - Accumulate all analysis results
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging
from dataclasses import asdict


class SignalRecorder:
    """전략 신호 기록 시스템"""
    
    def __init__(self, db_path: str = "data/signal_history.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('SignalRecorder')
        self._initialize_database()
    
    def _initialize_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 신호 기록 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                strategy_id TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                price REAL,
                suggested_amount REAL,
                reasoning TEXT,
                executed BOOLEAN DEFAULT FALSE,
                execution_result TEXT,
                market_data TEXT,
                additional_data TEXT
            )
        """)
        
        # 통합 신호 기록 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consolidated_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                suggested_amount REAL,
                reasoning TEXT,
                contributing_strategies TEXT,
                market_condition TEXT,
                executed BOOLEAN DEFAULT FALSE,
                execution_result TEXT,
                signal_distribution TEXT
            )
        """)
        
        # 분석 세션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                auto_trade_enabled BOOLEAN,
                strategies_analyzed INTEGER,
                signals_generated INTEGER,
                decision TEXT,
                session_metadata TEXT
            )
        """)
        
        # 성능 분석 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                date TEXT NOT NULL,
                total_signals INTEGER DEFAULT 0,
                executed_signals INTEGER DEFAULT 0,
                successful_signals INTEGER DEFAULT 0,
                avg_confidence REAL,
                total_pnl REAL DEFAULT 0,
                accuracy_rate REAL,
                UNIQUE(strategy_id, date)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_timestamp ON signal_history(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_strategy ON signal_history(strategy_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consolidated_timestamp ON consolidated_signals(timestamp)")
        
        conn.commit()
        conn.close()
        
        self.logger.info("신호 기록 데이터베이스 초기화 완료")
    
    def record_signal(self, signal_data: Dict, executed: bool = False) -> int:
        """개별 전략 신호 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO signal_history 
            (timestamp, strategy_id, action, confidence, price, suggested_amount, 
             reasoning, executed, market_data, additional_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            signal_data.get('strategy_id'),
            signal_data.get('action'),
            signal_data.get('confidence', 0),
            signal_data.get('price', 0),
            signal_data.get('suggested_amount', 0),
            signal_data.get('reasoning', ''),
            executed,
            json.dumps(signal_data.get('market_data', {})),
            json.dumps(signal_data.get('additional_data', {}))
        ))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 일일 성능 업데이트
        self._update_daily_performance(signal_data['strategy_id'])
        
        return signal_id
    
    def record_consolidated_signal(self, consolidated_data: Dict, executed: bool = False) -> int:
        """통합 신호 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO consolidated_signals 
            (timestamp, action, confidence, suggested_amount, reasoning,
             contributing_strategies, market_condition, executed, signal_distribution)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            consolidated_data.get('action'),
            consolidated_data.get('confidence', 0),
            consolidated_data.get('suggested_amount', 0),
            consolidated_data.get('reasoning', ''),
            json.dumps(consolidated_data.get('contributing_strategies', [])),
            consolidated_data.get('market_condition', ''),
            executed,
            json.dumps(consolidated_data.get('signal_distribution', {}))
        ))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return signal_id
    
    def record_analysis_session(self, session_data: Dict) -> int:
        """분석 세션 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO analysis_sessions 
            (timestamp, auto_trade_enabled, strategies_analyzed, signals_generated,
             decision, session_metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            session_data.get('auto_trade_enabled', False),
            session_data.get('strategies_analyzed', 0),
            session_data.get('signals_generated', 0),
            session_data.get('decision', 'hold'),
            json.dumps(session_data.get('metadata', {}))
        ))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def update_signal_execution(self, signal_id: int, result: str, is_consolidated: bool = False):
        """신호 실행 결과 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        table = "consolidated_signals" if is_consolidated else "signal_history"
        
        cursor.execute(f"""
            UPDATE {table}
            SET executed = TRUE, execution_result = ?
            WHERE id = ?
        """, (result, signal_id))
        
        conn.commit()
        conn.close()
    
    def _update_daily_performance(self, strategy_id: str):
        """일일 성능 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 오늘의 신호 통계 계산
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
                AVG(confidence) as avg_conf
            FROM signal_history
            WHERE strategy_id = ? 
            AND date(datetime(timestamp, 'unixepoch')) = ?
        """, (strategy_id, today))
        
        stats = cursor.fetchone()
        if stats and stats[0] > 0:
            cursor.execute("""
                INSERT OR REPLACE INTO signal_performance 
                (strategy_id, date, total_signals, executed_signals, avg_confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                strategy_id, today, stats[0], stats[1] or 0, stats[2] or 0
            ))
        
        conn.commit()
        conn.close()
    
    def get_signal_history(self, strategy_id: Optional[str] = None, 
                          days: int = 7) -> List[Dict]:
        """신호 히스토리 조회"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT * FROM signal_history
            WHERE timestamp > ?
        """
        params = [int((datetime.now().timestamp() - days * 86400))]
        
        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        
        query += " ORDER BY timestamp DESC"
        
        cursor = conn.execute(query, params)
        columns = [col[0] for col in cursor.description]
        
        results = []
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            # JSON 필드 파싱
            if result.get('market_data'):
                result['market_data'] = json.loads(result['market_data'])
            if result.get('additional_data'):
                result['additional_data'] = json.loads(result['additional_data'])
            results.append(result)
        
        conn.close()
        return results
    
    def get_strategy_accuracy(self, strategy_id: str, days: int = 30) -> Dict:
        """전략 정확도 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 실행된 신호들의 성공률 계산
        cursor.execute("""
            SELECT 
                COUNT(*) as total_executed,
                SUM(CASE WHEN execution_result LIKE '%success%' THEN 1 ELSE 0 END) as successful,
                AVG(confidence) as avg_confidence
            FROM signal_history
            WHERE strategy_id = ?
            AND executed = TRUE
            AND timestamp > ?
        """, (
            strategy_id,
            int((datetime.now().timestamp() - days * 86400))
        ))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] > 0:
            return {
                'total_executed': result[0],
                'successful': result[1] or 0,
                'accuracy_rate': (result[1] or 0) / result[0] * 100,
                'avg_confidence': result[2] or 0
            }
        
        return {
            'total_executed': 0,
            'successful': 0,
            'accuracy_rate': 0,
            'avg_confidence': 0
        }
    
    def analyze_signal_performance(self, days: int = 30) -> Dict:
        """신호 성능 종합 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_timestamp = int((datetime.now().timestamp() - days * 86400))
        
        # 전략별 성능
        cursor.execute("""
            SELECT 
                strategy_id,
                COUNT(*) as total_signals,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed_signals,
                AVG(confidence) as avg_confidence,
                SUM(CASE WHEN action = 'buy' THEN 1 ELSE 0 END) as buy_signals,
                SUM(CASE WHEN action = 'sell' THEN 1 ELSE 0 END) as sell_signals
            FROM signal_history
            WHERE timestamp > ?
            GROUP BY strategy_id
        """, (start_timestamp,))
        
        strategy_performance = {}
        for row in cursor.fetchall():
            strategy_performance[row[0]] = {
                'total_signals': row[1],
                'executed_signals': row[2],
                'avg_confidence': row[3],
                'buy_signals': row[4],
                'sell_signals': row[5],
                'execution_rate': row[2] / row[1] * 100 if row[1] > 0 else 0
            }
        
        # 시간대별 분석
        cursor.execute("""
            SELECT 
                strftime('%H', datetime(timestamp, 'unixepoch')) as hour,
                COUNT(*) as signal_count,
                AVG(confidence) as avg_confidence
            FROM signal_history
            WHERE timestamp > ?
            GROUP BY hour
            ORDER BY hour
        """, (start_timestamp,))
        
        hourly_distribution = {}
        for row in cursor.fetchall():
            hourly_distribution[int(row[0])] = {
                'signal_count': row[1],
                'avg_confidence': row[2]
            }
        
        # 실행 vs 미실행 비교
        cursor.execute("""
            SELECT 
                executed,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM signal_history
            WHERE timestamp > ?
            GROUP BY executed
        """, (start_timestamp,))
        
        execution_comparison = {}
        for row in cursor.fetchall():
            execution_comparison['executed' if row[0] else 'not_executed'] = {
                'count': row[1],
                'avg_confidence': row[2]
            }
        
        conn.close()
        
        return {
            'strategy_performance': strategy_performance,
            'hourly_distribution': hourly_distribution,
            'execution_comparison': execution_comparison,
            'analysis_period_days': days
        }


# 싱글톤 인스턴스
signal_recorder = SignalRecorder()