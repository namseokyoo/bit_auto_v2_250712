#!/usr/bin/env python3
"""
모든 거래 프로세스 시작 스크립트
"""

import subprocess
import time
import os
import sys
import psutil
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_process_running(script_name):
    """프로세스가 실행 중인지 확인"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if script_name in cmdline:
                return True, proc.info['pid']
        except:
            pass
    return False, None

def start_process(script_name, display_name, dry_run=False):
    """프로세스 시작"""
    running, pid = check_process_running(script_name)
    
    if running:
        logger.info(f"✅ {display_name} 이미 실행중 (PID: {pid})")
        return pid
    
    try:
        # 스크립트 파일 존재 확인
        if not os.path.exists(script_name):
            logger.warning(f"⚠️ {script_name} 파일이 없습니다")
            return None
        
        # 프로세스 시작
        cmd = [sys.executable, script_name]
        if dry_run and 'trading' in script_name:
            cmd.append('--dry-run')
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # 잠시 대기 후 상태 확인
        time.sleep(2)
        
        if process.poll() is None:
            logger.info(f"✅ {display_name} 시작됨 (PID: {process.pid})")
            return process.pid
        else:
            stderr = process.stderr.read().decode() if process.stderr else ""
            logger.error(f"❌ {display_name} 시작 실패: {stderr}")
            return None
            
    except Exception as e:
        logger.error(f"❌ {display_name} 시작 오류: {e}")
        return None

def main():
    """메인 함수"""
    print("=" * 60)
    print("🚀 Quantum Trading System - 프로세스 시작")
    print("=" * 60)
    
    # 드라이런 모드 확인
    dry_run = '--dry-run' in sys.argv or '--test' in sys.argv
    if dry_run:
        print("⚠️ DRY-RUN 모드로 실행 (실제 거래 없음)")
    else:
        print("💰 LIVE 모드로 실행 (실제 거래 진행)")
        response = input("계속하시겠습니까? (y/n): ")
        if response.lower() != 'y':
            print("중단됨")
            return
    
    print("\n프로세스 시작중...")
    print("-" * 40)
    
    # 프로세스 목록
    processes = [
        # ('integrated_trading_system.py', 'Integrated System'),
        ('quantum_trading.py', 'Quantum Trading'),
        # ('multi_coin_trading.py', 'Multi-Coin Trading'),
        # ('feedback_scheduler.py', 'AI Feedback'),
        ('dashboard.py', 'Dashboard')
    ]
    
    started = []
    failed = []
    
    for script, name in processes:
        pid = start_process(script, name, dry_run)
        if pid:
            started.append((name, pid))
        else:
            failed.append(name)
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print("📊 프로세스 시작 결과")
    print("=" * 60)
    
    if started:
        print("\n✅ 성공적으로 시작된 프로세스:")
        for name, pid in started:
            print(f"   - {name} (PID: {pid})")
    
    if failed:
        print("\n❌ 시작 실패한 프로세스:")
        for name in failed:
            print(f"   - {name}")
    
    print("\n💡 팁:")
    print("   - 프로세스 상태 확인: ps aux | grep trading")
    print("   - 대시보드 접속: http://localhost:5000")
    print("   - 모든 프로세스 중지: python3 stop_all_processes.py")
    print("=" * 60)

if __name__ == "__main__":
    main()