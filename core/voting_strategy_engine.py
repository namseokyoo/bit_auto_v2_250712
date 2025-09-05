"""
투표 기반 전략 엔진 (Voting Strategy Engine)
독립 전략들의 투표를 통한 통합 의사결정 시스템
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.independent_strategy_engine import (
    IndependentStrategyEngine, VotingDecision, StrategySignal
)
from core.independent_strategies import (
    RSIMomentumStrategy, BollingerBandStrategy, SupportResistanceStrategy
)
from core.phase2_strategies import (
    EMACrossoverStrategy, MACDStrategy, StochasticStrategy,
    WilliamsRStrategy, CCIStrategy, VolumeSurgeStrategy, PriceActionStrategy
)
from core.upbit_api import UpbitAPI
from core.signal_manager import TradingSignal
from core.strategy_execution_tracker import execution_tracker, StrategyExecution
from core.regime_detector import RegimeDetector
from core.dynamic_threshold_manager import DynamicThresholdManager
from core.strategy_adapter import StrategyAdapter
from config.config_manager import config_manager


@dataclass
class VotingResult:
    """투표 결과"""
    decision: VotingDecision
    execution_time: datetime
    market_data_summary: Dict[str, Any]

    def to_trading_signal(self, price: float, amount: float) -> Optional[TradingSignal]:
        """TradingSignal로 변환"""
        if self.decision.final_signal == StrategySignal.HOLD:
            return None

        return TradingSignal(
            strategy_id="voting_engine",
            action=self.decision.final_signal.value,
            confidence=self.decision.confidence,
            price=price,
            suggested_amount=amount,
            reasoning=self.decision.reasoning,
            timestamp=self.execution_time,
            timeframe="multi"
        )


class VotingStrategyEngine:
    """투표 기반 전략 엔진"""

    def __init__(self, upbit_api: UpbitAPI):
        self.upbit_api = upbit_api
        self.logger = logging.getLogger('VotingStrategyEngine')

        # 독립 전략 엔진 초기화
        self.engine = IndependentStrategyEngine(upbit_api)

        # 체제 기반 동적 임계값 시스템 초기화
        self.regime_detector = RegimeDetector(upbit_api)
        self.threshold_manager = DynamicThresholdManager()
        self.strategy_adapter = StrategyAdapter(self.regime_detector, self.threshold_manager)

        # 전략 등록
        self._register_strategies()

        # 설정 로드
        self._load_config()

        self.logger.info("VotingStrategyEngine 초기화 완료 (체제 기반 동적 임계값 통합)")

    def _register_strategies(self):
        """전략들 등록"""
        strategies = [
            # Phase 1 기본 전략들
            (RSIMomentumStrategy(), 1.0),
            (BollingerBandStrategy(), 1.0),
            (SupportResistanceStrategy(), 1.0),

            # Phase 2 추가 전략들
            (EMACrossoverStrategy(), 1.0),
            (MACDStrategy(), 1.0),
            (StochasticStrategy(), 1.0),
            (WilliamsRStrategy(), 1.0),
            (CCIStrategy(), 1.0),
            (VolumeSurgeStrategy(), 1.0),
            (PriceActionStrategy(), 1.0)
        ]

        for strategy, weight in strategies:
            self.engine.register_strategy(strategy, weight)

        self.logger.info(
            f"🎯 총 {len(strategies)}개 전략 등록 완료 (Phase 1: 3개 + Phase 2: 7개)")

    def _load_config(self):
        """설정 로드"""
        try:
            config = config_manager.get_config('voting_strategy_engine') or {}
            self.config = {
                'enabled': config.get('enabled', True),
                'min_confidence_threshold': config.get('min_confidence_threshold', 0.5),
                'max_trade_amount': config.get('max_trade_amount', 100000),
                'trade_amount_ratio': config.get('trade_amount_ratio', 0.3),
                'record_all_decisions': config.get('record_all_decisions', True)
            }
        except Exception as e:
            self.logger.error(f"설정 로드 오류: {e}")
            self.config = {
                'enabled': True,
                'min_confidence_threshold': 0.5,
                'max_trade_amount': 100000,
                'trade_amount_ratio': 0.3,
                'record_all_decisions': True
            }

    def analyze(self) -> Optional[VotingResult]:
        """시장 분석 및 투표 결과"""
        if not self.config.get('enabled', True):
            self.logger.info("VotingStrategyEngine 비활성화됨")
            return None

        try:
            # 0) 체제 기반 동적 임계값 적용
            try:
                self._apply_regime_based_thresholds()
            except Exception as e:
                self.logger.error(f"체제 기반 임계값 적용 오류: {e}")

            # 독립 전략 엔진으로 분석
            decision = self.engine.analyze_market()

            if not decision:
                self.logger.warning("투표 결정 생성 실패")
                return None

            # 결과 생성
            result = VotingResult(
                decision=decision,
                execution_time=datetime.now(),
                market_data_summary=self._get_market_summary()
            )

            # 실행 기록 저장
            if self.config.get('record_all_decisions', True):
                self._record_execution(result)

            # 로그 출력
            self.logger.info(
                f"투표 결과: {decision.final_signal.value.upper()} "
                f"(신뢰도: {decision.confidence:.3f}, 투표수: {decision.total_votes})"
            )

            return result

        except Exception as e:
            self.logger.error(f"분석 오류: {e}")
            return None

    def _apply_regime_based_thresholds(self):
        """체제 기반 동적 임계값 적용"""
        try:
            # 현재 시장 체제 감지
            regime_result = self.regime_detector.detect_regime()
            if not regime_result:
                self.logger.warning("체제 감지 실패, 기본 임계값 사용")
                return
            
            # 체제 정보 로깅
            self.logger.info(f"🔍 시장 체제 감지: {regime_result.primary_regime.value} "
                           f"(신뢰도: {regime_result.confidence:.3f})")
            self.logger.info(f"📊 판단 근거: {regime_result.reasoning}")
            
            # 모든 전략의 동적 임계값 계산
            all_thresholds = self.threshold_manager.get_all_strategy_thresholds(regime_result)
            
            if all_thresholds:
                self.logger.info(f"🎯 {len(all_thresholds)}개 전략에 동적 임계값 적용")
                
                # 임계값 변경사항 로깅
                self.threshold_manager.log_threshold_changes(regime_result)
                
                # 전략 어댑터에 체제 정보 업데이트
                self.strategy_adapter.force_regime_update()
                
            else:
                self.logger.warning("동적 임계값 계산 실패, 기본 임계값 사용")
                
        except Exception as e:
            self.logger.error(f"체제 기반 임계값 적용 중 오류: {e}")
            raise

    def get_regime_info(self) -> Dict[str, Any]:
        """현재 체제 정보 반환"""
        try:
            regime_result = self.regime_detector.detect_regime()
            if not regime_result:
                return {"status": "unavailable", "message": "체제 감지 불가"}
            
            return {
                "status": "active",
                "regime": regime_result.primary_regime.value,
                "secondary_regime": regime_result.secondary_regime.value if regime_result.secondary_regime else None,
                "confidence": regime_result.confidence,
                "reasoning": regime_result.reasoning,
                "timestamp": regime_result.timestamp.isoformat(),
                "metrics": {
                    "rsi": regime_result.metrics.rsi,
                    "atr": regime_result.metrics.atr,
                    "volume_ratio": regime_result.metrics.volume_ratio,
                    "price_vs_ema50": regime_result.metrics.price_vs_ema50,
                    "price_vs_ema200": regime_result.metrics.price_vs_ema200
                }
            }
        except Exception as e:
            self.logger.error(f"체제 정보 조회 오류: {e}")
            return {"status": "error", "message": str(e)}

    def get_threshold_adjustments(self) -> Dict[str, Any]:
        """현재 적용된 임계값 조정사항 반환"""
        try:
            regime_result = self.regime_detector.detect_regime()
            if not regime_result:
                return {"status": "unavailable", "message": "체제 감지 불가"}
            
            return self.threshold_manager.get_adjustment_summary(regime_result)
        except Exception as e:
            self.logger.error(f"임계값 조정사항 조회 오류: {e}")
            return {"status": "error", "message": str(e)}

    def should_execute_trade(self, result: VotingResult) -> bool:
        """거래 실행 여부 판단"""
        if not result or result.decision.final_signal == StrategySignal.HOLD:
            return False

        # 최소 신뢰도 확인
        min_confidence = self.config.get('min_confidence_threshold', 0.5)
        if result.decision.confidence < min_confidence:
            self.logger.info(
                f"신뢰도 부족으로 거래 보류 ({result.decision.confidence:.3f} < {min_confidence})"
            )
            return False

        return True

    def calculate_trade_amount(self, result: VotingResult) -> int:
        """거래 금액 계산"""
        try:
            base_amount = self.config.get('max_trade_amount', 100000)
            ratio = self.config.get('trade_amount_ratio', 0.3)

            # 신뢰도에 따른 조정
            confidence_multiplier = result.decision.confidence

            # 참여 전략 수에 따른 조정
            participation_multiplier = min(
                1.0, result.decision.total_votes / 3)

            calculated_amount = int(
                base_amount * ratio * confidence_multiplier * participation_multiplier
            )

            # 최소 1만원, 최대 설정값
            return max(10000, min(calculated_amount, base_amount))

        except Exception as e:
            self.logger.error(f"거래 금액 계산 오류: {e}")
            return 50000  # 기본값

    def get_trading_signal(self) -> Optional[TradingSignal]:
        """거래 신호 생성 (항상 실행 기록 저장)"""
        try:
            # 항상 분석 수행 및 기록 저장
            result = self.analyze()

            if not result:
                self.logger.warning("투표 분석 결과가 없습니다")
                return None

            # 거래 실행 여부와 관계없이 분석은 완료되었음
            # (analyze()에서 이미 _record_execution 호출됨)

            # 거래 신호 생성 여부 판단
            if not self.should_execute_trade(result):
                self.logger.info(
                    f"거래 조건 미충족 - 신호: {result.decision.final_signal.value}, 신뢰도: {result.decision.confidence:.3f}")
                return None

            # 현재가 조회
            ticker = self.upbit_api._make_request(
                'GET', '/v1/ticker', {'markets': 'KRW-BTC'})
            current_price = float(ticker[0]['trade_price']) if ticker else 0

            if current_price <= 0:
                self.logger.error("현재가 조회 실패")
                return None

            # 거래 금액 계산
            trade_amount = self.calculate_trade_amount(result)

            # TradingSignal 생성
            self.logger.info(
                f"거래 신호 생성: {result.decision.final_signal.value} (신뢰도: {result.decision.confidence:.3f})")
            return result.to_trading_signal(current_price, trade_amount)

        except Exception as e:
            self.logger.error(f"거래 신호 생성 오류: {e}")
            return None

    def _record_execution(self, result: VotingResult):
        """실행 기록 저장"""
        try:
            # 전략별 기여도 계산
            tier_contributions = {}

            for vote in result.decision.contributing_strategies:
                tier_contributions[vote.strategy_id] = {
                    'signal': vote.signal.value,
                    'confidence': vote.confidence,
                    'strength': vote.strength,
                    'reasoning': vote.reasoning
                }

            # StrategyExecution 생성
            execution = StrategyExecution(
                strategy_tier="voting",
                strategy_id="voting_engine",
                execution_time=result.execution_time,
                signal_action=result.decision.final_signal.value,
                confidence=result.decision.confidence,
                strength=result.decision.confidence,  # 투표 기반이므로 신뢰도와 동일
                reasoning=result.decision.reasoning,
                market_regime=getattr(self, "_last_market_regime", "unknown"),
                indicators={
                    'vote_distribution': result.decision.vote_distribution,
                    'tier_contributions': tier_contributions,
                    'total_votes': result.decision.total_votes,
                    'market_regime': getattr(self, "_last_market_regime", "unknown")
                },
                trade_executed=False,  # 실제 거래 여부는 나중에 업데이트
                trade_id=None,
                pnl=0.0
            )

            # 저장
            execution_tracker.record_execution(execution)

        except Exception as e:
            self.logger.error(f"실행 기록 저장 오류: {e}")

    def _get_market_summary(self) -> Dict[str, Any]:
        """시장 데이터 요약"""
        try:
            # 현재가 정보
            ticker = self.upbit_api._make_request(
                'GET', '/v1/ticker', {'markets': 'KRW-BTC'})

            if ticker:
                current_data = ticker[0]
                return {
                    'current_price': float(current_data['trade_price']),
                    'change_rate': float(current_data['signed_change_rate']),
                    'volume': float(current_data['acc_trade_volume_24h']),
                    'timestamp': datetime.now().isoformat()
                }

            return {}

        except Exception as e:
            self.logger.error(f"시장 요약 생성 오류: {e}")
            return {}

    # -----------------------------
    # Regime-based dynamic weighting
    # -----------------------------
    def _detect_market_regime(self) -> str:
        """간단한 레짐 탐지 (상승/하락/횡보) - 현재가 변화율 기준"""
        try:
            summary = self._get_market_summary() or {}
            change_rate = summary.get('change_rate')
            if change_rate is None:
                return 'sideways'

            # 임계값: ±1% (단기)
            if change_rate >= 0.01:
                return 'bullish'
            if change_rate <= -0.01:
                return 'bearish'
            return 'sideways'
        except Exception:
            return 'sideways'

    def _apply_regime_based_weights(self) -> None:
        """레짐에 따라 전략 가중치 동적 조정 (설정 없으면 기본 매핑 사용)"""
        regime = self._detect_market_regime()
        self._last_market_regime = regime

        # 설정에서 레짐 가중치 로드 (없으면 기본)
        cfg = config_manager.get_config('voting_strategy_engine.regime_weights') or {}

        default_map = {
            'bullish': {
                'ema_crossover': 1.5,
                'macd_signal': 1.3,
                'rsi_momentum': 1.2,
                'support_resistance': 0.9,
                'price_action': 0.9
            },
            'bearish': {
                'ema_crossover': 1.2,
                'macd_signal': 1.4,
                'rsi_momentum': 1.1,
                'support_resistance': 1.1,
                'price_action': 1.0
            },
            'sideways': {
                'bollinger_squeeze': 1.4,
                'stochastic_oscillator': 1.2,
                'price_action': 1.2,
                'ema_crossover': 0.8,
                'macd_signal': 0.9
            }
        }

        regime_weights = cfg.get(regime, {}) or default_map.get(regime, {})

        # 기존 기본 가중치(IndependentStrategyEngine 로드) 위에 멀티플라이어 적용
        # IndependentStrategyEngine은 strategy_weights를 1.0로 초기화했을 수 있음.
        # 여기서는 곱셈 방식으로 적용하기 위해 현재 가중치를 읽을 수 없으므로
        # 멀티플라이어를 절대 가중치로 해석(없으면 1.0) → 실무에서는 기준가중치*멀티플라이어 권장
        for strategy_id, weight in regime_weights.items():
            try:
                self.engine.voting_manager.set_strategy_weight(strategy_id, float(weight))
            except Exception as e:
                self.logger.error(f"가중치 적용 실패: {strategy_id}={weight} ({e})")

    def get_engine_status(self) -> Dict[str, Any]:
        """엔진 상태 정보"""
        try:
            strategy_summary = self.engine.get_strategy_summary()

            return {
                'engine_type': 'VotingStrategyEngine',
                'enabled': self.config.get('enabled', True),
                'strategies': strategy_summary['strategy_list'],
                'total_strategies': strategy_summary['total_strategies'],
                'enabled_strategies': strategy_summary['enabled_strategies'],
                'config': self.config,
                'last_updated': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"상태 조회 오류: {e}")
            return {
                'engine_type': 'VotingStrategyEngine',
                'enabled': False,
                'error': str(e)
            }

    def update_strategy_weights(self, weights: Dict[str, float]):
        """전략 가중치 업데이트"""
        try:
            for strategy_id, weight in weights.items():
                self.engine.voting_manager.set_strategy_weight(
                    strategy_id, weight)

            self.logger.info(f"전략 가중치 업데이트 완료: {weights}")

        except Exception as e:
            self.logger.error(f"가중치 업데이트 오류: {e}")

    def get_recent_decisions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """최근 결정 내역 조회"""
        try:
            executions = execution_tracker.get_execution_history(
                strategy_tier="voting",
                hours=hours
            )

            return [
                {
                    'timestamp': exec_data.get('execution_time'),
                    'signal': exec_data.get('signal_action'),
                    'confidence': exec_data.get('confidence'),
                    'reasoning': exec_data.get('reasoning'),
                    'vote_distribution': exec_data.get('indicators', {}).get('vote_distribution', {}),
                    'total_votes': exec_data.get('indicators', {}).get('total_votes', 0),
                    'trade_executed': exec_data.get('trade_executed', False)
                }
                for exec_data in executions
            ]

        except Exception as e:
            self.logger.error(f"최근 결정 조회 오류: {e}")
            return []


# 전역 인스턴스 (필요시 사용)
voting_engine = None


def get_voting_engine(upbit_api: UpbitAPI = None) -> VotingStrategyEngine:
    """VotingStrategyEngine 인스턴스 반환"""
    global voting_engine

    if voting_engine is None and upbit_api is not None:
        voting_engine = VotingStrategyEngine(upbit_api)

    return voting_engine
