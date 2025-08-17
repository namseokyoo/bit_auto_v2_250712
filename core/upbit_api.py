"""
Upbit API 래퍼 클래스
안전한 거래 실행과 에러 처리, 레이트 리미팅 포함
"""

import os
import jwt
import uuid
import hashlib
import requests
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, unquote
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading

@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    message: str = ""
    data: Optional[Dict] = None

@dataclass
class MarketData:
    market: str
    price: float
    volume: float
    timestamp: datetime
    high: float = 0
    low: float = 0
    open: float = 0
    prev_close: float = 0

class RateLimiter:
    def __init__(self, max_calls: int = 600, time_window: int = 600):  # 10분에 600회
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self.lock = threading.Lock()

    def can_call(self) -> bool:
        with self.lock:
            now = time.time()
            # 시간 창 밖의 호출 기록 제거
            self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
            return len(self.calls) < self.max_calls

    def add_call(self):
        with self.lock:
            self.calls.append(time.time())

    def wait_if_needed(self):
        if not self.can_call():
            wait_time = self.time_window - (time.time() - self.calls[0])
            if wait_time > 0:
                time.sleep(wait_time + 1)

class UpbitAPI:
    def __init__(self, access_key: str = None, secret_key: str = None, paper_trading: bool = False):
        # 로거 먼저 설정
        self.logger = self._setup_logger()
        
        # 환경 변수에서 키 로드 (우선순위)
        self.access_key = access_key or os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = secret_key or os.getenv('UPBIT_SECRET_KEY')
        
        # 키 존재 여부 로깅 (보안상 키 값은 로깅하지 않음)
        has_access_key = bool(self.access_key and self.access_key != 'your_access_key_here')
        has_secret_key = bool(self.secret_key and self.secret_key != 'your_secret_key_here')
        
        self.logger.info(f"API 키 상태 - Access: {has_access_key}, Secret: {has_secret_key}")
        
        if not has_access_key or not has_secret_key:
            if paper_trading:
                self.logger.warning("API 키가 없거나 기본값이어서 모의투자 모드로 전환됩니다.")
                self.paper_trading = True
            else:
                self.logger.error("Upbit API 키가 설정되지 않았습니다.")
                # 실거래 모드에서도 일단 paper_trading으로 설정하여 에러 방지
                self.paper_trading = True
                self.logger.warning("API 키 없음 - 임시로 모의투자 모드로 설정")
        else:
            self.paper_trading = paper_trading
        
        self.base_url = "https://api.upbit.com"
        self.rate_limiter = RateLimiter()
        
        # Paper trading용 가상 잔고
        self.paper_balance = {
            'KRW': 1000000,  # 초기 원화 100만원
            'BTC': 0
        }
        self.paper_orders = []
        
        self.logger.info(f"Upbit API 초기화 완료 - {'모의투자' if self.paper_trading else '실거래'} 모드")

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('UpbitAPI')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _get_headers(self, query_string: str = None) -> Dict[str, str]:
        """JWT 토큰이 포함된 헤더 생성"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        if query_string:
            m = hashlib.sha512()
            m.update(query_string.encode())
            query_hash = m.hexdigest()
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'
        
        jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        
        return {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """안전한 API 요청 실행"""
        # 레이트 리미팅 확인
        self.rate_limiter.wait_if_needed()
        
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method.upper() == 'GET':
                query_string = urlencode(params) if params else ""
                headers = self._get_headers(query_string)
                response = requests.get(url, params=params, headers=headers, timeout=10)
            else:
                query_string = urlencode(params) if params else ""
                headers = self._get_headers(query_string)
                response = requests.post(url, json=params, headers=headers, timeout=10)
            
            self.rate_limiter.add_call()
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"API 요청 실패: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"API 요청 중 오류 발생: {e}")
            return None

    def get_accounts(self) -> Optional[List[Dict]]:
        """계좌 정보 조회"""
        if self.paper_trading:
            return [
                {'currency': 'KRW', 'balance': str(self.paper_balance['KRW']), 'locked': '0', 'avg_buy_price': '0'},
                {'currency': 'BTC', 'balance': str(self.paper_balance['BTC']), 'locked': '0', 'avg_buy_price': '0'}
            ]
        
        return self._make_request('GET', '/v1/accounts')
    
    def get_candles(self, market: str = "KRW-BTC", minutes: int = 60, count: int = 100) -> Optional[List[Dict]]:
        """캔들 데이터 조회
        
        Args:
            market: 마켓 코드 (예: KRW-BTC)
            minutes: 분 단위 (1, 3, 5, 15, 10, 30, 60, 240)
            count: 캔들 개수 (최대 200)
        """
        if self.paper_trading:
            # 모의투자 모드에서도 실제 캔들 데이터는 가져와야 함
            pass
        
        try:
            # 레이트 리미팅 없이 공개 API 호출
            if minutes == 1440:  # 일봉
                url = f"https://api.upbit.com/v1/candles/days"
            elif minutes >= 60:  # 시간봉
                url = f"https://api.upbit.com/v1/candles/minutes/{minutes}"
            else:  # 분봉
                url = f"https://api.upbit.com/v1/candles/minutes/{minutes}"
            
            params = {
                'market': market,
                'count': min(count, 200)  # 최대 200개
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                candles = response.json()
                # 시간 역순으로 정렬 (오래된 것부터)
                candles.reverse()
                return candles
            else:
                self.logger.error(f"캔들 데이터 조회 실패: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"캔들 데이터 조회 오류: {e}")
            return None
    
    def get_balance(self, currency: str = 'KRW') -> float:
        """특정 화폐의 잔고 조회"""
        try:
            accounts = self.get_accounts()
            if not accounts:
                self.logger.warning(f"{currency} 잔고 조회 실패 - 계좌 정보 없음")
                return 0.0
            
            for account in accounts:
                if account.get('currency') == currency:
                    balance = float(account.get('balance', 0))
                    locked = float(account.get('locked', 0))
                    total = balance + locked
                    self.logger.info(f"{currency} 잔고: {total:,.2f} (가용: {balance:,.2f}, 잠김: {locked:,.2f})")
                    return total
            
            self.logger.info(f"{currency} 잔고 없음")
            return 0.0
        except Exception as e:
            self.logger.error(f"{currency} 잔고 조회 중 오류: {e}")
            return 0.0

    def get_current_price(self, market: str = "KRW-BTC") -> Optional[float]:
        """현재가 조회"""
        result = self._make_request('GET', '/v1/ticker', {'markets': market})
        if result and len(result) > 0:
            return float(result[0]['trade_price'])
        return None

    def get_market_data(self, market: str = "KRW-BTC") -> Optional[MarketData]:
        """시장 데이터 조회"""
        result = self._make_request('GET', '/v1/ticker', {'markets': market})
        if result and len(result) > 0:
            data = result[0]
            return MarketData(
                market=market,
                price=float(data['trade_price']),
                volume=float(data['acc_trade_volume_24h']),
                timestamp=datetime.now(),
                high=float(data['high_price']),
                low=float(data['low_price']),
                open=float(data['opening_price']),
                prev_close=float(data['prev_closing_price'])
            )
        return None

    def get_candles(self, market: str = "KRW-BTC", timeframe: str = "minutes", 
                   interval: int = 60, count: int = 200) -> Optional[List[Dict]]:
        """캔들 데이터 조회"""
        endpoint_map = {
            'minutes': f'/v1/candles/minutes/{interval}',
            'hours': '/v1/candles/minutes/240',  # 4시간
            'days': '/v1/candles/days',
            'weeks': '/v1/candles/weeks'
        }
        
        endpoint = endpoint_map.get(timeframe)
        if not endpoint:
            self.logger.error(f"지원하지 않는 시간프레임: {timeframe}")
            return None
        
        params = {
            'market': market,
            'count': min(count, 200)  # API 제한
        }
        
        return self._make_request('GET', endpoint, params)

    def place_buy_order(self, market: str, price: float, volume: float = None, 
                       amount: float = None) -> OrderResult:
        """매수 주문"""
        if not volume and not amount:
            return OrderResult(False, message="거래량 또는 거래금액을 지정해야 합니다")

        if self.paper_trading:
            return self._paper_buy_order(market, price, volume, amount)

        # 실거래 주문
        params = {
            'market': market,
            'side': 'bid',
            'ord_type': 'limit',
            'price': str(price)
        }
        
        if volume:
            params['volume'] = str(volume)
        else:
            params['price'] = str(amount)  # 시장가 매수의 경우

        result = self._make_request('POST', '/v1/orders', params)
        
        if result:
            self.logger.info(f"매수 주문 성공: {result.get('uuid')}")
            return OrderResult(True, result.get('uuid'), "매수 주문 성공", result)
        else:
            return OrderResult(False, message="매수 주문 실패")

    def place_sell_order(self, market: str, price: float, volume: float) -> OrderResult:
        """매도 주문"""
        if self.paper_trading:
            return self._paper_sell_order(market, price, volume)

        params = {
            'market': market,
            'side': 'ask',
            'volume': str(volume),
            'price': str(price),
            'ord_type': 'limit'
        }

        result = self._make_request('POST', '/v1/orders', params)
        
        if result:
            self.logger.info(f"매도 주문 성공: {result.get('uuid')}")
            return OrderResult(True, result.get('uuid'), "매도 주문 성공", result)
        else:
            return OrderResult(False, message="매도 주문 실패")

    def _paper_buy_order(self, market: str, price: float, volume: float = None, 
                        amount: float = None) -> OrderResult:
        """모의 매수 주문"""
        if amount:
            # 금액 기준 매수
            if self.paper_balance['KRW'] < amount:
                return OrderResult(False, message="잔고 부족")
            
            volume = amount / price
            self.paper_balance['KRW'] -= amount
            self.paper_balance['BTC'] += volume * 0.9995  # 수수료 0.05% 차감
            
        else:
            # 수량 기준 매수
            total_amount = price * volume
            if self.paper_balance['KRW'] < total_amount:
                return OrderResult(False, message="잔고 부족")
            
            self.paper_balance['KRW'] -= total_amount
            self.paper_balance['BTC'] += volume * 0.9995  # 수수료 차감

        order_id = str(uuid.uuid4())
        order_data = {
            'uuid': order_id,
            'market': market,
            'side': 'bid',
            'volume': str(volume),
            'price': str(price),
            'timestamp': datetime.now().isoformat()
        }
        
        self.paper_orders.append(order_data)
        self.logger.info(f"모의 매수 완료: {volume:.8f} BTC @ {price:,.0f} KRW")
        
        return OrderResult(True, order_id, "모의 매수 성공", order_data)

    def _paper_sell_order(self, market: str, price: float, volume: float) -> OrderResult:
        """모의 매도 주문"""
        if self.paper_balance['BTC'] < volume:
            return OrderResult(False, message="BTC 잔고 부족")

        total_amount = price * volume * 0.9995  # 수수료 차감
        self.paper_balance['BTC'] -= volume
        self.paper_balance['KRW'] += total_amount

        order_id = str(uuid.uuid4())
        order_data = {
            'uuid': order_id,
            'market': market,
            'side': 'ask',
            'volume': str(volume),
            'price': str(price),
            'timestamp': datetime.now().isoformat()
        }
        
        self.paper_orders.append(order_data)
        self.logger.info(f"모의 매도 완료: {volume:.8f} BTC @ {price:,.0f} KRW")
        
        return OrderResult(True, order_id, "모의 매도 성공", order_data)

    def get_balance(self, currency: str = "KRW") -> float:
        """특정 통화 잔고 조회"""
        if self.paper_trading:
            return self.paper_balance.get(currency, 0)

        accounts = self.get_accounts()
        if accounts:
            for account in accounts:
                if account['currency'] == currency:
                    return float(account['balance'])
        return 0

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """주문 상태 조회"""
        if self.paper_trading:
            for order in self.paper_orders:
                if order['uuid'] == order_id:
                    order['state'] = 'done'  # 모의거래는 즉시 체결
                    return order
            return None

        params = {'uuid': order_id}
        return self._make_request('GET', '/v1/order', params)

    def cancel_order(self, order_id: str) -> OrderResult:
        """주문 취소"""
        if self.paper_trading:
            return OrderResult(True, message="모의거래에서는 주문 취소가 즉시 처리됩니다")

        params = {'uuid': order_id}
        result = self._make_request('DELETE', '/v1/order', params)
        
        if result:
            return OrderResult(True, message="주문 취소 성공", data=result)
        else:
            return OrderResult(False, message="주문 취소 실패")

# 사용 예시
if __name__ == "__main__":
    # 환경변수에서 API 키 로드
    api = UpbitAPI(paper_trading=True)
    
    # 현재가 조회
    current_price = api.get_current_price("KRW-BTC")
    print(f"현재 BTC 가격: {current_price:,.0f} KRW")
    
    # 잔고 조회
    krw_balance = api.get_balance("KRW")
    btc_balance = api.get_balance("BTC")
    print(f"KRW 잔고: {krw_balance:,.0f}")
    print(f"BTC 잔고: {btc_balance:.8f}")
    
    # 테스트 매수 주문
    if current_price:
        result = api.place_buy_order("KRW-BTC", current_price, amount=100000)
        print(f"매수 결과: {result.success} - {result.message}")
        
        if result.success:
            print(f"주문 ID: {result.order_id}")
            
            # 잔고 재확인
            krw_balance = api.get_balance("KRW")
            btc_balance = api.get_balance("BTC")
            print(f"거래 후 KRW 잔고: {krw_balance:,.0f}")
            print(f"거래 후 BTC 잔고: {btc_balance:.8f}")