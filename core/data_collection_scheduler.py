"""
데이터 수집 스케줄러
5분 캔들 데이터 및 기타 시장 데이터의 정기 수집을 관리
"""

import asyncio
import schedule
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from core.candle_data_collector import candle_collector
from core.upbit_api import UpbitAPI


class DataCollectionScheduler:
    """데이터 수집 스케줄 관리자"""

    def __init__(self):
        self.logger = logging.getLogger('DataCollectionScheduler')
        self.running = False
        self.scheduler_thread = None

        # 수집 대상 시간대
        self.timeframes = ['1m', '5m', '15m', '1h', '1d']

        # 수집 상태 추적
        self.collection_status = {}
        self.last_collection_times = {}

    def start(self):
        """스케줄러 시작"""
        if self.running:
            self.logger.warning("데이터 수집 스케줄러가 이미 실행 중입니다.")
            return

        self.running = True
        self._setup_schedules()

        # 스케줄러 스레드 시작
        self.scheduler_thread = threading.Thread(
            target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

        # 캔들 데이터 수집기 시작
        candle_collector.start_collection(self.timeframes)

        self.logger.info("데이터 수집 스케줄러 시작됨")

    def stop(self):
        """스케줄러 중지"""
        self.running = False

        # 캔들 데이터 수집기 중지
        candle_collector.stop_collection()

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        # 스케줄 정리
        schedule.clear()

        self.logger.info("데이터 수집 스케줄러 중지됨")

    def _setup_schedules(self):
        """수집 스케줄 설정"""
        # 매 5분마다 5분 캔들 데이터 품질 체크
        schedule.every(5).minutes.do(self._check_5min_data_quality)

        # 매 시간마다 1시간 캔들 데이터 보완
        schedule.every().hour.at(":05").do(self._collect_hourly_data)

        # 매일 자정 5분에 일일 데이터 수집 및 정리
        schedule.every().day.at("00:05").do(self._daily_data_maintenance)

        # 매 30분마다 수집 상태 점검
        schedule.every(30).minutes.do(self._check_collection_health)

        # 매주 일요일 자정에 데이터 정리
        schedule.every().sunday.at("00:00").do(self._weekly_cleanup)

        self.logger.info("데이터 수집 스케줄 설정 완료")

    def _run_scheduler(self):
        """스케줄러 실행 루프"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"스케줄러 실행 오류: {e}")
                time.sleep(10)

    def _check_5min_data_quality(self):
        """5분 캔들 데이터 품질 체크"""
        try:
            # 최근 5분 데이터 존재 여부 확인
            recent_candles = candle_collector.get_candles('5m', 1)

            if not recent_candles:
                self.logger.warning("최근 5분 캔들 데이터가 없습니다.")
                self._emergency_data_collection('5m')
                return

            latest_candle = recent_candles[0]
            time_diff = datetime.now() - latest_candle.timestamp

            # 최신 데이터가 10분 이상 오래된 경우 긴급 수집
            if time_diff.seconds > 600:
                self.logger.warning(f"5분 캔들 데이터가 {time_diff.seconds}초 지연됨")
                self._emergency_data_collection('5m')

            # 데이터 품질 검증 (가격 합리성 체크)
            self._validate_candle_data(latest_candle)

        except Exception as e:
            self.logger.error(f"5분 데이터 품질 체크 오류: {e}")

    def _emergency_data_collection(self, timeframe: str):
        """긴급 데이터 수집"""
        try:
            self.logger.info(f"{timeframe} 긴급 데이터 수집 시작")

            # Upbit API 직접 호출
            api = UpbitAPI(paper_trading=False)

            minutes_map = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '1d': 1440}
            minutes = minutes_map.get(timeframe)

            if minutes:
                candles = api.get_candles("KRW-BTC", minutes=minutes, count=20)
                if candles:
                    # 강제로 데이터 저장
                    saved_count = 0
                    for candle in candles:
                        if candle_collector._save_candle_data(candle, timeframe):
                            saved_count += 1

                    self.logger.info(
                        f"{timeframe} 긴급 데이터 수집 완료: {saved_count}개")
                else:
                    self.logger.error(f"{timeframe} 긴급 데이터 수집 실패")

        except Exception as e:
            self.logger.error(f"긴급 데이터 수집 오류: {e}")

    def _validate_candle_data(self, candle):
        """캔들 데이터 유효성 검증"""
        try:
            # 기본 유효성 체크
            if candle.high < candle.low:
                self.logger.error("캔들 데이터 오류: high < low")
                return False

            if candle.open < 0 or candle.close < 0:
                self.logger.error("캔들 데이터 오류: 음수 가격")
                return False

            if candle.volume < 0:
                self.logger.error("캔들 데이터 오류: 음수 거래량")
                return False

            # 가격 급변 체크 (전 캔들 대비 20% 이상 변화 시 경고)
            prev_candles = candle_collector.get_candles('5m', 2)
            if len(prev_candles) >= 2:
                prev_close = prev_candles[-2].close
                price_change = abs(candle.close - prev_close) / prev_close

                if price_change > 0.2:  # 20% 이상 변화
                    self.logger.warning(f"급격한 가격 변화 감지: {price_change:.2%}")

            return True

        except Exception as e:
            self.logger.error(f"캔들 데이터 검증 오류: {e}")
            return False

    def _collect_hourly_data(self):
        """시간별 데이터 수집"""
        try:
            self.logger.info("시간별 데이터 수집 시작")

            # 1시간 캔들 데이터 보완
            api = UpbitAPI(paper_trading=False)
            candles = api.get_candles(
                "KRW-BTC", minutes=60, count=24)  # 최근 24시간

            if candles:
                saved_count = 0
                for candle in candles:
                    if candle_collector._save_candle_data(candle, '1h'):
                        saved_count += 1

                self.logger.info(f"1시간 캔들 데이터 {saved_count}개 수집 완료")

        except Exception as e:
            self.logger.error(f"시간별 데이터 수집 오류: {e}")

    def _daily_data_maintenance(self):
        """일일 데이터 유지보수"""
        try:
            self.logger.info("일일 데이터 유지보수 시작")

            # 1. 일일 캔들 데이터 수집
            api = UpbitAPI(paper_trading=False)
            daily_candles = api.get_candles(
                "KRW-BTC", minutes=1440, count=30)  # 최근 30일

            if daily_candles:
                saved_count = 0
                for candle in daily_candles:
                    if candle_collector._save_candle_data(candle, '1d'):
                        saved_count += 1

                self.logger.info(f"일일 캔들 데이터 {saved_count}개 수집 완료")

            # 2. 데이터 무결성 체크
            self._check_data_integrity()

            # 3. 수집 통계 정리
            stats = candle_collector.get_collection_stats(1)
            self.logger.info(f"어제 데이터 수집 통계: {stats}")

        except Exception as e:
            self.logger.error(f"일일 데이터 유지보수 오류: {e}")

    def _check_data_integrity(self):
        """데이터 무결성 체크"""
        try:
            # 각 시간대별 데이터 연속성 체크
            for timeframe in ['5m', '1h', '1d']:
                candles = candle_collector.get_candles(timeframe, 100)

                if len(candles) < 2:
                    continue

                # 시간 간격 체크
                gaps = []
                for i in range(1, len(candles)):
                    time_diff = candles[i].timestamp - candles[i-1].timestamp
                    expected_diff = {
                        '5m': timedelta(minutes=5),
                        '1h': timedelta(hours=1),
                        '1d': timedelta(days=1)
                    }[timeframe]

                    if time_diff > expected_diff * 1.5:  # 50% 이상 차이
                        gaps.append(
                            (candles[i-1].timestamp, candles[i].timestamp))

                if gaps:
                    self.logger.warning(f"{timeframe} 데이터 갭 발견: {len(gaps)}개")
                    for gap in gaps[:5]:  # 최대 5개만 로깅
                        self.logger.warning(f"  갭: {gap[0]} ~ {gap[1]}")

        except Exception as e:
            self.logger.error(f"데이터 무결성 체크 오류: {e}")

    def _check_collection_health(self):
        """수집 상태 건강성 체크"""
        try:
            stats = candle_collector.get_collection_stats(1)

            if not stats:
                self.logger.warning("수집 통계가 없습니다.")
                return

            today = datetime.now().date().isoformat()

            if today in stats:
                today_stats = stats[today]

                for timeframe, stat in today_stats.items():
                    success_rate = stat['success_rate']

                    if success_rate < 0.9:  # 성공률 90% 미만
                        self.logger.warning(
                            f"{timeframe} 수집 성공률 낮음: {success_rate:.1%}"
                        )

                    # 최근 수집 시간 체크
                    if stat['last_collection']:
                        last_time = datetime.fromisoformat(
                            stat['last_collection'])
                        time_since = datetime.now() - last_time

                        max_interval = {
                            '1m': timedelta(minutes=5),
                            '5m': timedelta(minutes=15),
                            '15m': timedelta(minutes=30),
                            '1h': timedelta(hours=2),
                            '1d': timedelta(days=2)
                        }.get(timeframe, timedelta(hours=1))

                        if time_since > max_interval:
                            self.logger.warning(
                                f"{timeframe} 수집이 {time_since} 동안 중단됨"
                            )

        except Exception as e:
            self.logger.error(f"수집 상태 체크 오류: {e}")

    def _weekly_cleanup(self):
        """주간 데이터 정리"""
        try:
            self.logger.info("주간 데이터 정리 시작")

            # 30일 이상 된 분/시간 데이터 정리
            candle_collector.cleanup_old_data(days=30)

            # 수집 통계는 90일간 보관
            cutoff_date = (datetime.now() - timedelta(days=90)
                           ).date().isoformat()

            import sqlite3
            with sqlite3.connect(candle_collector.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM collection_stats WHERE date < ?
                ''', (cutoff_date,))

                deleted_count = cursor.rowcount
                conn.commit()

                self.logger.info(f"오래된 수집 통계 {deleted_count}개 정리 완료")

        except Exception as e:
            self.logger.error(f"주간 데이터 정리 오류: {e}")

    def get_status(self) -> Dict:
        """데이터 수집 상태 조회"""
        try:
            status = {
                'running': self.running,
                'collection_active': candle_collector.running,
                'timeframes': self.timeframes,
                'last_collection': candle_collector.last_collection_time,
                'stats': candle_collector.get_collection_stats(7)
            }

            return status

        except Exception as e:
            self.logger.error(f"상태 조회 오류: {e}")
            return {'error': str(e)}


# 전역 인스턴스
data_scheduler = DataCollectionScheduler()
