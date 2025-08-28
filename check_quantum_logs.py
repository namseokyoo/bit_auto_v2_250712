#!/usr/bin/env python3
"""
Quantum Trading 로그 및 상태 확인 스크립트
서버에서 실행하여 문제를 진단
"""

import os
import subprocess
import sys

def check_process():
    """프로세스 실행 상태 확인"""
    print("=== Quantum Trading 프로세스 상태 ===")
    result = subprocess.run(['pgrep', '-f', 'quantum_trading.py'], capture_output=True, text=True)
    if result.stdout:
        print(f"✅ 실행 중 (PID: {result.stdout.strip()})")
    else:
        print("❌ 실행되지 않음")
    print()

def check_logs():
    """로그 파일 확인"""
    print("=== 최근 로그 (마지막 50줄) ===")
    log_file = "logs/quantum_trading.log"
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-50:]:
                print(line.strip())
    else:
        print(f"로그 파일이 없습니다: {log_file}")
    print()

def check_dependencies():
    """필요한 모듈 확인"""
    print("=== 의존성 확인 ===")
    required_modules = [
        'pyupbit',
        'redis',
        'pandas',
        'numpy',
        'yaml',
        'sklearn'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}: 설치됨")
        except ImportError:
            print(f"❌ {module}: 설치 필요")
    print()

def test_import():
    """quantum_trading.py 임포트 테스트"""
    print("=== Import 테스트 ===")
    try:
        # 현재 디렉토리를 sys.path에 추가
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import quantum_trading
        print("✅ quantum_trading.py 임포트 성공")
    except Exception as e:
        print(f"❌ Import 실패: {e}")
        import traceback
        traceback.print_exc()
    print()

def check_config():
    """설정 파일 확인"""
    print("=== Config 파일 확인 ===")
    config_file = "config/config.yaml"
    if os.path.exists(config_file):
        print(f"✅ {config_file} 존재")
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                trading_mode = config.get('trading', {}).get('mode', 'unknown')
                trading_enabled = config.get('trading', {}).get('enabled', False)
                print(f"  - Trading Mode: {trading_mode}")
                print(f"  - Trading Enabled: {trading_enabled}")
        except Exception as e:
            print(f"❌ Config 읽기 실패: {e}")
    else:
        print(f"❌ {config_file} 없음")
    print()

def try_start():
    """Quantum Trading 시작 시도"""
    print("=== Quantum Trading 시작 시도 ===")
    try:
        # Dry-run 모드로 테스트
        result = subprocess.run(
            ['python3', 'quantum_trading.py', '--dry-run'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ 시작 성공")
        else:
            print(f"❌ 시작 실패 (exit code: {result.returncode})")
            print("STDOUT:", result.stdout[:500] if result.stdout else "없음")
            print("STDERR:", result.stderr[:500] if result.stderr else "없음")
    except subprocess.TimeoutExpired:
        print("✅ 프로세스 시작됨 (5초 이상 실행)")
    except Exception as e:
        print(f"❌ 시작 실패: {e}")

def main():
    print("=" * 50)
    print("Quantum Trading 진단 스크립트")
    print("=" * 50)
    print()
    
    check_process()
    check_dependencies()
    check_config()
    check_logs()
    test_import()
    
    # 시작 시도는 선택적으로
    response = input("Quantum Trading을 시작해보시겠습니까? (y/n): ")
    if response.lower() == 'y':
        try_start()
    
    print("\n진단 완료!")

if __name__ == "__main__":
    main()