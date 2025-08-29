"""
거래/분석 상태 관리 스텁
- 파일 없이 인메모리로 잠금/상태/히스토리 제공
"""
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime, timedelta
import threading


class ResultManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._trading_locked = False
        self._history: List[Dict[str, Any]] = []
        self._status: Dict[str, Any] = {
            "running": False,
            "last_execution": None,
            "next_execution": None,
            "auto_trading_enabled": False,
        }

    # 상태
    def get_current_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    # 분석 히스토리 (최근 N일)
    def get_analysis_history(self, days: int = 1) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            return [h for h in self._history if h.get("timestamp_dt", datetime.min) >= cutoff]

    # 거래 락
    def is_trading_locked(self) -> bool:
        with self._lock:
            return self._trading_locked

    def acquire_trading_lock(self, timeout: int = 5) -> bool:
        # 간단 구현: 즉시 획득 시도
        with self._lock:
            if self._trading_locked:
                return False
            self._trading_locked = True
            return True

    def release_trading_lock(self):
        with self._lock:
            self._trading_locked = False


result_manager = ResultManager()
