#!/usr/bin/env python3
"""
AI Prediction 모델 학습 스크립트
RandomForest를 사용하여 BTC 가격 예측 모델 생성
"""

import os
import pickle
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pyupbit
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIModelTrainer:
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.model_path = "models/rf_model.pkl"
        
        # 모델 디렉토리 생성
        os.makedirs("models", exist_ok=True)
        
    def prepare_data(self, symbol="KRW-BTC", days=30):
        """데이터 수집 및 전처리"""
        logger.info(f"Collecting {days} days of {symbol} data...")
        
        # 데이터 수집
        df = pyupbit.get_ohlcv(symbol, interval="minute60", count=days*24)
        
        # 기술적 지표 추가
        df = self.add_technical_indicators(df)
        
        # 특징 생성
        df = self.create_features(df)
        
        # 타겟 생성 (1시간 후 가격이 오르면 1, 내리면 0)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        # NaN 제거
        df = df.dropna()
        
        logger.info(f"Data prepared: {len(df)} samples")
        return df
    
    def add_technical_indicators(self, df):
        """기술적 지표 추가"""
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
        
        # ATR (Average True Range)
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
        """특징 생성"""
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
    
    def train_model(self, df):
        """모델 학습"""
        # 특징 선택
        feature_columns = [
            'return_1', 'return_3', 'return_5', 'return_10', 'return_20',
            'ma5_distance', 'ma20_distance', 'ma50_distance',
            'rsi', 'macd_diff', 'bb_position',
            'volume_ratio', 'volume_change',
            'atr_ratio', 'volatility',
            'body_size', 'upper_shadow', 'lower_shadow',
            'hour', 'day_of_week'
        ]
        
        self.feature_names = feature_columns
        
        X = df[feature_columns]
        y = df['target']
        
        # 학습/테스트 분할
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=False
        )
        
        logger.info(f"Training with {len(X_train)} samples...")
        
        # 모델 학습
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            random_state=42,
            n_jobs=-1
        )
        
        self.model.fit(X_train, y_train)
        
        # 평가
        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)
        
        train_acc = accuracy_score(y_train, train_pred)
        test_acc = accuracy_score(y_test, test_pred)
        
        logger.info(f"Training Accuracy: {train_acc:.4f}")
        logger.info(f"Testing Accuracy: {test_acc:.4f}")
        
        # 상세 평가
        print("\n=== Classification Report ===")
        print(classification_report(y_test, test_pred, target_names=['DOWN', 'UP']))
        
        print("\n=== Confusion Matrix ===")
        cm = confusion_matrix(y_test, test_pred)
        print(f"True Negatives: {cm[0,0]}, False Positives: {cm[0,1]}")
        print(f"False Negatives: {cm[1,0]}, True Positives: {cm[1,1]}")
        
        # 특징 중요도
        feature_importance = pd.DataFrame({
            'feature': feature_columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\n=== Top 10 Important Features ===")
        print(feature_importance.head(10))
        
        return test_acc
    
    def save_model(self):
        """모델 저장"""
        model_data = {
            'model': self.model,
            'feature_names': self.feature_names,
            'trained_at': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {self.model_path}")
    
    def backtest(self, df, initial_capital=1_000_000):
        """간단한 백테스트"""
        X = df[self.feature_names]
        predictions = self.model.predict_proba(X)
        
        df['prediction'] = predictions[:, 1]  # UP 확률
        df['signal'] = df['prediction'].apply(
            lambda x: 'BUY' if x > 0.6 else ('SELL' if x < 0.4 else 'HOLD')
        )
        
        capital = initial_capital
        position = 0
        trades = []
        
        for i in range(1, len(df)):
            if df['signal'].iloc[i] == 'BUY' and position == 0:
                position = capital / df['close'].iloc[i]
                capital = 0
                trades.append({
                    'type': 'BUY',
                    'price': df['close'].iloc[i],
                    'time': df.index[i]
                })
                
            elif df['signal'].iloc[i] == 'SELL' and position > 0:
                capital = position * df['close'].iloc[i]
                position = 0
                trades.append({
                    'type': 'SELL',
                    'price': df['close'].iloc[i],
                    'time': df.index[i]
                })
        
        # 최종 포지션 청산
        if position > 0:
            capital = position * df['close'].iloc[-1]
        
        total_return = (capital - initial_capital) / initial_capital * 100
        
        logger.info(f"Backtest Results:")
        logger.info(f"  Total Trades: {len(trades)}")
        logger.info(f"  Final Capital: {capital:,.0f}원")
        logger.info(f"  Total Return: {total_return:.2f}%")
        
        return total_return

def main():
    """메인 실행 함수"""
    print("=" * 50)
    print("🤖 AI Prediction Model Training")
    print("=" * 50)
    
    trainer = AIModelTrainer()
    
    # 1. 데이터 준비
    df = trainer.prepare_data(days=30)
    
    # 2. 모델 학습
    accuracy = trainer.train_model(df)
    
    # 3. 백테스트
    if accuracy > 0.5:  # 정확도가 50% 이상일 때만
        returns = trainer.backtest(df.tail(7*24))  # 최근 7일
        
        if returns > 0:  # 수익이 양수일 때만 저장
            # 4. 모델 저장
            trainer.save_model()
            
            print("\n" + "=" * 50)
            print("✅ AI Model Training Complete!")
            print(f"  Accuracy: {accuracy:.2%}")
            print(f"  Backtest Return: {returns:.2f}%")
            print(f"  Model saved to: {trainer.model_path}")
            print("=" * 50)
        else:
            print("\n⚠️ Model not saved due to negative returns")
    else:
        print("\n⚠️ Model not saved due to low accuracy")

if __name__ == "__main__":
    main()