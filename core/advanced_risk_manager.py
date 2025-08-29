"""
고급 리스크 관리자 스텁
- TradingEngine이 기대하는 최소 API 제공
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np


@dataclass
class RiskMetrics:
    position_size: float
    kelly_fraction: float
    stop_loss: float
    risk_reward_ratio: float


class AdvancedRiskManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.active_positions: Dict[str, Dict] = {}

    def check_loss_limits(self) -> Dict[str, object]:
        daily_limit = self.config.get_config('risk_management.loss_limits.daily_loss_limit') or self.config.get_config('trading.daily_loss_limit') or 50000
        weekly_limit = self.config.get_config('risk_management.loss_limits.weekly_loss_limit') or 150000
        monthly_limit = self.config.get_config('risk_management.loss_limits.monthly_loss_limit') or 300000
        # 간단 캡: 일일 한도 대비 최대 리스크 금액 1/3
        max_risk_amount = max(10000, min(self.config.get_trade_amount_limit(), daily_limit / 3))
        return {"can_trade": True, "reason": "", "max_risk_amount": max_risk_amount}

    def check_position_correlation(self, symbol: str, direction: str) -> Dict[str, object]:
        return {"allowed": True, "reason": "ok"}

    def get_risk_metrics(self, df, entry_price: float, direction: str, signal_strength: float, account_balance: float) -> RiskMetrics:
        """ATR 기반 SL/TP, Kelly 캡, VaR 캡을 반영한 리스크 메트릭 산출
        df: pandas.DataFrame with columns [high, low, close]
        """
        # 1) ATR 추정 (단순 근사: 최근 N=14 구간의 (high-low) 평균)
        try:
            atr_window = int(self.config.get_config('risk_management.atr_stop_loss.atr_period') or 14)
            recent = df.tail(atr_window)
            atr = float(np.mean(recent['high'] - recent['low'])) if len(recent) >= 3 else entry_price * 0.01
        except Exception:
            atr = entry_price * 0.01
        atr_mult = float(self.config.get_config('risk_management.atr_stop_loss.atr_multiplier') or 1.5)

        # 2) Kelly fraction (보수적 캡)
        kelly_fraction = float(self.config.get_config('risk_management.kelly_criterion.kelly_fraction') or 0.25)
        min_win_rate = float(self.config.get_config('risk_management.kelly_criterion.min_win_rate') or 0.45)
        avg_win_loss = float(self.config.get_config('risk_management.kelly_criterion.avg_win_loss_ratio') or 1.5)
        # 보수 Kelly: f* = min(kelly_fraction, max(0, p - (1-p)/R))
        base_kelly = max(0.0, min_win_rate - (1 - min_win_rate) / max(avg_win_loss, 0.1))
        kelly = min(kelly_fraction, max(0.05, base_kelly * signal_strength))  # 신뢰도로 스케일

        # 3) VaR 캡 (간단 근사: Z * std, 여기서는 ATR로 근사)
        var_multiplier = 2.33  # 99% 근사
        var_risk = var_multiplier * (atr / max(entry_price, 1.0))  # 비율 리스크
        max_exposure_pct = float(self.config.get_config('position_management.max_total_exposure_percent') or 80) / 100.0

        # 4) 포지션 크기 산출
        trade_cap = float(self.config.get_trade_amount_limit())
        kelly_size = account_balance * kelly
        var_size_cap = account_balance * max(0.05, (max_exposure_pct * (0.02 / max(var_risk, 1e-4))))  # 리스크 클수록 축소
        position_size = min(trade_cap, kelly_size, var_size_cap)

        # 5) SL/TP 산출 (ATR 기반)
        sl = entry_price - atr_mult * atr if direction == 'long' else entry_price + atr_mult * atr
        rr = float(self.config.get_config('risk_management.default_rr') or 2.0)
        tp = entry_price + rr * atr_mult * atr if direction == 'long' else entry_price - rr * atr_mult * atr

        return RiskMetrics(position_size=position_size, kelly_fraction=kelly, stop_loss=sl, risk_reward_ratio=rr)

    def add_position(self, position_id: str, symbol: str, direction: str, size: float):
        self.active_positions[position_id] = {"symbol": symbol, "direction": direction, "size": size}

    def update_position(self, position_id: str, pnl: float):
        # 최소 구현
        pass
