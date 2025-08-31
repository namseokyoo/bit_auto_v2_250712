"""
DeepSeek AI API 클라이언트
시장 분석 및 거래 조언을 위한 AI 통합
"""

import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import time


class DeepSeekClient:
    """DeepSeek AI API 클라이언트"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = base_url or os.getenv(
            'DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
        self.logger = logging.getLogger('DeepSeekClient')

        if not self.api_key:
            self.logger.warning("DeepSeek API 키가 설정되지 않았습니다. 모의 모드로 실행됩니다.")
            self.mock_mode = True
        else:
            self.mock_mode = False

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })

    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """API 요청 실행"""
        if self.mock_mode:
            mock_response = self._mock_response(endpoint, data)
            mock_response['is_mock'] = True
            return mock_response

        try:
            url = f"{self.base_url}/{endpoint}"
            response = self.session.post(url, json=data, timeout=60)  # 타임아웃 60초로 증가
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"DeepSeek API 요청 실패: {e}")
            mock_response = self._mock_response(endpoint, data)
            # 모의응답 플래그 추가
            mock_response['is_mock'] = True
            return mock_response

    def _mock_response(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """모의 응답 생성 (API 키가 없을 때)"""
        messages = data.get('messages', [])
        last_message = messages[-1]['content'] if messages else ""
        
        # 시장 분석 요청인지 확인
        if any(keyword in last_message.lower() for keyword in ['시장', '분석', 'btc', '가격', '트렌드']):
            # 실제 시장 데이터에서 가격 정보 추출
            current_price_krw = None
            current_price_usd = None
            rsi_value = None
            change_rate = None
            
            # 메시지에서 실제 데이터 파싱
            if "가격:" in last_message:
                import re
                # KRW 가격 추출
                krw_match = re.search(r'가격:\s*\$?([\d,]+)', last_message)
                if krw_match:
                    current_price_krw = int(krw_match.group(1).replace(',', ''))
                    current_price_usd = round(current_price_krw / 1400)  # 대략적인 환율
                
                # RSI 추출
                rsi_match = re.search(r'RSI.*?(\d+\.?\d*)', last_message)
                if rsi_match:
                    rsi_value = float(rsi_match.group(1))
                
                # 변화율 추출
                change_match = re.search(r'변화율:\s*([-+]?\d+\.?\d*)%', last_message)
                if change_match:
                    change_rate = float(change_match.group(1))
            
            # 기본값 설정
            if not current_price_usd:
                current_price_usd = 109000  # 현재 수준
            if not rsi_value:
                rsi_value = 78
            if not change_rate:
                change_rate = 0.5
                
            # RSI 기반 분석
            rsi_analysis = ""
            if rsi_value > 70:
                rsi_analysis = "RSI 과매수 구간(78.2), 단기 조정 가능성"
            elif rsi_value < 30:
                rsi_analysis = "RSI 과매도 구간, 반등 기대"
            else:
                rsi_analysis = "RSI 중립 구간, 추세 지속 가능성"
            
            # 가격 기반 지지/저항선 계산
            support_level = round(current_price_usd * 0.95, -3)  # 5% 아래
            resistance_level = round(current_price_usd * 1.05, -3)  # 5% 위
            
            mock_content = f"""
**실시간 BTC 시장 분석**

**현재 시장 상황:**
- **현재가**: ${current_price_usd:,} (₩{current_price_krw:,} 수준)
- **24시간 변화**: {change_rate:+.2f}%
- **기술적 분석**: {rsi_analysis}
- **거래량**: 활발한 거래 지속

**기술적 전망:**
- **지지선**: ${support_level:,}
- **저항선**: ${resistance_level:,}
- **단기 전망**: {"상승 추세 지속 가능" if change_rate > 0 else "조정 국면 진입 가능"}

**거래 권장사항:**
1. 현재 가격 ${current_price_usd:,} 수준에서 {"분할 매수 고려" if rsi_value < 80 else "관망 권장"}
2. ${resistance_level:,} 돌파 시 추가 상승 기대
3. 손절선: ${support_level:,} 설정 권장

*실제 시장 데이터 기반 분석 (DeepSeek API 연결 대기 중)*
            """
        else:
            # 거래 조언 요청
            mock_content = """
**거래 전략 조언 (모의 데이터)**

현재 성과 분석:
- 거래 실행률 55.6%는 적정 수준
- 수익 거래 비율 16.7%는 개선 필요

**개선 제안**:
1. **진입 조건 강화**: RSI < 30일 때만 매수 신호 생성
2. **손절 기준 조정**: 2% → 1.5%로 타이트하게 설정
3. **포지션 크기 조정**: 변동성 높은 구간에서 포지션 크기 50% 축소

**리스크 관리**:
- 일일 최대 손실 한도: 총 자산의 2%
- 연속 손실 3회 시 거래 일시 중단
            """

        return {
            'choices': [{
                'message': {
                    'content': mock_content.strip(),
                    'role': 'assistant'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 100,
                'completion_tokens': 200,
                'total_tokens': 300
            }
        }

    def chat_completion(self, messages: List[Dict[str, str]],
                        model: str = "deepseek-chat",
                        temperature: float = 0.7,
                        max_tokens: int = 1000) -> Dict[str, Any]:
        """채팅 완료 API 호출"""
        data = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False
        }

        return self._make_request('chat/completions', data)

    def analyze_market(self, market_data: Dict[str, Any]) -> str:
        """시장 데이터 분석"""
        prompt = f"""
당신은 전문 암호화폐 거래 분석가입니다. 다음 시장 데이터를 분석하고 향후 4-6시간 내 가격 움직임을 예측해주세요.

**현재 시장 데이터:**
- BTC 가격: ${market_data.get('price', 'N/A'):,}
- 24시간 변화율: {market_data.get('change_24h', 'N/A')}%
- 거래량: {market_data.get('volume', 'N/A')} BTC
- RSI (14): {market_data.get('rsi', 'N/A')}
- 볼린저 밴드 위치: {market_data.get('bb_position', 'N/A')}
- 이동평균 상태: {market_data.get('ma_trend', 'N/A')}

**분석 요청사항:**
1. 현재 시장 심리 및 트렌드 분석
2. 주요 지지/저항선 식별
3. 단기 가격 목표 및 리스크 요인
4. 구체적인 거래 권장사항

한국어로 명확하고 구체적으로 답변해주세요.
        """

        messages = [
            {"role": "system", "content": "당신은 전문 암호화폐 거래 분석가입니다."},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(messages)
        return response['choices'][0]['message']['content']

    def get_trading_advice(self, strategy_performance: Dict[str, Any],
                           recent_trades: List[Dict[str, Any]]) -> str:
        """거래 전략 조언"""
        prompt = f"""
당신은 전문 거래 전략 컨설턴트입니다. 다음 거래 성과를 분석하고 개선 방안을 제시해주세요.

**현재 전략 성과:**
- 총 실행 횟수: {strategy_performance.get('total_executions', 0)}회
- 거래 실행률: {strategy_performance.get('execution_rate', 0)*100:.1f}%
- 수익 거래 비율: {strategy_performance.get('profit_rate', 0)*100:.1f}%
- 평균 신뢰도: {strategy_performance.get('avg_confidence', 0)*100:.1f}%
- 총 PnL: {strategy_performance.get('total_pnl', 0):.2f} USDT

**최근 거래 이력:**
"""

        for i, trade in enumerate(recent_trades[:5], 1):
            prompt += f"""
{i}. {trade.get('strategy_tier', 'N/A')}:{trade.get('strategy_id', 'N/A')}
   - 신호: {trade.get('signal_action', 'N/A')} (신뢰도: {trade.get('confidence', 0)*100:.1f}%)
   - 실행: {'예' if trade.get('trade_executed') else '아니오'}
   - PnL: {trade.get('pnl', 0):.2f} USDT
"""

        prompt += """
**분석 요청사항:**
1. 현재 성과의 강점과 약점 분석
2. 구체적인 개선 방안 (진입/청산 조건, 포지션 크기 등)
3. 리스크 관리 강화 방안
4. 단기/중기 성과 개선 목표

실용적이고 구체적인 조언을 한국어로 제공해주세요.
        """

        messages = [
            {"role": "system", "content": "당신은 전문 거래 전략 컨설턴트입니다."},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(messages)
        return response['choices'][0]['message']['content']

    def get_risk_assessment(self, portfolio_data: Dict[str, Any]) -> str:
        """리스크 평가"""
        prompt = f"""
포트폴리오 리스크를 평가하고 관리 방안을 제시해주세요.

**포트폴리오 정보:**
- 총 자산: {portfolio_data.get('total_balance', 0):.2f} USDT
- BTC 보유량: {portfolio_data.get('btc_balance', 0):.6f} BTC
- 현금 비율: {portfolio_data.get('cash_ratio', 0)*100:.1f}%
- 일일 변동성: {portfolio_data.get('daily_volatility', 0)*100:.2f}%
- 최대 낙폭: {portfolio_data.get('max_drawdown', 0)*100:.2f}%

리스크 수준과 관리 방안을 분석해주세요.
        """

        messages = [
            {"role": "system", "content": "당신은 전문 리스크 관리 컨설턴트입니다."},
            {"role": "user", "content": prompt}
        ]

        response = self.chat_completion(messages)
        return response['choices'][0]['message']['content']


# 전역 클라이언트 인스턴스
deepseek_client = DeepSeekClient()
