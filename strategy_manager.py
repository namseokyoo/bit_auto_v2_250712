"""
Bitcoin Auto Trading Strategy Manager
전략 관리, 성능 추적, 동적 활성화/비활성화 시스템
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

class StrategyCategory(Enum):
    TREND_FOLLOWING = "trend_following"
    REVERSAL = "reversal"
    MOMENTUM = "momentum"
    VOLATILITY_BREAKOUT = "volatility_breakout"
    SUPPORT_RESISTANCE = "support_resistance"
    VOLUME_ANALYSIS = "volume_analysis"
    SENTIMENT_CONTRARIAN = "sentiment_contrarian"
    FUNDAMENTAL_ONCHAIN = "fundamental_onchain"
    META_STRATEGY = "meta_strategy"

@dataclass
class PerformanceMetrics:
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    profitable_trades: int
    avg_win: float
    avg_loss: float
    profit_factor: float
    last_updated: datetime

@dataclass
class TradeRecord:
    strategy_id: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    position_size: float
    side: str  # 'long' or 'short'
    pnl: Optional[float]
    fees: float
    status: str  # 'open', 'closed', 'cancelled'

class StrategyManager:
    def __init__(self, config_path: str = "trading_strategies.json"):
        self.config_path = config_path
        self.strategies = {}
        self.performance_data = {}
        self.trade_history = []
        self.logger = self._setup_logger()
        self.load_strategies()

    def _setup_logger(self) -> logging.Logger:
        """로깅 설정"""
        logger = logging.getLogger('StrategyManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def load_strategies(self) -> None:
        """JSON 파일에서 전략 설정 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.strategies = config['strategies']
                self.performance_thresholds = config['strategy_management']['performance_thresholds']
                self.auto_disable_conditions = config['strategy_management']['auto_disable_conditions']
                self.logger.info(f"전략 설정 로드 완료: {len(self._get_all_strategies())}개 전략")
        except FileNotFoundError:
            self.logger.error(f"전략 설정 파일을 찾을 수 없습니다: {self.config_path}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {e}")

    def save_strategies(self) -> None:
        """현재 전략 설정을 JSON 파일에 저장"""
        try:
            config = {
                "strategy_metadata": {
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "total_strategies": len(self._get_all_strategies())
                },
                "strategies": self.strategies,
                "strategy_management": {
                    "performance_thresholds": self.performance_thresholds,
                    "auto_disable_conditions": self.auto_disable_conditions,
                    "optimization_schedule": {
                        "daily_performance_check": True,
                        "weekly_parameter_optimization": True,
                        "monthly_strategy_review": True
                    }
                }
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.logger.info("전략 설정 저장 완료")
        except Exception as e:
            self.logger.error(f"전략 설정 저장 실패: {e}")

    def _get_all_strategies(self) -> Dict[str, Dict]:
        """모든 전략을 단일 딕셔너리로 반환"""
        all_strategies = {}
        for timeframe_group in self.strategies.values():
            all_strategies.update(timeframe_group)
        return all_strategies

    def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """특정 전략 조회"""
        all_strategies = self._get_all_strategies()
        return all_strategies.get(strategy_id)

    def get_active_strategies(self, timeframe: str = None) -> Dict[str, Dict]:
        """활성화된 전략 조회"""
        active_strategies = {}
        
        if timeframe:
            # 특정 시간대의 활성 전략만 조회
            timeframe_key = f"{timeframe}_strategies"
            if timeframe_key in self.strategies:
                for strategy_id, strategy in self.strategies[timeframe_key].items():
                    if strategy.get('active', False):
                        active_strategies[strategy_id] = strategy
        else:
            # 모든 활성 전략 조회
            for timeframe_group in self.strategies.values():
                for strategy_id, strategy in timeframe_group.items():
                    if strategy.get('active', False):
                        active_strategies[strategy_id] = strategy
        
        return active_strategies

    def enable_strategy(self, strategy_id: str) -> bool:
        """전략 활성화"""
        strategy = self.get_strategy(strategy_id)
        if strategy:
            strategy['active'] = True
            self.save_strategies()
            self.logger.info(f"전략 활성화: {strategy_id}")
            return True
        return False

    def disable_strategy(self, strategy_id: str, reason: str = "Manual") -> bool:
        """전략 비활성화"""
        strategy = self.get_strategy(strategy_id)
        if strategy:
            strategy['active'] = False
            strategy['disabled_reason'] = reason
            strategy['disabled_at'] = datetime.now().isoformat()
            self.save_strategies()
            self.logger.info(f"전략 비활성화: {strategy_id}, 사유: {reason}")
            return True
        return False

    def update_strategy_parameters(self, strategy_id: str, parameters: Dict) -> bool:
        """전략 파라미터 업데이트"""
        strategy = self.get_strategy(strategy_id)
        if strategy:
            strategy['parameters'].update(parameters)
            strategy['last_parameter_update'] = datetime.now().isoformat()
            self.save_strategies()
            self.logger.info(f"전략 파라미터 업데이트: {strategy_id}")
            return True
        return False

    def add_trade_record(self, trade: TradeRecord) -> None:
        """거래 기록 추가"""
        self.trade_history.append(trade)
        self.logger.info(f"거래 기록 추가: {trade.strategy_id}, PnL: {trade.pnl}")

    def calculate_performance_metrics(self, strategy_id: str, 
                                    lookback_days: int = 30) -> Optional[PerformanceMetrics]:
        """전략별 성능 지표 계산"""
        strategy_trades = [
            trade for trade in self.trade_history 
            if trade.strategy_id == strategy_id 
            and trade.status == 'closed'
            and trade.exit_time 
            and trade.exit_time >= datetime.now() - timedelta(days=lookback_days)
        ]
        
        if len(strategy_trades) < 5:  # 최소 거래 수 체크
            return None
        
        # 기본 통계
        total_trades = len(strategy_trades)
        profitable_trades = len([t for t in strategy_trades if t.pnl > 0])
        win_rate = profitable_trades / total_trades
        
        # 수익률 계산
        returns = [trade.pnl / (trade.entry_price * trade.position_size) for trade in strategy_trades]
        avg_return = np.mean(returns)
        
        # 승리/패배 평균
        winning_trades = [t.pnl for t in strategy_trades if t.pnl > 0]
        losing_trades = [t.pnl for t in strategy_trades if t.pnl <= 0]
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0
        
        # 최대 손실폭 계산 (연속 손실 기준)
        cumulative_returns = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max)
        max_drawdown = abs(np.min(drawdown))
        
        # 샤프 비율 (일일 수익률 기준으로 간소화)
        sharpe_ratio = avg_return / np.std(returns) if np.std(returns) > 0 else 0
        
        # 수익 팩터
        total_profit = sum(winning_trades)
        total_loss = abs(sum(losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        return PerformanceMetrics(
            win_rate=win_rate,
            avg_return=avg_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            last_updated=datetime.now()
        )

    def update_strategy_performance(self, strategy_id: str) -> None:
        """전략 성능 업데이트"""
        metrics = self.calculate_performance_metrics(strategy_id)
        if metrics:
            strategy = self.get_strategy(strategy_id)
            if strategy:
                strategy['performance'] = {
                    'win_rate': metrics.win_rate,
                    'avg_return': metrics.avg_return,
                    'max_drawdown': metrics.max_drawdown,
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'last_performance_check': metrics.last_updated.isoformat()
                }
                self.performance_data[strategy_id] = metrics
                self.save_strategies()

    def check_auto_disable_conditions(self, strategy_id: str) -> bool:
        """자동 비활성화 조건 체크"""
        metrics = self.performance_data.get(strategy_id)
        if not metrics:
            return False
        
        # 연속 손실 체크
        recent_trades = [
            trade for trade in self.trade_history[-self.auto_disable_conditions['consecutive_losses']:]
            if trade.strategy_id == strategy_id and trade.status == 'closed'
        ]
        
        if len(recent_trades) >= self.auto_disable_conditions['consecutive_losses']:
            if all(trade.pnl <= 0 for trade in recent_trades):
                self.disable_strategy(strategy_id, "연속 손실 한계 도달")
                return True
        
        # 최대 손실폭 체크
        if metrics.max_drawdown > self.auto_disable_conditions['drawdown_threshold']:
            self.disable_strategy(strategy_id, "최대 손실폭 초과")
            return True
        
        # 승률 체크
        if (metrics.total_trades >= self.performance_thresholds['min_trades_for_evaluation'] and
            metrics.win_rate < self.auto_disable_conditions['win_rate_below']):
            self.disable_strategy(strategy_id, "승률 기준 미달")
            return True
        
        return False

    def daily_performance_check(self) -> None:
        """일일 성능 체크 및 자동 관리"""
        self.logger.info("일일 성능 체크 시작")
        
        for strategy_id in self._get_all_strategies():
            # 성능 업데이트
            self.update_strategy_performance(strategy_id)
            
            # 자동 비활성화 조건 체크
            self.check_auto_disable_conditions(strategy_id)
        
        self.logger.info("일일 성능 체크 완료")

    def get_strategy_recommendations(self, market_condition: str = None) -> List[str]:
        """시장 상황에 맞는 전략 추천"""
        active_strategies = self.get_active_strategies()
        recommendations = []
        
        # 시장 상황별 전략 카테고리 매핑
        market_strategy_map = {
            'trending_up': [StrategyCategory.TREND_FOLLOWING],
            'trending_down': [StrategyCategory.TREND_FOLLOWING, StrategyCategory.SENTIMENT_CONTRARIAN],
            'sideways': [StrategyCategory.SUPPORT_RESISTANCE, StrategyCategory.REVERSAL],
            'high_volatility': [StrategyCategory.VOLATILITY_BREAKOUT],
            'low_volatility': [StrategyCategory.SUPPORT_RESISTANCE]
        }
        
        preferred_categories = market_strategy_map.get(market_condition, [])
        
        for strategy_id, strategy in active_strategies.items():
            strategy_category = strategy.get('category')
            
            # 성능 기반 필터링
            metrics = self.performance_data.get(strategy_id)
            if metrics and metrics.total_trades >= 10:
                if (metrics.win_rate >= self.performance_thresholds['min_win_rate'] and
                    metrics.sharpe_ratio >= self.performance_thresholds['min_sharpe_ratio']):
                    
                    if not market_condition or strategy_category in [cat.value for cat in preferred_categories]:
                        recommendations.append(strategy_id)
        
        return recommendations

    def export_performance_report(self, filepath: str = None) -> Dict:
        """성능 리포트 내보내기"""
        if not filepath:
            filepath = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'report_date': datetime.now().isoformat(),
            'total_strategies': len(self._get_all_strategies()),
            'active_strategies': len(self.get_active_strategies()),
            'strategy_performance': {}
        }
        
        for strategy_id, metrics in self.performance_data.items():
            strategy = self.get_strategy(strategy_id)
            if strategy:
                report['strategy_performance'][strategy_id] = {
                    'name': strategy['name'],
                    'category': strategy['category'],
                    'active': strategy['active'],
                    'win_rate': metrics.win_rate,
                    'avg_return': metrics.avg_return,
                    'max_drawdown': metrics.max_drawdown,
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'total_trades': metrics.total_trades,
                    'profit_factor': metrics.profit_factor
                }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"성능 리포트 저장: {filepath}")
        return report

# 사용 예시
if __name__ == "__main__":
    # 전략 매니저 초기화
    strategy_manager = StrategyManager()
    
    # 활성 전략 조회
    active_strategies = strategy_manager.get_active_strategies('hourly')
    print(f"활성 시간 단위 전략: {len(active_strategies)}개")
    
    # 시장 상황에 맞는 전략 추천
    recommendations = strategy_manager.get_strategy_recommendations('trending_up')
    print(f"상승 추세 시장 추천 전략: {recommendations}")
    
    # 일일 성능 체크 실행
    strategy_manager.daily_performance_check()