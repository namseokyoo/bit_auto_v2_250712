#!/usr/bin/env python3
"""계좌 상태 확인 및 분석"""

import os
import sys
import pyupbit
from dotenv import load_dotenv
from datetime import datetime
import json

# 환경 변수 로드
load_dotenv('config/.env')

def check_account():
    """업비트 계좌 상태 확인"""
    
    access_key = os.getenv('UPBIT_ACCESS_KEY')
    secret_key = os.getenv('UPBIT_SECRET_KEY')
    
    if not access_key or not secret_key:
        print("❌ API 키가 설정되지 않았습니다")
        return None
    
    try:
        upbit = pyupbit.Upbit(access_key, secret_key)
        
        # 전체 잔고 조회
        balances = upbit.get_balances()
        
        print("\n" + "="*60)
        print("📊 계좌 상태 분석")
        print("="*60)
        print(f"🕒 조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        
        total_krw = 0
        total_value = 0
        positions = []
        
        for balance in balances:
            currency = balance['currency']
            amount = float(balance['balance'])
            locked = float(balance['locked'])
            avg_price = float(balance['avg_buy_price'])
            
            if currency == 'KRW':
                total_krw = amount + locked
                print(f"\n💵 원화 잔고:")
                print(f"   사용 가능: ₩{amount:,.0f}")
                print(f"   주문 중: ₩{locked:,.0f}")
                print(f"   총액: ₩{total_krw:,.0f}")
            else:
                if amount > 0:
                    symbol = f"KRW-{currency}"
                    try:
                        current_price = pyupbit.get_current_price(symbol)
                        if current_price:
                            current_value = amount * current_price
                            total_value += current_value
                            
                            if avg_price > 0:
                                profit = (current_price - avg_price) * amount
                                profit_rate = ((current_price / avg_price) - 1) * 100
                            else:
                                profit = 0
                                profit_rate = 0
                            
                            positions.append({
                                'currency': currency,
                                'amount': amount,
                                'avg_price': avg_price,
                                'current_price': current_price,
                                'current_value': current_value,
                                'profit': profit,
                                'profit_rate': profit_rate
                            })
                    except:
                        pass
        
        # 포지션 정보 출력
        if positions:
            print("\n📈 보유 코인:")
            for pos in positions:
                print(f"\n   {pos['currency']}:")
                print(f"      보유량: {pos['amount']:.8f}")
                print(f"      평균가: ₩{pos['avg_price']:,.0f}")
                print(f"      현재가: ₩{pos['current_price']:,.0f}")
                print(f"      평가액: ₩{pos['current_value']:,.0f}")
                print(f"      손익: ₩{pos['profit']:,.0f} ({pos['profit_rate']:+.2f}%)")
        
        # 총 자산 계산
        total_assets = total_krw + total_value
        
        print("\n" + "="*60)
        print("💰 총 자산 요약")
        print("-"*60)
        print(f"   원화: ₩{total_krw:,.0f}")
        print(f"   코인 평가액: ₩{total_value:,.0f}")
        print(f"   총 자산: ₩{total_assets:,.0f}")
        print("="*60)
        
        # 하루 2% 수익 목표 계산
        daily_target = total_assets * 0.02
        print(f"\n🎯 일일 수익 목표 (2%): ₩{daily_target:,.0f}")
        print(f"   → 시간당: ₩{daily_target/24:,.0f}")
        print(f"   → 거래당 목표 (일 100회 기준): ₩{daily_target/100:,.0f}")
        
        return {
            'total_krw': total_krw,
            'total_value': total_value,
            'total_assets': total_assets,
            'positions': positions,
            'daily_target': daily_target
        }
        
    except Exception as e:
        print(f"❌ 계좌 조회 실패: {e}")
        return None

def analyze_trading_requirements(account_info):
    """하루 2% 수익을 위한 거래 요구사항 분석"""
    
    if not account_info:
        return
    
    print("\n" + "="*60)
    print("📊 하루 2% 수익 달성 전략 분석")
    print("="*60)
    
    total_assets = account_info['total_assets']
    daily_target = account_info['daily_target']
    
    # 전략별 요구사항 계산
    strategies = [
        {
            'name': '고빈도 스캘핑',
            'trades_per_day': 200,
            'profit_per_trade': daily_target / 200,
            'win_rate_needed': 0.55,
            'risk_reward': 1.0
        },
        {
            'name': '중빈도 데이트레이딩',
            'trades_per_day': 50,
            'profit_per_trade': daily_target / 50,
            'win_rate_needed': 0.60,
            'risk_reward': 1.5
        },
        {
            'name': '저빈도 스윙',
            'trades_per_day': 10,
            'profit_per_trade': daily_target / 10,
            'win_rate_needed': 0.65,
            'risk_reward': 2.0
        }
    ]
    
    for strategy in strategies:
        print(f"\n📌 {strategy['name']}:")
        print(f"   일일 거래 횟수: {strategy['trades_per_day']}회")
        print(f"   거래당 목표 수익: ₩{strategy['profit_per_trade']:,.0f}")
        print(f"   필요 승률: {strategy['win_rate_needed']*100:.0f}%")
        print(f"   손익비: 1:{strategy['risk_reward']}")
        
        # 포지션 크기 계산
        position_size = total_assets * 0.1  # 총 자산의 10%씩 사용
        profit_rate_needed = strategy['profit_per_trade'] / position_size * 100
        print(f"   포지션 크기: ₩{position_size:,.0f}")
        print(f"   필요 수익률: {profit_rate_needed:.3f}%")
    
    print("\n" + "="*60)
    print("🎯 권장 전략: 고빈도 스캘핑 + AI 신호 결합")
    print("-"*60)
    print("   1. 1-5분봉 기준 단기 변동성 포착")
    print("   2. 기술적 지표 + AI 분석 결합")
    print("   3. 엄격한 손절/익절 (0.3% / 0.5%)")
    print("   4. 자동 포지션 관리")
    print("   5. 실시간 성과 모니터링")
    print("="*60)

if __name__ == "__main__":
    account_info = check_account()
    if account_info:
        analyze_trading_requirements(account_info)
        
        # 결과를 파일로 저장
        with open('account_status.json', 'w') as f:
            json.dump(account_info, f, indent=2, ensure_ascii=False)
        
        print("\n✅ 계좌 정보가 account_status.json에 저장되었습니다")