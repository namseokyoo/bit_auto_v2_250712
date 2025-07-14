"""
에러 로깅 시스템
거래 로그와 별도로 시스템 오류를 관리
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import traceback
import json

class ErrorLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # 에러 전용 로거 설정
        self.error_logger = self._setup_error_logger()
        
        # 거래 전용 로거 설정
        self.trade_logger = self._setup_trade_logger()
        
        # 시스템 전용 로거 설정
        self.system_logger = self._setup_system_logger()
    
    def _setup_error_logger(self) -> logging.Logger:
        """에러 전용 로거 설정"""
        logger = logging.getLogger('ErrorLogger')
        logger.setLevel(logging.ERROR)
        
        # 기존 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 파일 핸들러 (에러 전용)
        error_file = os.path.join(self.log_dir, 'errors.log')
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        
        # 포맷터 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
        )
        error_handler.setFormatter(formatter)
        
        logger.addHandler(error_handler)
        logger.propagate = False  # 중복 로깅 방지
        
        return logger
    
    def _setup_trade_logger(self) -> logging.Logger:
        """거래 전용 로거 설정"""
        logger = logging.getLogger('TradeLogger')
        logger.setLevel(logging.INFO)
        
        # 기존 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 파일 핸들러 (거래 전용)
        trade_file = os.path.join(self.log_dir, 'trades.log')
        trade_handler = logging.FileHandler(trade_file, encoding='utf-8')
        trade_handler.setLevel(logging.INFO)
        
        # 포맷터 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        trade_handler.setFormatter(formatter)
        
        logger.addHandler(trade_handler)
        logger.propagate = False
        
        return logger
    
    def _setup_system_logger(self) -> logging.Logger:
        """시스템 전용 로거 설정"""
        logger = logging.getLogger('SystemLogger')
        logger.setLevel(logging.INFO)
        
        # 기존 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 파일 핸들러 (시스템 전용)
        system_file = os.path.join(self.log_dir, 'system.log')
        system_handler = logging.FileHandler(system_file, encoding='utf-8')
        system_handler.setLevel(logging.INFO)
        
        # 포맷터 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(module)s] - %(message)s'
        )
        system_handler.setFormatter(formatter)
        
        logger.addHandler(system_handler)
        logger.propagate = False
        
        return logger
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None, 
                  module: str = "Unknown"):
        """에러 로깅"""
        try:
            error_info = {
                'timestamp': datetime.now().isoformat(),
                'module': module,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'traceback': traceback.format_exc(),
                'context': context or {}
            }
            
            # 에러 로그 파일에 기록
            self.error_logger.error(f"[{module}] {type(error).__name__}: {str(error)}")
            self.error_logger.error(f"Context: {json.dumps(context or {}, ensure_ascii=False)}")
            self.error_logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            # JSON 형태로도 별도 저장
            error_json_file = os.path.join(self.log_dir, 'errors.json')
            try:
                if os.path.exists(error_json_file):
                    with open(error_json_file, 'r', encoding='utf-8') as f:
                        errors = json.load(f)
                else:
                    errors = []
                
                errors.append(error_info)
                
                # 최대 1000개 에러만 보관
                if len(errors) > 1000:
                    errors = errors[-1000:]
                
                with open(error_json_file, 'w', encoding='utf-8') as f:
                    json.dump(errors, f, ensure_ascii=False, indent=2, default=str)
            except Exception as json_error:
                self.error_logger.error(f"JSON 에러 로그 저장 실패: {json_error}")
                
        except Exception as log_error:
            # 로깅 자체에서 오류 발생 시 최소한의 로깅
            print(f"에러 로깅 실패: {log_error}")
            print(f"원본 에러: {error}")
    
    def log_trade(self, action: str, symbol: str, amount: float, price: float, 
                  strategy: str = "", success: bool = True, message: str = ""):
        """거래 로깅"""
        try:
            trade_info = {
                'timestamp': datetime.now().isoformat(),
                'action': action,
                'symbol': symbol,
                'amount': amount,
                'price': price,
                'strategy': strategy,
                'success': success,
                'message': message
            }
            
            status = "SUCCESS" if success else "FAILED"
            log_message = f"[{status}] {action.upper()} {symbol} - Amount: {amount}, Price: {price:,.0f}, Strategy: {strategy}"
            if message:
                log_message += f" - {message}"
            
            self.trade_logger.info(log_message)
            
            # JSON 형태로도 별도 저장
            trade_json_file = os.path.join(self.log_dir, 'trades.json')
            try:
                if os.path.exists(trade_json_file):
                    with open(trade_json_file, 'r', encoding='utf-8') as f:
                        trades = json.load(f)
                else:
                    trades = []
                
                trades.append(trade_info)
                
                # 최대 5000개 거래만 보관
                if len(trades) > 5000:
                    trades = trades[-5000:]
                
                with open(trade_json_file, 'w', encoding='utf-8') as f:
                    json.dump(trades, f, ensure_ascii=False, indent=2, default=str)
            except Exception as json_error:
                self.trade_logger.error(f"JSON 거래 로그 저장 실패: {json_error}")
                
        except Exception as log_error:
            print(f"거래 로깅 실패: {log_error}")
    
    def log_system(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        """시스템 로깅"""
        try:
            log_message = f"[{module}] {message}"
            if data:
                log_message += f" - Data: {json.dumps(data, ensure_ascii=False)}"
            
            if level.upper() == 'ERROR':
                self.system_logger.error(log_message)
            elif level.upper() == 'WARNING':
                self.system_logger.warning(log_message)
            elif level.upper() == 'DEBUG':
                self.system_logger.debug(log_message)
            else:
                self.system_logger.info(log_message)
                
        except Exception as log_error:
            print(f"시스템 로깅 실패: {log_error}")
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 에러 조회"""
        try:
            error_json_file = os.path.join(self.log_dir, 'errors.json')
            if os.path.exists(error_json_file):
                with open(error_json_file, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
                return errors[-limit:] if len(errors) > limit else errors
            return []
        except Exception as e:
            print(f"에러 조회 실패: {e}")
            return []
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 거래 조회"""
        try:
            trade_json_file = os.path.join(self.log_dir, 'trades.json')
            if os.path.exists(trade_json_file):
                with open(trade_json_file, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
                return trades[-limit:] if len(trades) > limit else trades
            return []
        except Exception as e:
            print(f"거래 조회 실패: {e}")
            return []


# 전역 인스턴스
error_logger = ErrorLogger()

def log_error(error: Exception, context: Optional[Dict[str, Any]] = None, module: str = "Unknown"):
    """에러 로깅 헬퍼 함수"""
    error_logger.log_error(error, context, module)

def log_trade(action: str, symbol: str, amount: float, price: float, 
              strategy: str = "", success: bool = True, message: str = ""):
    """거래 로깅 헬퍼 함수"""
    error_logger.log_trade(action, symbol, amount, price, strategy, success, message)

def log_system(level: str, module: str, message: str, data: Optional[Dict] = None):
    """시스템 로깅 헬퍼 함수"""
    error_logger.log_system(level, module, message, data)


if __name__ == "__main__":
    # 테스트
    try:
        # 에러 로깅 테스트
        raise ValueError("테스트 에러입니다")
    except Exception as e:
        log_error(e, {'test_context': '에러 로깅 테스트'}, 'TestModule')
    
    # 거래 로깅 테스트
    log_trade('buy', 'KRW-BTC', 50000, 95000000, 'test_strategy', True, '테스트 거래')
    
    # 시스템 로깅 테스트
    log_system('INFO', 'TestModule', '시스템 로깅 테스트', {'version': '1.0'})
    
    print("로깅 테스트 완료")