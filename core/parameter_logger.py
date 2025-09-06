#!/usr/bin/env python3
"""
파라미터 조정 전용 로깅 시스템
시장 체제 기반 전략 파라미터 조정 내역을 상세히 기록
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from core.regime_detector import MarketRegime, RegimeResult
from core.dynamic_threshold_manager import ThresholdAdjustment, StrategyThresholds


@dataclass
class ParameterAdjustmentLog:
    """파라미터 조정 로그 엔트리"""
    timestamp: str
    regime: str
    regime_confidence: float
    regime_reasoning: str
    strategy_name: str
    parameter_name: str
    base_value: float
    adjusted_value: float
    adjustment_factor: float
    adjustment_reason: str
    market_data: Dict[str, Any]


@dataclass
class RegimeChangeLog:
    """체제 변경 로그 엔트리"""
    timestamp: str
    previous_regime: Optional[str]
    current_regime: str
    confidence: float
    reasoning: str
    affected_strategies: List[str]
    total_adjustments: int


class ParameterLogger:
    """파라미터 조정 전용 로거"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 로그 파일 경로
        self.parameter_log_file = self.log_dir / "parameter_adjustments.json"
        self.regime_log_file = self.log_dir / "regime_changes.json"
        self.summary_log_file = self.log_dir / "parameter_summary.log"
        
        # 로거 설정
        self.logger = self._setup_logger()
        
        # 이전 체제 추적
        self.previous_regime = None
        
        self.logger.info("ParameterLogger 초기화 완료")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger('ParameterLogger')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # 파일 핸들러
            file_handler = logging.FileHandler(self.summary_log_file)
            file_handler.setLevel(logging.INFO)
            
            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 포맷터
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger
    
    def log_parameter_adjustment(self, regime_result: RegimeResult, 
                               strategy_name: str, adjustment: ThresholdAdjustment,
                               market_data: Dict[str, Any] = None):
        """개별 파라미터 조정 로깅"""
        try:
            log_entry = ParameterAdjustmentLog(
                timestamp=datetime.now().isoformat(),
                regime=regime_result.primary_regime.value,
                regime_confidence=regime_result.confidence,
                regime_reasoning=regime_result.reasoning,
                strategy_name=strategy_name,
                parameter_name=adjustment.parameter_name,
                base_value=adjustment.base_value,
                adjusted_value=adjustment.adjusted_value,
                adjustment_factor=adjustment.adjustment_factor,
                adjustment_reason=adjustment.adjustment_reason,
                market_data=market_data or {}
            )
            
            # JSON 파일에 추가
            self._append_to_json_log(self.parameter_log_file, asdict(log_entry))
            
            # 상세 로그
            self.logger.info(
                f"🔧 파라미터 조정: {strategy_name}.{adjustment.parameter_name} | "
                f"{adjustment.base_value:.4f} → {adjustment.adjusted_value:.4f} "
                f"(x{adjustment.adjustment_factor:.2f}) | {regime_result.primary_regime.value}"
            )
            
        except Exception as e:
            self.logger.error(f"파라미터 조정 로깅 오류: {e}")
    
    def log_regime_change(self, regime_result: RegimeResult, 
                         affected_strategies: List[str], 
                         total_adjustments: int):
        """체제 변경 로깅"""
        try:
            log_entry = RegimeChangeLog(
                timestamp=datetime.now().isoformat(),
                previous_regime=self.previous_regime,
                current_regime=regime_result.primary_regime.value,
                confidence=regime_result.confidence,
                reasoning=regime_result.reasoning,
                affected_strategies=affected_strategies,
                total_adjustments=total_adjustments
            )
            
            # JSON 파일에 추가
            self._append_to_json_log(self.regime_log_file, asdict(log_entry))
            
            # 체제 변경 로그
            if self.previous_regime != regime_result.primary_regime.value:
                self.logger.info(
                    f"🔄 체제 변경: {self.previous_regime or 'Unknown'} → {regime_result.primary_regime.value} | "
                    f"신뢰도: {regime_result.confidence:.3f} | "
                    f"영향받은 전략: {len(affected_strategies)}개 | "
                    f"총 조정: {total_adjustments}개"
                )
                self.logger.info(f"📊 판단 근거: {regime_result.reasoning}")
            
            # 이전 체제 업데이트
            self.previous_regime = regime_result.primary_regime.value
            
        except Exception as e:
            self.logger.error(f"체제 변경 로깅 오류: {e}")
    
    def log_batch_adjustments(self, regime_result: RegimeResult, 
                            all_thresholds: Dict[str, StrategyThresholds],
                            market_data: Dict[str, Any] = None):
        """일괄 파라미터 조정 로깅"""
        try:
            affected_strategies = []
            total_adjustments = 0
            
            self.logger.info(f"=== 파라미터 일괄 조정 시작 ({regime_result.primary_regime.value}) ===")
            self.logger.info(f"신뢰도: {regime_result.confidence:.3f}")
            self.logger.info(f"판단 근거: {regime_result.reasoning}")
            
            for strategy_name, thresholds in all_thresholds.items():
                strategy_adjustments = 0
                
                self.logger.info(f"\n📊 {strategy_name}:")
                
                for param_name, adjustment in thresholds.adjustments.items():
                    # 개별 조정 로깅
                    self.log_parameter_adjustment(
                        regime_result, strategy_name, adjustment, market_data
                    )
                    
                    if adjustment.adjustment_factor != 1.0:
                        strategy_adjustments += 1
                        total_adjustments += 1
                
                if strategy_adjustments > 0:
                    affected_strategies.append(strategy_name)
                    self.logger.info(f"  총 {strategy_adjustments}개 파라미터 조정됨")
                else:
                    self.logger.info(f"  조정 없음 (기본값 유지)")
            
            # 체제 변경 로깅
            self.log_regime_change(regime_result, affected_strategies, total_adjustments)
            
            self.logger.info(f"\n✅ 일괄 조정 완료: {len(affected_strategies)}개 전략, {total_adjustments}개 파라미터")
            
        except Exception as e:
            self.logger.error(f"일괄 조정 로깅 오류: {e}")
    
    def _append_to_json_log(self, log_file: Path, data: Dict[str, Any]):
        """JSON 로그 파일에 데이터 추가"""
        try:
            # 기존 데이터 로드
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            # 새 데이터 추가
            logs.append(data)
            
            # 최근 1000개만 유지
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            # 파일에 저장
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"JSON 로그 저장 오류: {e}")
    
    def get_recent_adjustments(self, hours: int = 24) -> List[Dict[str, Any]]:
        """최근 조정 내역 조회"""
        try:
            if not self.parameter_log_file.exists():
                return []
            
            with open(self.parameter_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 시간 필터링
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            recent_logs = []
            
            for log in logs:
                log_time = datetime.fromisoformat(log['timestamp']).timestamp()
                if log_time >= cutoff_time:
                    recent_logs.append(log)
            
            return recent_logs
            
        except Exception as e:
            self.logger.error(f"최근 조정 내역 조회 오류: {e}")
            return []
    
    def get_regime_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """체제 변경 이력 조회"""
        try:
            if not self.regime_log_file.exists():
                return []
            
            with open(self.regime_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # 시간 필터링
            cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
            recent_logs = []
            
            for log in logs:
                log_time = datetime.fromisoformat(log['timestamp']).timestamp()
                if log_time >= cutoff_time:
                    recent_logs.append(log)
            
            return recent_logs
            
        except Exception as e:
            self.logger.error(f"체제 이력 조회 오류: {e}")
            return []
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """요약 리포트 생성"""
        try:
            recent_adjustments = self.get_recent_adjustments(24)
            regime_history = self.get_regime_history(7)
            
            # 통계 계산
            strategy_stats = {}
            regime_stats = {}
            
            for adj in recent_adjustments:
                strategy = adj['strategy_name']
                regime = adj['regime']
                
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {'count': 0, 'regimes': set()}
                strategy_stats[strategy]['count'] += 1
                strategy_stats[strategy]['regimes'].add(regime)
                
                if regime not in regime_stats:
                    regime_stats[regime] = 0
                regime_stats[regime] += 1
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'period_hours': 24,
                'total_adjustments': len(recent_adjustments),
                'strategy_stats': {k: {'count': v['count'], 'regimes': list(v['regimes'])} 
                                for k, v in strategy_stats.items()},
                'regime_stats': regime_stats,
                'regime_changes': len(regime_history),
                'current_regime': self.previous_regime
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"요약 리포트 생성 오류: {e}")
            return {}


# 전역 인스턴스
parameter_logger = ParameterLogger()
