#!/usr/bin/env python3
"""
고급 트레이딩 전략 모음
- 머신러닝 기반 전략
- 통계적 차익거래
- 오더북 불균형
- VWAP 추종
- 페어 트레이딩
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class AdvancedStrategies:
    """고급 전략 모음"""
    
    def __init__(self):
        self.ml_model = None
        self.scaler = StandardScaler()
        self.pair_ratio_history = []
        
    def calculate_advanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """고급 기술적 지표 계산"""
        
        # VWAP (Volume Weighted Average Price)
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['vwap_distance'] = (df['close'] - df['vwap']) / df['vwap']
        
        # OBV (On Balance Volume)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = ranges.max(axis=1).rolling(14).mean()
        df['atr_ratio'] = df['atr'] / df['close']
        
        # Stochastic Oscillator
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # Williams %R
        df['williams_r'] = -100 * ((high_14 - df['close']) / (high_14 - low_14))
        
        # Money Flow Index (MFI)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        positive_flow = pd.Series(0.0, index=df.index)
        negative_flow = pd.Series(0.0, index=df.index)
        
        positive_mask = typical_price > typical_price.shift(1)
        negative_mask = typical_price < typical_price.shift(1)
        
        positive_flow[positive_mask] = money_flow[positive_mask]
        negative_flow[negative_mask] = money_flow[negative_mask]
        
        positive_mf = positive_flow.rolling(14).sum()
        negative_mf = negative_flow.rolling(14).sum()
        
        mfi_ratio = positive_mf / negative_mf
        df['mfi'] = 100 - (100 / (1 + mfi_ratio))
        
        # Ichimoku Cloud
        period9_high = df['high'].rolling(9).max()
        period9_low = df['low'].rolling(9).min()
        df['tenkan_sen'] = (period9_high + period9_low) / 2
        
        period26_high = df['high'].rolling(26).max()
        period26_low = df['low'].rolling(26).min()
        df['kijun_sen'] = (period26_high + period26_low) / 2
        
        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)
        
        period52_high = df['high'].rolling(52).max()
        period52_low = df['low'].rolling(52).min()
        df['senkou_span_b'] = ((period52_high + period52_low) / 2).shift(26)
        
        df['chikou_span'] = df['close'].shift(-26)
        
        # 변동성 지표
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['volatility_ratio'] = df['volatility'] / df['volatility'].rolling(50).mean()
        
        return df
    
    def strategy_ml_prediction(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """머신러닝 기반 가격 예측 전략"""
        df = df.copy()
        
        # 특징 생성
        features = []
        feature_names = []
        
        # 가격 관련 특징
        for period in [5, 10, 20, 50]:
            col_name = f'return_{period}'
            df[col_name] = df['close'].pct_change(period)
            features.append(col_name)
            feature_names.append(col_name)
        
        # 기술적 지표 특징
        indicators = ['RSI', 'MACD_diff', 'BB_position', 'volume_ratio', 
                     'vwap_distance', 'stoch_k', 'mfi', 'atr_ratio']
        
        for indicator in indicators:
            if indicator in df.columns:
                features.append(indicator)
                feature_names.append(indicator)
        
        # 타겟 생성 (다음 캔들이 상승하면 1, 하락하면 0)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        # NaN 제거
        df_clean = df[features + ['target']].dropna()
        
        if len(df_clean) < 100:
            df['signal'] = 0
            df['signal_strength'] = 0
            return df
        
        # 학습/예측 분할 (80/20)
        split_idx = int(len(df_clean) * 0.8)
        
        X_train = df_clean[features].iloc[:split_idx]
        y_train = df_clean['target'].iloc[:split_idx]
        X_test = df_clean[features].iloc[split_idx:]
        
        # 모델 학습
        if self.ml_model is None or params.get('retrain', False):
            self.ml_model = RandomForestClassifier(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 5),
                random_state=42
            )
            
            # 스케일링
            X_train_scaled = self.scaler.fit_transform(X_train)
            self.ml_model.fit(X_train_scaled, y_train)
        
        # 예측
        X_test_scaled = self.scaler.transform(X_test)
        predictions = self.ml_model.predict(X_test_scaled)
        probabilities = self.ml_model.predict_proba(X_test_scaled)
        
        # 신호 생성
        df['signal'] = 0
        df['signal_strength'] = 0
        
        test_indices = df_clean.index[split_idx:]
        
        for i, idx in enumerate(test_indices):
            if i < len(predictions):
                # 확률이 임계값 이상일 때만 거래
                threshold = params.get('probability_threshold', 0.6)
                
                if probabilities[i][1] > threshold:  # 상승 예측
                    df.loc[idx, 'signal'] = 1
                    df.loc[idx, 'signal_strength'] = probabilities[i][1]
                elif probabilities[i][0] > threshold:  # 하락 예측
                    df.loc[idx, 'signal'] = -1
                    df.loc[idx, 'signal_strength'] = probabilities[i][0]
        
        return df
    
    def strategy_statistical_arbitrage(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """통계적 차익거래 전략"""
        df = df.copy()
        
        # 가격의 로그 변환
        df['log_price'] = np.log(df['close'])
        
        # Ornstein-Uhlenbeck 프로세스 파라미터 추정
        lookback = params.get('lookback', 60)
        
        # 평균 회귀 속도 계산
        df['log_return'] = df['log_price'].diff()
        
        # 이동 평균과의 차이
        df['ma_long'] = df['close'].rolling(lookback).mean()
        df['spread'] = df['close'] - df['ma_long']
        df['spread_mean'] = df['spread'].rolling(lookback).mean()
        df['spread_std'] = df['spread'].rolling(lookback).std()
        
        # Z-Score 계산
        df['z_score'] = (df['spread'] - df['spread_mean']) / df['spread_std']
        
        # 반감기 계산
        df['half_life'] = -np.log(2) / np.log(df['spread'].autocorr())
        
        # 신호 생성
        entry_z = params.get('entry_zscore', 2.0)
        exit_z = params.get('exit_zscore', 0.5)
        
        df['signal'] = 0
        df['signal_strength'] = 0
        
        # 매수 신호: Z-score가 -entry_z 이하
        buy_signal = df['z_score'] < -entry_z
        df.loc[buy_signal, 'signal'] = 1
        df.loc[buy_signal, 'signal_strength'] = np.abs(df.loc[buy_signal, 'z_score']) / 3
        
        # 매도 신호: Z-score가 entry_z 이상
        sell_signal = df['z_score'] > entry_z
        df.loc[sell_signal, 'signal'] = -1
        df.loc[sell_signal, 'signal_strength'] = np.abs(df.loc[sell_signal, 'z_score']) / 3
        
        # 포지션 청산: Z-score가 -exit_z와 exit_z 사이
        exit_signal = (df['z_score'] > -exit_z) & (df['z_score'] < exit_z)
        df.loc[exit_signal, 'signal'] = -1 if df['z_score'].shift(1) > 0 else 1
        df.loc[exit_signal, 'signal_strength'] = 0.5
        
        df['signal_strength'] = df['signal_strength'].clip(0, 1)
        
        return df
    
    def strategy_orderbook_imbalance(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """오더북 불균형 전략 (거래량 기반 근사)"""
        df = df.copy()
        
        # 거래량 불균형 계산 (실제로는 오더북 데이터 필요)
        # 여기서는 가격 변화와 거래량으로 근사
        
        # 매수/매도 압력 추정
        df['price_change'] = df['close'].diff()
        df['buy_volume'] = df['volume'].where(df['price_change'] > 0, 0)
        df['sell_volume'] = df['volume'].where(df['price_change'] < 0, 0)
        
        # 이동 평균
        window = params.get('window', 20)
        df['buy_volume_ma'] = df['buy_volume'].rolling(window).mean()
        df['sell_volume_ma'] = df['sell_volume'].rolling(window).mean()
        
        # 오더북 불균형 지표
        df['order_imbalance'] = (df['buy_volume_ma'] - df['sell_volume_ma']) / (df['buy_volume_ma'] + df['sell_volume_ma'] + 1)
        
        # 거래량 급증 감지
        df['volume_surge'] = df['volume'] / df['volume'].rolling(window).mean()
        
        # 가격 모멘텀
        df['price_momentum'] = df['close'].pct_change(params.get('momentum_period', 10))
        
        # 신호 생성
        imbalance_threshold = params.get('imbalance_threshold', 0.3)
        volume_threshold = params.get('volume_threshold', 1.5)
        
        df['signal'] = 0
        df['signal_strength'] = 0
        
        # 강한 매수 압력
        buy_signal = (
            (df['order_imbalance'] > imbalance_threshold) &
            (df['volume_surge'] > volume_threshold) &
            (df['price_momentum'] > 0)
        )
        df.loc[buy_signal, 'signal'] = 1
        df.loc[buy_signal, 'signal_strength'] = df.loc[buy_signal, 'order_imbalance']
        
        # 강한 매도 압력
        sell_signal = (
            (df['order_imbalance'] < -imbalance_threshold) &
            (df['volume_surge'] > volume_threshold) &
            (df['price_momentum'] < 0)
        )
        df.loc[sell_signal, 'signal'] = -1
        df.loc[sell_signal, 'signal_strength'] = np.abs(df.loc[sell_signal, 'order_imbalance'])
        
        df['signal_strength'] = df['signal_strength'].clip(0, 1)
        
        return df
    
    def strategy_vwap_trading(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """VWAP 기반 거래 전략"""
        df = df.copy()
        
        # VWAP는 이미 calculate_advanced_indicators에서 계산됨
        if 'vwap' not in df.columns:
            df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            df['vwap_distance'] = (df['close'] - df['vwap']) / df['vwap']
        
        # VWAP 밴드 생성
        df['vwap_std'] = df['vwap_distance'].rolling(params.get('std_period', 20)).std()
        df['vwap_upper'] = df['vwap'] * (1 + params.get('band_multiplier', 2) * df['vwap_std'])
        df['vwap_lower'] = df['vwap'] * (1 - params.get('band_multiplier', 2) * df['vwap_std'])
        
        # 트렌드 필터
        df['trend'] = df['close'].rolling(params.get('trend_period', 50)).mean()
        df['trend_direction'] = np.where(df['close'] > df['trend'], 1, -1)
        
        # 거래량 필터
        df['volume_filter'] = df['volume'] > df['volume'].rolling(20).mean()
        
        # 신호 생성
        df['signal'] = 0
        df['signal_strength'] = 0
        
        # VWAP 아래에서 매수 (상승 트렌드에서만)
        buy_signal = (
            (df['close'] < df['vwap_lower']) &
            (df['trend_direction'] > 0) &
            df['volume_filter']
        )
        df.loc[buy_signal, 'signal'] = 1
        df.loc[buy_signal, 'signal_strength'] = np.abs(df.loc[buy_signal, 'vwap_distance'])
        
        # VWAP 위에서 매도 (하락 트렌드에서만)
        sell_signal = (
            (df['close'] > df['vwap_upper']) &
            (df['trend_direction'] < 0) &
            df['volume_filter']
        )
        df.loc[sell_signal, 'signal'] = -1
        df.loc[sell_signal, 'signal_strength'] = np.abs(df.loc[sell_signal, 'vwap_distance'])
        
        # VWAP 복귀 신호 (평균 회귀)
        mean_reversion = params.get('mean_reversion', True)
        if mean_reversion:
            reversion_buy = (
                (df['close'] < df['vwap'] * 0.995) &
                (df['vwap_distance'] < -0.01)
            )
            df.loc[reversion_buy, 'signal'] = 1
            df.loc[reversion_buy, 'signal_strength'] = 0.5
            
            reversion_sell = (
                (df['close'] > df['vwap'] * 1.005) &
                (df['vwap_distance'] > 0.01)
            )
            df.loc[reversion_sell, 'signal'] = -1
            df.loc[reversion_sell, 'signal_strength'] = 0.5
        
        df['signal_strength'] = df['signal_strength'].clip(0, 1)
        
        return df
    
    def strategy_ichimoku_cloud(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """일목균형표 (Ichimoku Cloud) 전략"""
        df = df.copy()
        
        # 일목균형표 지표는 이미 calculate_advanced_indicators에서 계산됨
        required_cols = ['tenkan_sen', 'kijun_sen', 'senkou_span_a', 'senkou_span_b']
        if not all(col in df.columns for col in required_cols):
            # 재계산
            period9_high = df['high'].rolling(9).max()
            period9_low = df['low'].rolling(9).min()
            df['tenkan_sen'] = (period9_high + period9_low) / 2
            
            period26_high = df['high'].rolling(26).max()
            period26_low = df['low'].rolling(26).min()
            df['kijun_sen'] = (period26_high + period26_low) / 2
            
            df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)
            
            period52_high = df['high'].rolling(52).max()
            period52_low = df['low'].rolling(52).min()
            df['senkou_span_b'] = ((period52_high + period52_low) / 2).shift(26)
        
        # 구름 상태 판단
        df['cloud_top'] = df[['senkou_span_a', 'senkou_span_b']].max(axis=1)
        df['cloud_bottom'] = df[['senkou_span_a', 'senkou_span_b']].min(axis=1)
        df['cloud_thickness'] = df['cloud_top'] - df['cloud_bottom']
        
        # 가격 위치
        df['above_cloud'] = df['close'] > df['cloud_top']
        df['below_cloud'] = df['close'] < df['cloud_bottom']
        df['in_cloud'] = (~df['above_cloud']) & (~df['below_cloud'])
        
        # TK 크로스
        df['tk_cross_bull'] = (
            (df['tenkan_sen'] > df['kijun_sen']) &
            (df['tenkan_sen'].shift(1) <= df['kijun_sen'].shift(1))
        )
        df['tk_cross_bear'] = (
            (df['tenkan_sen'] < df['kijun_sen']) &
            (df['tenkan_sen'].shift(1) >= df['kijun_sen'].shift(1))
        )
        
        # 신호 생성
        df['signal'] = 0
        df['signal_strength'] = 0
        
        # 강한 매수 신호: 가격이 구름 위 + TK 불 크로스
        strong_buy = df['above_cloud'] & df['tk_cross_bull']
        df.loc[strong_buy, 'signal'] = 1
        df.loc[strong_buy, 'signal_strength'] = 0.9
        
        # 일반 매수 신호: 가격이 구름 돌파
        cloud_breakout = df['above_cloud'] & df['below_cloud'].shift(1)
        df.loc[cloud_breakout, 'signal'] = 1
        df.loc[cloud_breakout, 'signal_strength'] = 0.7
        
        # 강한 매도 신호: 가격이 구름 아래 + TK 베어 크로스
        strong_sell = df['below_cloud'] & df['tk_cross_bear']
        df.loc[strong_sell, 'signal'] = -1
        df.loc[strong_sell, 'signal_strength'] = 0.9
        
        # 일반 매도 신호: 가격이 구름 아래로 돌파
        cloud_breakdown = df['below_cloud'] & df['above_cloud'].shift(1)
        df.loc[cloud_breakdown, 'signal'] = -1
        df.loc[cloud_breakdown, 'signal_strength'] = 0.7
        
        # 구름 내부에서는 신호 약화
        df.loc[df['in_cloud'], 'signal_strength'] *= 0.5
        
        return df
    
    def strategy_combined_signal(self, df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        """여러 전략의 신호를 결합하는 앙상블 전략"""
        df = df.copy()
        
        # 사용할 전략들
        strategies = params.get('strategies', [
            'momentum_scalping',
            'mean_reversion',
            'vwap_trading',
            'ichimoku_cloud'
        ])
        
        # 각 전략의 가중치
        weights = params.get('weights', {
            'momentum_scalping': 0.25,
            'mean_reversion': 0.25,
            'vwap_trading': 0.25,
            'ichimoku_cloud': 0.25
        })
        
        # 각 전략 실행 및 신호 수집
        signals = []
        strengths = []
        
        for strategy in strategies:
            if strategy == 'momentum_scalping':
                # 기본 모멘텀 전략 (backtest_runner에서 가져옴)
                momentum_period = params.get('momentum_period', 20)
                df['momentum'] = df['close'].pct_change(momentum_period)
                
                temp_signal = pd.Series(0, index=df.index)
                temp_strength = pd.Series(0, index=df.index)
                
                buy_mask = df['momentum'] > 0.002
                temp_signal[buy_mask] = 1
                temp_strength[buy_mask] = np.abs(df['momentum'][buy_mask]) / 0.01
                
                sell_mask = df['momentum'] < -0.002
                temp_signal[sell_mask] = -1
                temp_strength[sell_mask] = np.abs(df['momentum'][sell_mask]) / 0.01
                
                signals.append(temp_signal * weights.get(strategy, 0.25))
                strengths.append(temp_strength * weights.get(strategy, 0.25))
                
            elif strategy == 'vwap_trading':
                result = self.strategy_vwap_trading(df, params)
                signals.append(result['signal'] * weights.get(strategy, 0.25))
                strengths.append(result['signal_strength'] * weights.get(strategy, 0.25))
                
            elif strategy == 'ichimoku_cloud':
                result = self.strategy_ichimoku_cloud(df, params)
                signals.append(result['signal'] * weights.get(strategy, 0.25))
                strengths.append(result['signal_strength'] * weights.get(strategy, 0.25))
        
        # 신호 결합
        if signals:
            df['combined_signal'] = sum(signals)
            df['combined_strength'] = sum(strengths)
            
            # 최종 신호 결정 (임계값 기반)
            signal_threshold = params.get('signal_threshold', 0.5)
            
            df['signal'] = 0
            df.loc[df['combined_signal'] > signal_threshold, 'signal'] = 1
            df.loc[df['combined_signal'] < -signal_threshold, 'signal'] = -1
            
            df['signal_strength'] = df['combined_strength'].clip(0, 1)
        else:
            df['signal'] = 0
            df['signal_strength'] = 0
        
        return df