"""
전략 라우터 스텁
- route_strategy가 None을 반환하여 안전하게 넘어가도록 함
"""
from __future__ import annotations
from typing import Any, Dict, Optional


class StrategyRouter:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def route_strategy(self, strategy_id: str, df, additional_data: Optional[Dict[str, Any]] = None):
        # 최소 스텁: 아직 실제 라우팅 없음
        return None
