#!/usr/bin/env python3
"""
AI 최적화 통합 관리자
모든 AI 최적화 시스템을 통합 관리하고 조율하는 마스터 클래스
"""

import logging
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json

from config.config_manager import config_manager
from core.ai_performance_analyzer import ai_performance_analyzer
from core.dynamic_weight_optimizer import dynamic_weight_optimizer
from core.adaptive_trading_optimizer import adaptive_trading_optimizer
from core.ai_parameter_tuner import ai_parameter_tuner


class OptimizationMode(Enum):
    """최적화 모드"""
    CONSERVATIVE = "conservative"    # 보수적 (안정성 우선)
    BALANCED = "balanced"           # 균형 (기본값)
    AGGRESSIVE = "aggressive"       # 공격적 (수익성 우선)
    MANUAL = "manual"              # 수동 제어


class OptimizationStatus(Enum):
    """최적화 상태"""
    IDLE = "idle"                  # 대기
    RUNNING = "running"            # 실행 중
    COMPLETED = "completed"        # 완료
    ERROR = "error"               # 오류
    DISABLED = "disabled"         # 비활성화


@dataclass
class OptimizationTask:
    """최적화 작업"""
    task_id: str
    task_type: str
    priority: int
    scheduled_time: datetime
    status: OptimizationStatus
    progress: float
    result: Optional[Dict] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'priority': self.priority,
            'scheduled_time': self.scheduled_time.isoformat(),
            'status': self.status.value,
            'progress': self.progress,
            'result': self.result,
            'error_message': self.error_message
        }


@dataclass
class SystemHealthMetrics:
    """시스템 건강도 지표"""
    overall_score: float           # 전체 점수 (0-100)
    performance_score: float       # 성과 점수
    risk_score: float             # 리스크 점수
    optimization_score: float     # 최적화 점수
    stability_score: float        # 안정성 점수
    last_updated: datetime

    def to_dict(self) -> Dict:
        return asdict(self)


class AIOptimizationManager:
    """AI 최적화 통합 관리자"""

    def __init__(self):
        self.logger = logging.getLogger('AIOptimizationManager')

        # 설정
        self.optimization_mode = OptimizationMode.BALANCED
        self.auto_optimization_enabled = True
        self.optimization_interval = 6  # 6시간마다

        # 상태 관리
        self.current_status = OptimizationStatus.IDLE
        self.task_queue: List[OptimizationTask] = []
        self.execution_history: List[OptimizationTask] = []
        self.system_health: Optional[SystemHealthMetrics] = None

        # 스케줄링
        self.scheduler_thread = None
        self.scheduler_running = False
        self.last_optimization_time = None

        # 통계
        self.total_optimizations = 0
        self.successful_optimizations = 0

        # 스레드 안전성
        self._lock = threading.Lock()

        self.logger.info("AI 최적화 통합 관리자 초기화 완료")

    def start_optimization_scheduler(self):
        """최적화 스케줄러 시작"""
        if self.scheduler_running:
            self.logger.warning("스케줄러가 이미 실행 중입니다")
            return

        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

        self.logger.info("AI 최적화 스케줄러 시작")

    def stop_optimization_scheduler(self):
        """최적화 스케줄러 중지"""
        self.scheduler_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        self.logger.info("AI 최적화 스케줄러 중지")

    def execute_full_optimization(self, mode: OptimizationMode = None) -> Dict[str, Any]:
        """전체 최적화 실행"""

        if mode:
            self.optimization_mode = mode

        try:
            with self._lock:
                if self.current_status == OptimizationStatus.RUNNING:
                    return {'success': False, 'message': '이미 최적화가 실행 중입니다'}

                self.current_status = OptimizationStatus.RUNNING

            self.logger.info(f"전체 최적화 시작: {self.optimization_mode.value}")

            optimization_results = {}

            # 1. 시스템 건강도 평가
            self.logger.info("🔍 시스템 건강도 평가 중...")
            health_metrics = self._evaluate_system_health()
            optimization_results['system_health'] = health_metrics.to_dict()

            # 2. 성과 분석
            self.logger.info("📊 전략 성과 분석 중...")
            performance_summary = ai_performance_analyzer.get_portfolio_performance_summary(
                30)
            optimization_results['performance_analysis'] = performance_summary

            # 3. 가중치 최적화
            if self._should_run_weight_optimization(health_metrics):
                self.logger.info("⚖️ 가중치 최적화 중...")
                weight_result = dynamic_weight_optimizer.auto_optimize_weights()
                optimization_results['weight_optimization'] = weight_result.to_dict(
                ) if weight_result else None

            # 4. 거래 주기 최적화
            if self._should_run_trading_optimization(health_metrics):
                self.logger.info("⏱️ 거래 주기 최적화 중...")
                trading_result = adaptive_trading_optimizer.auto_optimize()
                optimization_results['trading_optimization'] = trading_result

            # 5. 파라미터 튜닝
            if self._should_run_parameter_tuning(health_metrics):
                self.logger.info("🔧 파라미터 튜닝 중...")
                tuning_result = ai_parameter_tuner.auto_tune_all_strategies()
                optimization_results['parameter_tuning'] = tuning_result

            # 6. 최적화 후 건강도 재평가
            self.logger.info("🔄 최적화 효과 평가 중...")
            time.sleep(5)  # 설정 적용 대기
            post_health_metrics = self._evaluate_system_health()
            optimization_results['post_optimization_health'] = post_health_metrics.to_dict(
            )

            # 7. 결과 정리
            optimization_summary = self._create_optimization_summary(
                optimization_results)

            # 8. 통계 업데이트
            self.total_optimizations += 1
            if optimization_summary.get('overall_improvement', 0) > 0:
                self.successful_optimizations += 1

            self.last_optimization_time = datetime.now()

            with self._lock:
                self.current_status = OptimizationStatus.COMPLETED
                self.system_health = post_health_metrics

            self.logger.info(
                f"전체 최적화 완료: {optimization_summary.get('overall_improvement', 0):.1f}% 개선")

            return {
                'success': True,
                'mode': self.optimization_mode.value,
                'execution_time': datetime.now().isoformat(),
                'summary': optimization_summary,
                'detailed_results': optimization_results
            }

        except Exception as e:
            self.logger.error(f"전체 최적화 오류: {e}")

            with self._lock:
                self.current_status = OptimizationStatus.ERROR

            return {
                'success': False,
                'error': str(e),
                'execution_time': datetime.now().isoformat()
            }

    def get_optimization_status(self) -> Dict[str, Any]:
        """최적화 상태 조회"""

        with self._lock:
            status_info = {
                'status': self.current_status.value,
                'mode': self.optimization_mode.value,
                'auto_enabled': self.auto_optimization_enabled,
                'scheduler_running': self.scheduler_running,
                'last_optimization': self.last_optimization_time.isoformat() if self.last_optimization_time else None,
                'next_scheduled': self._get_next_optimization_time().isoformat() if self.auto_optimization_enabled else None,
                'system_health': self.system_health.to_dict() if self.system_health else None,
                'statistics': {
                    'total_optimizations': self.total_optimizations,
                    'successful_optimizations': self.successful_optimizations,
                    'success_rate': (self.successful_optimizations / self.total_optimizations * 100)
                    if self.total_optimizations > 0 else 0
                }
            }

        return status_info

    def get_optimization_history(self, limit: int = 10) -> List[Dict]:
        """최적화 이력 조회"""

        with self._lock:
            return [task.to_dict() for task in self.execution_history[-limit:]]

    def configure_optimization(self, config: Dict[str, Any]) -> bool:
        """최적화 설정"""

        try:
            if 'mode' in config:
                mode_value = config['mode']
                if mode_value in [m.value for m in OptimizationMode]:
                    self.optimization_mode = OptimizationMode(mode_value)
                    self.logger.info(f"최적화 모드 변경: {mode_value}")

            if 'auto_enabled' in config:
                self.auto_optimization_enabled = bool(config['auto_enabled'])
                self.logger.info(
                    f"자동 최적화: {'활성화' if self.auto_optimization_enabled else '비활성화'}")

            if 'interval_hours' in config:
                self.optimization_interval = max(
                    1, int(config['interval_hours']))
                self.logger.info(f"최적화 주기: {self.optimization_interval}시간")

            return True

        except Exception as e:
            self.logger.error(f"최적화 설정 오류: {e}")
            return False

    def _scheduler_loop(self):
        """스케줄러 메인 루프"""

        while self.scheduler_running:
            try:
                if (self.auto_optimization_enabled and
                    self.current_status != OptimizationStatus.RUNNING and
                        self._should_run_scheduled_optimization()):

                    self.logger.info("예정된 자동 최적화 실행")
                    self.execute_full_optimization()

                # 1분마다 체크
                time.sleep(60)

            except Exception as e:
                self.logger.error(f"스케줄러 루프 오류: {e}")
                time.sleep(60)

    def _should_run_scheduled_optimization(self) -> bool:
        """예정된 최적화 실행 여부"""

        if self.last_optimization_time is None:
            return True

        hours_since_last = (
            datetime.now() - self.last_optimization_time).total_seconds() / 3600
        return hours_since_last >= self.optimization_interval

    def _get_next_optimization_time(self) -> datetime:
        """다음 최적화 예정 시간"""

        if self.last_optimization_time:
            return self.last_optimization_time + timedelta(hours=self.optimization_interval)
        else:
            return datetime.now() + timedelta(hours=self.optimization_interval)

    def _evaluate_system_health(self) -> SystemHealthMetrics:
        """시스템 건강도 평가"""

        try:
            # 포트폴리오 성과 요약
            portfolio_summary = ai_performance_analyzer.get_portfolio_performance_summary(
                30)

            # 성과 점수 (0-100)
            total_pnl = portfolio_summary.get('total_pnl', 0)
            win_rate = portfolio_summary.get('overall_win_rate', 0)
            sharpe_ratio = portfolio_summary.get('portfolio_sharpe_ratio', 0)

            performance_score = min(
                (win_rate * 50) +                    # 승률 기여 (최대 50점)
                (max(sharpe_ratio * 25, 0)) +        # 샤프 비율 기여 (최대 25점)
                (min(max(total_pnl / 1000000, 0), 25)),  # PnL 기여 (최대 25점)
                100
            )

            # 리스크 점수 (높을수록 안전)
            strategies_needing_optimization = portfolio_summary.get(
                'strategies_needing_optimization', 0)
            total_strategies = portfolio_summary.get('total_strategies', 1)

            risk_score = max(
                100 - (strategies_needing_optimization / total_strategies * 100), 0)

            # 최적화 점수
            avg_ai_score = portfolio_summary.get('avg_ai_score', 50)
            optimization_score = avg_ai_score

            # 안정성 점수
            volatility = portfolio_summary.get('portfolio_volatility', 0)
            stability_score = max(100 - (volatility * 1000), 0)  # 변동성 기반

            # 전체 점수 (가중 평균)
            overall_score = (
                performance_score * 0.3 +
                risk_score * 0.25 +
                optimization_score * 0.25 +
                stability_score * 0.2
            )

            return SystemHealthMetrics(
                overall_score=overall_score,
                performance_score=performance_score,
                risk_score=risk_score,
                optimization_score=optimization_score,
                stability_score=stability_score,
                last_updated=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"시스템 건강도 평가 오류: {e}")
            return SystemHealthMetrics(
                overall_score=50.0,
                performance_score=50.0,
                risk_score=50.0,
                optimization_score=50.0,
                stability_score=50.0,
                last_updated=datetime.now()
            )

    def _should_run_weight_optimization(self, health_metrics: SystemHealthMetrics) -> bool:
        """가중치 최적화 실행 여부"""

        # 성과가 낮거나 최적화 점수가 낮으면 실행
        return (health_metrics.performance_score < 60 or
                health_metrics.optimization_score < 70 or
                self.optimization_mode == OptimizationMode.AGGRESSIVE)

    def _should_run_trading_optimization(self, health_metrics: SystemHealthMetrics) -> bool:
        """거래 최적화 실행 여부"""

        # 리스크가 높거나 안정성이 낮으면 실행
        return (health_metrics.risk_score < 70 or
                health_metrics.stability_score < 60 or
                self.optimization_mode in [OptimizationMode.AGGRESSIVE, OptimizationMode.BALANCED])

    def _should_run_parameter_tuning(self, health_metrics: SystemHealthMetrics) -> bool:
        """파라미터 튜닝 실행 여부"""

        # 전체 건강도가 낮으면 실행
        return (health_metrics.overall_score < 70 or
                self.optimization_mode == OptimizationMode.AGGRESSIVE)

    def _create_optimization_summary(self, optimization_results: Dict[str, Any]) -> Dict[str, Any]:
        """최적화 요약 생성"""

        summary = {
            'execution_time': datetime.now().isoformat(),
            'mode': self.optimization_mode.value,
            'components_executed': [],
            'overall_improvement': 0,
            'key_changes': [],
            'recommendations': []
        }

        try:
            # 건강도 개선
            pre_health = optimization_results.get('system_health', {})
            post_health = optimization_results.get(
                'post_optimization_health', {})

            if pre_health and post_health:
                health_improvement = post_health.get(
                    'overall_score', 0) - pre_health.get('overall_score', 0)
                summary['health_improvement'] = health_improvement
                summary['overall_improvement'] += health_improvement * 0.4

            # 가중치 최적화 결과
            weight_result = optimization_results.get('weight_optimization')
            if weight_result:
                summary['components_executed'].append('weight_optimization')
                if weight_result.get('confidence', 0) > 0.6:
                    summary['overall_improvement'] += 10
                    summary['key_changes'].append('전략 가중치 최적화 적용')

            # 거래 최적화 결과
            trading_result = optimization_results.get('trading_optimization')
            if trading_result and trading_result.get('success'):
                summary['components_executed'].append('trading_optimization')
                applied_count = trading_result.get(
                    'applied_recommendations', 0)
                if applied_count > 0:
                    summary['overall_improvement'] += applied_count * 5
                    summary['key_changes'].append(
                        f'{applied_count}개 거래 파라미터 최적화')

            # 파라미터 튜닝 결과
            tuning_result = optimization_results.get('parameter_tuning')
            if tuning_result and tuning_result.get('success'):
                summary['components_executed'].append('parameter_tuning')
                total_optimizations = tuning_result.get(
                    'total_optimizations', 0)
                if total_optimizations > 0:
                    summary['overall_improvement'] += total_optimizations * 3
                    summary['key_changes'].append(
                        f'{total_optimizations}개 전략 파라미터 튜닝')

            # 권장사항 생성
            if summary['overall_improvement'] < 5:
                summary['recommendations'].append('시스템 성과가 안정적입니다')
            elif summary['overall_improvement'] > 20:
                summary['recommendations'].append(
                    '상당한 개선이 이루어졌습니다. 성과를 모니터링하세요')

            if post_health.get('risk_score', 100) < 60:
                summary['recommendations'].append('리스크 관리 강화가 필요합니다')

            if not summary['components_executed']:
                summary['recommendations'].append('현재 시스템이 최적 상태입니다')

        except Exception as e:
            self.logger.error(f"최적화 요약 생성 오류: {e}")
            summary['error'] = str(e)

        return summary


# 전역 인스턴스
ai_optimization_manager = AIOptimizationManager()
