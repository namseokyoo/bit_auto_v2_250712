"""
데이터 수집기 스텁
- DB 우선 조회/수집 인터페이스와 동일한 시그니처만 유지
"""
from __future__ import annotations
from typing import Optional
import pandas as pd


class DataCollector:
    def get_historical_data(self, market: str, timeframe: str, start_date, end_date) -> Optional[pd.DataFrame]:
        return None

    def collect_historical_candles(self, market: str, timeframe: str, days_back: int) -> Optional[pd.DataFrame]:
        return None
