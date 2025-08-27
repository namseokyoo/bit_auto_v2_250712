#!/usr/bin/env python3
"""
DeepSeek API 설정 및 테스트 스크립트
"""

import os
import sys
import json
import asyncio
import httpx
from dotenv import load_dotenv, set_key
from pathlib import Path

# 환경 변수 로드
env_path = Path('config/.env')
load_dotenv(env_path)

async def test_deepseek_api():
    """DeepSeek API 연결 테스트"""
    
    api_key = os.getenv('DEEPSEEK_API_KEY', '')
    
    if not api_key or api_key == 'your_deepseek_api_key_here':
        print("❌ DeepSeek API 키가 설정되지 않았습니다.")
        print("\n📝 DeepSeek API 키를 입력하세요:")
        print("   (https://platform.deepseek.com 에서 발급)")
        new_key = input("API Key: ").strip()
        
        if new_key:
            # .env 파일 업데이트
            set_key(env_path, 'DEEPSEEK_API_KEY', new_key)
            api_key = new_key
            print("✅ API 키가 저장되었습니다.")
        else:
            print("❌ API 키 입력이 취소되었습니다.")
            return False
    
    # API 테스트
    print("\n🔍 DeepSeek API 연결 테스트 중...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    test_data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a cryptocurrency trading analyst."},
            {"role": "user", "content": "Analyze BTC price trend briefly in one sentence."}
        ],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=test_data
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ API 연결 성공!")
                print(f"응답: {result['choices'][0]['message']['content']}")
                return True
            else:
                print(f"❌ API 오류: {response.status_code}")
                print(f"응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 연결 실패: {e}")
            return False

async def setup_ai_database():
    """AI 분석 데이터베이스 초기화"""
    import sqlite3
    
    print("\n📊 AI 분석 데이터베이스 설정 중...")
    
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            date DATE,
            total_trades INTEGER,
            win_rate REAL,
            total_pnl REAL,
            ai_feedback TEXT,
            adjustments TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            strategy_name TEXT,
            parameter TEXT,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            confidence REAL,
            applied BOOLEAN DEFAULT FALSE
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ 데이터베이스 설정 완료")

def update_config():
    """config.yaml에 AI 분석 설정 추가"""
    import yaml
    
    config_path = Path('config/config.yaml')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # AI 분석 설정 추가
    if 'ai_analysis' not in config:
        config['ai_analysis'] = {
            'enabled': True,
            'provider': 'deepseek',
            'analysis_interval': 3600,  # 1시간마다
            'features': {
                'daily_review': True,
                'strategy_optimization': True,
                'market_forecast': True,
                'risk_assessment': True
            },
            'auto_apply_suggestions': False  # 자동 적용 비활성화 (수동 확인 필요)
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        print("✅ config.yaml에 AI 분석 설정 추가됨")
    else:
        print("ℹ️ AI 분석 설정이 이미 존재합니다")

async def main():
    """메인 설정 프로세스"""
    print("🚀 DeepSeek AI 통합 설정 시작\n")
    
    # 1. API 테스트
    api_success = await test_deepseek_api()
    
    if not api_success:
        print("\n⚠️ API 설정을 완료해주세요.")
        print("config/.env 파일에서 DEEPSEEK_API_KEY를 직접 설정할 수도 있습니다.")
        return
    
    # 2. 데이터베이스 설정
    await setup_ai_database()
    
    # 3. 설정 파일 업데이트
    update_config()
    
    print("\n✨ DeepSeek AI 통합 설정 완료!")
    print("\n다음 단계:")
    print("1. 대시보드를 재시작하세요")
    print("2. AI 분석 탭에서 실시간 분석을 확인하세요")
    print("3. 일일 리뷰는 매일 자정에 자동 실행됩니다")

if __name__ == "__main__":
    asyncio.run(main())