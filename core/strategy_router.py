"""
전략 라우터 - 모든 전략을 통합 관리하는 중앙 시스템
Strategy Router - Central system for managing all strategies
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
from datetime import datetime
import logging

from core.professional_strategies import ProfessionalStrategyAnalyzer, ProfessionalSignal
from core.enhanced_strategy_implementation import EnhancedStrategyAnalyzer, EnhancedSignal
from core.real_strategy_signals import RealStrategySignals
from core.signal_manager import TradingSignal

class StrategyRouter:
    """전략 라우팅 및 통합 관리 시스템"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logger = logging.getLogger('StrategyRouter')
        
        # 거래 설정 가져오기
        self.max_trade_amount = self.config.get('trading', {}).get('max_trade_amount', 100000)
        self.base_trade_amount = self.max_trade_amount * 0.5  # 기본 거래 금액은 최대의 50%
        
        # 전략 분석기 초기화
        self.professional_analyzer = ProfessionalStrategyAnalyzer(config)
        self.enhanced_analyzer = EnhancedStrategyAnalyzer()
        self.real_signals = RealStrategySignals()
        
        # 전략 매핑 테이블
        self.strategy_map = self._initialize_strategy_map()
        
        # 전략 성능 추적
        self.performance_tracker = {}
        
    def _initialize_strategy_map(self) -> Dict:
        """전략 매핑 테이블 초기화"""
        return {
            # 시간봉 전략 (Professional)
            'h1': {'analyzer': 'professional', 'method': 'h1_ema_crossover_strategy', 'name': 'EMA Crossover'},
            'h2': {'analyzer': 'professional', 'method': 'h2_rsi_divergence_strategy', 'name': 'RSI Divergence'},
            'h3': {'analyzer': 'professional', 'method': 'h3_pivot_point_strategy', 'name': 'Pivot Point Bounce'},
            'h4': {'analyzer': 'professional', 'method': 'h4_vwap_strategy', 'name': 'VWAP Pullback'},
            'h5': {'analyzer': 'professional', 'method': 'h5_macd_histogram_strategy', 'name': 'MACD Histogram'},
            'h6': {'analyzer': 'professional', 'method': 'h6_bollinger_squeeze_strategy', 'name': 'Bollinger Squeeze'},
            'h7': {'analyzer': 'professional', 'method': 'h7_open_interest_funding_strategy', 'name': 'OI & Funding'},
            'h8': {'analyzer': 'professional', 'method': 'h8_flag_pennant_strategy', 'name': 'Flag/Pennant'},
            
            # 일봉 전략
            'd1': {'analyzer': 'professional', 'method': 'd1_weekly_ma50_strategy', 'name': 'Weekly + MA50'},
            'd2': {'analyzer': 'enhanced', 'method': 'ichimoku_cloud_strategy', 'name': 'Ichimoku Cloud'},
            'd3': {'analyzer': 'enhanced', 'method': 'bollinger_width_strategy', 'name': 'BB Width Compression'},
            'd4': {'analyzer': 'real', 'method': 'fear_greed_strategy', 'name': 'Fear & Greed Index'},
            'd5': {'analyzer': 'real', 'method': 'golden_cross_strategy', 'name': 'Golden Cross Pullback'},
            'd6': {'analyzer': 'real', 'method': 'on_chain_strategy', 'name': 'MVRV Z-Score'},
            'd7': {'analyzer': 'enhanced', 'method': 'stochastic_rsi_strategy', 'name': 'Stochastic RSI'},
            'd8': {'analyzer': 'enhanced', 'method': 'adx_meta_strategy', 'name': 'ADX Trend Strength'},
        }
    
    def route_strategy(self, strategy_id: str, df: pd.DataFrame, 
                       additional_data: Dict = None) -> Optional[TradingSignal]:
        """전략 라우팅 - 적절한 분석기로 전달"""
        try:
            if strategy_id not in self.strategy_map:
                self.logger.warning(f"Unknown strategy: {strategy_id}")
                return None
            
            strategy_info = self.strategy_map[strategy_id]
            analyzer_type = strategy_info['analyzer']
            method_name = strategy_info['method']
            
            # 분석기 선택 및 실행
            signal = None
            
            if analyzer_type == 'professional':
                analyzer = self.professional_analyzer
                method = getattr(analyzer, method_name, None)
                if method:
                    # Professional 전략 실행
                    if strategy_id == 'h7' and additional_data:
                        # OI 전략은 추가 데이터 필요
                        professional_signal = method(df, 
                                                    additional_data.get('oi_data'),
                                                    additional_data.get('funding_rate'))
                    elif strategy_id == 'd1' and additional_data:
                        # D1은 주봉 데이터도 필요
                        professional_signal = method(df, additional_data.get('weekly_df'))
                    else:
                        professional_signal = method(df)
                    
                    if professional_signal:
                        signal = self._convert_professional_to_trading(professional_signal)
            
            elif analyzer_type == 'enhanced':
                analyzer = self.enhanced_analyzer
                method = getattr(analyzer, method_name, None)
                if method:
                    enhanced_signal = method(df)
                    if enhanced_signal:
                        signal = self._convert_enhanced_to_trading(enhanced_signal, strategy_id)
            
            elif analyzer_type == 'real':
                # RealStrategySignals는 다르게 처리
                if method_name == 'fear_greed_strategy':
                    signal = self._get_fear_greed_signal(df, strategy_id)
                elif method_name == 'golden_cross_strategy':
                    signal = self._get_golden_cross_signal(df, strategy_id)
                elif method_name == 'on_chain_strategy':
                    signal = self._get_on_chain_signal(df, strategy_id, additional_data)
            
            # 성능 기록
            if signal:
                self._record_signal(strategy_id, signal)
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Strategy routing error for {strategy_id}: {e}")
            return None
    
    def _convert_professional_to_trading(self, prof_signal: ProfessionalSignal) -> TradingSignal:
        """ProfessionalSignal을 TradingSignal로 변환"""
        return TradingSignal(
            strategy_id=prof_signal.strategy_id,
            action='buy' if prof_signal.action == 'long' else 'sell' if prof_signal.action == 'short' else 'hold',
            confidence=prof_signal.confidence,
            price=prof_signal.entry_price,
            suggested_amount=prof_signal.position_size,
            reasoning=prof_signal.reasoning,
            timestamp=prof_signal.timestamp,
            timeframe=prof_signal.timeframe,
            stop_loss=prof_signal.stop_loss,
            take_profits=prof_signal.take_profits,
            risk_reward_ratio=prof_signal.risk_reward_ratio
        )
    
    def _convert_enhanced_to_trading(self, enh_signal: EnhancedSignal, strategy_id: str) -> TradingSignal:
        """EnhancedSignal을 TradingSignal로 변환"""
        action = 'hold'
        if enh_signal.direction == 'long':
            action = 'buy'
        elif enh_signal.direction == 'short':
            action = 'sell'
        
        return TradingSignal(
            strategy_id=strategy_id,
            action=action,
            confidence=enh_signal.confidence,
            price=enh_signal.entry_price,
            suggested_amount=enh_signal.position_size,
            reasoning=enh_signal.reason,
            timestamp=datetime.now(),
            timeframe='1h' if strategy_id.startswith('h') else '1d',
            stop_loss=enh_signal.stop_loss,
            take_profits=enh_signal.take_profits
        )
    
    def _get_fear_greed_signal(self, df: pd.DataFrame, strategy_id: str) -> Optional[TradingSignal]:
        """공포탐욕 지수 신호"""
        # 간단한 구현 (실제로는 더 복잡한 계산 필요)
        rsi = df['close'].pct_change().rolling(14).apply(
            lambda x: 100 - (100 / (1 + (x[x > 0].sum() / -x[x < 0].sum())))
        ).iloc[-1]
        
        if rsi < 30:  # Extreme fear
            # 공포 지수가 낮을수록 더 큰 금액
            amount_multiplier = (30 - rsi) / 30  # 0 ~ 1
            suggested_amount = self.base_trade_amount * (0.4 + 0.3 * amount_multiplier)
            
            return TradingSignal(
                strategy_id=strategy_id,
                action='buy',
                confidence=0.65,
                price=df['close'].iloc[-1],
                suggested_amount=int(suggested_amount),
                reasoning=f"Extreme Fear (RSI: {rsi:.1f})",
                timestamp=datetime.now(),
                timeframe='1d'
            )
        elif rsi > 70:  # Extreme greed
            return TradingSignal(
                strategy_id=strategy_id,
                action='sell',
                confidence=0.60,
                price=df['close'].iloc[-1],
                suggested_amount=0,
                reasoning=f"Extreme Greed (RSI: {rsi:.1f})",
                timestamp=datetime.now(),
                timeframe='1d'
            )
        
        return None
    
    def _get_golden_cross_signal(self, df: pd.DataFrame, strategy_id: str) -> Optional[TradingSignal]:
        """골든크로스 신호"""
        if len(df) < 200:
            return None
        
        ma50 = df['close'].rolling(50).mean()
        ma200 = df['close'].rolling(200).mean()
        
        # 골든크로스 체크
        if ma50.iloc[-2] <= ma200.iloc[-2] and ma50.iloc[-1] > ma200.iloc[-1]:
            # 설정 기반 거래 금액 계산 (기본 금액의 60%)
            suggested_amount = self.base_trade_amount * 0.6
            
            return TradingSignal(
                strategy_id=strategy_id,
                action='buy',
                confidence=0.75,
                price=df['close'].iloc[-1],
                suggested_amount=int(suggested_amount),
                reasoning="Golden Cross Detected",
                timestamp=datetime.now(),
                timeframe='1d'
            )
        
        return None
    
    def _get_on_chain_signal(self, df: pd.DataFrame, strategy_id: str, 
                            additional_data: Dict = None) -> Optional[TradingSignal]:
        """온체인 지표 신호 (MVRV 등)"""
        # 실제로는 온체인 데이터 API 필요
        # 여기서는 간단한 시뮬레이션
        current_price = df['close'].iloc[-1]
        avg_price_30d = df['close'].rolling(30).mean().iloc[-1]
        
        mvrv_ratio = current_price / avg_price_30d
        
        if mvrv_ratio < 0.8:  # Undervalued
            # MVRV 비율에 따른 동적 금액 계산
            # 저평가 정도가 클수록 더 큰 금액
            undervalue_factor = (0.8 - mvrv_ratio) / 0.2  # 0 ~ 1
            suggested_amount = self.base_trade_amount * (0.3 + 0.2 * undervalue_factor)
            
            return TradingSignal(
                strategy_id=strategy_id,
                action='buy',
                confidence=0.70,
                price=current_price,
                suggested_amount=int(suggested_amount),
                reasoning=f"MVRV Undervalued ({mvrv_ratio:.2f})",
                timestamp=datetime.now(),
                timeframe='1d'
            )
        
        return None
    
    def _record_signal(self, strategy_id: str, signal: TradingSignal):
        """신호 기록 (성능 추적용)"""
        if strategy_id not in self.performance_tracker:
            self.performance_tracker[strategy_id] = {
                'signals': [],
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'avg_confidence': 0
            }
        
        tracker = self.performance_tracker[strategy_id]
        tracker['signals'].append({
            'timestamp': signal.timestamp,
            'action': signal.action,
            'confidence': signal.confidence,
            'price': signal.price
        })
        
        tracker['total_signals'] += 1
        if signal.action == 'buy':
            tracker['buy_signals'] += 1
        elif signal.action == 'sell':
            tracker['sell_signals'] += 1
        
        # 평균 신뢰도 업데이트
        all_confidences = [s['confidence'] for s in tracker['signals']]
        tracker['avg_confidence'] = np.mean(all_confidences)
    
    def get_strategy_performance(self, strategy_id: str = None) -> Dict:
        """전략 성능 조회"""
        if strategy_id:
            return self.performance_tracker.get(strategy_id, {})
        return self.performance_tracker
    
    def get_active_strategies(self) -> List[str]:
        """활성 전략 목록"""
        return list(self.strategy_map.keys())
    
    def get_strategy_info(self, strategy_id: str) -> Dict:
        """전략 정보 조회"""
        if strategy_id in self.strategy_map:
            info = self.strategy_map[strategy_id].copy()
            info['performance'] = self.get_strategy_performance(strategy_id)
            return info
        return {}