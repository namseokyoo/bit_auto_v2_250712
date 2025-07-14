"""
스마트 포지션 관리 시스템
다중 전략의 포지션을 효율적으로 관리하고 리스크를 제어하는 시스템
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

@dataclass
class Position:
    id: str
    strategy_id: str
    symbol: str
    side: str  # 'long', 'short'
    size: float  # 수량
    entry_price: float
    current_price: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: bool = False
    trailing_stop_distance: float = 0.03  # 3%
    max_drawdown: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = 'open'  # 'open', 'closed', 'partial'
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

@dataclass
class PositionSummary:
    total_positions: int
    total_exposure: float
    unrealized_pnl: float
    used_capital: float
    available_capital: float
    risk_level: str
    positions_by_strategy: Dict[str, int] = field(default_factory=dict)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

class PositionManager:
    def __init__(self, config_manager, api_client):
        self.config = config_manager
        self.api = api_client
        self.positions: Dict[str, Position] = {}
        self.closed_positions = []
        self.logger = self._setup_logger()
        
        # 포지션 관리 설정
        self.max_positions = self.config.get_config('trading.max_positions')
        self.max_total_exposure = 0.8  # 총 자본의 80%까지 사용
        self.max_strategy_exposure = 0.3  # 단일 전략당 30%까지
        
        self.logger.info("포지션 매니저 초기화 완료")

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('PositionManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def can_open_position(self, strategy_id: str, amount: float) -> Tuple[bool, str]:
        """새 포지션 오픈 가능 여부 확인"""
        
        # 1. 최대 포지션 수 확인
        if len(self.positions) >= self.max_positions:
            return False, f"최대 포지션 수 초과 ({len(self.positions)}/{self.max_positions})"
        
        # 2. 총 노출 한도 확인
        current_exposure = self.get_total_exposure()
        total_balance = self.api.get_balance('KRW') + self.get_total_value()
        
        if (current_exposure + amount) / total_balance > self.max_total_exposure:
            return False, f"총 노출 한도 초과 (현재: {current_exposure/total_balance:.1%})"
        
        # 3. 전략별 노출 한도 확인
        strategy_exposure = self.get_strategy_exposure(strategy_id)
        if (strategy_exposure + amount) / total_balance > self.max_strategy_exposure:
            return False, f"전략별 노출 한도 초과 (전략 {strategy_id}: {strategy_exposure/total_balance:.1%})"
        
        # 4. 일일 거래 한도 확인
        daily_trades = self.get_daily_trade_count()
        max_daily_trades = self.config.get_config('risk_management.max_daily_trades')
        if daily_trades >= max_daily_trades:
            return False, f"일일 거래 한도 초과 ({daily_trades}/{max_daily_trades})"
        
        # 5. 잔고 확인
        available_balance = self.api.get_balance('KRW')
        if available_balance < amount:
            return False, f"잔고 부족 (요청: {amount:,.0f}, 가용: {available_balance:,.0f})"
        
        return True, "포지션 오픈 가능"

    def create_position(self, strategy_id: str, symbol: str, side: str, 
                       size: float, entry_price: float) -> Optional[Position]:
        """새 포지션 생성"""
        
        amount = size * entry_price
        can_open, reason = self.can_open_position(strategy_id, amount)
        
        if not can_open:
            self.logger.warning(f"포지션 생성 불가: {reason}")
            return None
        
        # 리스크 관리 설정 적용
        stop_loss = self._calculate_stop_loss(entry_price, side)
        take_profit = self._calculate_take_profit(entry_price, side)
        
        position = Position(
            id=str(uuid.uuid4()),
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=self.config.get_config('risk_management.trailing_stop_enabled')
        )
        
        self.positions[position.id] = position
        self.logger.info(f"포지션 생성: {position.id} - {strategy_id} {side} {size:.8f} @ {entry_price:,.0f}")
        
        return position

    def _calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """손절매 가격 계산"""
        stop_loss_percent = self.config.get_config('risk_management.stop_loss_percent') / 100
        
        if side == 'long':
            return entry_price * (1 - stop_loss_percent)
        else:  # short
            return entry_price * (1 + stop_loss_percent)

    def _calculate_take_profit(self, entry_price: float, side: str) -> float:
        """익절 가격 계산"""
        take_profit_percent = self.config.get_config('risk_management.take_profit_percent') / 100
        
        if side == 'long':
            return entry_price * (1 + take_profit_percent)
        else:  # short
            return entry_price * (1 - take_profit_percent)

    def update_positions(self, current_prices: Dict[str, float]):
        """모든 포지션 업데이트"""
        positions_to_close = []
        
        for position_id, position in self.positions.items():
            current_price = current_prices.get(position.symbol)
            if not current_price:
                continue
            
            position.current_price = current_price
            
            # PnL 계산
            if position.side == 'long':
                position.unrealized_pnl = (current_price - position.entry_price) * position.size
            else:  # short
                position.unrealized_pnl = (position.entry_price - current_price) * position.size
            
            # 최대 손실폭 업데이트
            if position.unrealized_pnl < position.max_drawdown:
                position.max_drawdown = position.unrealized_pnl
            
            # 트레일링 스탑 업데이트
            if position.trailing_stop:
                self._update_trailing_stop(position)
            
            # 손절매/익절 체크
            if self._should_close_position(position):
                positions_to_close.append(position_id)
        
        # 종료할 포지션들 처리
        for position_id in positions_to_close:
            self.close_position(position_id, "자동 손절/익절")

    def _update_trailing_stop(self, position: Position):
        """트레일링 스탑 업데이트"""
        if position.side == 'long' and position.current_price > position.entry_price:
            # 상승 추세에서 손절매 라인을 올림
            new_stop_loss = position.current_price * (1 - position.trailing_stop_distance)
            if position.stop_loss is None or new_stop_loss > position.stop_loss:
                position.stop_loss = new_stop_loss
                self.logger.debug(f"트레일링 스탑 업데이트: {position.id} -> {new_stop_loss:,.0f}")

    def _should_close_position(self, position: Position) -> bool:
        """포지션 종료 조건 확인"""
        current_price = position.current_price
        
        # 손절매 확인
        if position.stop_loss:
            if position.side == 'long' and current_price <= position.stop_loss:
                self.logger.info(f"손절매 실행: {position.id} (가격: {current_price:,.0f} <= 손절: {position.stop_loss:,.0f})")
                return True
            elif position.side == 'short' and current_price >= position.stop_loss:
                self.logger.info(f"손절매 실행: {position.id} (가격: {current_price:,.0f} >= 손절: {position.stop_loss:,.0f})")
                return True
        
        # 익절 확인
        if position.take_profit:
            if position.side == 'long' and current_price >= position.take_profit:
                self.logger.info(f"익절 실행: {position.id} (가격: {current_price:,.0f} >= 익절: {position.take_profit:,.0f})")
                return True
            elif position.side == 'short' and current_price <= position.take_profit:
                self.logger.info(f"익절 실행: {position.id} (가격: {current_price:,.0f} <= 익절: {position.take_profit:,.0f})")
                return True
        
        return False

    def close_position(self, position_id: str, reason: str = "수동 종료") -> bool:
        """포지션 종료"""
        if position_id not in self.positions:
            self.logger.warning(f"존재하지 않는 포지션: {position_id}")
            return False
        
        position = self.positions[position_id]
        
        # 실제 매도 주문 실행 (모의거래에서는 시뮬레이션)
        if position.side == 'long':
            # 매도 주문
            result = self.api.place_sell_order(position.symbol, position.current_price, position.size)
        else:
            # 숏 포지션 청산 (매수)
            result = self.api.place_buy_order(position.symbol, position.current_price, amount=position.size * position.current_price)
        
        if result.success:
            # 포지션을 종료 목록으로 이동
            position.status = 'closed'
            self.closed_positions.append(position)
            del self.positions[position_id]
            
            self.logger.info(f"포지션 종료 완료: {position_id} - {reason} (PnL: {position.unrealized_pnl:+,.0f})")
            return True
        else:
            self.logger.error(f"포지션 종료 실패: {position_id} - {result.message}")
            return False

    def get_position_summary(self) -> PositionSummary:
        """포지션 요약 정보"""
        total_exposure = self.get_total_exposure()
        total_value = self.get_total_value()
        unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        
        available_balance = self.api.get_balance('KRW')
        used_capital = total_exposure
        total_capital = available_balance + used_capital
        
        # 전략별 포지션 수
        positions_by_strategy = {}
        for position in self.positions.values():
            strategy_id = position.strategy_id
            positions_by_strategy[strategy_id] = positions_by_strategy.get(strategy_id, 0) + 1
        
        # 리스크 레벨 계산
        risk_level = self._calculate_risk_level(total_exposure, total_capital, unrealized_pnl)
        
        return PositionSummary(
            total_positions=len(self.positions),
            total_exposure=total_exposure,
            unrealized_pnl=unrealized_pnl,
            used_capital=used_capital,
            available_capital=available_balance,
            risk_level=risk_level.value,
            positions_by_strategy=positions_by_strategy
        )

    def get_total_exposure(self) -> float:
        """총 노출 금액"""
        return sum(pos.size * pos.current_price for pos in self.positions.values())

    def get_total_value(self) -> float:
        """총 포지션 가치 (원화 기준)"""
        btc_balance = self.api.get_balance('BTC')
        current_price = self.api.get_current_price('KRW-BTC')
        return btc_balance * current_price if current_price else 0

    def get_strategy_exposure(self, strategy_id: str) -> float:
        """특정 전략의 노출 금액"""
        return sum(
            pos.size * pos.current_price 
            for pos in self.positions.values() 
            if pos.strategy_id == strategy_id
        )

    def get_daily_trade_count(self) -> int:
        """오늘 거래 횟수"""
        today = datetime.now().date()
        return len([
            pos for pos in self.closed_positions 
            if pos.entry_time.date() == today
        ])

    def _calculate_risk_level(self, total_exposure: float, total_capital: float, unrealized_pnl: float) -> RiskLevel:
        """리스크 레벨 계산"""
        if total_capital == 0:
            return RiskLevel.LOW
        
        exposure_ratio = total_exposure / total_capital
        pnl_ratio = abs(unrealized_pnl) / total_capital
        
        if exposure_ratio > 0.7 or pnl_ratio > 0.1:
            return RiskLevel.EXTREME
        elif exposure_ratio > 0.5 or pnl_ratio > 0.05:
            return RiskLevel.HIGH
        elif exposure_ratio > 0.3 or pnl_ratio > 0.02:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def emergency_close_all(self) -> List[str]:
        """긴급 전체 포지션 종료"""
        closed_positions = []
        
        for position_id in list(self.positions.keys()):
            if self.close_position(position_id, "긴급 종료"):
                closed_positions.append(position_id)
        
        self.logger.critical(f"긴급 전체 포지션 종료 완료: {len(closed_positions)}개")
        return closed_positions

    def get_position_by_strategy(self, strategy_id: str) -> List[Position]:
        """특정 전략의 포지션 목록"""
        return [pos for pos in self.positions.values() if pos.strategy_id == strategy_id]

    def cleanup_old_positions(self, days: int = 30):
        """오래된 종료 포지션 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        original_count = len(self.closed_positions)
        
        self.closed_positions = [
            pos for pos in self.closed_positions 
            if pos.entry_time >= cutoff_date
        ]
        
        cleaned_count = original_count - len(self.closed_positions)
        if cleaned_count > 0:
            self.logger.info(f"오래된 포지션 {cleaned_count}개 정리 완료")

# 사용 예시
if __name__ == "__main__":
    from config.config_manager import config_manager
    from core.upbit_api import UpbitAPI
    
    api = UpbitAPI(paper_trading=False)
    position_manager = PositionManager(config_manager, api)
    
    # 테스트 포지션 생성
    position = position_manager.create_position(
        strategy_id='h1',
        symbol='KRW-BTC',
        side='long',
        size=0.001,
        entry_price=50000000
    )
    
    if position:
        print(f"포지션 생성됨: {position.id}")
        
        # 포지션 업데이트 시뮬레이션
        position_manager.update_positions({'KRW-BTC': 51000000})
        
        summary = position_manager.get_position_summary()
        print(f"포지션 요약: {summary}")
    
    else:
        print("포지션 생성 실패")