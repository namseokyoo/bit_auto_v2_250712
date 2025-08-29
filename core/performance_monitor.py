"""
퍼포먼스 모니터 스텁
- 최소 기록 기능만 제공
"""
from __future__ import annotations
from typing import Any, Dict
from datetime import datetime


class PerformanceMonitor:
    def __init__(self):
        self._trade_id = 0

    def record_trade(self, strategy_id: str, action: str, price: float, quantity: float, amount: float, confidence: float, reasoning: str) -> int:
        self._trade_id += 1
        return self._trade_id

    def open_position(self, strategy_id: str, entry_price: float, quantity: float, side: str):
        # 최소 구현
        return {"id": f"pos-{datetime.now().timestamp()}"}
