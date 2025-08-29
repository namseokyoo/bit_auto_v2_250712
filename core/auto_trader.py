"""
간단한 자동 거래 스케줄러 스텁
- 실행/중지 상태만 관리하여 ImportError 방지
- web/app.py, main.py 호환 API 제공
"""

import threading
import time
from dataclasses import dataclass


@dataclass
class AutoTraderState:
    running: bool = False
    last_started_at: float | None = None


class AutoTrader:
    def __init__(self):
        self.state = AutoTraderState()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self.state.running

    def start(self):
        if self.state.running:
            return
        self.state.running = True
        self.state.last_started_at = time.time()
        # 백그라운드 더미 루프
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.state.running = False

    def _loop(self):
        while self.state.running:
            time.sleep(1)


auto_trader = AutoTrader()


def start_auto_trading():
    auto_trader.start()


def stop_auto_trading():
    auto_trader.stop()


def get_auto_trading_status() -> dict:
    return {
        "running": auto_trader.running,
        "last_started_at": auto_trader.state.last_started_at,
    }
