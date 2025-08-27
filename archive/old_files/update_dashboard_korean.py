#!/usr/bin/env python3
"""대시보드 한글화 스크립트"""

import re

# 한글 번역 매핑
translations = {
    # Title and headers
    'Quantum Trading Dashboard v3.0': '퀀텀 트레이딩 대시보드 v3.0',
    
    # Tab buttons
    '📊 Overview': '📊 개요',
    '🤖 AI Analysis': '🤖 AI 분석',
    '💰 Multi-Coin': '💰 멀티코인',
    '🎮 Control': '🎮 제어판',
    '📈 Trades': '📈 거래내역',
    '⚙️ Settings': '⚙️ 설정',
    '📝 Logs': '📝 로그',
    
    # Overview section
    '📊 System Status': '📊 시스템 상태',
    '💵 Portfolio Summary': '💵 포트폴리오 요약',
    "📈 Today's Performance": '📈 오늘의 성과',
    '🎯 Active Strategies': '🎯 활성 전략',
    'Loading system status...': '시스템 상태 로딩중...',
    'Loading portfolio...': '포트폴리오 로딩중...',
    'Loading performance...': '성과 로딩중...',
    'Loading strategies...': '전략 로딩중...',
    
    # AI Analysis section
    '🤖 DeepSeek AI Analysis': '🤖 DeepSeek AI 분석',
    'Refresh': '새로고침',
    'Trigger Analysis Now': '지금 분석 실행',
    'Loading AI analysis...': 'AI 분석 로딩중...',
    
    # Multi-Coin section
    '💰 Multi-Coin Trading Status': '💰 멀티코인 거래 상태',
    '📊 Coin Performance': '📊 코인 성과',
    'Loading coin status...': '코인 상태 로딩중...',
    'Coin': '코인',
    'Holdings': '보유량',
    'Avg Price': '평균가',
    'Current Price': '현재가',
    'PnL': '손익',
    'PnL %': '손익률',
    'Loading...': '로딩중...',
    
    # Control section
    '🎮 System Control': '🎮 시스템 제어',
    '▶️ Start Trading': '▶️ 거래 시작',
    '⏹️ Stop Trading': '⏹️ 거래 중지',
    '🔄 Restart System': '🔄 시스템 재시작',
    '🛠️ Quick Actions': '🛠️ 빠른 작업',
    '🚨 Emergency Stop': '🚨 긴급 중지',
    '💸 Close All Positions': '💸 모든 포지션 청산',
    '📊 Run Backtest': '📊 백테스트 실행',
    '📊 Process Monitor': '📊 프로세스 모니터',
    'Loading process status...': '프로세스 상태 로딩중...',
    
    # Trades section
    '📈 Recent Trades': '📈 최근 거래',
    'Time': '시간',
    'Symbol': '심볼',
    'Side': '방향',
    'Price': '가격',
    'Amount': '수량',
    'Status': '상태',
    'Strategy': '전략',
    'No trades yet': '거래 없음',
    
    # Settings section
    '⚙️ Trading Configuration': '⚙️ 거래 설정',
    '🔌 API Connection': '🔌 API 연결',
    'Check Connection': '연결 확인',
    'Click to check API status': 'API 상태를 확인하려면 클릭',
    'Loading configuration...': '설정 로딩중...',
    
    # Logs section
    '📝 System Logs': '📝 시스템 로그',
    'All Logs': '전체 로그',
    'Errors Only': '에러만',
    'Trade Logs': '거래 로그',
    'No logs available': '로그 없음',
    
    # Status messages
    'Running': '실행중',
    'Stopped': '중지됨',
    'Connected': '연결됨',
    'Disconnected': '연결 끊김',
    'Success': '성공',
    'Failed': '실패',
    'Error': '에러',
    'Warning': '경고',
    'Info': '정보',
    
    # Common buttons
    '🔄 Refresh': '🔄 새로고침',
    'Submit': '제출',
    'Cancel': '취소',
    'Save': '저장',
    'Delete': '삭제',
    'Edit': '편집',
    'View': '보기',
    
    # Performance metrics
    'Total Value': '총 자산',
    'KRW Balance': 'KRW 잔액',
    'Invested': '투자금',
    'Total PnL': '총 손익',
    "Today's PnL": '오늘 손익',
    'Return Rate': '수익률',
    'Win Rate': '승률',
    'Trade Count': '거래 횟수',
    
    # System metrics
    'CPU Usage': 'CPU 사용률',
    'Memory Usage': '메모리 사용률',
    'Uptime': '가동 시간',
    'Process Count': '프로세스 수',
    
    # JavaScript strings
    'Are you sure you want to close all positions?': '모든 포지션을 청산하시겠습니까?',
    'System control action completed': '시스템 제어 작업 완료',
    'Failed to perform action': '작업 실행 실패',
    'API is connected and working': 'API가 연결되어 정상 작동 중입니다',
    'API connection failed': 'API 연결 실패',
    'Analysis triggered successfully': '분석이 성공적으로 실행되었습니다',
    'Failed to trigger analysis': '분석 실행 실패',
}

def update_dashboard():
    """대시보드 파일 한글화"""
    
    # dashboard.py 파일 읽기
    with open('dashboard.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 번역 적용
    for eng, kor in translations.items():
        # HTML 문자열 내의 텍스트 교체
        content = content.replace(f'>{eng}<', f'>{kor}<')
        content = content.replace(f'"{eng}"', f'"{kor}"')
        content = content.replace(f"'{eng}'", f"'{kor}'")
        
        # JavaScript 문자열 교체
        content = content.replace(f'= "{eng}";', f'= "{kor}";')
        content = content.replace(f"= '{eng}';", f"= '{kor}';")
        
        # innerHTML 및 textContent 교체
        content = content.replace(f'innerHTML = `{eng}`', f'innerHTML = `{kor}`')
        content = content.replace(f'innerHTML = "{eng}"', f'innerHTML = "{kor}"')
        content = content.replace(f"innerHTML = '{eng}'", f"innerHTML = '{kor}'")
        content = content.replace(f'textContent = "{eng}"', f'textContent = "{kor}"')
        content = content.replace(f"textContent = '{eng}'", f"textContent = '{kor}'")
    
    # 파일 저장
    with open('dashboard.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 대시보드 한글화 완료!")
    
    # JavaScript 함수 내부의 문자열도 업데이트
    additional_replacements = [
        ('System is running', '시스템 실행중'),
        ('System is stopped', '시스템 중지됨'),
        ('No recent trades', '최근 거래 없음'),
        ('No active strategies', '활성 전략 없음'),
        ('Loading data...', '데이터 로딩중...'),
        ('Fetching data...', '데이터 가져오는 중...'),
        ('Updated', '업데이트됨'),
        ('Last update:', '마지막 업데이트:'),
        ('Buy', '매수'),
        ('Sell', '매도'),
        ('Market Making', '마켓 메이킹'),
        ('Statistical Arbitrage', '통계적 차익거래'),
        ('Microstructure', '미시구조'),
        ('Momentum Scalping', '모멘텀 스캘핑'),
        ('Mean Reversion', '평균 회귀'),
    ]
    
    # 추가 교체 수행
    with open('dashboard.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    for eng, kor in additional_replacements:
        content = content.replace(eng, kor)
    
    with open('dashboard.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 추가 한글화 완료!")

if __name__ == '__main__':
    update_dashboard()