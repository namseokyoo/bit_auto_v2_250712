#!/usr/bin/env python3
"""
백테스트 실행기
- 다양한 전략 백테스트
- DeepSeek AI 분석 통합
- 실시간 진행상황 추적
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import pyupbit
import yaml
import requests
from dotenv import load_dotenv

from backtest_engine import BacktestEngine, Trade

# 환경변수 로드
load_dotenv('config/.env')

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyTester:
    """전략 테스터"""
    
    def __init__(self):
        # 설정 로드
        with open('config/config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
            
        # DeepSeek AI 설정 (선택적)
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.use_ai_analysis = bool(self.deepseek_api_key)
        
        if self.use_ai_analysis:
            logger.info("DeepSeek AI 분석 활성화")
        else:
            logger.info("DeepSeek AI 분석 비활성화 (API 키 없음)")
            
    def get_historical_data(self, 
                           symbol: str = "KRW-BTC",
                           interval: str = "minute5",
                           days: int = 30) -> pd.DataFrame:
        """
        과거 데이터 조회
        
        Args:
            symbol: 거래 심볼
            interval: 캔들 간격 (minute1, minute5, minute15, etc.)
            days: 조회 일수
            
        Returns:
            OHLCV 데이터프레임
        """
        try:
            # Upbit에서 과거 데이터 조회
            if interval.startswith("minute"):
                minutes = int(interval.replace("minute", ""))
                df = pyupbit.get_ohlcv(symbol, interval=interval, count=days * 24 * 60 // minutes)
            else:
                df = pyupbit.get_ohlcv(symbol, interval=interval, count=days)
                
            if df is None or df.empty:
                logger.error(f"데이터 조회 실패: {symbol}")
                return pd.DataFrame()
                
            logger.info(f"데이터 로드 완료: {len(df)}개 캔들")
            return df
            
        except Exception as e:
            logger.error(f"데이터 조회 오류: {e}")
            return pd.DataFrame()
            
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        # 이동평균
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['EMA_12'] = df['close'].ewm(span=12).mean()
        df['EMA_26'] = df['close'].ewm(span=26).mean()
        
        # MACD
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_diff'] = df['MACD'] - df['MACD_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['BB_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
        df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
        df['BB_width'] = df['BB_upper'] - df['BB_lower']
        df['BB_position'] = (df['close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
        
        # Volume indicators
        df['volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_SMA']
        
        # Price changes
        df['price_change'] = df['close'].pct_change()
        df['high_low_ratio'] = df['high'] / df['low'] - 1
        
        return df
    
    def strategy_momentum_scalping(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """모멘텀 스캘핑 전략"""
        df = df.copy()
        
        # 파라미터
        momentum_period = params.get('momentum_period', 20)
        entry_threshold = params.get('entry_threshold', 0.002)
        stop_loss = params.get('stop_loss', -0.003)
        take_profit = params.get('take_profit', 0.003)
        
        # 모멘텀 계산
        df['momentum'] = df['close'].pct_change(momentum_period)
        df['volume_surge'] = df['volume'] > df['volume_SMA'] * 1.5
        
        # 신호 생성
        df['buy_signal'] = (
            (df['momentum'] > entry_threshold) &
            (df['RSI'] < 70) &
            (df['volume_surge']) &
            (df['MACD_diff'] > 0)
        )
        
        df['sell_signal'] = (
            (df['momentum'] < -entry_threshold) |
            (df['RSI'] > 80) |
            (df['MACD_diff'] < 0)
        )
        
        df['signal'] = 0
        df.loc[df['buy_signal'], 'signal'] = 1
        df.loc[df['sell_signal'], 'signal'] = -1
        
        # 신호 강도 (0~1)
        df['signal_strength'] = abs(df['momentum']) / 0.01  # 1% 기준
        df['signal_strength'] = df['signal_strength'].clip(0, 1)
        
        return df
    
    def strategy_mean_reversion(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """평균 회귀 전략"""
        df = df.copy()
        
        # 파라미터
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2)
        rsi_oversold = params.get('rsi_oversold', 30)
        rsi_overbought = params.get('rsi_overbought', 70)
        
        # 신호 생성
        df['buy_signal'] = (
            (df['close'] < df['BB_lower']) &
            (df['RSI'] < rsi_oversold)
        )
        
        df['sell_signal'] = (
            (df['close'] > df['BB_upper']) &
            (df['RSI'] > rsi_overbought)
        )
        
        df['signal'] = 0
        df.loc[df['buy_signal'], 'signal'] = 1
        df.loc[df['sell_signal'], 'signal'] = -1
        
        # 신호 강도
        df['signal_strength'] = abs(df['BB_position'] - 0.5) * 2
        df['signal_strength'] = df['signal_strength'].clip(0, 1)
        
        return df
    
    def strategy_trend_following(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """추세 추종 전략"""
        df = df.copy()
        
        # Golden Cross / Death Cross
        df['golden_cross'] = (
            (df['SMA_20'] > df['SMA_50']) &
            (df['SMA_20'].shift(1) <= df['SMA_50'].shift(1))
        )
        
        df['death_cross'] = (
            (df['SMA_20'] < df['SMA_50']) &
            (df['SMA_20'].shift(1) >= df['SMA_50'].shift(1))
        )
        
        # MACD 신호
        df['macd_buy'] = (
            (df['MACD'] > df['MACD_signal']) &
            (df['MACD'].shift(1) <= df['MACD_signal'].shift(1))
        )
        
        df['macd_sell'] = (
            (df['MACD'] < df['MACD_signal']) &
            (df['MACD'].shift(1) >= df['MACD_signal'].shift(1))
        )
        
        # 종합 신호
        df['buy_signal'] = df['golden_cross'] | df['macd_buy']
        df['sell_signal'] = df['death_cross'] | df['macd_sell']
        
        df['signal'] = 0
        df.loc[df['buy_signal'], 'signal'] = 1
        df.loc[df['sell_signal'], 'signal'] = -1
        
        # 신호 강도
        df['trend_strength'] = abs(df['SMA_20'] - df['SMA_50']) / df['close']
        df['signal_strength'] = df['trend_strength'].clip(0, 1)
        
        return df
    
    def run_backtest(self,
                    strategy_name: str,
                    symbol: str = "KRW-BTC",
                    days: int = 30,
                    initial_capital: float = 1_000_000,
                    position_size: float = 0.1,
                    params: Dict = None) -> Dict:
        """
        백테스트 실행
        
        Args:
            strategy_name: 전략 이름
            symbol: 거래 심볼
            days: 백테스트 기간 (일)
            initial_capital: 초기 자본
            position_size: 포지션 크기 비율
            params: 전략 파라미터
            
        Returns:
            백테스트 결과
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"백테스트 시작: {strategy_name}")
        logger.info(f"심볼: {symbol}, 기간: {days}일, 초기자본: ₩{initial_capital:,.0f}")
        logger.info(f"{'='*60}")
        
        # 과거 데이터 조회
        df = self.get_historical_data(symbol, "minute5", days)
        if df.empty:
            return {"error": "데이터 조회 실패"}
            
        # 지표 계산
        df = self.calculate_indicators(df)
        
        # 전략별 신호 생성
        if strategy_name == "momentum_scalping":
            df = self.strategy_momentum_scalping(df, params or {})
        elif strategy_name == "mean_reversion":
            df = self.strategy_mean_reversion(df, params or {})
        elif strategy_name == "trend_following":
            df = self.strategy_trend_following(df, params or {})
        else:
            return {"error": f"알 수 없는 전략: {strategy_name}"}
            
        # 백테스트 엔진 초기화
        engine = BacktestEngine(initial_capital)
        
        # 거래 시뮬레이션
        position_open = False
        entry_price = 0
        entry_time = None
        trade_count = 0
        
        for idx, row in df.iterrows():
            if pd.isna(row['signal']):
                continue
                
            # 매수 신호
            if row['signal'] == 1 and not position_open:
                trade_amount = engine.current_capital * position_size
                quantity = trade_amount / row['close']
                
                trade = engine.execute_trade(
                    timestamp=idx,
                    symbol=symbol,
                    side='buy',
                    signal_price=row['close'],
                    quantity=quantity,
                    strategy=strategy_name,
                    signal_strength=row.get('signal_strength', 0.5)
                )
                
                if trade:
                    position_open = True
                    entry_price = trade.price
                    entry_time = idx
                    trade_count += 1
                    
                    if trade_count % 100 == 0:
                        logger.info(f"진행중... {trade_count}개 거래 완료")
                        
            # 매도 신호
            elif row['signal'] == -1 and position_open:
                trade = engine.execute_trade(
                    timestamp=idx,
                    symbol=symbol,
                    side='sell',
                    signal_price=row['close'],
                    quantity=engine.position,
                    strategy=strategy_name,
                    signal_strength=row.get('signal_strength', 0.5)
                )
                
                if trade:
                    position_open = False
                    entry_price = 0
                    entry_time = None
                    
        # 마지막 포지션 정리
        if position_open and len(df) > 0:
            last_price = df.iloc[-1]['close']
            engine.execute_trade(
                timestamp=df.index[-1],
                symbol=symbol,
                side='sell',
                signal_price=last_price,
                quantity=engine.position,
                strategy=strategy_name,
                signal_strength=0.5
            )
            
        # 결과 계산
        result = engine.calculate_metrics()
        
        # 결과 저장
        session_id = engine.save_results(
            strategy=strategy_name,
            symbol=symbol,
            period_start=df.index[0],
            period_end=df.index[-1],
            parameters=params
        )
        
        # AI 분석 (선택적)
        ai_analysis = None
        if self.use_ai_analysis and result.total_trades > 0:
            ai_analysis = self.get_ai_analysis(result, strategy_name)
            
        # 결과 출력
        engine.print_summary()
        
        return {
            'session_id': session_id,
            'strategy': strategy_name,
            'symbol': symbol,
            'period': f"{df.index[0].date()} ~ {df.index[-1].date()}",
            'metrics': {
                'total_trades': result.total_trades,
                'win_rate': round(result.win_rate, 2),
                'net_pnl': round(result.net_pnl, 0),
                'roi': round(result.roi, 2),
                'max_drawdown': round(result.max_drawdown_percent, 2),
                'sharpe_ratio': round(result.sharpe_ratio, 2),
                'profit_factor': round(result.profit_factor, 2),
                'total_fees': round(result.total_fees, 0),
                'total_slippage': round(result.total_slippage, 0)
            },
            'ai_analysis': ai_analysis,
            'equity_curve': result.equity_curve[-100:] if len(result.equity_curve) > 100 else result.equity_curve
        }
    
    def get_ai_analysis(self, result, strategy_name: str) -> Optional[str]:
        """DeepSeek AI를 사용한 백테스트 결과 분석"""
        if not self.deepseek_api_key:
            return None
            
        try:
            # DeepSeek API 호출
            headers = {
                'Authorization': f'Bearer {self.deepseek_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = f"""
            다음 백테스트 결과를 분석하고 개선점을 제안해주세요:
            
            전략: {strategy_name}
            총 거래: {result.total_trades}회
            승률: {result.win_rate:.1f}%
            순수익: {result.net_pnl:,.0f}원
            ROI: {result.roi:.2f}%
            최대낙폭: {result.max_drawdown_percent:.2f}%
            Sharpe Ratio: {result.sharpe_ratio:.2f}
            Profit Factor: {result.profit_factor:.2f}
            
            1. 이 결과의 강점과 약점은 무엇인가요?
            2. 개선할 수 있는 구체적인 방법은 무엇인가요?
            3. 실거래에 적용하기 전 주의사항은 무엇인가요?
            
            간단명료하게 답변해주세요.
            """
            
            data = {
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': '당신은 퀀트 트레이딩 전문가입니다.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7,
                'max_tokens': 500
            }
            
            response = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content']
                logger.info("AI 분석 완료")
                return analysis
            else:
                logger.warning(f"AI 분석 실패: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"AI 분석 오류: {e}")
            return None
    
    def compare_strategies(self, 
                          strategies: List[str],
                          symbol: str = "KRW-BTC",
                          days: int = 30,
                          initial_capital: float = 1_000_000) -> pd.DataFrame:
        """여러 전략 비교"""
        results = []
        
        for strategy in strategies:
            logger.info(f"\n전략 테스트: {strategy}")
            result = self.run_backtest(
                strategy_name=strategy,
                symbol=symbol,
                days=days,
                initial_capital=initial_capital
            )
            
            if 'error' not in result:
                results.append({
                    '전략': strategy,
                    '총거래': result['metrics']['total_trades'],
                    '승률(%)': result['metrics']['win_rate'],
                    '순수익': result['metrics']['net_pnl'],
                    'ROI(%)': result['metrics']['roi'],
                    'MDD(%)': result['metrics']['max_drawdown'],
                    'Sharpe': result['metrics']['sharpe_ratio'],
                    'PF': result['metrics']['profit_factor']
                })
                
        if results:
            comparison_df = pd.DataFrame(results)
            comparison_df = comparison_df.sort_values('ROI(%)', ascending=False)
            
            print("\n" + "="*80)
            print("📊 전략 비교 결과")
            print("="*80)
            print(comparison_df.to_string(index=False))
            print("="*80)
            
            return comparison_df
        else:
            logger.error("비교할 결과가 없습니다")
            return pd.DataFrame()


def main():
    """메인 실행 함수"""
    tester = StrategyTester()
    
    # 단일 전략 백테스트
    result = tester.run_backtest(
        strategy_name="momentum_scalping",
        symbol="KRW-BTC",
        days=30,
        initial_capital=1_000_000,
        position_size=0.1
    )
    
    # AI 분석 결과 출력
    if result.get('ai_analysis'):
        print("\n🤖 AI 분석 결과:")
        print("-" * 60)
        print(result['ai_analysis'])
        print("-" * 60)
    
    # 여러 전략 비교
    print("\n전략 비교 시작...")
    comparison = tester.compare_strategies(
        strategies=["momentum_scalping", "mean_reversion", "trend_following"],
        symbol="KRW-BTC",
        days=30,
        initial_capital=1_000_000
    )
    
    print("\n✅ 백테스트 완료!")


if __name__ == "__main__":
    main()