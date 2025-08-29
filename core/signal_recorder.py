"""
신호 기록 스텁
- 최소 기능의 인메모리 저장 제공
- web/app.py, core/trading_engine.py에서 호출되는 API 충족
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading


@dataclass
class RecordedSignal:
    strategy_id: str
    action: str
    confidence: float
    price: float
    suggested_amount: int
    reasoning: str
    timestamp: datetime
    executed: bool


class SignalRecorder:
    def __init__(self):
        self._signals: List[RecordedSignal] = []
        self._consolidated: List[Dict[str, Any]] = []
        self._analysis_sessions: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._id = 0

    def _next_id(self) -> int:
        with self._lock:
            self._id += 1
            return self._id

    def record_signal(self, data: Dict[str, Any], executed: bool = False) -> int:
        rec = RecordedSignal(
            strategy_id=data.get("strategy_id", "unknown"),
            action=data.get("action", "hold"),
            confidence=float(data.get("confidence", 0)),
            price=float(data.get("price", 0)),
            suggested_amount=int(data.get("suggested_amount", 0)),
            reasoning=data.get("reasoning", ""),
            timestamp=datetime.now(),
            executed=executed,
        )
        with self._lock:
            self._signals.append(rec)
            rid = self._next_id()
        return rid

    def record_consolidated_signal(self, data: Dict[str, Any], executed: bool = False) -> int:
        payload = {**data, "executed": executed, "timestamp": datetime.now().isoformat()}
        with self._lock:
            self._consolidated.append(payload)
            rid = self._next_id()
        return rid

    def record_analysis_session(self, data: Dict[str, Any]) -> int:
        payload = {**data, "timestamp": datetime.now().isoformat()}
        with self._lock:
            self._analysis_sessions.append(payload)
            rid = self._next_id()
        return rid

    def get_signal_history(self, strategy_id: Optional[str], days: int = 7) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            sigs = [s for s in self._signals if s.timestamp >= cutoff]
        if strategy_id:
            sigs = [s for s in sigs if s.strategy_id == strategy_id]
        return [s.__dict__ for s in sigs]

    def analyze_signal_performance(self, days: int = 7) -> Dict[str, Any]:
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            total = len([s for s in self._signals if s.timestamp >= cutoff])
        return {"total_signals": total, "win_rate": 0.0}

    def get_strategy_accuracy(self, strategy_id: str, days: int = 30) -> float:
        return 0.0


signal_recorder = SignalRecorder()
