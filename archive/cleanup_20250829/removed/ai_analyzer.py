"""
AI 기반 트레이딩 분석 및 피드백 시스템
DeepSeek API를 활용한 전략 최적화
"""

import os
import json
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from dotenv import load_dotenv
import logging
import sqlite3
from collections import defaultdict

# 환경 변수 로드
load_dotenv('config/.env')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeepSeekAnalyzer:
    """DeepSeek API를 활용한 트레이딩 분석"""
    
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def analyze_daily_performance(self, data: Dict) -> Dict:
        """일일 성과 분석 및 개선안 도출"""
        
        prompt = self._build_daily_analysis_prompt(data)
        
        try:
            response = await self._call_api(prompt)
            analysis = self._parse_json_response(response)
            
            # 분석 결과 저장
            self._save_analysis(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Daily analysis failed: {e}")
            return self._get_fallback_analysis(data)
    
    async def suggest_strategy_adjustments(self, 
                                         performance_data: Dict,
                                         market_forecast: Dict) -> Dict:
        """전략 파라미터 조정 제안"""
        
        prompt = f"""
        Based on the trading performance and market conditions, suggest parameter adjustments.
        
        Current Strategy Performance:
        {json.dumps(performance_data, indent=2)}
        
        Market Forecast:
        {json.dumps(market_forecast, indent=2)}
        
        Provide specific parameter adjustments in JSON format:
        {{
            "adjustments": {{
                "signal_threshold": {{
                    "current": 0.03,
                    "suggested": <float>,
                    "reason": "<explanation>"
                }},
                "position_limits": {{
                    "max_position": {{
                        "current": 10000000,
                        "suggested": <int>,
                        "reason": "<explanation>"
                    }}
                }},
                "strategy_weights": {{
                    "market_making": <float>,
                    "statistical_arbitrage": <float>,
                    "microstructure": <float>,
                    "momentum_scalping": <float>,
                    "mean_reversion": <float>
                }},
                "risk_parameters": {{
                    "stop_loss": <float>,
                    "take_profit": <float>,
                    "max_daily_loss": <float>
                }}
            }},
            "confidence": <float between 0 and 1>,
            "expected_improvement": <float>
        }}
        """
        
        try:
            response = await self._call_api(prompt)
            adjustments = self._parse_json_response(response)
            
            # 조정안 검증
            if self._validate_adjustments(adjustments):
                return adjustments
            else:
                logger.warning("Invalid adjustments suggested, using conservative approach")
                return self._get_conservative_adjustments(performance_data)
                
        except Exception as e:
            logger.error(f"Strategy adjustment failed: {e}")
            return self._get_conservative_adjustments(performance_data)
    
    async def identify_patterns(self, historical_data: List[Dict]) -> Dict:
        """거래 패턴 인식 및 학습"""
        
        # 데이터 전처리
        df = pd.DataFrame(historical_data)
        
        patterns = {
            'time_patterns': self._analyze_time_patterns(df),
            'strategy_patterns': self._analyze_strategy_patterns(df),
            'market_condition_patterns': self._analyze_market_patterns(df),
            'failure_patterns': self._identify_failure_patterns(df)
        }
        
        # AI 분석 추가
        prompt = f"""
        Analyze the following trading patterns and identify actionable insights:
        
        {json.dumps(patterns, indent=2)}
        
        Provide:
        1. Key success patterns to replicate
        2. Failure patterns to avoid
        3. Optimal trading conditions
        4. Recommended strategy modifications
        """
        
        try:
            response = await self._call_api(prompt)
            ai_insights = self._parse_json_response(response)
            patterns['ai_insights'] = ai_insights
            
        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")
            
        return patterns
    
    async def _call_api(self, prompt: str) -> str:
        """DeepSeek API 호출"""
        
        if not self.api_key:
            logger.warning("DeepSeek API key not found, using mock response")
            return self._get_mock_response(prompt)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert cryptocurrency trading analyst."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            response = await self.client.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except httpx.HTTPStatusError as e:
            logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def _build_daily_analysis_prompt(self, data: Dict) -> str:
        """일일 분석용 프롬프트 생성"""
        
        return f"""
        Analyze today's cryptocurrency automated trading results:
        
        === Trading Summary ===
        - Total trades: {data.get('total_trades', 0)}
        - Profitable trades: {data.get('profitable_trades', 0)}
        - Total return: {data.get('total_return', 0):.2f}%
        - Win rate: {data.get('win_rate', 0):.2f}%
        - Sharpe ratio: {data.get('sharpe_ratio', 0):.2f}
        
        === Strategy Performance ===
        {json.dumps(data.get('strategy_performance', {}), indent=2)}
        
        === Market Conditions ===
        - Volatility: {data.get('volatility', 'N/A')}
        - Trend: {data.get('trend', 'N/A')}
        - Volume: {data.get('volume', 'N/A')}
        
        Provide analysis in JSON format:
        {{
            "success_factors": [],
            "failure_factors": [],
            "strategy_effectiveness": {{}},
            "missed_opportunities": [],
            "risk_assessment": {{}},
            "recommendations": {{
                "immediate_actions": [],
                "parameter_adjustments": {{}},
                "strategy_changes": []
            }}
        }}
        """
    
    def _parse_json_response(self, response: str) -> Dict:
        """JSON 응답 파싱"""
        
        try:
            # JSON 블록 추출
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "{" in response and "}" in response:
                # 첫 번째 { 부터 마지막 } 까지 추출
                start = response.index("{")
                end = response.rindex("}") + 1
                json_str = response[start:end]
            else:
                json_str = response
                
            return json.loads(json_str.strip())
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response: {response}")
            return {}
    
    def _validate_adjustments(self, adjustments: Dict) -> bool:
        """제안된 조정값 검증"""
        
        if not adjustments or 'adjustments' not in adjustments:
            return False
            
        adj = adjustments['adjustments']
        
        # 기본 검증
        checks = [
            # 신호 임계값은 0-1 사이
            0 <= adj.get('signal_threshold', {}).get('suggested', 0.03) <= 1,
            
            # 포지션 한도는 양수
            adj.get('position_limits', {}).get('max_position', {}).get('suggested', 10000000) > 0,
            
            # 전략 가중치 합은 1
            abs(sum(adj.get('strategy_weights', {}).values()) - 1.0) < 0.01 if 'strategy_weights' in adj else True,
            
            # 리스크 파라미터는 양수
            adj.get('risk_parameters', {}).get('stop_loss', 0.01) > 0,
            adj.get('risk_parameters', {}).get('max_daily_loss', 5.0) > 0
        ]
        
        return all(checks)
    
    def _save_analysis(self, analysis: Dict):
        """분석 결과 저장"""
        
        try:
            conn = sqlite3.connect('data/ai_analysis.db')
            cursor = conn.cursor()
            
            # 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    type TEXT,
                    analysis TEXT,
                    implemented BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # 분석 저장
            cursor.execute('''
                INSERT INTO analyses (type, analysis)
                VALUES (?, ?)
            ''', ('daily', json.dumps(analysis)))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
    
    def _get_fallback_analysis(self, data: Dict) -> Dict:
        """API 실패시 폴백 분석"""
        
        return {
            "success_factors": ["API unavailable, using rule-based analysis"],
            "failure_factors": [],
            "strategy_effectiveness": self._calculate_strategy_effectiveness(data),
            "recommendations": {
                "immediate_actions": [],
                "parameter_adjustments": self._calculate_basic_adjustments(data)
            }
        }
    
    def _get_conservative_adjustments(self, performance_data: Dict) -> Dict:
        """보수적 조정안"""
        
        current_return = performance_data.get('total_return', 0)
        
        # 수익이 음수면 리스크 축소
        if current_return < 0:
            factor = 0.9  # 10% 축소
        elif current_return < 2:
            factor = 1.0  # 유지
        else:
            factor = 1.1  # 10% 확대
            
        return {
            "adjustments": {
                "signal_threshold": {
                    "current": 0.03,
                    "suggested": 0.03 * factor,
                    "reason": "Conservative adjustment based on performance"
                },
                "risk_parameters": {
                    "stop_loss": 0.005 / factor,
                    "take_profit": 0.01 * factor,
                    "max_daily_loss": 5.0 / factor
                }
            },
            "confidence": 0.6,
            "expected_improvement": 0.5
        }
    
    def _analyze_time_patterns(self, df: pd.DataFrame) -> Dict:
        """시간대별 패턴 분석"""
        
        if df.empty:
            return {}
            
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        
        hourly_stats = df.groupby('hour').agg({
            'pnl': ['mean', 'sum', 'count'],
            'win_rate': 'mean'
        }).to_dict()
        
        return {
            'best_hours': self._get_best_hours(hourly_stats),
            'worst_hours': self._get_worst_hours(hourly_stats),
            'volume_distribution': self._get_volume_distribution(df)
        }
    
    def _analyze_strategy_patterns(self, df: pd.DataFrame) -> Dict:
        """전략별 패턴 분석"""
        
        if df.empty or 'strategy' not in df.columns:
            return {}
            
        strategy_stats = df.groupby('strategy').agg({
            'pnl': ['mean', 'sum', 'count', 'std'],
            'win_rate': 'mean'
        }).to_dict()
        
        return strategy_stats
    
    def _analyze_market_patterns(self, df: pd.DataFrame) -> Dict:
        """시장 조건별 패턴 분석"""
        
        patterns = {}
        
        if 'volatility' in df.columns:
            # 변동성별 수익률
            df['vol_category'] = pd.cut(df['volatility'], bins=3, labels=['Low', 'Medium', 'High'])
            patterns['volatility_performance'] = df.groupby('vol_category')['pnl'].mean().to_dict()
            
        if 'trend' in df.columns:
            # 추세별 수익률
            patterns['trend_performance'] = df.groupby('trend')['pnl'].mean().to_dict()
            
        return patterns
    
    def _identify_failure_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """실패 패턴 식별"""
        
        if df.empty:
            return []
            
        # 큰 손실 거래 분석
        losses = df[df['pnl'] < 0].nlargest(10, 'pnl', keep='all')
        
        patterns = []
        for _, trade in losses.iterrows():
            patterns.append({
                'timestamp': trade.get('timestamp'),
                'loss': trade.get('pnl'),
                'strategy': trade.get('strategy'),
                'conditions': {
                    'volatility': trade.get('volatility'),
                    'signal_strength': trade.get('signal_strength')
                }
            })
            
        return patterns
    
    def _get_mock_response(self, prompt: str) -> str:
        """API 키가 없을 때 모의 응답"""
        
        return json.dumps({
            "success_factors": ["Mock analysis - API key not configured"],
            "failure_factors": [],
            "strategy_effectiveness": {
                "market_making": 0.7,
                "momentum_scalping": 0.6
            },
            "recommendations": {
                "immediate_actions": ["Configure DeepSeek API key"],
                "parameter_adjustments": {}
            }
        })
    
    def _calculate_strategy_effectiveness(self, data: Dict) -> Dict:
        """전략 효과성 계산"""
        
        effectiveness = {}
        
        for strategy, performance in data.get('strategy_performance', {}).items():
            win_rate = performance.get('win_rate', 0)
            avg_return = performance.get('avg_return', 0)
            
            # 간단한 효과성 점수 (0-1)
            score = (win_rate * 0.4 + min(avg_return / 2, 1) * 0.6)
            effectiveness[strategy] = round(score, 2)
            
        return effectiveness
    
    def _calculate_basic_adjustments(self, data: Dict) -> Dict:
        """기본 파라미터 조정 계산"""
        
        adjustments = {}
        
        # 수익률에 따른 조정
        total_return = data.get('total_return', 0)
        
        if total_return < 0:
            # 손실시 보수적 조정
            adjustments['signal_threshold'] = 0.05  # 임계값 상향
            adjustments['position_size'] = 0.8  # 포지션 축소
        elif total_return < 1:
            # 저수익시 중간 조정
            adjustments['signal_threshold'] = 0.04
            adjustments['position_size'] = 0.9
        else:
            # 수익시 유지 또는 확대
            adjustments['signal_threshold'] = 0.03
            adjustments['position_size'] = 1.0
            
        return adjustments
    
    def _get_best_hours(self, hourly_stats: Dict) -> List[int]:
        """최고 수익 시간대"""
        # 구현 필요
        return [9, 10, 14, 15]
    
    def _get_worst_hours(self, hourly_stats: Dict) -> List[int]:
        """최악 수익 시간대"""
        # 구현 필요
        return [3, 4, 5]
    
    def _get_volume_distribution(self, df: pd.DataFrame) -> Dict:
        """거래량 분포"""
        # 구현 필요
        return {"morning": 0.3, "afternoon": 0.4, "evening": 0.3}
    
    async def close(self):
        """리소스 정리"""
        await self.client.aclose()


class FeedbackLoop:
    """피드백 루프 실행 관리"""
    
    def __init__(self):
        self.analyzer = DeepSeekAnalyzer()
        self.db_path = 'data/quantum.db'
        
    async def run_daily_analysis(self):
        """일일 분석 실행"""
        
        logger.info("Starting daily feedback analysis...")
        
        # 1. 오늘 거래 데이터 수집
        trading_data = self._collect_daily_data()
        
        # 2. AI 분석
        analysis = await self.analyzer.analyze_daily_performance(trading_data)
        
        # 3. 전략 조정 제안
        market_forecast = self._get_market_forecast()
        adjustments = await self.analyzer.suggest_strategy_adjustments(
            trading_data, 
            market_forecast
        )
        
        # 4. 조정사항 적용
        if adjustments and adjustments.get('confidence', 0) > 0.7:
            self._apply_adjustments(adjustments)
            logger.info("Strategy adjustments applied")
        
        # 5. 보고서 생성
        report = self._generate_report(analysis, adjustments)
        
        logger.info("Daily analysis completed")
        
        return report
    
    def _collect_daily_data(self) -> Dict:
        """일일 거래 데이터 수집"""
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 오늘 거래 통계
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as max_pnl,
                    MIN(pnl) as min_pnl
                FROM trades
                WHERE DATE(timestamp) = ?
            """, (today,))
            
            stats = cursor.fetchone()
            
            # 전략별 성과
            cursor.execute("""
                SELECT 
                    strategy_name,
                    COUNT(*) as trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
                FROM trades
                WHERE DATE(timestamp) = ?
                GROUP BY strategy_name
            """, (today,))
            
            strategy_performance = {}
            for row in cursor.fetchall():
                strategy_performance[row[0]] = {
                    'trades': row[1],
                    'total_pnl': row[2],
                    'avg_pnl': row[3],
                    'win_rate': row[4]
                }
            
            conn.close()
            
            # 결과 조합
            total_trades = stats[0] or 0
            profitable_trades = stats[1] or 0
            total_pnl = stats[2] or 0
            
            return {
                'total_trades': total_trades,
                'profitable_trades': profitable_trades,
                'total_return': (total_pnl / 10000000) * 100 if total_trades > 0 else 0,  # 초기 자금 대비 %
                'win_rate': (profitable_trades / total_trades * 100) if total_trades > 0 else 0,
                'sharpe_ratio': self._calculate_sharpe_ratio(),
                'strategy_performance': strategy_performance,
                'volatility': self._calculate_volatility(),
                'trend': self._identify_trend(),
                'volume': self._get_market_volume()
            }
            
        except Exception as e:
            logger.error(f"Failed to collect daily data: {e}")
            return {}
    
    def _get_market_forecast(self) -> Dict:
        """시장 전망 데이터"""
        
        # 실제로는 외부 API나 분석을 통해 가져와야 함
        return {
            'btc_trend': 'bullish',
            'volatility_forecast': 'increasing',
            'major_events': [],
            'sentiment': 'neutral'
        }
    
    def _apply_adjustments(self, adjustments: Dict):
        """전략 조정사항 적용"""
        
        try:
            # config.yaml 파일 업데이트
            import yaml
            
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            # 조정사항 적용
            adj = adjustments.get('adjustments', {})
            
            if 'signal_threshold' in adj:
                config['trading']['signal_threshold'] = adj['signal_threshold'].get('suggested', 0.03)
            
            if 'strategy_weights' in adj:
                weights = adj['strategy_weights']
                if 'market_making' in weights:
                    config['strategies']['market_making']['weight'] = weights['market_making']
                if 'statistical_arbitrage' in weights:
                    config['strategies']['statistical_arbitrage']['weight'] = weights['statistical_arbitrage']
                if 'microstructure' in weights:
                    config['strategies']['microstructure']['weight'] = weights['microstructure']
                if 'momentum_scalping' in weights:
                    config['strategies']['momentum_scalping']['weight'] = weights['momentum_scalping']
                if 'mean_reversion' in weights:
                    config['strategies']['mean_reversion']['weight'] = weights['mean_reversion']
            
            if 'risk_parameters' in adj:
                risk_params = adj['risk_parameters']
                if 'stop_loss' in risk_params:
                    config['strategies']['momentum_scalping']['params']['stop_loss'] = risk_params['stop_loss']
                if 'take_profit' in risk_params:
                    config['strategies']['momentum_scalping']['params']['take_profit'] = risk_params['take_profit']
                if 'max_daily_loss' in risk_params:
                    config['risk_management']['limits']['max_daily_loss_percent'] = risk_params['max_daily_loss']
            
            # 파일 저장
            with open('config/config.yaml', 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
                
            logger.info("Configuration updated with AI adjustments")
            
        except Exception as e:
            logger.error(f"Failed to apply adjustments: {e}")
    
    def _generate_report(self, analysis: Dict, adjustments: Dict) -> Dict:
        """분석 보고서 생성"""
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'analysis': analysis,
            'adjustments': adjustments,
            'summary': {
                'key_findings': analysis.get('success_factors', [])[:3],
                'immediate_actions': analysis.get('recommendations', {}).get('immediate_actions', []),
                'expected_improvement': adjustments.get('expected_improvement', 0)
            }
        }
        
        # 보고서 저장
        self._save_report(report)
        
        return report
    
    def _save_report(self, report: Dict):
        """보고서 저장"""
        
        try:
            # JSON 파일로 저장
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'reports/feedback_{timestamp}.json'
            
            os.makedirs('reports', exist_ok=True)
            
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
                
            logger.info(f"Report saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
    
    def _calculate_sharpe_ratio(self) -> float:
        """샤프 비율 계산"""
        # 실제 구현 필요
        return 1.5
    
    def _calculate_volatility(self) -> str:
        """변동성 계산"""
        # 실제 구현 필요
        return "Medium"
    
    def _identify_trend(self) -> str:
        """추세 식별"""
        # 실제 구현 필요
        return "Sideways"
    
    def _get_market_volume(self) -> str:
        """시장 거래량"""
        # 실제 구현 필요
        return "Normal"
    
    async def close(self):
        """리소스 정리"""
        await self.analyzer.close()


# 테스트 및 실행
async def main():
    """테스트 실행"""
    
    feedback_loop = FeedbackLoop()
    
    try:
        # 일일 분석 실행
        report = await feedback_loop.run_daily_analysis()
        
        print("Daily Analysis Report:")
        print(json.dumps(report, indent=2, default=str))
        
    finally:
        await feedback_loop.close()


if __name__ == "__main__":
    asyncio.run(main())