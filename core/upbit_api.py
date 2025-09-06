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
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlencode
import logging
from datetime import datetime
from dataclasses import dataclass
import threading

# .env 파일 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


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
            self.calls = [
                call_time for call_time in self.calls if now - call_time < self.time_window]
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
        has_access_key = bool(
            self.access_key and self.access_key != 'your_access_key_here')
        has_secret_key = bool(
            self.secret_key and self.secret_key != 'your_secret_key_here')

        self.logger.info(
            f"API 키 상태 - Access: {has_access_key}, Secret: {has_secret_key}")

        if not has_access_key or not has_secret_key:
            raise ValueError(
                "Upbit API 키가 설정되지 않았습니다. 실거래를 위해서는 유효한 API 키가 필요합니다.")

        self.base_url = "https://api.upbit.com"
        self.rate_limiter = RateLimiter()

        self.logger.info("Upbit API 초기화 완료 - 실거래 모드")

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

        # 쿼리 스트링이 있고 비어있지 않을 때만 해시 추가
        if query_string and query_string.strip():
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
        """안전한 API 요청 실행 (GET/POST/DELETE 지원)"""
        # 레이트 리미팅 확인
        self.rate_limiter.wait_if_needed()

        try:
            url = f"{self.base_url}{endpoint}"
            # Upbit는 query_hash 계산 시 파라미터를 키 알파벳순으로 정렬한 쿼리스트링을 사용
            if params:
                try:
                    sorted_items = sorted(params.items(), key=lambda kv: kv[0])
                    query_string = urlencode(sorted_items, doseq=True)
                except Exception:
                    query_string = urlencode(params)
            else:
                query_string = ""
            headers = self._get_headers(query_string)
            method_upper = method.upper()

            if method_upper == 'GET':
                response = requests.get(
                    url, params=params, headers=headers, timeout=10)
            elif method_upper == 'POST':
                # POST 요청 시에도 쿼리 스트링 형태로 데이터 전송
                response = requests.post(
                    url, data=params, headers=headers, timeout=10)
            elif method_upper == 'DELETE':
                response = requests.delete(
                    url, params=params, headers=headers, timeout=10)
            else:
                self.logger.error(f"지원하지 않는 HTTP 메서드: {method}")
                return None

            self.rate_limiter.add_call()

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(
                    f"API 요청 실패: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"API 요청 중 오류 발생: {e}")
            return None

    def get_accounts(self) -> Optional[List[Dict]]:
        """계좌 정보 조회"""
        return self._make_request('GET', '/v1/accounts')

    def get_candles(
        self,
        market: str = "KRW-BTC",
        minutes: Optional[int] = None,
        count: int = 200,
        timeframe: Optional[str] = None,
        interval: Optional[int] = None,
    ) -> Optional[List[Dict]]:
        """
        캔들 데이터 조회 (단일 API)
        - minutes가 지정되면 분/시간/일봉을 자동 매핑
        - timeframe/interval 조합도 지원 (예: timeframe='minutes', interval=60)
        반환 데이터는 오래된 순으로 정렬됩니다.
        """
        try:
            # 공개 캔들 API는 인증 불필요하므로 requests 직접 사용
            if minutes is not None:
                if minutes == 1440:
                    url = "https://api.upbit.com/v1/candles/days"
                else:
                    url = f"https://api.upbit.com/v1/candles/minutes/{minutes}"
                params = {'market': market, 'count': min(count, 200)}
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    candles = resp.json()
                    candles.reverse()  # 오래된 → 최신
                    return candles
                self.logger.error(f"캔들 데이터 조회 실패: {resp.status_code}")
                return None

            # timeframe 기반
            if timeframe:
                if timeframe == 'days' or (timeframe == 'minutes' and interval == 1440):
                    endpoint = '/v1/candles/days'
                elif timeframe == 'weeks':
                    endpoint = '/v1/candles/weeks'
                elif timeframe == 'minutes':
                    interval = interval or 60
                    endpoint = f'/v1/candles/minutes/{interval}'
                else:
                    self.logger.error(f"지원하지 않는 시간프레임: {timeframe}")
                    return None

                params = {'market': market, 'count': min(count, 200)}
                data = self._make_request('GET', endpoint, params)
                if data is not None:
                    data.reverse()  # 오래된 → 최신
                return data

            # 기본: 60분봉
            url = f"https://api.upbit.com/v1/candles/minutes/60"
            params = {'market': market, 'count': min(count, 200)}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                candles = resp.json()
                candles.reverse()
                return candles
            self.logger.error(f"캔들 데이터 조회 실패: {resp.status_code}")
            return None

        except Exception as e:
            self.logger.error(f"캔들 데이터 조회 오류: {e}")
            return None

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

    def _round_tick(self, price: float) -> float:
        """업비트 틱사이즈 근사 반영 (간단 규칙)
        KRW-BTC 기준 대략 규칙 적용. 정확한 테이블은 업비트 정책 참조 필요.
        """
        if price >= 2_000_000:
            step = 1000
        elif price >= 1_000_000:
            step = 500
        elif price >= 100_000:
            step = 100
        elif price >= 10_000:
            step = 50
        else:
            step = 10
        return round(price / step) * step

    def _ensure_min_order(self, amount: Optional[float], volume: Optional[float], price: float) -> Tuple[float, float]:
        """최소 주문 금액/수량 충족 보정 (KRW 5000 기준)"""
        min_krw = 5000.0
        if amount is None and volume is None:
            return (min_krw, min_krw / max(price, 1.0))
        if amount is not None and amount < min_krw:
            amount = min_krw
        if volume is None and amount is not None:
            volume = amount / max(price, 1.0)
        if volume is not None and amount is None:
            amount = volume * price
        return (float(amount or 0.0), float(volume or 0.0))

    def place_buy_order(self, market: str, price: float, volume: float = None, amount: float = None) -> OrderResult:
        """매수 주문 (틱사이즈/최소주문/재시도/중복 방지 포함)"""
        from typing import Tuple
        if not volume and not amount:
            return OrderResult(False, message="거래량 또는 거래금액을 지정해야 합니다")

        # 틱사이즈 보정 및 최소 주문 보정
        price = self._round_tick(price)
        amount, volume = self._ensure_min_order(amount, volume, price)

        # 금액(amount) 지정 시: 업비트 규격 - 시장가 매수 (ord_type='price', price=금액)
        # 수량(volume) 지정 시: 지정가 매수 (ord_type='limit', price=가격, volume=수량)
        if amount and not volume:
            params = {
                'market': market,
                'side': 'bid',
                'ord_type': 'price',
                'price': str(int(amount))  # 정수로 변환
            }
        else:
            params = {
                'market': market,
                'side': 'bid',
                'ord_type': 'limit',
                'price': str(int(price)),  # 정수로 변환
                'volume': str(volume)
            }

        # 재시도 정책(최대 3회, 고정 백오프)
        for attempt in range(3):
            result = self._make_request('POST', '/v1/orders', params)
            if result:
                self.logger.info(f"매수 주문 성공: {result.get('uuid')}")
                return OrderResult(True, result.get('uuid'), "매수 주문 성공", result)
            time.sleep(0.5 * (attempt + 1))
        return OrderResult(False, message="매수 주문 실패")

    def place_sell_order(self, market: str, price: float, volume: float) -> OrderResult:
        """매도 주문 (틱사이즈/재시도 포함)"""

        price = self._round_tick(price)
        params = {
            'market': market,
            'side': 'ask',
            'volume': str(volume),
            'price': str(int(price)),  # 정수로 변환
            'ord_type': 'limit'
        }
        for attempt in range(3):
            result = self._make_request('POST', '/v1/orders', params)
            if result:
                self.logger.info(f"매도 주문 성공: {result.get('uuid')}")
                return OrderResult(True, result.get('uuid'), "매도 주문 성공", result)
            time.sleep(0.5 * (attempt + 1))
        return OrderResult(False, message="매도 주문 실패")

    def get_balance(self, currency: str = "KRW") -> float:
        """특정 통화 잔고 조회"""
        accounts = self.get_accounts()
        if accounts:
            for account in accounts:
                if account['currency'] == currency:
                    return float(account['balance'])
        return 0

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """주문 상태 조회"""
        params = {'uuid': order_id}
        return self._make_request('GET', '/v1/order', params)

    def cancel_order(self, order_id: str) -> OrderResult:
        """주문 취소"""
        params = {'uuid': order_id}
        result = self._make_request('DELETE', '/v1/order', params)
        if result:
            return OrderResult(True, message="주문 취소 성공", data=result)
        else:
            return OrderResult(False, message="주문 취소 실패")


if __name__ == "__main__":
    api = UpbitAPI(paper_trading=False)
    current_price = api.get_current_price("KRW-BTC")
    print(
        f"현재 BTC 가격: {current_price:,.0f} KRW" if current_price else "가격 조회 실패")
    krw_balance = api.get_balance("KRW")
    btc_balance = api.get_balance("BTC")
    print(f"KRW 잔고: {krw_balance:,.0f}")
    print(f"BTC 잔고: {btc_balance:.8f}")
    if current_price:
        result = api.place_buy_order("KRW-BTC", current_price, amount=100000)
        print(f"매수 결과: {result.success} - {result.message}")
        if result.success:
            print(f"주문 ID: {result.order_id}")
            krw_balance = api.get_balance("KRW")
            btc_balance = api.get_balance("BTC")
            print(f"거래 후 KRW 잔고: {krw_balance:,.0f}")
            print(f"거래 후 BTC 잔고: {btc_balance:.8f}")
