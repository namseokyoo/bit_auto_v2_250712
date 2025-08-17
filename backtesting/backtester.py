"""
백테스팅 시스템
통합 전략 시스템의 과거 성과를 분석하고 최적화
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
from dataclasses import dataclass, asdict
import sqlite3

from core.upbit_api import UpbitAPI, MarketData
from core.signal_manager import TradingSignal, SignalManager

@dataclass
class ConsolidatedSignal:
    action: str
    confidence: float
    suggested_amount: float
    contributing_strategies: List[str]
    reasoning: str

# from core.position_manager import PositionManager, Position  # 백테스팅에서는 사용하지 않음
from core.real_strategy_signals import RealStrategySignals
from strategy_manager import StrategyManager

@dataclass
class BacktestTrade:
    """백테스트 거래 기록"""
    timestamp: datetime
    action: str  # 'buy', 'sell'
    price: float
    volume: float
    amount: float
    strategy_signals: List[str]  # 기여한 전략들
    confidence: float
    pnl: float = 0.0  # 실현 손익
    portfolio_value: float = 0.0

@dataclass
class BacktestMetrics:
    """백테스트 성과 지표"""
    start_date: datetime
    end_date: datetime
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    profitable_trades: int
    avg_trade_return: float
    best_trade: float
    worst_trade: float
    portfolio_final_value: float
    buy_and_hold_return: float
    alpha: float  # 시장 대비 초과 수익

class Backtester:
    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.btc_holdings = 0.0
        self.trades: List[BacktestTrade] = []
        self.portfolio_history: List[Dict] = []
        self.logger = logging.getLogger('Backtester')
        
        # 수수료 설정 (업비트 기준)
        self.trading_fee = 0.0005  # 0.05%
        
        # 전략 매니저들
        self.strategy_manager = StrategyManager()
        # signal_manager는 백테스팅에서 직접 구현
        # self.position_manager = PositionManager(initial_capital=initial_capital)  # 백테스팅에서는 간단한 구현 사용
        
        # 백테스트 설정
        self.use_multi_strategy = True  # 다중 전략 사용 여부
    
    def load_historical_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """과거 데이터 로드 (실제 구현에서는 Upbit API나 저장된 데이터 사용)"""
        try:
            # 실제 API 호출로 과거 데이터 수집
            api = UpbitAPI(paper_trading=True)
            
            # 일간 캔들 데이터 수집
            days_diff = (end_date - start_date).days
            candles = api.get_candles("KRW-BTC", "days", 1, min(200, days_diff))
            
            if not candles:
                # API 실패 시 시뮬레이션 데이터 생성
                return self._generate_simulation_data(start_date, end_date)
            
            # 데이터프레임으로 변환
            df = pd.DataFrame(candles)
            df['timestamp'] = pd.to_datetime(df['candle_date_time_utc'])
            df = df.sort_values('timestamp')
            
            # 필요한 컬럼만 선택하고 타입 변환
            df['open'] = df['opening_price'].astype(float)
            df['high'] = df['high_price'].astype(float)
            df['low'] = df['low_price'].astype(float)
            df['close'] = df['trade_price'].astype(float)
            df['volume'] = df['candle_acc_trade_volume'].astype(float)
            
            self.logger.info(f"과거 데이터 로드 완료: {len(df)}개 캔들")
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            self.logger.error(f"과거 데이터 로드 오류: {e}")
            return self._generate_simulation_data(start_date, end_date)
    
    def _generate_simulation_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """시뮬레이션 데이터 생성 (API 실패 시 대체)"""
        dates = pd.date_range(start_date, end_date, freq='D')
        np.random.seed(42)  # 재현 가능한 결과
        
        # 랜덤 워크 기반 가격 생성
        returns = np.random.normal(0.001, 0.03, len(dates))  # 일일 0.1% 평균 수익, 3% 변동성
        prices = [90000000]  # 시작 가격 9천만원
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            # OHLC 생성
            daily_volatility = 0.02
            high = price * (1 + np.random.uniform(0, daily_volatility))
            low = price * (1 - np.random.uniform(0, daily_volatility))
            open_price = prices[i-1] if i > 0 else price
            volume = np.random.uniform(100, 1000)
            
            data.append({
                'timestamp': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': price,
                'volume': volume
            })
        
        return pd.DataFrame(data)
    
    def run_backtest(self, start_date: datetime, end_date: datetime, 
                    strategy_configs: Dict = None) -> BacktestMetrics:
        """백테스트 실행"""
        self.logger.info(f"백테스트 시작: {start_date} ~ {end_date}")
        
        # 데이터 로드
        df = self.load_historical_data(start_date, end_date)
        if df.empty:
            raise ValueError("백테스트 데이터를 로드할 수 없습니다")
        
        # 초기화
        self.current_capital = self.initial_capital
        self.btc_holdings = 0.0
        self.trades = []
        self.portfolio_history = []
        
        # 활성 전략 설정
        if strategy_configs:
            self.strategy_manager.update_strategies(strategy_configs)
        
        # 모의 API 생성 (과거 데이터용)
        mock_api = MockUpbitAPI(df)
        real_signals = RealStrategySignals(mock_api)
        
        buy_and_hold_start_price = df.iloc[0]['close']
        
        # 각 시점에서 전략 실행
        for i in range(20, len(df)):  # 지표 계산을 위해 20일 후부터 시작
            current_row = df.iloc[i]
            current_price = current_row['close']
            current_time = current_row['timestamp']
            
            # 현재 시점까지의 데이터로 API 업데이트
            mock_api.update_current_position(i)
            
            # 전략 신호 수집
            strategy_signals = self._collect_strategy_signals(real_signals, current_time)
            
            if strategy_signals:
                # 신호 통합
                consolidated_signal = self._consolidate_signals(strategy_signals)
                
                if consolidated_signal and consolidated_signal.action != 'hold':
                    # 거래 실행
                    self._execute_backtest_trade(consolidated_signal, current_price, current_time)
            
            # 포트폴리오 가치 기록
            portfolio_value = self.current_capital + (self.btc_holdings * current_price)
            self.portfolio_history.append({
                'timestamp': current_time,
                'capital': self.current_capital,
                'btc_holdings': self.btc_holdings,
                'btc_value': self.btc_holdings * current_price,
                'total_value': portfolio_value,
                'btc_price': current_price
            })
        
        # 성과 지표 계산
        final_price = df.iloc[-1]['close']
        metrics = self._calculate_metrics(df, buy_and_hold_start_price, final_price)
        
        self.logger.info(f"백테스트 완료 - 총 수익률: {metrics.total_return:.2%}")
        return metrics
    
    def _collect_strategy_signals(self, real_signals: RealStrategySignals, 
                                current_time: datetime) -> List[TradingSignal]:
        """현재 시점에서 전략 신호 수집"""
        signals = []
        active_strategies = self.strategy_manager.get_active_strategies('hourly')
        
        for strategy_id, strategy in active_strategies.items():
            try:
                signal = None
                
                # 각 전략별 신호 생성
                if strategy_id == 'ema_cross':
                    signal = real_signals.generate_ema_cross_signal(strategy)
                elif strategy_id == 'rsi_divergence':
                    signal = real_signals.generate_rsi_divergence_signal(strategy)
                elif strategy_id == 'vwap_pullback':
                    signal = real_signals.generate_vwap_pullback_signal(strategy)
                elif strategy_id == 'macd_zero_cross':
                    signal = real_signals.generate_macd_zero_cross_signal(strategy)
                elif strategy_id == 'bollinger_band_strategy':
                    signal = real_signals.generate_bollinger_band_signal(strategy)
                elif strategy_id == 'pivot_points':
                    signal = real_signals.generate_pivot_points_signal(strategy)
                elif strategy_id == 'open_interest':
                    signal = real_signals.generate_open_interest_signal(strategy)
                elif strategy_id == 'flag_pennant':
                    signal = real_signals.generate_flag_pennant_signal(strategy)
                
                if signal and signal.action != 'hold':
                    signals.append(signal)
                    
            except Exception as e:
                self.logger.warning(f"전략 {strategy_id} 신호 생성 실패: {e}")
        
        return signals
    
    def _consolidate_signals(self, signals: List[TradingSignal]) -> Optional[ConsolidatedSignal]:
        """신호 통합 (실제 시스템과 동일한 로직)"""
        if not signals:
            return None
        
        buy_signals = [s for s in signals if s.action == 'buy']
        sell_signals = [s for s in signals if s.action == 'sell']
        
        # 신호 점수 계산
        buy_score = (sum(s.confidence for s in buy_signals) / len(buy_signals)) if buy_signals else 0
        sell_score = (sum(s.confidence for s in sell_signals) / len(sell_signals)) if sell_signals else 0
        
        # 신호 비율 가중치
        total_signals = len(signals)
        buy_weight = len(buy_signals) / total_signals
        sell_weight = len(sell_signals) / total_signals
        
        # 최종 점수
        final_buy_score = buy_score * buy_weight
        final_sell_score = sell_score * sell_weight
        
        # 결정 (임계값: 0.3)
        min_threshold = 0.3
        
        if final_buy_score > final_sell_score and final_buy_score > min_threshold:
            return ConsolidatedSignal(
                action='buy',
                confidence=final_buy_score,
                suggested_amount=int(self.config.get('trading', {}).get('max_trade_amount', 100000) * 0.5),
                contributing_strategies=[s.strategy_id for s in buy_signals],
                reasoning=f"매수 신호 우세 (점수: {final_buy_score:.3f})"
            )
        elif final_sell_score > final_buy_score and final_sell_score > min_threshold:
            return ConsolidatedSignal(
                action='sell',
                confidence=final_sell_score,
                suggested_amount=0,
                contributing_strategies=[s.strategy_id for s in sell_signals],
                reasoning=f"매도 신호 우세 (점수: {final_sell_score:.3f})"
            )
        
        return None
    
    def _execute_backtest_trade(self, signal: ConsolidatedSignal, price: float, timestamp: datetime):
        """백테스트 거래 실행"""
        if signal.action == 'buy' and self.current_capital > signal.suggested_amount:
            # 매수
            amount = min(signal.suggested_amount, self.current_capital * 0.95)  # 95%까지만 사용
            volume = amount / price
            fee = amount * self.trading_fee
            
            self.current_capital -= (amount + fee)
            self.btc_holdings += volume
            
            trade = BacktestTrade(
                timestamp=timestamp,
                action='buy',
                price=price,
                volume=volume,
                amount=amount,
                strategy_signals=signal.contributing_strategies,
                confidence=signal.confidence,
                portfolio_value=self.current_capital + (self.btc_holdings * price)
            )
            self.trades.append(trade)
            
        elif signal.action == 'sell' and self.btc_holdings > 0:
            # 매도 (전량)
            volume = self.btc_holdings
            amount = volume * price
            fee = amount * self.trading_fee
            
            # 손익 계산 (평균 매수가 대비)
            if self.trades:
                avg_buy_price = sum(t.price * t.volume for t in self.trades if t.action == 'buy') / sum(t.volume for t in self.trades if t.action == 'buy')
                pnl = (price - avg_buy_price) * volume - fee
            else:
                pnl = 0
            
            self.current_capital += (amount - fee)
            self.btc_holdings = 0
            
            trade = BacktestTrade(
                timestamp=timestamp,
                action='sell',
                price=price,
                volume=volume,
                amount=amount,
                strategy_signals=signal.contributing_strategies,
                confidence=signal.confidence,
                pnl=pnl,
                portfolio_value=self.current_capital
            )
            self.trades.append(trade)
    
    def _calculate_metrics(self, df: pd.DataFrame, start_price: float, end_price: float) -> BacktestMetrics:
        """성과 지표 계산"""
        if not self.portfolio_history:
            raise ValueError("포트폴리오 히스토리가 없습니다")
        
        start_date = df.iloc[0]['timestamp']
        end_date = df.iloc[-1]['timestamp']
        days = (end_date - start_date).days
        
        # 최종 포트폴리오 가치
        final_value = self.portfolio_history[-1]['total_value']
        
        # 기본 수익률
        total_return = (final_value - self.initial_capital) / self.initial_capital
        annualized_return = (final_value / self.initial_capital) ** (365 / days) - 1
        
        # Buy and Hold 수익률
        buy_and_hold_return = (end_price - start_price) / start_price
        alpha = total_return - buy_and_hold_return
        
        # 최대 낙폭 계산
        portfolio_values = [p['total_value'] for p in self.portfolio_history]
        peak = self.initial_capital
        max_drawdown = 0
        
        for value in portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # 샤프 비율 계산 (간단한 버전)
        returns = []
        for i in range(1, len(portfolio_values)):
            daily_return = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
            returns.append(daily_return)
        
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return * 365) / (std_return * np.sqrt(365)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 거래 통계
        buy_trades = [t for t in self.trades if t.action == 'buy']
        sell_trades = [t for t in self.trades if t.action == 'sell']
        
        total_trades = len(sell_trades)  # 매도 완료된 거래만 계산
        profitable_trades = len([t for t in sell_trades if t.pnl > 0])
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        if sell_trades:
            avg_trade_return = np.mean([t.pnl for t in sell_trades])
            best_trade = max([t.pnl for t in sell_trades])
            worst_trade = min([t.pnl for t in sell_trades])
        else:
            avg_trade_return = 0
            best_trade = 0
            worst_trade = 0
        
        return BacktestMetrics(
            start_date=start_date,
            end_date=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            avg_trade_return=avg_trade_return,
            best_trade=best_trade,
            worst_trade=worst_trade,
            portfolio_final_value=final_value,
            buy_and_hold_return=buy_and_hold_return,
            alpha=alpha
        )
    
    def save_results(self, metrics: BacktestMetrics, output_path: str = None):
        """백테스트 결과 저장"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"backtesting/results/backtest_{timestamp}.json"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        results = {
            'metrics': asdict(metrics),
            'trades': [asdict(t) for t in self.trades],
            'portfolio_history': self.portfolio_history,
            'settings': {
                'initial_capital': self.initial_capital,
                'trading_fee': self.trading_fee,
                'use_multi_strategy': self.use_multi_strategy
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)
        
        self.logger.info(f"백테스트 결과 저장됨: {output_path}")
        return output_path


class MockUpbitAPI:
    """백테스트용 모의 Upbit API"""
    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self.current_index = 0
    
    def update_current_position(self, index: int):
        """현재 시점 업데이트"""
        self.current_index = index
    
    def get_candles(self, market: str, timeframe: str, interval: int, count: int) -> List[Dict]:
        """과거 캔들 데이터 반환"""
        start_idx = max(0, self.current_index - count)
        end_idx = self.current_index + 1
        
        candles = []
        for i in range(start_idx, end_idx):
            if i < len(self.df):
                row = self.df.iloc[i]
                candle = {
                    'trade_price': str(row['close']),
                    'high_price': str(row['high']),
                    'low_price': str(row['low']),
                    'opening_price': str(row['open']),
                    'candle_acc_trade_volume': str(row['volume']),
                    'candle_date_time_utc': row['timestamp'].isoformat()
                }
                candles.append(candle)
        
        return list(reversed(candles))  # 최신순으로 정렬
    
    def get_current_price(self, market: str = "KRW-BTC") -> float:
        """현재가 반환"""
        if self.current_index < len(self.df):
            return float(self.df.iloc[self.current_index]['close'])
        return 0
    
    def get_market_data(self, market: str = "KRW-BTC"):
        """시장 데이터 반환"""
        if self.current_index < len(self.df):
            row = self.df.iloc[self.current_index]
            return MarketData(
                market=market,
                price=float(row['close']),
                volume=float(row['volume']),
                timestamp=row['timestamp'],
                high=float(row['high']),
                low=float(row['low']),
                open=float(row['open']),
                prev_close=float(self.df.iloc[self.current_index-1]['close']) if self.current_index > 0 else float(row['close'])
            )
        return None


if __name__ == "__main__":
    # 백테스트 실행 예시
    backtester = Backtester(initial_capital=1000000)  # 100만원 시작
    
    # 최근 3개월 백테스트
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    try:
        metrics = backtester.run_backtest(start_date, end_date)
        
        print("=== 백테스트 결과 ===")
        print(f"기간: {metrics.start_date.date()} ~ {metrics.end_date.date()}")
        print(f"총 수익률: {metrics.total_return:.2%}")
        print(f"연환산 수익률: {metrics.annualized_return:.2%}")
        print(f"최대 낙폭: {metrics.max_drawdown:.2%}")
        print(f"샤프 비율: {metrics.sharpe_ratio:.2f}")
        print(f"승률: {metrics.win_rate:.1%}")
        print(f"총 거래 수: {metrics.total_trades}")
        print(f"Buy & Hold 수익률: {metrics.buy_and_hold_return:.2%}")
        print(f"알파(초과수익): {metrics.alpha:.2%}")
        
        # 결과 저장
        output_file = backtester.save_results(metrics)
        print(f"상세 결과 저장됨: {output_file}")
        
    except Exception as e:
        print(f"백테스트 실행 오류: {e}")