"""
AI 어드바이저 - 시장 분석 및 거래 조언
DeepSeek AI를 활용한 지능형 거래 지원 시스템
"""

import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json

from .deepseek_client import deepseek_client
from .upbit_api import UpbitAPI
from .strategy_execution_tracker import execution_tracker

# KST 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def now_kst():
    """KST 시간으로 현재 시간 반환"""
    return datetime.now(KST)


@dataclass
class AIAnalysis:
    """AI 분석 결과"""
    analysis_type: str  # 'market' 또는 'trading'
    content: str
    confidence: float
    timestamp: datetime
    market_data: Dict[str, Any] = None
    recommendations: List[str] = None
    risk_level: str = "medium"  # low, medium, high
    is_mock: bool = False  # 모의응답 여부


class AIAdvisor:
    """AI 거래 어드바이저"""

    def __init__(self):
        self.logger = logging.getLogger('AIAdvisor')
        self.upbit_api = UpbitAPI()
        self.analysis_cache = {}
        self.cache_duration = 300  # 5분 캐시

    def get_current_market_data(self) -> Dict[str, Any]:
        """현재 시장 데이터 수집"""
        try:
            # Upbit API에서 직접 ticker 데이터 가져오기
            result = self.upbit_api._make_request(
                'GET', '/v1/ticker', {'markets': 'KRW-BTC'})
            if not result or len(result) == 0:
                return {}

            ticker_data = result[0]

            # 캔들 데이터 (기술적 지표 계산용)
            candles = self.upbit_api.get_candles(
                'KRW-BTC', minutes=60, count=50)
            if not candles:
                return {}

            # 기본 시장 데이터
            market_info = {
                'symbol': 'BTC/KRW',
                'price': float(ticker_data['trade_price']),
                'change_24h': float(ticker_data['signed_change_rate']) * 100,
                'volume': float(ticker_data['acc_trade_volume_24h']),
                'high_24h': float(ticker_data['high_price']),
                'low_24h': float(ticker_data['low_price']),
                'timestamp': now_kst().isoformat()
            }

            # 기술적 지표 계산
            if len(candles) >= 20:
                prices = [float(candle['trade_price']) for candle in candles]
                volumes = [float(candle['candle_acc_trade_volume'])
                           for candle in candles]

                # 단순 이동평균
                ma_5 = sum(prices[:5]) / 5
                ma_20 = sum(prices[:20]) / 20

                # RSI 간단 계산 (14일)
                if len(prices) >= 14:
                    gains = []
                    losses = []
                    for i in range(1, 15):
                        change = prices[i-1] - prices[i]
                        if change > 0:
                            gains.append(change)
                            losses.append(0)
                        else:
                            gains.append(0)
                            losses.append(abs(change))

                    avg_gain = sum(gains) / 14
                    avg_loss = sum(losses) / 14

                    if avg_loss != 0:
                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                    else:
                        rsi = 100
                else:
                    rsi = 50

                # 볼린저 밴드 위치
                if len(prices) >= 20:
                    sma_20 = sum(prices[:20]) / 20
                    variance = sum(
                        [(p - sma_20) ** 2 for p in prices[:20]]) / 20
                    std_dev = variance ** 0.5

                    upper_band = sma_20 + (2 * std_dev)
                    lower_band = sma_20 - (2 * std_dev)
                    current_price = prices[0]

                    if current_price > upper_band:
                        bb_position = "상단 돌파"
                    elif current_price < lower_band:
                        bb_position = "하단 돌파"
                    elif current_price > sma_20:
                        bb_position = "중심선 상단"
                    else:
                        bb_position = "중심선 하단"
                else:
                    bb_position = "계산 불가"

                # 트렌드 분석
                if ma_5 > ma_20:
                    ma_trend = "상승 추세"
                elif ma_5 < ma_20:
                    ma_trend = "하락 추세"
                else:
                    ma_trend = "횡보"

                market_info.update({
                    'rsi': round(rsi, 2),
                    'ma_5': round(ma_5, 2),
                    'ma_20': round(ma_20, 2),
                    'ma_trend': ma_trend,
                    'bb_position': bb_position,
                    'avg_volume': sum(volumes[:10]) / 10 if len(volumes) >= 10 else volumes[0] if volumes else 0
                })

            return market_info

        except Exception as e:
            self.logger.error(f"시장 데이터 수집 오류: {e}")
            return {}

    def analyze_market(self, force_refresh: bool = False) -> AIAnalysis:
        """시장 분석 수행"""
        cache_key = 'market_analysis'

        # 캐시 확인
        if not force_refresh and cache_key in self.analysis_cache:
            cached_analysis, cached_time = self.analysis_cache[cache_key]
            if (now_kst() - cached_time).total_seconds() < self.cache_duration:
                return cached_analysis

        try:
            # 시장 데이터 수집
            market_data = self.get_current_market_data()
            if not market_data:
                return AIAnalysis(
                    analysis_type='market',
                    content='시장 데이터를 가져올 수 없습니다.',
                    confidence=0.0,
                    timestamp=now_kst(),
                    risk_level='high'
                )

            # AI 분석 요청 (실제 시장 데이터 포함)
            ai_response = deepseek_client.chat_completion([
                {"role": "system", "content": "당신은 전문 암호화폐 거래 분석가입니다."},
                {"role": "user", "content": f"""
다음 실시간 BTC 시장 데이터를 분석해주세요:

현재가: ₩{market_data.get('price', 0):,.0f} (약 ${market_data.get('price', 0)/1400:,.0f})
24시간 변화율: {market_data.get('change_24h', 0):+.2f}%
RSI (14): {market_data.get('rsi', 50):.1f}
이동평균 추세: {market_data.get('ma_trend', '알 수 없음')}
볼린저 밴드 위치: {market_data.get('bb_position', '알 수 없음')}
거래량: {market_data.get('volume', 0):.2f} BTC

현재 시장 상황을 분석하고 향후 4-6시간 내 가격 움직임을 예측해주세요.
구체적인 지지/저항선과 거래 권장사항을 포함해주세요.
                """}
            ])
            
            analysis_content = ai_response['choices'][0]['message']['content']
            is_mock_response = ai_response.get('is_mock', False)

            # 신뢰도 계산 (간단한 휴리스틱)
            confidence = 0.8
            if market_data.get('rsi', 50) > 70 or market_data.get('rsi', 50) < 30:
                confidence += 0.1  # 극단적 RSI는 신뢰도 증가
            if abs(market_data.get('change_24h', 0)) > 5:
                confidence -= 0.1  # 급격한 변화는 신뢰도 감소
                
            confidence = max(0.1, min(0.95, confidence))
            
            # 리스크 레벨 계산
            risk_level = "medium"
            if market_data.get('rsi', 50) > 80 or market_data.get('rsi', 50) < 20:
                risk_level = "high"
            elif 40 <= market_data.get('rsi', 50) <= 60:
                risk_level = "low"
                
            analysis = AIAnalysis(
                analysis_type='market',
                content=analysis_content,
                confidence=confidence,
                timestamp=now_kst(),
                market_data=market_data,
                risk_level=risk_level,
                is_mock=is_mock_response
            )

            # 캐시 저장
            self.analysis_cache[cache_key] = (analysis, now_kst())

            return analysis

        except Exception as e:
            self.logger.error(f"시장 분석 오류: {e}")
            return AIAnalysis(
                analysis_type='market',
                content=f'분석 중 오류가 발생했습니다: {str(e)}',
                confidence=0.0,
                timestamp=now_kst(),
                risk_level='high'
            )

    def get_trading_advice(self, force_refresh: bool = False) -> AIAnalysis:
        """거래 조언 생성"""
        cache_key = 'trading_advice'

        # 캐시 확인
        if not force_refresh and cache_key in self.analysis_cache:
            cached_analysis, cached_time = self.analysis_cache[cache_key]
            if (now_kst() - cached_time).total_seconds() < self.cache_duration:
                return cached_analysis

        try:
            # 전략 성과 데이터 수집
            strategy_summary = execution_tracker.get_strategy_summary(days=7)
            recent_executions = execution_tracker.get_execution_history(
                hours=24, limit=10)

            if not strategy_summary or 'overall' not in strategy_summary:
                return AIAnalysis(
                    analysis_type='trading',
                    content='전략 성과 데이터가 부족합니다.',
                    confidence=0.0,
                    timestamp=now_kst(),
                    risk_level='medium'
                )

            # AI 조언 요청
            ai_response = deepseek_client.get_trading_advice(
                strategy_summary['overall'], 
                recent_executions
            )
            
            if isinstance(ai_response, str):
                advice_content = ai_response
                is_mock_response = False
            else:
                advice_content = ai_response.get('choices', [{}])[0].get('message', {}).get('content', '조언을 생성할 수 없습니다.')
                is_mock_response = ai_response.get('is_mock', False)

            # 성과 기반 신뢰도 계산
            overall = strategy_summary['overall']
            execution_rate = overall.get('avg_execution_rate', 0)
            profit_rate = overall.get('avg_profit_rate', 0)

            confidence = 0.7
            if execution_rate > 0.6:
                confidence += 0.1
            if profit_rate > 0.3:
                confidence += 0.1
            if overall.get('total_executions', 0) > 50:
                confidence += 0.1

            confidence = max(0.1, min(0.95, confidence))

            # 권장사항 추출 (간단한 파싱)
            recommendations = []
            if '매수' in advice_content:
                recommendations.append('매수 기회 검토')
            if '매도' in advice_content:
                recommendations.append('매도 타이밍 고려')
            if '손절' in advice_content:
                recommendations.append('손절 기준 점검')
            if '포지션' in advice_content:
                recommendations.append('포지션 크기 조정')

            analysis = AIAnalysis(
                analysis_type='trading',
                content=advice_content,
                confidence=confidence,
                timestamp=now_kst(),
                recommendations=recommendations,
                risk_level='medium',
                is_mock=is_mock_response
            )

            # 캐시 저장
            self.analysis_cache[cache_key] = (analysis, now_kst())

            return analysis

        except Exception as e:
            self.logger.error(f"거래 조언 생성 오류: {e}")
            return AIAnalysis(
                analysis_type='trading',
                content=f'조언 생성 중 오류가 발생했습니다: {str(e)}',
                confidence=0.0,
                timestamp=now_kst(),
                risk_level='high'
            )

    def get_comprehensive_analysis(self) -> Dict[str, AIAnalysis]:
        """종합 분석 (시장 + 거래)"""
        try:
            market_analysis = self.analyze_market()
            trading_advice = self.get_trading_advice()

            return {
                'market': market_analysis,
                'trading': trading_advice,
                'generated_at': now_kst().isoformat()
            }

        except Exception as e:
            self.logger.error(f"종합 분석 오류: {e}")
            return {
                'market': AIAnalysis(
                    analysis_type='market',
                    content='분석 실패',
                    confidence=0.0,
                    timestamp=now_kst()
                ),
                'trading': AIAnalysis(
                    analysis_type='trading',
                    content='분석 실패',
                    confidence=0.0,
                    timestamp=now_kst()
                ),
                'generated_at': now_kst().isoformat()
            }

    def clear_cache(self):
        """캐시 초기화"""
        self.analysis_cache.clear()
        self.logger.info("AI 분석 캐시가 초기화되었습니다.")


# 전역 AI 어드바이저 인스턴스
ai_advisor = AIAdvisor()
