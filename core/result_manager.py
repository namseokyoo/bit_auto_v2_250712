"""
거래 결과 파일 관리 시스템
자동 거래 봇과 대시보드 간의 데이터 공유를 파일을 통해 처리
"""

import json
import os
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional
import threading
import fcntl
import logging

class ResultFileManager:
    """결과 파일 관리자"""
    
    def __init__(self, base_dir: str = "data/results"):
        self.base_dir = base_dir
        self.kst = pytz.timezone('Asia/Seoul')
        self.logger = logging.getLogger('ResultFileManager')
        
        # 디렉토리 생성
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(f"{base_dir}/analysis", exist_ok=True)
        os.makedirs(f"{base_dir}/trades", exist_ok=True)
        os.makedirs(f"{base_dir}/status", exist_ok=True)
        
        # 파일 경로
        self.status_file = f"{base_dir}/status/current_status.json"
        self.analysis_file = f"{base_dir}/analysis/latest_analysis.json"
        self.lock_file = f"{base_dir}/trading.lock"
        
    def save_analysis_result(self, result: Dict) -> bool:
        """분석 결과 저장"""
        try:
            timestamp = datetime.now(self.kst)
            
            # 최신 분석 결과 저장
            analysis_data = {
                'timestamp': timestamp.isoformat(),
                'timestamp_kst': timestamp.strftime('%Y-%m-%d %H:%M:%S KST'),
                'result': result,
                'action': result.get('consolidated_signal', {}).get('action', 'hold'),
                'confidence': result.get('consolidated_signal', {}).get('confidence', 0),
                'reasoning': result.get('consolidated_signal', {}).get('reasoning', ''),
                'price': result.get('consolidated_signal', {}).get('price', 0)
            }
            
            # 최신 결과 저장
            with open(self.analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2, default=str)
            
            # 날짜별 파일에도 추가 저장
            date_str = timestamp.strftime('%Y%m%d')
            daily_file = f"{self.base_dir}/analysis/analysis_{date_str}.jsonl"
            
            with open(daily_file, 'a', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, default=str)
                f.write('\n')
            
            self.logger.info(f"분석 결과 저장 완료: {self.analysis_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"분석 결과 저장 오류: {e}")
            return False
    
    def save_trade_result(self, trade: Dict) -> bool:
        """거래 결과 저장"""
        try:
            timestamp = datetime.now(self.kst)
            
            # 거래 데이터 준비
            trade_data = {
                'timestamp': timestamp.isoformat(),
                'timestamp_kst': timestamp.strftime('%Y-%m-%d %H:%M:%S KST'),
                **trade
            }
            
            # 날짜별 파일에 저장
            date_str = timestamp.strftime('%Y%m%d')
            daily_file = f"{self.base_dir}/trades/trades_{date_str}.jsonl"
            
            with open(daily_file, 'a', encoding='utf-8') as f:
                json.dump(trade_data, f, ensure_ascii=False, default=str)
                f.write('\n')
            
            self.logger.info(f"거래 결과 저장 완료: {daily_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"거래 결과 저장 오류: {e}")
            return False
    
    def update_status(self, status: Dict) -> bool:
        """상태 업데이트"""
        try:
            timestamp = datetime.now(self.kst)
            
            status_data = {
                'timestamp': timestamp.isoformat(),
                'timestamp_kst': timestamp.strftime('%Y-%m-%d %H:%M:%S KST'),
                **status
            }
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2, default=str)
            
            return True
            
        except Exception as e:
            self.logger.error(f"상태 업데이트 오류: {e}")
            return False
    
    def get_latest_analysis(self) -> Optional[Dict]:
        """최신 분석 결과 조회"""
        try:
            if os.path.exists(self.analysis_file):
                with open(self.analysis_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"분석 결과 조회 오류: {e}")
            return None
    
    def get_analysis_history(self, days: int = 1) -> List[Dict]:
        """분석 이력 조회"""
        try:
            results = []
            end_date = datetime.now(self.kst)
            
            for i in range(days):
                date = end_date - timedelta(days=i)
                date_str = date.strftime('%Y%m%d')
                daily_file = f"{self.base_dir}/analysis/analysis_{date_str}.jsonl"
                
                if os.path.exists(daily_file):
                    with open(daily_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                results.append(json.loads(line))
            
            # 최신순 정렬
            results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return results
            
        except Exception as e:
            self.logger.error(f"분석 이력 조회 오류: {e}")
            return []
    
    def get_trade_history(self, days: int = 1) -> List[Dict]:
        """거래 이력 조회"""
        try:
            trades = []
            end_date = datetime.now(self.kst)
            
            for i in range(days):
                date = end_date - timedelta(days=i)
                date_str = date.strftime('%Y%m%d')
                daily_file = f"{self.base_dir}/trades/trades_{date_str}.jsonl"
                
                if os.path.exists(daily_file):
                    with open(daily_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                trades.append(json.loads(line))
            
            # 최신순 정렬
            trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return trades
            
        except Exception as e:
            self.logger.error(f"거래 이력 조회 오류: {e}")
            return []
    
    def get_current_status(self) -> Optional[Dict]:
        """현재 상태 조회"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"상태 조회 오류: {e}")
            return None
    
    def acquire_trading_lock(self, timeout: int = 5) -> bool:
        """거래 락 획득 (수동/자동 거래 충돌 방지)"""
        try:
            # 락 파일 생성
            self.lock_fd = open(self.lock_file, 'w')
            
            # Non-blocking 락 시도
            for _ in range(timeout):
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.lock_fd.write(f"{os.getpid()}\n")
                    self.lock_fd.flush()
                    return True
                except IOError:
                    import time
                    time.sleep(1)
            
            return False
            
        except Exception as e:
            self.logger.error(f"락 획득 오류: {e}")
            return False
    
    def release_trading_lock(self):
        """거래 락 해제"""
        try:
            if hasattr(self, 'lock_fd'):
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                if os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
                return True
        except Exception as e:
            self.logger.error(f"락 해제 오류: {e}")
        return False
    
    def is_trading_locked(self) -> bool:
        """거래 락 상태 확인"""
        try:
            if not os.path.exists(self.lock_file):
                return False
            
            # 락 파일이 존재하면 다른 프로세스가 거래 중
            with open(self.lock_file, 'r') as f:
                pid = f.read().strip()
                # PID가 실제로 실행 중인지 확인
                try:
                    os.kill(int(pid), 0)
                    return True  # 프로세스가 실행 중
                except (OSError, ValueError):
                    # 프로세스가 없으면 stale lock
                    os.remove(self.lock_file)
                    return False
                    
        except Exception:
            return False
    
    def cleanup_old_files(self, days_to_keep: int = 30):
        """오래된 파일 정리"""
        try:
            cutoff_date = datetime.now(self.kst) - timedelta(days=days_to_keep)
            
            for subdir in ['analysis', 'trades']:
                dir_path = f"{self.base_dir}/{subdir}"
                if not os.path.exists(dir_path):
                    continue
                
                for filename in os.listdir(dir_path):
                    if not filename.endswith('.jsonl'):
                        continue
                    
                    # 파일명에서 날짜 추출
                    try:
                        date_str = filename.split('_')[1].split('.')[0]
                        file_date = datetime.strptime(date_str, '%Y%m%d')
                        file_date = self.kst.localize(file_date)
                        
                        if file_date < cutoff_date:
                            file_path = os.path.join(dir_path, filename)
                            os.remove(file_path)
                            self.logger.info(f"오래된 파일 삭제: {file_path}")
                    except Exception:
                        continue
                        
        except Exception as e:
            self.logger.error(f"파일 정리 오류: {e}")

# 싱글톤 인스턴스
result_manager = ResultFileManager()