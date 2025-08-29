#!/usr/bin/env python3
"""
AI Prediction 전략 구현
학습된 ML 모델을 사용한 실시간 거래 신호 생성
"""

import os
import pickle
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any
import pyupbit

logger = logging.getLogger(__name__)

class AIPredictionStrategy:
    """AI 기반 가격 예측 전략"""
    
    def __init__(self, weight: float = 0.10, enabled: bool = False):
        self.weight = weight
        self.enabled = enabled
        self.model = None
        self.feature_names = []
        self.model_path = "models/rf_model.pkl"
        self.min_confidence = 0.60
        self.last_prediction = None
        self.last_update = None
        
        # 모델 로드
        if enabled:
            self.load_model()
    
    def load_model(self):
        """저장된 모델 로드"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.model = model_data['model']
                    self.feature_names = model_data['feature_names']
                    
                logger.info(f"AI model loaded from {self.model_path}")
                logger.info(f"Model trained at: {model_data.get('trained_at', 'Unknown')}")
                self.enabled = True
            else:
                logger.warning(f"Model file not found: {self.model_path}")
                self.enabled = False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.enabled = False
    
    def prepare_features(self, symbol="KRW-BTC"):
        """실시간 특징 추출"""
        try:
            # 최근 100시간 데이터 수집
            df = pyupbit.get_ohlcv(symbol, interval="minute60", count=100)
            
            # 기술적 지표 계산
            df = self.add_technical_indicators(df)
            
            # 특징 생성
            df = self.create_features(df)
            
            # 최신 데이터만 반환
            if len(df) > 0 and all(col in df.columns for col in self.feature_names):
                return df[self.feature_names].iloc[-1:].values
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to prepare features: {e}")
            return None
    
    def add_technical_indicators(self, df):
        """기술적 지표 추가 (train_ai_model.py와 동일)"""
        # 이동평균
        df['ma_5'] = df['close'].rolling(window=5).mean()
        df['ma_20'] = df['close'].rolling(window=20).mean()
        df['ma_50'] = df['close'].rolling(window=50).mean()
        
        # RSI
        df['rsi'] = self.calculate_rsi(df['close'])
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_diff'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (std * 2)
        df['bb_lower'] = df['bb_middle'] - (std * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 거래량 지표
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()
        df['atr_ratio'] = df['atr'] / df['close']
        
        return df
    
    def calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def create_features(self, df):
        """특징 생성 (train_ai_model.py와 동일)"""
        # 가격 변화율
        for period in [1, 3, 5, 10, 20]:
            df[f'return_{period}'] = df['close'].pct_change(period)
        
        # 이동평균 대비 위치
        df['ma5_distance'] = (df['close'] - df['ma_5']) / df['ma_5']
        df['ma20_distance'] = (df['close'] - df['ma_20']) / df['ma_20']
        df['ma50_distance'] = (df['close'] - df['ma_50']) / df['ma_50']
        
        # 거래량 변화
        df['volume_change'] = df['volume'].pct_change()
        
        # 변동성
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        
        # 캔들 패턴
        df['body_size'] = abs(df['close'] - df['open']) / df['open']
        df['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / df['open']
        df['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / df['open']
        
        # 시간 특징
        df['hour'] = pd.to_datetime(df.index).hour
        df['day_of_week'] = pd.to_datetime(df.index).dayofweek
        
        return df
    
    def generate_signal(self, symbol="KRW-BTC") -> Dict[str, Any]:
        """거래 신호 생성"""
        if not self.enabled or self.model is None:
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'reason': 'AI model not available'
            }
        
        try:
            # 특징 추출
            features = self.prepare_features(symbol)
            if features is None:
                return {
                    'action': 'HOLD',
                    'confidence': 0.0,
                    'reason': 'Failed to prepare features'
                }
            
            # 예측
            prediction_proba = self.model.predict_proba(features)[0]
            up_probability = prediction_proba[1]
            down_probability = prediction_proba[0]
            
            # 신호 결정
            if up_probability > self.min_confidence:
                action = 'BUY'
                confidence = up_probability
                reason = f'AI predicts price increase (confidence: {up_probability:.2%})'
            elif down_probability > self.min_confidence:
                action = 'SELL'
                confidence = down_probability
                reason = f'AI predicts price decrease (confidence: {down_probability:.2%})'
            else:
                action = 'HOLD'
                confidence = max(up_probability, down_probability)
                reason = f'Insufficient confidence (up: {up_probability:.2%}, down: {down_probability:.2%})'
            
            # 결과 저장
            self.last_prediction = {
                'timestamp': datetime.now(),
                'action': action,
                'confidence': confidence,
                'up_prob': up_probability,
                'down_prob': down_probability
            }
            
            logger.info(f"AI Signal: {action} - {reason}")
            
            return {
                'action': action,
                'confidence': confidence,
                'reason': reason,
                'up_probability': up_probability,
                'down_probability': down_probability,
                'strategy': 'ai_prediction'
            }
            
        except Exception as e:
            logger.error(f"Failed to generate AI signal: {e}")
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'reason': f'Error: {str(e)}'
            }
    
    def get_status(self) -> Dict[str, Any]:
        """전략 상태 반환"""
        return {
            'enabled': self.enabled,
            'model_loaded': self.model is not None,
            'weight': self.weight,
            'min_confidence': self.min_confidence,
            'last_prediction': self.last_prediction
        }

# 테스트 함수
def test_strategy():
    """전략 테스트"""
    print("Testing AI Prediction Strategy...")
    
    strategy = AIPredictionStrategy(weight=0.10, enabled=True)
    
    if strategy.enabled:
        signal = strategy.generate_signal()
        print(f"Signal: {signal}")
        
        status = strategy.get_status()
        print(f"Status: {status}")
    else:
        print("Strategy is disabled (model not found)")

if __name__ == "__main__":
    test_strategy()