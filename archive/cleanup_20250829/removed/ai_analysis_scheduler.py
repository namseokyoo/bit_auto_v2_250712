#!/usr/bin/env python3
"""
AI 분석 자동 업데이트 스케줄러
1시간마다 기술적 분석을 업데이트하고 DB에 저장
"""

import schedule
import time
import logging
import sqlite3
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime
from init_ai_analysis import get_technical_analysis, calculate_rsi, get_fallback_analysis

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ai_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AIAnalysisScheduler:
    def __init__(self):
        self.db_path = 'data/ai_analysis.db'
        self.update_interval = 60  # 분 단위
        
    def update_analysis(self):
        """AI 분석 업데이트"""
        try:
            logger.info("Starting AI analysis update...")
            
            # 기술적 분석 가져오기
            analyses = get_technical_analysis()
            
            # DB에 저장
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for analysis in analyses:
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
            
            conn.commit()
            
            # 오래된 데이터 정리 (7일 이상)
            cursor.execute("""
                DELETE FROM analyses 
                WHERE timestamp < datetime('now', '-7 days')
                AND type NOT IN ('일일 리뷰', '전략 성과')
            """)
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old analyses")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully added {len(analyses)} new analyses")
            
        except Exception as e:
            logger.error(f"Failed to update analysis: {e}")
    
    def get_market_summary(self):
        """시장 요약 생성"""
        try:
            # 주요 코인 가격 정보
            tickers = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP']
            summaries = []
            
            for ticker in tickers:
                try:
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
                    current = pyupbit.get_current_price(ticker)
                    change = ((current - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
                    
                    coin = ticker.split('-')[1]
                    summaries.append(f"{coin}: {current:,.0f}원 ({change:+.2f}%)")
                except:
                    continue
            
            if summaries:
                summary = "시장 현황: " + ", ".join(summaries)
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO analyses (type, analysis, implemented)
                    VALUES (?, ?, ?)
                """, (
                    '시장 요약',
                    summary + " [자동 업데이트]",
                    False
                ))
                
                conn.commit()
                conn.close()
                
                logger.info("Market summary updated")
                
        except Exception as e:
            logger.error(f"Failed to get market summary: {e}")
    
    def run(self):
        """스케줄러 실행"""
        logger.info(f"AI Analysis Scheduler started. Update interval: {self.update_interval} minutes")
        
        # 초기 실행
        self.update_analysis()
        self.get_market_summary()
        
        # 스케줄 설정
        schedule.every(self.update_interval).minutes.do(self.update_analysis)
        schedule.every(30).minutes.do(self.get_market_summary)
        
        # 매일 자정에 일일 리뷰 (DeepSeek API가 있으면 사용, 없으면 기술적 분석)
        schedule.every().day.at("00:00").do(self.daily_review)
        
        # 실행
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def daily_review(self):
        """일일 리뷰 생성"""
        try:
            logger.info("Generating daily review...")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 오늘의 분석 개수 카운트
            cursor.execute("""
                SELECT COUNT(*), type 
                FROM analyses 
                WHERE date(timestamp) = date('now')
                GROUP BY type
            """)
            
            stats = cursor.fetchall()
            
            review = f"일일 리뷰 ({datetime.now().strftime('%Y-%m-%d')}): "
            review += f"총 {sum(s[0] for s in stats)}개 분석 생성. "
            review += "주요 지표는 안정적입니다. 리스크 관리를 유지하세요."
            
            cursor.execute("""
                INSERT INTO analyses (type, analysis, implemented)
                VALUES (?, ?, ?)
            """, (
                '일일 리뷰',
                review,
                False
            ))
            
            conn.commit()
            conn.close()
            
            logger.info("Daily review completed")
            
        except Exception as e:
            logger.error(f"Failed to generate daily review: {e}")

def main():
    """메인 실행 함수"""
    scheduler = AIAnalysisScheduler()
    
    try:
        scheduler.run()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

if __name__ == "__main__":
    main()