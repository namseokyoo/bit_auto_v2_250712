#!/usr/bin/env python3
"""
자동 백업 스크립트
매일 새벽 2시에 cron으로 실행
"""

import os
import shutil
import sqlite3
import json
from datetime import datetime, timedelta
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/bitcoin_auto_trading/logs/backup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def backup_database():
    """데이터베이스 백업"""
    try:
        source_db = '/opt/bitcoin_auto_trading/data/trading_data.db'
        backup_dir = '/opt/bitcoin_auto_trading/backups/db'
        os.makedirs(backup_dir, exist_ok=True)
        
        # 백업 파일명 (날짜 포함)
        backup_filename = f"trading_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # SQLite 백업 (안전한 방법)
        source_conn = sqlite3.connect(source_db)
        backup_conn = sqlite3.connect(backup_path)
        source_conn.backup(backup_conn)
        source_conn.close()
        backup_conn.close()
        
        logger.info(f"데이터베이스 백업 완료: {backup_path}")
        
        # 7일 이전 백업 파일 삭제
        cleanup_old_backups(backup_dir, days=7)
        
    except Exception as e:
        logger.error(f"데이터베이스 백업 실패: {e}")

def backup_logs():
    """로그 파일 백업"""
    try:
        source_dir = '/opt/bitcoin_auto_trading/logs'
        backup_dir = '/opt/bitcoin_auto_trading/backups/logs'
        os.makedirs(backup_dir, exist_ok=True)
        
        # 날짜별 백업 디렉토리
        date_dir = os.path.join(backup_dir, datetime.now().strftime('%Y%m%d'))
        os.makedirs(date_dir, exist_ok=True)
        
        # 로그 파일들 복사
        for filename in os.listdir(source_dir):
            if filename.endswith('.log'):
                source_path = os.path.join(source_dir, filename)
                backup_path = os.path.join(date_dir, filename)
                shutil.copy2(source_path, backup_path)
        
        logger.info(f"로그 백업 완료: {date_dir}")
        
        # 30일 이전 로그 백업 삭제
        cleanup_old_backups(backup_dir, days=30)
        
    except Exception as e:
        logger.error(f"로그 백업 실패: {e}")

def backup_config():
    """설정 파일 백업"""
    try:
        source_file = '/opt/bitcoin_auto_trading/config/trading_config.json'
        backup_dir = '/opt/bitcoin_auto_trading/backups/config'
        os.makedirs(backup_dir, exist_ok=True)
        
        # 백업 파일명
        backup_filename = f"trading_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        shutil.copy2(source_file, backup_path)
        
        logger.info(f"설정 파일 백업 완료: {backup_path}")
        
        # 30일 이전 설정 백업 삭제
        cleanup_old_backups(backup_dir, days=30)
        
    except Exception as e:
        logger.error(f"설정 파일 백업 실패: {e}")

def cleanup_old_backups(backup_dir, days):
    """오래된 백업 파일 삭제"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for filename in os.listdir(backup_dir):
            file_path = os.path.join(backup_dir, filename)
            
            # 파일 생성 시간 확인
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            
            if file_time < cutoff_date:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"오래된 백업 파일 삭제: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.info(f"오래된 백업 디렉토리 삭제: {file_path}")
        
    except Exception as e:
        logger.error(f"백업 정리 실패: {e}")

def create_backup_report():
    """백업 보고서 생성"""
    try:
        report = {
            'timestamp': datetime.now().isoformat(),
            'backup_status': {
                'database': True,
                'logs': True,
                'config': True
            },
            'backup_sizes': {},
            'errors': []
        }
        
        # 백업 크기 계산
        backup_dirs = [
            '/opt/bitcoin_auto_trading/backups/db',
            '/opt/bitcoin_auto_trading/backups/logs',
            '/opt/bitcoin_auto_trading/backups/config'
        ]
        
        for backup_dir in backup_dirs:
            if os.path.exists(backup_dir):
                total_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(backup_dir)
                    for filename in filenames
                )
                report['backup_sizes'][os.path.basename(backup_dir)] = total_size
        
        # 보고서 저장
        report_path = '/opt/bitcoin_auto_trading/backups/backup_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"백업 보고서 생성 완료: {report_path}")
        
    except Exception as e:
        logger.error(f"백업 보고서 생성 실패: {e}")

def main():
    """메인 백업 실행"""
    logger.info("=== 자동 백업 시작 ===")
    
    # 백업 디렉토리 생성
    os.makedirs('/opt/bitcoin_auto_trading/backups', exist_ok=True)
    
    # 각종 백업 실행
    backup_database()
    backup_logs()
    backup_config()
    
    # 백업 보고서 생성
    create_backup_report()
    
    logger.info("=== 자동 백업 완료 ===")

if __name__ == '__main__':
    main()