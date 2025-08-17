"""
히스토리컬 데이터 수집 및 관리 시스템
Historical Data Collection and Management System
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple
import requests
import json

class DataCollector:
    """히스토리컬 데이터 수집기"""
    
    def __init__(self, db_path: str = "data/market_data.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('DataCollector')
        self.base_url = "https://api.upbit.com"
        
        # 데이터베이스 초기화
        self._initialize_database()
        
    def _initialize_database(self):
        """데이터베이스 테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # OHLCV 데이터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(market, timeframe, timestamp)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ohlcv_market_timeframe_timestamp 
            ON ohlcv(market, timeframe, timestamp)
        """)
        
        # 티커 데이터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                trade_price REAL NOT NULL,
                trade_volume REAL NOT NULL,
                acc_trade_volume_24h REAL,
                acc_trade_price_24h REAL,
                high_price REAL,
                low_price REAL,
                UNIQUE(market, timestamp)
            )
        """)
        
        # 오더북 스냅샷 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orderbook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                total_ask_size REAL,
                total_bid_size REAL,
                orderbook_units TEXT,  -- JSON 형태로 저장
                UNIQUE(market, timestamp)
            )
        """)
        
        # 거래 체결 데이터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                trade_timestamp INTEGER NOT NULL,
                trade_price REAL NOT NULL,
                trade_volume REAL NOT NULL,
                ask_bid TEXT NOT NULL,  -- 'ASK' or 'BID'
                sequential_id INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
        
        self.logger.info("데이터베이스 초기화 완료")
    
    def collect_historical_candles(self, market: str = "KRW-BTC", 
                                  timeframe: str = "60", 
                                  days_back: int = 30) -> pd.DataFrame:
        """히스토리컬 캔들 데이터 수집"""
        try:
            all_candles = []
            current_time = datetime.now()
            
            # 시간 단위별 API 엔드포인트 설정
            if timeframe == "1":
                endpoint = "/v1/candles/minutes/1"
                max_count = 200
            elif timeframe == "60":
                endpoint = "/v1/candles/minutes/60"
                max_count = 200
            elif timeframe == "240":
                endpoint = "/v1/candles/minutes/240"
                max_count = 200
            elif timeframe == "1440":
                endpoint = "/v1/candles/days"
                max_count = 200
            else:
                self.logger.error(f"지원하지 않는 timeframe: {timeframe}")
                return pd.DataFrame()
            
            # 날짜별로 데이터 수집
            for day_offset in range(days_back):
                to_time = current_time - timedelta(days=day_offset)
                
                params = {
                    'market': market,
                    'to': to_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'count': max_count
                }
                
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    params=params
                )
                
                if response.status_code == 200:
                    candles = response.json()
                    all_candles.extend(candles)
                    
                    # 데이터베이스에 저장
                    self._save_candles_to_db(candles, market, timeframe)
                    
                    # API 레이트 리밋 고려
                    time.sleep(0.2)
                else:
                    self.logger.error(f"API 오류: {response.status_code}")
                    break
            
            # DataFrame으로 변환
            if all_candles:
                df = pd.DataFrame(all_candles)
                df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
                df = df.sort_values('candle_date_time_kst')
                df = df.drop_duplicates(subset=['candle_date_time_kst'])
                
                # 컬럼명 정리
                df = df.rename(columns={
                    'candle_date_time_kst': 'timestamp',
                    'opening_price': 'open',
                    'high_price': 'high',
                    'low_price': 'low',
                    'trade_price': 'close',
                    'candle_acc_trade_volume': 'volume'
                })
                
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            return pd.DataFrame()
            
        except Exception as e:
            self.logger.error(f"히스토리컬 데이터 수집 오류: {e}")
            return pd.DataFrame()
    
    def _save_candles_to_db(self, candles: List[Dict], market: str, timeframe: str):
        """캔들 데이터를 데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for candle in candles:
            try:
                timestamp = int(pd.Timestamp(candle['candle_date_time_kst']).timestamp())
                
                cursor.execute("""
                    INSERT OR REPLACE INTO ohlcv 
                    (market, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    market,
                    timeframe,
                    timestamp,
                    candle['opening_price'],
                    candle['high_price'],
                    candle['low_price'],
                    candle['trade_price'],
                    candle['candle_acc_trade_volume']
                ))
            except Exception as e:
                self.logger.error(f"캔들 저장 오류: {e}")
        
        conn.commit()
        conn.close()
    
    def get_historical_data(self, market: str = "KRW-BTC", 
                           timeframe: str = "60",
                           start_date: datetime = None,
                           end_date: datetime = None) -> pd.DataFrame:
        """데이터베이스에서 히스토리컬 데이터 조회"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE market = ? AND timeframe = ?
        """
        
        params = [market, timeframe]
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(int(start_date.timestamp()))
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(int(end_date.timestamp()))
        
        query += " ORDER BY timestamp"
        
        df = pd.read_sql_query(query, conn, params=params)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        conn.close()
        
        return df
    
    def collect_orderbook(self, market: str = "KRW-BTC") -> Dict:
        """오더북 데이터 수집"""
        try:
            response = requests.get(
                f"{self.base_url}/v1/orderbook",
                params={'markets': market}
            )
            
            if response.status_code == 200:
                data = response.json()[0]
                
                # 데이터베이스에 저장
                self._save_orderbook_to_db(data)
                
                return data
            
            return {}
            
        except Exception as e:
            self.logger.error(f"오더북 수집 오류: {e}")
            return {}
    
    def _save_orderbook_to_db(self, orderbook_data: Dict):
        """오더북 데이터를 데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT INTO orderbook 
            (market, timestamp, total_ask_size, total_bid_size, orderbook_units)
            VALUES (?, ?, ?, ?, ?)
        """, (
            orderbook_data['market'],
            timestamp,
            orderbook_data['total_ask_size'],
            orderbook_data['total_bid_size'],
            json.dumps(orderbook_data['orderbook_units'])
        ))
        
        conn.commit()
        conn.close()
    
    def collect_trades(self, market: str = "KRW-BTC", count: int = 100) -> List[Dict]:
        """최근 체결 데이터 수집"""
        try:
            response = requests.get(
                f"{self.base_url}/v1/trades/ticks",
                params={'market': market, 'count': count}
            )
            
            if response.status_code == 200:
                trades = response.json()
                
                # 데이터베이스에 저장
                self._save_trades_to_db(trades, market)
                
                return trades
            
            return []
            
        except Exception as e:
            self.logger.error(f"체결 데이터 수집 오류: {e}")
            return []
    
    def _save_trades_to_db(self, trades: List[Dict], market: str):
        """체결 데이터를 데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = int(datetime.now().timestamp())
        
        for trade in trades:
            try:
                cursor.execute("""
                    INSERT INTO trades 
                    (market, timestamp, trade_timestamp, trade_price, trade_volume, ask_bid, sequential_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    market,
                    timestamp,
                    trade['timestamp'],
                    trade['trade_price'],
                    trade['trade_volume'],
                    trade['ask_bid'],
                    trade['sequential_id']
                ))
            except Exception as e:
                self.logger.error(f"체결 데이터 저장 오류: {e}")
        
        conn.commit()
        conn.close()
    
    def get_data_summary(self) -> Dict:
        """저장된 데이터 요약 정보"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        summary = {}
        
        # OHLCV 데이터 요약
        cursor.execute("""
            SELECT 
                market,
                timeframe,
                COUNT(*) as count,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time
            FROM ohlcv
            GROUP BY market, timeframe
        """)
        
        summary['ohlcv'] = cursor.fetchall()
        
        # 오더북 데이터 요약
        cursor.execute("""
            SELECT 
                market,
                COUNT(*) as count,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time
            FROM orderbook
            GROUP BY market
        """)
        
        summary['orderbook'] = cursor.fetchall()
        
        # 체결 데이터 요약
        cursor.execute("""
            SELECT 
                market,
                COUNT(*) as count,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time
            FROM trades
            GROUP BY market
        """)
        
        summary['trades'] = cursor.fetchall()
        
        conn.close()
        
        return summary
    
    def run_continuous_collection(self, interval_minutes: int = 5):
        """지속적인 데이터 수집 실행"""
        self.logger.info(f"데이터 수집 시작 (간격: {interval_minutes}분)")
        
        while True:
            try:
                # 캔들 데이터 수집 (1시간봉)
                self.collect_historical_candles("KRW-BTC", "60", days_back=1)
                
                # 오더북 데이터 수집
                self.collect_orderbook("KRW-BTC")
                
                # 체결 데이터 수집
                self.collect_trades("KRW-BTC", count=100)
                
                self.logger.info("데이터 수집 완료")
                
                # 대기
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                self.logger.info("데이터 수집 중단")
                break
            except Exception as e:
                self.logger.error(f"데이터 수집 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기

# 사용 예시
if __name__ == "__main__":
    collector = DataCollector()
    
    # 히스토리컬 데이터 수집 (30일)
    df = collector.collect_historical_candles("KRW-BTC", "60", days_back=30)
    print(f"수집된 데이터: {len(df)} 개")
    
    # 데이터 요약
    summary = collector.get_data_summary()
    print("데이터 요약:", summary)