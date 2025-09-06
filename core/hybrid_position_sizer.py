"""
하이브리드 포지션 크기 결정 시스템
수동거래의 단순함과 자동거래의 지능성을 결합
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class PositionSizeResult:
    """포지션 크기 계산 결과"""
    amount: float
    method: str
    confidence: float
    risk_level: str
    reason: str

class HybridPositionSizer:
    """하이브리드 포지션 크기 결정기"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # 설정값들
        self.base_amount = self.config.get_config('trading.base_trade_amount', 5000)  # 기본 거래 금액
        self.max_position_percent = self.config.get_config('risk_management.max_position_size_percent', 10) / 100
        self.min_amount = self.config.get_config('trading.min_trade_amount', 5000)
        self.max_amount = self.config.get_config('trading.max_trade_amount', 100000)
        
        # 성과 추적
        self.trade_history = []
        self.win_rate = 0.5  # 초기값
        self.avg_win_loss_ratio = 1.0  # 초기값
        
    def calculate_position_size(self, signal: Dict[str, Any], balance: float, 
                              market_data: Optional[pd.DataFrame] = None) -> PositionSizeResult:
        """포지션 크기 계산 - 하이브리드 방식"""
        
        # 1. 기본 금액 (수동거래와 동일)
        base_amount = self.base_amount
        
        # 2. 신호 강도 조정
        signal_strength = signal.get('confidence', 0.5)
        strength_multiplier = self._calculate_strength_multiplier(signal_strength)
        
        # 3. 변동성 조정 (ATR 기반)
        volatility_multiplier = self._calculate_volatility_multiplier(market_data, signal.get('price', 0))
        
        # 4. 성과 기반 조정 (Kelly Criterion 간소화)
        performance_multiplier = self._calculate_performance_multiplier()
        
        # 5. 잔고 제한
        balance_limit = balance * self.max_position_percent
        
        # 최종 계산
        adjusted_amount = base_amount * strength_multiplier * volatility_multiplier * performance_multiplier
        
        # 제한 적용
        final_amount = max(
            self.min_amount,
            min(adjusted_amount, balance_limit, self.max_amount)
        )
        
        # 방법 결정
        method = self._determine_method(strength_multiplier, volatility_multiplier, performance_multiplier)
        
        # 리스크 레벨 결정
        risk_level = self._determine_risk_level(final_amount, balance)
        
        # 이유 설명
        reason = self._generate_reason(base_amount, strength_multiplier, 
                                     volatility_multiplier, performance_multiplier, final_amount)
        
        return PositionSizeResult(
            amount=final_amount,
            method=method,
            confidence=signal_strength,
            risk_level=risk_level,
            reason=reason
        )
    
    def _calculate_strength_multiplier(self, signal_strength: float) -> float:
        """신호 강도에 따른 배수 계산"""
        # 신호 강도: 0.0 ~ 1.0
        # 배수: 0.5 ~ 2.0
        return 0.5 + (signal_strength * 1.5)
    
    def _calculate_volatility_multiplier(self, market_data: Optional[pd.DataFrame], 
                                       current_price: float) -> float:
        """변동성에 따른 배수 계산"""
        if market_data is None or len(market_data) < 20:
            return 1.0  # 기본값
        
        try:
            # ATR 계산 (20일)
            high_low = market_data['high'] - market_data['low']
            high_close = np.abs(market_data['high'] - market_data['close'].shift())
            low_close = np.abs(market_data['low'] - market_data['close'].shift())
            
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = true_range.rolling(20).mean().iloc[-1]
            
            # 변동성이 높으면 포지션 크기 감소
            volatility_ratio = atr / current_price
            if volatility_ratio > 0.05:  # 5% 이상 변동성
                return 0.7
            elif volatility_ratio > 0.03:  # 3% 이상 변동성
                return 0.85
            else:
                return 1.0
                
        except Exception as e:
            self.logger.warning(f"변동성 계산 오류: {e}")
            return 1.0
    
    def _calculate_performance_multiplier(self) -> float:
        """성과에 따른 배수 계산 (Kelly Criterion 간소화)"""
        if len(self.trade_history) < 10:
            return 1.0  # 초기값
        
        # 최근 20개 거래의 성과 분석
        recent_trades = self.trade_history[-20:]
        wins = [t for t in recent_trades if t > 0]
        losses = [t for t in recent_trades if t < 0]
        
        if len(wins) == 0 or len(losses) == 0:
            return 1.0
        
        win_rate = len(wins) / len(recent_trades)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        
        if avg_loss == 0:
            return 1.0
        
        win_loss_ratio = avg_win / avg_loss
        
        # Kelly Criterion 간소화: f = (p * b - q) / b
        # p = win_rate, b = win_loss_ratio, q = 1 - win_rate
        kelly_fraction = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # 안전을 위해 Kelly의 50%만 사용하고, 0.5 ~ 1.5 범위로 제한
        safe_kelly = max(0.5, min(kelly_fraction * 0.5, 1.5))
        
        return safe_kelly
    
    def _determine_method(self, strength_mult: float, volatility_mult: float, 
                         performance_mult: float) -> str:
        """사용된 방법 결정"""
        if abs(strength_mult - 1.0) > 0.2:
            return "신호강도조정"
        elif abs(volatility_mult - 1.0) > 0.1:
            return "변동성조정"
        elif abs(performance_mult - 1.0) > 0.1:
            return "성과기반조정"
        else:
            return "기본금액"
    
    def _determine_risk_level(self, amount: float, balance: float) -> str:
        """리스크 레벨 결정"""
        risk_ratio = amount / balance
        
        if risk_ratio > 0.08:
            return "높음"
        elif risk_ratio > 0.05:
            return "중간"
        else:
            return "낮음"
    
    def _generate_reason(self, base_amount: float, strength_mult: float, 
                        volatility_mult: float, performance_mult: float, 
                        final_amount: float) -> str:
        """계산 이유 생성"""
        reasons = []
        
        if abs(strength_mult - 1.0) > 0.1:
            reasons.append(f"신호강도 {strength_mult:.2f}배")
        
        if abs(volatility_mult - 1.0) > 0.1:
            reasons.append(f"변동성 {volatility_mult:.2f}배")
        
        if abs(performance_mult - 1.0) > 0.1:
            reasons.append(f"성과 {performance_mult:.2f}배")
        
        if not reasons:
            reasons.append("기본금액")
        
        return f"기본 {base_amount:,.0f}원 → {' × '.join(reasons)} → {final_amount:,.0f}원"
    
    def update_trade_result(self, pnl: float):
        """거래 결과 업데이트"""
        self.trade_history.append(pnl)
        
        # 최근 100개 거래만 유지
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]
        
        self.logger.info(f"거래 결과 업데이트: PnL={pnl:,.0f}, 총 거래수={len(self.trade_history)}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성과 요약 반환"""
        if not self.trade_history:
            return {"message": "거래 기록이 없습니다"}
        
        total_trades = len(self.trade_history)
        wins = [t for t in self.trade_history if t > 0]
        losses = [t for t in self.trade_history if t < 0]
        
        return {
            "총_거래수": total_trades,
            "승률": len(wins) / total_trades if total_trades > 0 else 0,
            "평균_수익": np.mean(wins) if wins else 0,
            "평균_손실": np.mean(losses) if losses else 0,
            "총_PnL": sum(self.trade_history),
            "최대_연속_승": self._max_consecutive_wins(),
            "최대_연속_패": self._max_consecutive_losses()
        }
    
    def _max_consecutive_wins(self) -> int:
        """최대 연속 승수"""
        max_wins = 0
        current_wins = 0
        
        for pnl in self.trade_history:
            if pnl > 0:
                current_wins += 1
                max_wins = max(max_wins, current_wins)
            else:
                current_wins = 0
        
        return max_wins
    
    def _max_consecutive_losses(self) -> int:
        """최대 연속 패수"""
        max_losses = 0
        current_losses = 0
        
        for pnl in self.trade_history:
            if pnl < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0
        
        return max_losses
