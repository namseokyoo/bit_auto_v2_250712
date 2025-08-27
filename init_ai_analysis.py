#!/usr/bin/env python3
"""
AI 분석 탭 초기 데이터 생성 및 기술적 분석 제공
"""

import sqlite3
import json
from datetime import datetime, timedelta
import random
import pyupbit
import pandas as pd
import numpy as np

def init_database():
    """데이터베이스 초기화"""
    conn = sqlite3.connect('data/ai_analysis.db')
    cursor = conn.cursor()
    
    # 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            type TEXT NOT NULL,
            analysis TEXT NOT NULL,
            confidence REAL,
            suggestions TEXT,
            implemented BOOLEAN DEFAULT FALSE
        )
    ''')
    
    conn.commit()
    return conn, cursor

def get_technical_analysis():
    """기술적 지표 기반 분석 생성"""
    try:
        # 최근 BTC 데이터 가져오기
        df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=200)
        
        # 기술적 지표 계산
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA50'] = df['close'].rolling(window=50).mean()
        df['RSI'] = calculate_rsi(df['close'])
        
        # Bollinger Bands
        std = df['close'].rolling(window=20).std()
        df['BB_upper'] = df['MA20'] + (std * 2)
        df['BB_lower'] = df['MA20'] - (std * 2)
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 분석 생성
        analyses = []
        
        # 트렌드 분석
        trend_signal = "상승" if current['close'] > current['MA20'] > current['MA50'] else "하락"
        analyses.append({
            'type': '트렌드 분석',
            'analysis': f"현재 BTC는 {trend_signal} 트렌드입니다. MA20: {current['MA20']:,.0f}원, MA50: {current['MA50']:,.0f}원",
            'confidence': 0.75
        })
        
        # RSI 분석
        rsi_value = current['RSI']
        if rsi_value > 70:
            rsi_signal = "과매수 구간 (매도 신호)"
        elif rsi_value < 30:
            rsi_signal = "과매도 구간 (매수 신호)"
        else:
            rsi_signal = "중립 구간"
        
        analyses.append({
            'type': 'RSI 지표',
            'analysis': f"RSI {rsi_value:.1f} - {rsi_signal}. 단기적 조정 가능성을 고려하세요.",
            'confidence': 0.68
        })
        
        # Bollinger Bands 분석
        bb_position = (current['close'] - current['BB_lower']) / (current['BB_upper'] - current['BB_lower'])
        if bb_position > 0.8:
            bb_signal = "상단 밴드 근접 - 과매수 가능성"
        elif bb_position < 0.2:
            bb_signal = "하단 밴드 근접 - 과매도 가능성"
        else:
            bb_signal = "중간 영역 - 안정적"
        
        analyses.append({
            'type': 'Bollinger Bands',
            'analysis': f"{bb_signal}. 현재 가격은 밴드의 {bb_position*100:.0f}% 위치",
            'confidence': 0.70
        })
        
        # MACD 분석
        if current['MACD'] > current['Signal'] and prev['MACD'] <= prev['Signal']:
            macd_signal = "골든크로스 발생 - 매수 신호"
        elif current['MACD'] < current['Signal'] and prev['MACD'] >= prev['Signal']:
            macd_signal = "데드크로스 발생 - 매도 신호"
        else:
            macd_signal = "추세 유지 중"
        
        analyses.append({
            'type': 'MACD',
            'analysis': f"{macd_signal}. MACD: {current['MACD']:,.0f}, Signal: {current['Signal']:,.0f}",
            'confidence': 0.72
        })
        
        # 거래량 분석
        vol_avg = df['volume'].rolling(window=20).mean().iloc[-1]
        vol_ratio = current['volume'] / vol_avg
        if vol_ratio > 1.5:
            vol_signal = "거래량 급증 - 추세 전환 가능성"
        elif vol_ratio < 0.5:
            vol_signal = "거래량 감소 - 횡보 가능성"
        else:
            vol_signal = "평균 거래량 유지"
        
        analyses.append({
            'type': '거래량 분석',
            'analysis': f"{vol_signal}. 현재 거래량은 20일 평균 대비 {vol_ratio:.1f}배",
            'confidence': 0.65
        })
        
        return analyses
        
    except Exception as e:
        print(f"기술적 분석 오류: {e}")
        return get_fallback_analysis()

def calculate_rsi(prices, period=14):
    """RSI 계산"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_fallback_analysis():
    """API나 데이터 없을 때 기본 분석"""
    analyses = [
        {
            'type': '시장 개요',
            'analysis': '현재 암호화폐 시장은 변동성이 높은 상태입니다. 리스크 관리에 주의하세요.',
            'confidence': 0.60
        },
        {
            'type': '전략 권장사항',
            'analysis': '단기 스캘핑보다는 중장기 포지션을 권장합니다. 일일 손실 한도를 2%로 유지하세요.',
            'confidence': 0.65
        },
        {
            'type': '리스크 관리',
            'analysis': '현재 포지션 크기를 줄이고 분산 투자를 고려하세요. 변동성이 높은 시간대는 거래를 자제하세요.',
            'confidence': 0.70
        },
        {
            'type': '최적화 제안',
            'analysis': '모멘텀 전략의 가중치를 높이고 평균 회귀 전략은 일시 중단을 권장합니다.',
            'confidence': 0.55
        }
    ]
    return analyses

def insert_analyses(cursor, analyses):
    """분석 결과를 DB에 저장"""
    for analysis in analyses:
        # confidence를 analysis 텍스트에 포함
        confidence_text = f" [신뢰도: {analysis.get('confidence', 0.5):.0%}]"
        full_analysis = analysis['analysis'] + confidence_text
        
        cursor.execute("""
            INSERT INTO analyses (type, analysis, implemented)
            VALUES (?, ?, ?)
        """, (
            analysis['type'],
            full_analysis,
            False
        ))
    print(f"✅ {len(analyses)}개 분석 추가됨")

def add_sample_history(cursor):
    """샘플 히스토리 데이터 추가"""
    # 최근 7일간의 가상 분석 데이터
    for days_ago in range(7, 0, -1):
        timestamp = datetime.now() - timedelta(days=days_ago)
        
        sample_analyses = [
            {
                'type': '일일 리뷰',
                'analysis': f"{days_ago}일 전 시장 분석: {'상승' if days_ago % 2 else '하락'} 추세 지속. "
                          f"일일 수익률 {random.uniform(-2, 3):.2f}%",
                'confidence': random.uniform(0.6, 0.8)
            },
            {
                'type': '전략 성과',
                'analysis': f"모멘텀 전략 {random.uniform(-1, 2):.2f}%, "
                          f"평균회귀 전략 {random.uniform(-1, 2):.2f}% 수익",
                'confidence': random.uniform(0.65, 0.85)
            }
        ]
        
        for analysis in sample_analyses:
            confidence_text = f" [신뢰도: {analysis['confidence']:.0%}]"
            full_analysis = analysis['analysis'] + confidence_text
            
            cursor.execute("""
                INSERT INTO analyses (timestamp, type, analysis, implemented)
                VALUES (?, ?, ?, ?)
            """, (
                timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                analysis['type'],
                full_analysis,
                random.choice([True, False])
            ))
    
    print("✅ 샘플 히스토리 데이터 추가됨")

def main():
    """메인 실행 함수"""
    print("🤖 AI 분석 데이터 초기화\n")
    
    # 데이터베이스 초기화
    conn, cursor = init_database()
    
    # 기존 데이터 확인
    cursor.execute("SELECT COUNT(*) FROM analyses")
    existing_count = cursor.fetchone()[0]
    print(f"기존 분석 데이터: {existing_count}개")
    
    if existing_count == 0:
        # 샘플 히스토리 추가
        add_sample_history(cursor)
    
    # 현재 기술적 분석 추가
    print("\n📊 기술적 분석 생성 중...")
    analyses = get_technical_analysis()
    insert_analyses(cursor, analyses)
    
    # 커밋 및 종료
    conn.commit()
    
    # 결과 확인
    cursor.execute("SELECT COUNT(*) FROM analyses")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT type, analysis
        FROM analyses 
        ORDER BY timestamp DESC 
        LIMIT 3
    """)
    recent = cursor.fetchall()
    
    print(f"\n📊 전체 분석 데이터: {total_count}개")
    print("\n최근 분석:")
    for row in recent:
        print(f"- [{row[0]}] {row[1][:80]}...")
    
    conn.close()
    
    print("\n✨ AI 분석 탭 데이터 준비 완료!")
    print("대시보드를 새로고침하면 AI 분석 탭에서 확인 가능합니다.")

if __name__ == "__main__":
    main()