"""
5분 캔들 데이터 수집 및 관리 시스템
실시간 5분 캔들 데이터 수집, 저장, 캐싱을 담당
"""

import asyncio
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import logging
from dataclasses import dataclass, asdict
import json
import os

from core.upbit_api import UpbitAPI


@dataclass
class CandleData:
    """캔들 데이터 구조"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    market: str = "KRW-BTC"
    timeframe: str = "5m"

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'market': self.market,
            'timeframe': self.timeframe
        }


class CandleDataCollector:
    """5분 캔들 데이터 수집기"""

    def __init__(self, db_path: str = "data/candle_data.db"):
        self.db_path = db_path
        self.api = UpbitAPI(paper_trading=False)  # 공개 API는 인증 불필요
        self.logger = logging.getLogger('CandleDataCollector')

        # 실시간 수집 제어
        self.running = False
        self.collection_thread = None
        self.last_collection_time = None

        # 캐시 시스템
        self.cache = {}
        self.cache_duration = 60  # 1분 캐시
        self.cache_lock = threading.Lock()

        # 데이터베이스 초기화
        self._init_database()

        # 수집 간격 설정
        self.collection_intervals = {
            '1m': 60,      # 1분
            '5m': 300,     # 5분
            '15m': 900,    # 15분
            '1h': 3600,    # 1시간
            '1d': 86400    # 1일
        }

    def _init_database(self):
        """데이터베이스 초기화"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # 캔들 데이터 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS candle_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    market TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(timestamp, market, timeframe)
                )
            ''')

            # 인덱스 생성
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_candle_timestamp_market_timeframe 
                ON candle_data(timestamp, market, timeframe)
            ''')

            # 수집 통계 테이블
            conn.execute('''
                CREATE TABLE IF NOT EXISTS collection_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    collected_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    last_collection TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, timeframe)
                )
            ''')

            conn.commit()
            self.logger.info("캔들 데이터 데이터베이스 초기화 완료")

    def start_collection(self, timeframes: List[str] = ['5m']):
        """실시간 데이터 수집 시작"""
        if self.running:
            self.logger.warning("데이터 수집이 이미 실행 중입니다.")
            return

        self.running = True
        self.timeframes = timeframes

        # 수집 스레드 시작
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()

        self.logger.info(f"캔들 데이터 수집 시작 - 시간대: {timeframes}")

    def stop_collection(self):
        """데이터 수집 중지"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        self.logger.info("캔들 데이터 수집 중지됨")

    def _collection_loop(self):
        """데이터 수집 메인 루프"""
        while self.running:
            try:
                for timeframe in self.timeframes:
                    if not self.running:
                        break

                    self._collect_timeframe_data(timeframe)

                # 5초 대기 (5분마다 수집하되 체크는 자주)
                time.sleep(5)

            except Exception as e:
                self.logger.error(f"데이터 수집 루프 오류: {e}")
                time.sleep(30)  # 오류 시 30초 대기

    def _collect_timeframe_data(self, timeframe: str):
        """특정 시간대 데이터 수집"""
        try:
            # 수집 간격 체크
            interval = self.collection_intervals.get(timeframe, 300)
            if self.last_collection_time and \
               (datetime.now() - self.last_collection_time).seconds < interval - 10:
                return

            # Upbit API에서 데이터 수집
            minutes_map = {
                '1m': 1,
                '5m': 5,
                '15m': 15,
                '1h': 60,
                '1d': 1440
            }

            minutes = minutes_map.get(timeframe)
            if not minutes:
                self.logger.error(f"지원하지 않는 시간대: {timeframe}")
                return

            # 최신 캔들 데이터 수집 (최근 10개)
            candles = self.api.get_candles(
                "KRW-BTC", minutes=minutes, count=10)

            if not candles:
                self.logger.warning(f"{timeframe} 캔들 데이터 수집 실패")
                self._update_collection_stats(timeframe, False)
                return

            # 데이터베이스에 저장
            saved_count = 0
            for candle in candles:
                if self._save_candle_data(candle, timeframe):
                    saved_count += 1

            if saved_count > 0:
                self.logger.info(f"{timeframe} 캔들 데이터 {saved_count}개 수집 완료")
                self._update_collection_stats(timeframe, True, saved_count)

            self.last_collection_time = datetime.now()

        except Exception as e:
            self.logger.error(f"{timeframe} 데이터 수집 오류: {e}")
            self._update_collection_stats(timeframe, False)

    def _save_candle_data(self, candle: Dict, timeframe: str) -> bool:
        """캔들 데이터를 데이터베이스에 저장"""
        try:
            timestamp = candle['candle_date_time_kst']

            candle_data = CandleData(
                timestamp=datetime.fromisoformat(
                    timestamp.replace('Z', '+00:00')),
                open=float(candle['opening_price']),
                high=float(candle['high_price']),
                low=float(candle['low_price']),
                close=float(candle['trade_price']),
                volume=float(candle['candle_acc_trade_volume']),
                market="KRW-BTC",
                timeframe=timeframe
            )

            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO candle_data 
                    (timestamp, market, timeframe, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    candle_data.timestamp.isoformat(),
                    candle_data.market,
                    candle_data.timeframe,
                    candle_data.open,
                    candle_data.high,
                    candle_data.low,
                    candle_data.close,
                    candle_data.volume
                ))
                conn.commit()

            return True

        except Exception as e:
            self.logger.error(f"캔들 데이터 저장 오류: {e}")
            return False

    def _update_collection_stats(self, timeframe: str, success: bool, count: int = 0):
        """수집 통계 업데이트"""
        try:
            today = datetime.now().date().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                # 기존 통계 조회
                cursor = conn.execute('''
                    SELECT collected_count, failed_count FROM collection_stats 
                    WHERE date = ? AND timeframe = ?
                ''', (today, timeframe))

                row = cursor.fetchone()

                if row:
                    # 기존 통계 업데이트
                    collected, failed = row
                    if success:
                        collected += count
                    else:
                        failed += 1

                    conn.execute('''
                        UPDATE collection_stats 
                        SET collected_count = ?, failed_count = ?, last_collection = ?
                        WHERE date = ? AND timeframe = ?
                    ''', (collected, failed, datetime.now().isoformat(), today, timeframe))
                else:
                    # 새 통계 생성
                    collected = count if success else 0
                    failed = 0 if success else 1

                    conn.execute('''
                        INSERT INTO collection_stats 
                        (date, timeframe, collected_count, failed_count, last_collection)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (today, timeframe, collected, failed, datetime.now().isoformat()))

                conn.commit()

        except Exception as e:
            self.logger.error(f"수집 통계 업데이트 오류: {e}")

    def get_candles(self, timeframe: str = '5m', count: int = 100,
                    end_time: Optional[datetime] = None) -> List[CandleData]:
        """저장된 캔들 데이터 조회"""
        try:
            # 캐시 확인
            cache_key = f"{timeframe}_{count}_{end_time}"
            with self.cache_lock:
                if cache_key in self.cache:
                    cache_time, cached_data = self.cache[cache_key]
                    if (datetime.now() - cache_time).seconds < self.cache_duration:
                        return cached_data

            with sqlite3.connect(self.db_path) as conn:
                if end_time:
                    cursor = conn.execute('''
                        SELECT timestamp, open, high, low, close, volume, market, timeframe
                        FROM candle_data 
                        WHERE timeframe = ? AND timestamp <= ?
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (timeframe, end_time.isoformat(), count))
                else:
                    cursor = conn.execute('''
                        SELECT timestamp, open, high, low, close, volume, market, timeframe
                        FROM candle_data 
                        WHERE timeframe = ?
                        ORDER BY timestamp DESC LIMIT ?
                    ''', (timeframe, count))

                rows = cursor.fetchall()

                candles = []
                for row in rows:
                    candle = CandleData(
                        timestamp=datetime.fromisoformat(row[0]),
                        open=row[1],
                        high=row[2],
                        low=row[3],
                        close=row[4],
                        volume=row[5],
                        market=row[6],
                        timeframe=row[7]
                    )
                    candles.append(candle)

                # 시간순 정렬 (오래된 것부터)
                candles.reverse()

                # 캐시 저장
                with self.cache_lock:
                    self.cache[cache_key] = (datetime.now(), candles)

                return candles

        except Exception as e:
            self.logger.error(f"캔들 데이터 조회 오류: {e}")
            return []

    def get_dataframe(self, timeframe: str = '5m', count: int = 100) -> Optional[pd.DataFrame]:
        """pandas DataFrame 형태로 캔들 데이터 반환"""
        candles = self.get_candles(timeframe, count)

        if not candles:
            return None

        data = []
        for candle in candles:
            data.append({
                'timestamp': candle.timestamp,
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })

        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def get_latest_price(self) -> Optional[float]:
        """최신 가격 조회"""
        candles = self.get_candles('5m', 1)
        if candles:
            return candles[-1].close
        return None

    def get_collection_stats(self, days: int = 7) -> Dict[str, Any]:
        """데이터 수집 통계 조회"""
        try:
            start_date = (datetime.now() - timedelta(days=days)
                          ).date().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT date, timeframe, collected_count, failed_count, last_collection
                    FROM collection_stats 
                    WHERE date >= ?
                    ORDER BY date DESC, timeframe
                ''', (start_date,))

                stats = {}
                for row in cursor.fetchall():
                    date, timeframe, collected, failed, last_collection = row

                    if date not in stats:
                        stats[date] = {}

                    stats[date][timeframe] = {
                        'collected': collected,
                        'failed': failed,
                        'last_collection': last_collection,
                        'success_rate': collected / (collected + failed) if (collected + failed) > 0 else 0
                    }

                return stats

        except Exception as e:
            self.logger.error(f"수집 통계 조회 오류: {e}")
            return {}

    def get_candles_cached(self, timeframe_type: str, interval: int, count: int = 100) -> Optional[List[Dict]]:
        """
        VotingStrategyEngine 호환성을 위한 캐시된 캔들 데이터 조회
        
        Args:
            timeframe_type: "minutes" 또는 "days"
            interval: 시간 간격 (1, 5, 15, 60, 1440)
            count: 개수
            
        Returns:
            Upbit API 형식과 호환되는 캔들 데이터 리스트
        """
        try:
            # 시간대 매핑
            timeframe_map = {
                ("minutes", 1): "1m",
                ("minutes", 5): "5m", 
                ("minutes", 15): "15m",
                ("minutes", 60): "1h",
                ("days", 1): "1d"
            }
            
            timeframe = timeframe_map.get((timeframe_type, interval))
            if not timeframe:
                self.logger.warning(f"지원하지 않는 시간대: {timeframe_type}={interval}")
                # 대체로 UpbitAPI 직접 호출
                return self.api.get_candles("KRW-BTC", minutes=interval if timeframe_type == "minutes" else None, count=count)
            
            # 저장된 데이터 조회
            candles = self.get_candles(timeframe, count)
            
            if not candles:
                self.logger.info(f"저장된 {timeframe} 데이터가 없음, UpbitAPI로 대체")
                # 저장된 데이터가 없으면 UpbitAPI 직접 호출
                return self.api.get_candles("KRW-BTC", minutes=interval if timeframe_type == "minutes" else None, count=count)
            
            # Upbit API 형식으로 변환
            result = []
            for candle in candles:
                result.append({
                    'candle_date_time_kst': candle.timestamp.isoformat(),
                    'opening_price': candle.open,
                    'high_price': candle.high,
                    'low_price': candle.low,
                    'trade_price': candle.close,
                    'candle_acc_trade_volume': candle.volume,
                    'market': candle.market
                })
            
            self.logger.debug(f"{timeframe} 캐시된 데이터 {len(result)}개 반환")
            return result
            
        except Exception as e:
            self.logger.error(f"캐시된 캔들 데이터 조회 오류: {e}")
            # 오류 시 UpbitAPI 직접 호출로 대체
            try:
                return self.api.get_candles("KRW-BTC", minutes=interval if timeframe_type == "minutes" else None, count=count)
            except Exception as api_error:
                self.logger.error(f"UpbitAPI 대체 호출도 실패: {api_error}")
                return None

    def cleanup_old_data(self, days: int = 30):
        """오래된 데이터 정리"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM candle_data WHERE timestamp < ?
                ''', (cutoff_date,))

                deleted_count = cursor.rowcount
                conn.commit()

                self.logger.info(f"오래된 캔들 데이터 {deleted_count}개 정리 완료")

        except Exception as e:
            self.logger.error(f"데이터 정리 오류: {e}")


# 전역 인스턴스
candle_collector = CandleDataCollector()
