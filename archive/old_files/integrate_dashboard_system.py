#!/usr/bin/env python3
"""대시보드와 Enhanced Trading System 통합을 위한 실행 스크립트"""

import subprocess
import sys
import os
import time

def run_integration():
    """대시보드 통합 실행"""
    
    print("="*60)
    print("🚀 대시보드 통합 시스템 시작")
    print("="*60)
    print("")
    
    # SSH 키 경로
    SSH_KEY = "/Users/namseokyoo/project/bit_auto_v2_250712/ssh-key-2025-07-14.key"
    SERVER = "ubuntu@158.180.82.112"
    
    commands = [
        # 1. Enhanced Trading System을 백그라운드로 실행
        {
            'name': 'Enhanced Trading System 시작',
            'cmd': f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {SSH_KEY} {SERVER} "cd /home/ubuntu/bit_auto_v2 && source venv/bin/activate && nohup python enhanced_trading_system.py --dry-run > logs/enhanced_trading.log 2>&1 & echo $!"',
            'description': '하루 2% 수익 목표 트레이딩 시스템'
        },
        
        # 2. 대시보드 재시작
        {
            'name': '대시보드 재시작',
            'cmd': f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {SSH_KEY} {SERVER} "cd /home/ubuntu/bit_auto_v2 && pkill -f dashboard.py; sleep 2; source venv/bin/activate && nohup python dashboard.py > logs/dashboard.log 2>&1 & echo $!"',
            'description': '실시간 모니터링 대시보드'
        },
        
        # 3. 시스템 상태 확인
        {
            'name': '시스템 상태 확인',
            'cmd': f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {SSH_KEY} {SERVER} "ps aux | grep -E \'(enhanced_trading|dashboard)\' | grep -v grep"',
            'description': '실행 중인 프로세스 확인'
        },
        
        # 4. Redis 상태 확인
        {
            'name': 'Redis 상태 확인',  
            'cmd': f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {SSH_KEY} {SERVER} "redis-cli ping"',
            'description': 'Redis 서버 연결 확인'
        }
    ]
    
    pids = {}
    
    for command in commands:
        print(f"\n📌 {command['name']}")
        print(f"   {command['description']}")
        print("-"*40)
        
        try:
            result = subprocess.run(command['cmd'], shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                print(f"✅ 성공: {output}")
                
                if 'echo $!' in command['cmd']:
                    pids[command['name']] = output
                    
            else:
                print(f"❌ 실패: {result.stderr}")
                
        except Exception as e:
            print(f"❌ 오류: {e}")
        
        time.sleep(2)
    
    print("\n" + "="*60)
    print("📊 통합 시스템 상태")
    print("="*60)
    
    if pids:
        print("\n실행 중인 프로세스:")
        for name, pid in pids.items():
            print(f"  • {name}: PID {pid}")
    
    print("\n🌐 대시보드 접속 정보:")
    print("  URL: http://158.180.82.112:8080")
    print("")
    print("✅ 다음 기능들이 활성화되었습니다:")
    print("  • 실시간 계좌 잔고 표시")
    print("  • 거래 전략 및 기준 표시")
    print("  • 목표 달성률 모니터링")
    print("  • 실시간 거래 통계")
    print("")
    print("📌 주의사항:")
    print("  • 현재 DRY-RUN 모드로 실행 중 (가상 거래)")
    print("  • 실제 거래를 원하면 --dry-run 플래그를 제거하세요")
    print("")
    print("로그 확인:")
    print("  • 트레이딩: tail -f /home/ubuntu/bit_auto_v2/logs/enhanced_trading.log")
    print("  • 대시보드: tail -f /home/ubuntu/bit_auto_v2/logs/dashboard.log")

if __name__ == "__main__":
    run_integration()