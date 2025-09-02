#!/usr/bin/env python3
"""
AI 기반 파라미터 튜닝 시스템
DeepSeek AI를 활용하여 전략 파라미터를 지능적으로 최적화하는 시스템
"""

import logging
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time

from config.config_manager import config_manager
from core.ai_performance_analyzer import ai_performance_analyzer, AdvancedPerformanceMetrics
from core.dynamic_weight_optimizer import dynamic_weight_optimizer
from core.adaptive_trading_optimizer import adaptive_trading_optimizer
from core.deepseek_client import deepseek_client


class TuningObjective(Enum):
    """튜닝 목표"""
    MAXIMIZE_RETURN = "maximize_return"          # 수익률 최대화
    MINIMIZE_RISK = "minimize_risk"              # 리스크 최소화
    MAXIMIZE_SHARPE = "maximize_sharpe"          # 샤프 비율 최대화
    MINIMIZE_DRAWDOWN = "minimize_drawdown"      # 최대 낙폭 최소화
    OPTIMIZE_WIN_RATE = "optimize_win_rate"      # 승률 최적화
    BALANCE_RISK_RETURN = "balance_risk_return"  # 리스크-수익 균형


class ParameterType(Enum):
    """파라미터 유형"""
    TECHNICAL_INDICATOR = "technical_indicator"  # 기술적 지표
    THRESHOLD = "threshold"                      # 임계값
    TIMING = "timing"                           # 타이밍
    RISK_MANAGEMENT = "risk_management"         # 리스크 관리
    STRATEGY_WEIGHT = "strategy_weight"         # 전략 가중치


@dataclass
class ParameterRange:
    """파라미터 범위"""
    min_value: float
    max_value: float
    step: float
    current_value: float
    parameter_type: ParameterType
    description: str


@dataclass
class TuningResult:
    """튜닝 결과"""
    strategy_id: str
    parameter_name: str
    original_value: Any
    optimized_value: Any
    improvement: float
    confidence: float
    reasoning: str
    objective: TuningObjective
    timestamp: datetime

    def to_dict(self) -> Dict:
        return {
            'strategy_id': self.strategy_id,
            'parameter_name': self.parameter_name,
            'original_value': self.original_value,
            'optimized_value': self.optimized_value,
            'improvement': self.improvement,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'objective': self.objective.value,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AITuningRequest:
    """AI 튜닝 요청"""
    strategy_id: str
    performance_data: AdvancedPerformanceMetrics
    market_condition: str
    current_parameters: Dict[str, Any]
    parameter_ranges: Dict[str, ParameterRange]
    objective: TuningObjective
    constraints: Dict[str, Any]


class AIParameterTuner:
    """AI 기반 파라미터 튜너"""

    def __init__(self):
        self.logger = logging.getLogger('AIParameterTuner')

        # 튜닝 설정
        self.tuning_interval_hours = 24  # 24시간마다 실행
        self.min_confidence_for_application = 0.7
        self.max_parameter_change_ratio = 0.3  # 최대 30% 변경

        # 튜닝 이력
        self.tuning_history: List[TuningResult] = []
        self.last_tuning_time = None

        # 파라미터 정의
        self.parameter_definitions = self._define_tunable_parameters()

        # 스레드 안전성
        self._lock = threading.Lock()

        self.logger.info("AI 파라미터 튜너 초기화 완료")

    def tune_strategy_parameters(self, strategy_id: str,
                                 objective: TuningObjective = TuningObjective.BALANCE_RISK_RETURN) -> List[TuningResult]:
        """전략 파라미터 튜닝"""

        try:
            self.logger.info(f"전략 파라미터 튜닝 시작: {strategy_id}")

            # 1. 성과 데이터 수집
            performance_data = ai_performance_analyzer.analyze_strategy_performance(
                strategy_id, 30)
            if not performance_data:
                self.logger.warning(f"성과 데이터 없음: {strategy_id}")
                return []

            # 2. 시장 상황 분석
            market_analysis = adaptive_trading_optimizer.analyze_market_condition()
            market_condition = market_analysis.condition.value if market_analysis else "unknown"

            # 3. 현재 파라미터 가져오기
            current_parameters = self._get_strategy_parameters(strategy_id)
            if not current_parameters:
                self.logger.warning(f"현재 파라미터 없음: {strategy_id}")
                return []

            # 4. 파라미터 범위 정의
            parameter_ranges = self._get_parameter_ranges(
                strategy_id, current_parameters)

            # 5. AI 튜닝 요청 생성
            tuning_request = AITuningRequest(
                strategy_id=strategy_id,
                performance_data=performance_data,
                market_condition=market_condition,
                current_parameters=current_parameters,
                parameter_ranges=parameter_ranges,
                objective=objective,
                constraints=self._get_tuning_constraints(strategy_id)
            )

            # 6. AI 기반 최적화 실행
            tuning_results = self._execute_ai_tuning(tuning_request)

            # 7. 결과 검증 및 필터링
            validated_results = self._validate_tuning_results(
                tuning_results, performance_data)

            # 8. 이력에 추가
            with self._lock:
                self.tuning_history.extend(validated_results)
                if len(self.tuning_history) > 100:
                    self.tuning_history = self.tuning_history[-100:]

            self.logger.info(f"파라미터 튜닝 완료: {len(validated_results)}개 최적화")
            return validated_results

        except Exception as e:
            self.logger.error(f"파라미터 튜닝 오류 ({strategy_id}): {e}")
            return []

    def apply_tuning_results(self, tuning_results: List[TuningResult]) -> Dict[str, bool]:
        """튜닝 결과 적용"""
        application_results = {}

        for result in tuning_results:
            try:
                if result.confidence < self.min_confidence_for_application:
                    self.logger.info(
                        f"신뢰도 부족으로 {result.parameter_name} 적용 건너뜀")
                    application_results[f"{result.strategy_id}.{result.parameter_name}"] = False
                    continue

                success = self._apply_parameter_change(result)
                application_results[f"{result.strategy_id}.{result.parameter_name}"] = success

                if success:
                    self.logger.info(
                        f"파라미터 적용: {result.strategy_id}.{result.parameter_name} = {result.optimized_value}")
                else:
                    self.logger.warning(
                        f"파라미터 적용 실패: {result.strategy_id}.{result.parameter_name}")

            except Exception as e:
                self.logger.error(f"튜닝 결과 적용 오류: {e}")
                application_results[f"{result.strategy_id}.{result.parameter_name}"] = False

        return application_results

    def auto_tune_all_strategies(self,
                                 objective: TuningObjective = TuningObjective.BALANCE_RISK_RETURN) -> Dict[str, Any]:
        """모든 전략 자동 튜닝"""

        try:
            if not self._should_run_tuning():
                return {'success': False, 'message': '튜닝 주기 미도달'}

            self.logger.info("전체 전략 자동 튜닝 시작")

            # 활성 전략 목록
            active_strategies = self._get_active_strategies()
            if not active_strategies:
                return {'success': False, 'message': '활성 전략 없음'}

            all_results = []
            strategy_results = {}

            # 각 전략별 튜닝
            for strategy_id in active_strategies:
                try:
                    results = self.tune_strategy_parameters(
                        strategy_id, objective)
                    all_results.extend(results)
                    strategy_results[strategy_id] = len(results)

                    # 결과 적용
                    if results:
                        application_results = self.apply_tuning_results(
                            results)
                        applied_count = sum(
                            1 for success in application_results.values() if success)
                        self.logger.info(
                            f"{strategy_id}: {applied_count}/{len(results)} 파라미터 적용")

                except Exception as e:
                    self.logger.error(f"전략 튜닝 오류 ({strategy_id}): {e}")
                    strategy_results[strategy_id] = 0

            # 튜닝 시간 업데이트
            self.last_tuning_time = datetime.now()

            return {
                'success': True,
                'total_optimizations': len(all_results),
                'strategy_results': strategy_results,
                'objective': objective.value,
                'tuning_time': self.last_tuning_time.isoformat(),
                'top_improvements': [
                    {
                        'strategy': r.strategy_id,
                        'parameter': r.parameter_name,
                        'improvement': r.improvement
                    }
                    for r in sorted(all_results, key=lambda x: x.improvement, reverse=True)[:5]
                ]
            }

        except Exception as e:
            self.logger.error(f"자동 튜닝 오류: {e}")
            return {'success': False, 'message': f'자동 튜닝 오류: {str(e)}'}

    def _execute_ai_tuning(self, request: AITuningRequest) -> List[TuningResult]:
        """AI 기반 튜닝 실행"""

        try:
            # AI 프롬프트 생성
            prompt = self._generate_tuning_prompt(request)

            # DeepSeek AI 호출
            response = deepseek_client.analyze_market(prompt)

            if not response or response.get('is_mock', False):
                self.logger.warning("AI 응답 없음 또는 모의 응답, 기본 최적화 사용")
                return self._fallback_optimization(request)

            # AI 응답 파싱
            tuning_results = self._parse_ai_response(
                response['analysis'], request)

            return tuning_results

        except Exception as e:
            self.logger.error(f"AI 튜닝 실행 오류: {e}")
            return self._fallback_optimization(request)

    def _generate_tuning_prompt(self, request: AITuningRequest) -> str:
        """AI 튜닝 프롬프트 생성"""

        performance = request.performance_data

        prompt = f"""
전략 파라미터 최적화 분석을 요청합니다.

**전략 정보:**
- 전략 ID: {request.strategy_id}
- 분석 기간: {performance.period_days}일
- 목표: {request.objective.value}

**현재 성과:**
- 총 거래: {performance.total_trades}
- 승률: {performance.win_rate:.1%}
- 총 손익: {performance.total_pnl:,.0f} KRW
- 평균 손익: {performance.average_pnl:,.0f} KRW
- 샤프 비율: {performance.sharpe_ratio:.3f}
- 최대 낙폭: {performance.max_drawdown:,.0f} KRW
- AI 점수: {performance.ai_optimization_score:.1f}/100

**시장 상황:** {request.market_condition}

**현재 파라미터:**
{json.dumps(request.current_parameters, indent=2, ensure_ascii=False)}

**파라미터 범위:**
{self._format_parameter_ranges(request.parameter_ranges)}

**최적화 목표:** {request.objective.value}

**분석 요청:**
1. 현재 성과의 문제점과 개선 가능한 영역을 분석해주세요.
2. 각 파라미터가 성과에 미치는 영향을 평가해주세요.
3. 목표({request.objective.value})에 따른 최적 파라미터 값을 제안해주세요.
4. 각 제안의 예상 개선 효과와 리스크를 평가해주세요.
5. 시장 상황({request.market_condition})을 고려한 조정사항을 제안해주세요.

**응답 형식:**
다음 JSON 형식으로 응답해주세요:
{{
    "analysis": "성과 분석 및 문제점",
    "recommendations": [
        {{
            "parameter": "파라미터명",
            "current_value": 현재값,
            "recommended_value": 권장값,
            "reasoning": "변경 이유",
            "expected_improvement": 예상개선율(%),
            "confidence": 신뢰도(0-1),
            "risk_level": "low/medium/high"
        }}
    ],
    "market_considerations": "시장 상황 고려사항",
    "overall_confidence": 전체신뢰도(0-1)
}}
"""

        return prompt

    def _format_parameter_ranges(self, parameter_ranges: Dict[str, ParameterRange]) -> str:
        """파라미터 범위 포맷팅"""
        formatted = []
        for name, range_info in parameter_ranges.items():
            formatted.append(
                f"- {name}: {range_info.min_value} ~ {range_info.max_value} (현재: {range_info.current_value})")

        return "\n".join(formatted)

    def _parse_ai_response(self, ai_response: str, request: AITuningRequest) -> List[TuningResult]:
        """AI 응답 파싱"""

        try:
            # JSON 응답 파싱 시도
            if isinstance(ai_response, str):
                # JSON 부분 추출
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = ai_response[json_start:json_end]
                    response_data = json.loads(json_str)
                else:
                    raise ValueError("JSON 형식 찾을 수 없음")
            else:
                response_data = ai_response

            tuning_results = []

            for rec in response_data.get('recommendations', []):
                try:
                    # 파라미터 변경 검증
                    if not self._validate_parameter_change(
                        request.strategy_id,
                        rec['parameter'],
                        rec['current_value'],
                        rec['recommended_value']
                    ):
                        self.logger.warning(
                            f"유효하지 않은 파라미터 변경: {rec['parameter']}")
                        continue

                    result = TuningResult(
                        strategy_id=request.strategy_id,
                        parameter_name=rec['parameter'],
                        original_value=rec['current_value'],
                        optimized_value=rec['recommended_value'],
                        improvement=rec.get('expected_improvement', 0),
                        confidence=rec.get('confidence', 0.5),
                        reasoning=rec.get('reasoning', ''),
                        objective=request.objective,
                        timestamp=datetime.now()
                    )

                    tuning_results.append(result)

                except Exception as e:
                    self.logger.error(f"권장사항 파싱 오류: {e}")
                    continue

            return tuning_results

        except Exception as e:
            self.logger.error(f"AI 응답 파싱 오류: {e}")
            return self._fallback_optimization(request)

    def _fallback_optimization(self, request: AITuningRequest) -> List[TuningResult]:
        """대체 최적화 (AI 실패 시)"""

        results = []
        performance = request.performance_data

        try:
            # 간단한 휴리스틱 기반 최적화

            # 1. 승률이 낮으면 임계값 조정
            if performance.win_rate < 0.4:
                for param_name in ['rsi_oversold', 'rsi_overbought', 'bollinger_std']:
                    if param_name in request.current_parameters:
                        current_value = request.current_parameters[param_name]

                        # 보수적으로 조정
                        if param_name == 'rsi_oversold':
                            new_value = min(current_value + 5, 35)
                        elif param_name == 'rsi_overbought':
                            new_value = max(current_value - 5, 65)
                        elif param_name == 'bollinger_std':
                            new_value = min(current_value + 0.2, 2.5)
                        else:
                            continue

                        if new_value != current_value:
                            result = TuningResult(
                                strategy_id=request.strategy_id,
                                parameter_name=param_name,
                                original_value=current_value,
                                optimized_value=new_value,
                                improvement=5.0,
                                confidence=0.6,
                                reasoning=f"승률 개선을 위한 {param_name} 조정",
                                objective=request.objective,
                                timestamp=datetime.now()
                            )
                            results.append(result)

            # 2. 높은 변동성 시 민감도 감소
            if request.market_condition in ['high_volatility', 'bear_market']:
                for param_name in ['period', 'sensitivity']:
                    if param_name in request.current_parameters:
                        current_value = request.current_parameters[param_name]
                        new_value = int(current_value * 1.2)  # 20% 증가

                        if new_value != current_value:
                            result = TuningResult(
                                strategy_id=request.strategy_id,
                                parameter_name=param_name,
                                original_value=current_value,
                                optimized_value=new_value,
                                improvement=8.0,
                                confidence=0.7,
                                reasoning=f"고변동성 시장에서 {param_name} 조정",
                                objective=request.objective,
                                timestamp=datetime.now()
                            )
                            results.append(result)

        except Exception as e:
            self.logger.error(f"대체 최적화 오류: {e}")

        return results

    def _validate_parameter_change(self, strategy_id: str, parameter_name: str,
                                   current_value: Any, new_value: Any) -> bool:
        """파라미터 변경 검증"""

        try:
            # 타입 검증
            if type(current_value) != type(new_value):
                return False

            # 숫자형 파라미터 검증
            if isinstance(current_value, (int, float)):
                change_ratio = abs((new_value - current_value) /
                                   current_value) if current_value != 0 else 0
                if change_ratio > self.max_parameter_change_ratio:
                    self.logger.warning(
                        f"파라미터 변경 비율 초과: {parameter_name} ({change_ratio:.1%})")
                    return False

            # 파라미터별 범위 검증
            param_ranges = self.parameter_definitions.get(strategy_id, {})
            if parameter_name in param_ranges:
                range_info = param_ranges[parameter_name]
                if not (range_info.min_value <= new_value <= range_info.max_value):
                    self.logger.warning(
                        f"파라미터 범위 초과: {parameter_name} = {new_value}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"파라미터 검증 오류: {e}")
            return False

    def _validate_tuning_results(self, tuning_results: List[TuningResult],
                                 performance_data: AdvancedPerformanceMetrics) -> List[TuningResult]:
        """튜닝 결과 검증"""

        validated_results = []

        for result in tuning_results:
            # 신뢰도 검증
            if result.confidence < 0.5:
                self.logger.info(f"낮은 신뢰도로 제외: {result.parameter_name}")
                continue

            # 개선 효과 검증
            if result.improvement < 1.0:
                self.logger.info(f"낮은 개선 효과로 제외: {result.parameter_name}")
                continue

            # 성과 기반 신뢰도 조정
            if performance_data.total_trades < 20:
                result.confidence *= 0.8  # 데이터 부족으로 신뢰도 감소

            if performance_data.ai_optimization_score < 30:
                result.confidence *= 0.9  # 낮은 성과로 신뢰도 감소

            validated_results.append(result)

        return validated_results

    def _apply_parameter_change(self, result: TuningResult) -> bool:
        """파라미터 변경 적용"""

        try:
            # 설정 경로 생성
            config_path = f"independent_strategies.strategies.{result.strategy_id}.{result.parameter_name}"

            # 설정 업데이트
            success = config_manager.update_config(
                config_path, result.optimized_value)

            if success:
                self.logger.info(
                    f"파라미터 업데이트: {config_path} = {result.optimized_value}")

            return success

        except Exception as e:
            self.logger.error(f"파라미터 적용 오류: {e}")
            return False

    def _should_run_tuning(self) -> bool:
        """튜닝 실행 여부 판단"""
        if self.last_tuning_time is None:
            return True

        hours_since_last = (
            datetime.now() - self.last_tuning_time).total_seconds() / 3600
        return hours_since_last >= self.tuning_interval_hours

    def _get_strategy_parameters(self, strategy_id: str) -> Dict[str, Any]:
        """전략 파라미터 가져오기"""
        try:
            strategy_config = config_manager.get_config(
                f'independent_strategies.strategies.{strategy_id}', {})

            # enabled 제외하고 파라미터만 추출
            parameters = {k: v for k, v in strategy_config.items()
                          if k != 'enabled'}

            return parameters

        except Exception as e:
            self.logger.error(f"전략 파라미터 조회 오류: {e}")
            return {}

    def _get_parameter_ranges(self, strategy_id: str, current_parameters: Dict[str, Any]) -> Dict[str, ParameterRange]:
        """파라미터 범위 정의"""

        ranges = {}

        # 기본 범위 정의
        default_ranges = {
            'period': (5, 50, 1, ParameterType.TECHNICAL_INDICATOR),
            'rsi_period': (10, 30, 1, ParameterType.TECHNICAL_INDICATOR),
            'rsi_overbought': (60, 90, 1, ParameterType.THRESHOLD),
            'rsi_oversold': (10, 40, 1, ParameterType.THRESHOLD),
            'bollinger_period': (10, 30, 1, ParameterType.TECHNICAL_INDICATOR),
            'bollinger_std': (1.5, 3.0, 0.1, ParameterType.THRESHOLD),
            'fast_ema': (5, 20, 1, ParameterType.TECHNICAL_INDICATOR),
            'slow_ema': (20, 50, 1, ParameterType.TECHNICAL_INDICATOR),
            'volume_threshold': (1.0, 3.0, 0.1, ParameterType.THRESHOLD),
        }

        for param_name, current_value in current_parameters.items():
            if param_name in default_ranges:
                min_val, max_val, step, param_type = default_ranges[param_name]

                ranges[param_name] = ParameterRange(
                    min_value=min_val,
                    max_value=max_val,
                    step=step,
                    current_value=current_value,
                    parameter_type=param_type,
                    description=f"{param_name} 파라미터"
                )

        return ranges

    def _get_tuning_constraints(self, strategy_id: str) -> Dict[str, Any]:
        """튜닝 제약 조건"""
        return {
            'max_change_ratio': self.max_parameter_change_ratio,
            'min_confidence': self.min_confidence_for_application,
            'strategy_enabled': True
        }

    def _define_tunable_parameters(self) -> Dict[str, Dict[str, ParameterRange]]:
        """튜닝 가능한 파라미터 정의"""
        # 전략별 파라미터 정의는 추후 확장
        return {}

    def _get_active_strategies(self) -> List[str]:
        """활성화된 전략 목록"""
        try:
            strategy_config = config_manager.get_config(
                'independent_strategies.strategies', {})
            return [strategy_id for strategy_id, config in strategy_config.items()
                    if config.get('enabled', True)]
        except Exception as e:
            self.logger.error(f"활성 전략 조회 오류: {e}")
            return []

    def get_tuning_summary(self) -> Dict[str, Any]:
        """튜닝 요약 정보"""
        try:
            recent_results = self.tuning_history[-20:
                                                 ] if self.tuning_history else []

            # 전략별 튜닝 횟수
            strategy_counts = {}
            for result in recent_results:
                strategy_counts[result.strategy_id] = strategy_counts.get(
                    result.strategy_id, 0) + 1

            # 평균 개선율
            avg_improvement = np.mean(
                [r.improvement for r in recent_results]) if recent_results else 0

            # 최고 성과 튜닝
            best_tuning = max(
                recent_results, key=lambda x: x.improvement) if recent_results else None

            return {
                'total_tuning_sessions': len(self.tuning_history),
                'recent_tuning_count': len(recent_results),
                'last_tuning_time': self.last_tuning_time.isoformat() if self.last_tuning_time else None,
                'avg_improvement': avg_improvement,
                'strategy_tuning_counts': strategy_counts,
                'best_recent_tuning': {
                    'strategy': best_tuning.strategy_id,
                    'parameter': best_tuning.parameter_name,
                    'improvement': best_tuning.improvement
                } if best_tuning else None,
                'next_tuning_due': (self.last_tuning_time + timedelta(hours=self.tuning_interval_hours)).isoformat()
                if self.last_tuning_time else datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"튜닝 요약 생성 오류: {e}")
            return {}


# 전역 인스턴스
ai_parameter_tuner = AIParameterTuner()
