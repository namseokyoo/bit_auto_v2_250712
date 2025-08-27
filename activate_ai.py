#!/usr/bin/env python3
"""
AI 분석 기능 활성화 및 초기 실행
"""

import os
import sys
import json
import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# 경로 설정
sys.path.insert(0, '.')
env_path = Path('config/.env')
load_dotenv(env_path)

async def test_deepseek_connection():
    """DeepSeek API 연결 테스트"""
    try:
        import httpx
        
        api_key = os.getenv('DEEPSEEK_API_KEY', '').strip("'\"")
        if not api_key or 'your_' in api_key:
            print("❌ DeepSeek API 키가 설정되지 않았습니다.")
            return False
            
        print("🔍 DeepSeek API 연결 테스트 중...")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        test_data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a cryptocurrency trading analyst. Respond in Korean."},
                {"role": "user", "content": "비트코인 현재 시장 상황을 한 문장으로 분석해주세요."}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=test_data
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ DeepSeek API 연결 성공!")
                print(f"테스트 응답: {result['choices'][0]['message']['content']}")
                return True
            else:
                print(f"❌ API 오류: {response.status_code}")
                print(f"응답: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False

async def run_initial_analysis():
    """초기 AI 분석 실행"""
    print("\n🤖 초기 AI 분석 실행 중...")
    
    from ai_analyzer import FeedbackLoop
    
    try:
        feedback = FeedbackLoop()
        
        # 일일 분석 실행
        print("📊 일일 성과 분석 중...")
        await feedback.run_daily_analysis()
        
        # 시장 예측
        print("📈 시장 예측 생성 중...")
        # 여기에 시장 예측 로직 추가 가능
        
        await feedback.close()
        print("✅ AI 분석 완료")
        
        # 결과 확인
        conn = sqlite3.connect('data/ai_analysis.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM analyses 
            WHERE timestamp > datetime('now', '-1 hour')
        """)
        count = cursor.fetchone()[0]
        conn.close()
        
        print(f"📝 생성된 분석: {count}개")
        return True
        
    except Exception as e:
        print(f"❌ AI 분석 실패: {e}")
        return False

def setup_ai_scheduler():
    """AI 분석 스케줄러 설정"""
    print("\n⏰ AI 분석 스케줄러 설정 중...")
    
    # feedback_scheduler.py 확인 및 업데이트
    scheduler_path = Path('feedback_scheduler.py')
    if scheduler_path.exists():
        print("✅ 스케줄러 파일 존재")
        
        # 스케줄러가 활성화되어 있는지 확인
        with open(scheduler_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'DEEPSEEK_API_KEY' in content:
                print("✅ 스케줄러에 AI 분석 통합됨")
            else:
                print("⚠️ 스케줄러 업데이트 필요")
    else:
        print("❌ 스케줄러 파일 없음")

def check_dashboard_integration():
    """대시보드 AI 탭 통합 확인"""
    print("\n🖥️ 대시보드 통합 확인 중...")
    
    dashboard_path = Path('dashboard.py')
    if dashboard_path.exists():
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        checks = {
            "AI 분석 탭": "data-tab=\"ai\"" in content,
            "AI API 엔드포인트": "/api/ai-analysis" in content,
            "트리거 기능": "/api/ai-analysis/trigger" in content,
        }
        
        for feature, exists in checks.items():
            if exists:
                print(f"✅ {feature}: 활성화됨")
            else:
                print(f"❌ {feature}: 비활성화")
    else:
        print("❌ 대시보드 파일 없음")

async def main():
    """메인 실행 함수"""
    print("🚀 DeepSeek AI 분석 기능 활성화\n")
    print("=" * 50)
    
    # 1. API 연결 테스트
    api_success = await test_deepseek_connection()
    if not api_success:
        print("\n⚠️ API 연결 실패. config/.env 파일을 확인하세요.")
        return
    
    # 2. 초기 분석 실행
    analysis_success = await run_initial_analysis()
    
    # 3. 스케줄러 확인
    setup_ai_scheduler()
    
    # 4. 대시보드 통합 확인
    check_dashboard_integration()
    
    print("\n" + "=" * 50)
    if api_success and analysis_success:
        print("✨ AI 분석 기능이 성공적으로 활성화되었습니다!")
        print("\n다음 단계:")
        print("1. 대시보드를 재시작하세요: python3 dashboard.py")
        print("2. http://localhost:8080 에서 AI 분석 탭 확인")
        print("3. '분석 실행' 버튼으로 수동 분석 가능")
    else:
        print("⚠️ 일부 기능이 제대로 설정되지 않았습니다.")
        print("로그를 확인하고 문제를 해결하세요.")

if __name__ == "__main__":
    asyncio.run(main())