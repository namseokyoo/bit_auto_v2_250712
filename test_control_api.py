#!/usr/bin/env python3
"""
제어판 API 테스트 스크립트
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8080"

def test_trading_mode():
    """거래 모드 API 테스트"""
    print("\n" + "="*50)
    print("거래 모드 API 테스트")
    print("="*50)
    
    # 1. 현재 모드 조회
    print("\n1. 현재 모드 조회...")
    try:
        response = requests.get(f"{BASE_URL}/api/trading-mode")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 현재 모드: {data.get('mode')}")
        else:
            print(f"   ❌ 오류: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 연결 실패: {e}")
        return False
    
    # 2. dry_run으로 변경
    print("\n2. dry_run 모드로 변경...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/trading-mode",
            json={"mode": "dry_run"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ {data.get('message')}")
            print(f"   새 모드: {data.get('mode')}")
        else:
            print(f"   ❌ 오류: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 실패: {e}")
    
    # 3. live로 변경
    print("\n3. live 모드로 변경...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/trading-mode",
            json={"mode": "live"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ {data.get('message')}")
            print(f"   새 모드: {data.get('mode')}")
        else:
            print(f"   ❌ 오류: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 실패: {e}")
    
    return True

def test_system_control():
    """시스템 제어 API 테스트"""
    print("\n" + "="*50)
    print("시스템 제어 API 테스트")
    print("="*50)
    
    # 1. 시스템 중지
    print("\n1. 시스템 중지...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/system-control",
            json={"action": "stop"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 상태: {data.get('status')}")
            print(f"   시간: {data.get('timestamp')}")
        else:
            print(f"   ❌ 오류: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 실패: {e}")
    
    time.sleep(2)
    
    # 2. 시스템 시작
    print("\n2. 시스템 시작...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/system-control",
            json={"action": "start"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 상태: {data.get('status')}")
            print(f"   모드: {data.get('mode')}")
            print(f"   시간: {data.get('timestamp')}")
        else:
            print(f"   ❌ 오류: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 실패: {e}")

def test_emergency_stop():
    """긴급 정지 API 테스트"""
    print("\n" + "="*50)
    print("긴급 정지 API 테스트")
    print("="*50)
    
    print("\n긴급 정지 실행...")
    try:
        response = requests.post(f"{BASE_URL}/api/emergency-stop")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 상태: {data.get('status')}")
            print(f"   메시지: {data.get('message')}")
            print(f"   시간: {data.get('timestamp')}")
        else:
            print(f"   ❌ 오류: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ 실패: {e}")

def check_dashboard_running():
    """대시보드 실행 확인"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        return response.status_code == 200
    except:
        return False

def main():
    print("\n" + "="*60)
    print("🔧 제어판 API 테스트 시작")
    print("="*60)
    
    # 대시보드 실행 확인
    if not check_dashboard_running():
        print("\n❌ 대시보드가 실행되고 있지 않습니다!")
        print("   다음 명령어로 대시보드를 실행하세요:")
        print("   python dashboard.py")
        sys.exit(1)
    
    print("\n✅ 대시보드 연결 확인")
    
    # 각 API 테스트
    test_trading_mode()
    test_system_control()
    
    # 긴급 정지는 마지막에 (모든 프로세스가 중지됨)
    print("\n⚠️  긴급 정지를 테스트하시겠습니까? (y/n): ", end="")
    if input().lower() == 'y':
        test_emergency_stop()
    
    print("\n" + "="*60)
    print("✅ 테스트 완료")
    print("="*60)

if __name__ == "__main__":
    main()