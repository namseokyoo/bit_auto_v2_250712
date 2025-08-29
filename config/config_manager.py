"""
동적 설정 관리자
외부에서 설정 파일을 업데이트하면 실시간으로 반영되는 시스템
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file: str = "config/trading_config.json"):
        self.config_file = Path(config_file)
        self.config_data = {}
        self.last_modified = 0
        self.lock = threading.Lock()
        self.logger = self._setup_logger()
        self.callbacks = []
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        # 초기 설정 로드
        self.load_config()
        self.start_monitoring()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('ConfigManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def load_config(self) -> bool:
        """설정 파일 로드"""
        try:
            if not self.config_file.exists():
                self.logger.error(f"설정 파일을 찾을 수 없습니다: {self.config_file}")
                return False
            
            with self.lock:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                
                # 파일 수정 시간 업데이트
                self.last_modified = os.path.getmtime(self.config_file)
                
                # 설정 업데이트 시간 기록
                self.config_data['system']['last_updated'] = datetime.now().isoformat()
                
            self.logger.info("설정 파일 로드 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"설정 파일 로드 실패: {e}")
            return False

    def save_config(self) -> bool:
        """설정 파일 저장"""
        try:
            with self.lock:
                # 업데이트 시간 갱신
                self.config_data['system']['last_updated'] = datetime.now().isoformat()
                
                # 백업 생성
                backup_file = self.config_file.with_suffix('.backup.json')
                if self.config_file.exists():
                    self.config_file.rename(backup_file)
                
                # 새 설정 저장
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config_data, f, indent=2, ensure_ascii=False)
                
                # 파일 수정 시간 업데이트
                self.last_modified = os.path.getmtime(self.config_file)
                
            self.logger.info("설정 파일 저장 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"설정 파일 저장 실패: {e}")
            return False

    def get_config(self, key_path: str = None) -> Any:
        """설정값 조회 (점 표기법 지원: 'trading.max_trade_amount')"""
        with self.lock:
            if key_path is None:
                return self.config_data.copy()
            
            keys = key_path.split('.')
            value = self.config_data
            
            try:
                for key in keys:
                    value = value[key]
                return value
            except (KeyError, TypeError):
                self.logger.warning(f"설정 키를 찾을 수 없습니다: {key_path}")
                return None

    def set_config(self, key_path: str, value: Any) -> bool:
        """설정값 업데이트"""
        try:
            with self.lock:
                keys = key_path.split('.')
                config = self.config_data
                
                # 마지막 키를 제외하고 경로 탐색
                for key in keys[:-1]:
                    if key not in config:
                        config[key] = {}
                    config = config[key]
                
                # 값 설정
                old_value = config.get(keys[-1])
                config[keys[-1]] = value
                
                # 변경 로그
                self.logger.info(f"설정 변경: {key_path} = {old_value} -> {value}")
            
            # 파일 저장
            self.save_config()
            
            # 콜백 실행
            self._notify_callbacks(key_path, value, old_value)
            
            return True
            
        except Exception as e:
            self.logger.error(f"설정 업데이트 실패: {e}")
            return False

    def register_callback(self, callback_func):
        """설정 변경 시 실행할 콜백 함수 등록"""
        self.callbacks.append(callback_func)

    def _notify_callbacks(self, key_path: str, new_value: Any, old_value: Any):
        """설정 변경 콜백 실행"""
        for callback in self.callbacks:
            try:
                callback(key_path, new_value, old_value)
            except Exception as e:
                self.logger.error(f"콜백 실행 오류: {e}")

    def start_monitoring(self):
        """설정 파일 변경 모니터링 시작"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.stop_monitoring = False
            self.monitoring_thread = threading.Thread(
                target=self._monitor_config_file,
                daemon=True
            )
            self.monitoring_thread.start()
            self.logger.info("설정 파일 모니터링 시작")

    def stop_monitoring_thread(self):
        """설정 파일 모니터링 중지"""
        self.stop_monitoring = True
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
            self.logger.info("설정 파일 모니터링 중지")

    def _monitor_config_file(self):
        """설정 파일 변경 감지 및 자동 리로드"""
        while not self.stop_monitoring:
            try:
                if self.config_file.exists():
                    current_modified = os.path.getmtime(self.config_file)
                    
                    if current_modified > self.last_modified:
                        self.logger.info("설정 파일 변경 감지 - 리로드 중...")
                        old_config = self.config_data.copy()
                        
                        if self.load_config():
                            # 변경된 설정들에 대해 콜백 실행
                            self._compare_and_notify(old_config, self.config_data)
                        
                time.sleep(1)  # 1초마다 체크
                
            except Exception as e:
                self.logger.error(f"설정 파일 모니터링 오류: {e}")
                time.sleep(5)  # 오류 시 5초 대기

    def _compare_and_notify(self, old_config: Dict, new_config: Dict, prefix: str = ""):
        """설정 변경사항 비교 및 알림"""
        for key, new_value in new_config.items():
            key_path = f"{prefix}.{key}" if prefix else key
            old_value = old_config.get(key)
            
            if isinstance(new_value, dict) and isinstance(old_value, dict):
                # 중첩된 딕셔너리인 경우 재귀 호출
                self._compare_and_notify(old_value, new_value, key_path)
            elif old_value != new_value:
                # 값이 변경된 경우 콜백 실행
                self._notify_callbacks(key_path, new_value, old_value)

    # 편의 메서드들
    def is_trading_enabled(self) -> bool:
        return self.get_config('trading.auto_trade_enabled') or False

    def is_system_enabled(self) -> bool:
        return self.get_config('system.enabled') or False

    def get_trade_amount_limit(self) -> int:
        return self.get_config('trading.max_trade_amount') or 100000

    def get_emergency_stop_loss(self) -> int:
        return self.get_config('trading.emergency_stop_loss') or 100000

    def get_active_strategies(self) -> list:
        return self.get_config('strategies.active_strategies') or []

    # 추가 편의 메서드
    def get_all_config(self) -> Dict[str, Any]:
        return self.get_config() or {}

    def get_trading_config(self) -> Dict[str, Any]:
        return self.get_config('trading') or {}

    def get_monitoring_config(self) -> Dict[str, Any]:
        return self.get_config('monitoring') or {}

    def get_risk_management_config(self) -> Dict[str, Any]:
        return self.get_config('risk_management') or {}

    def get_system_config(self) -> Dict[str, Any]:
        return self.get_config('system') or {}

    def get_mode(self) -> Optional[str]:
        return self.get_config('system.mode')

    def set_mode(self, mode: str) -> bool:
        return self.set_config('system.mode', mode)

    def enable_trading(self):
        """거래 활성화"""
        self.set_config('trading.auto_trade_enabled', True)

    def disable_trading(self):
        """거래 비활성화"""
        self.set_config('trading.auto_trade_enabled', False)

    def enable_system(self):
        """시스템 활성화"""
        self.set_config('system.enabled', True)

    def disable_system(self):
        """시스템 비활성화"""
        self.set_config('system.enabled', False)

    def emergency_stop(self):
        """긴급 정지"""
        self.disable_trading()
        self.disable_system()
        self.logger.critical("긴급 정지 실행됨")

# 전역 설정 관리자 인스턴스
config_manager = ConfigManager()

# 사용 예시
if __name__ == "__main__":
    def on_config_change(key_path, new_value, old_value):
        print(f"설정 변경됨: {key_path} = {old_value} -> {new_value}")

    config_manager.register_callback(on_config_change)
    
    print("현재 거래 활성화 상태:", config_manager.is_trading_enabled())
    print("최대 거래 금액:", config_manager.get_trade_amount_limit())
    
    # 테스트 설정 변경
    config_manager.set_config('trading.max_trade_amount', 150000)
    
    # 프로그램 실행 중 대기 (실제 환경에서는 메인 프로그램이 실행됨)
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        config_manager.stop_monitoring_thread()
        print("프로그램 종료")