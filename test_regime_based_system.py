"""
체제 기반 동적 임계값 시스템 통합 테스트
"""

import sys
import os
import logging
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.regime_detector import RegimeDetector, MarketRegime
from core.dynamic_threshold_manager import DynamicThresholdManager
from core.strategy_adapter import StrategyAdapter
from core.upbit_api import UpbitAPI
from core.voting_strategy_engine import VotingStrategyEngine
from core.independent_strategies import RSIMomentumStrategy, BollingerBandStrategy
from config.config_manager import config_manager


def setup_logging():
    """로깅 설정"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/regime_test.log')
        ]
    )


def test_regime_detection():
    """체제 감지 테스트"""
    print("\n=== 체제 감지 테스트 ===")
    
    try:
        upbit_api = UpbitAPI()
        regime_detector = RegimeDetector(upbit_api)
        
        # 체제 감지 실행
        regime_result = regime_detector.detect_regime("KRW-BTC")
        
        if regime_result:
            print(f"✅ 체제 감지 성공:")
            print(f"   주요 체제: {regime_result.primary_regime.value}")
            print(f"   보조 체제: {regime_result.secondary_regime.value if regime_result.secondary_regime else 'None'}")
            print(f"   신뢰도: {regime_result.confidence:.3f}")
            print(f"   판단 근거: {regime_result.reasoning}")
            print(f"   RSI: {regime_result.metrics.rsi:.2f}")
            print(f"   ATR: {regime_result.metrics.atr:.4f}")
            print(f"   거래량 비율: {regime_result.metrics.volume_ratio:.2f}")
            
            # 체제별 점수 출력
            print(f"   체제별 점수:")
            for regime, score in regime_result.regime_scores.items():
                print(f"     {regime.value}: {score:.3f}")
            
            return regime_result
        else:
            print("❌ 체제 감지 실패")
            return None
            
    except Exception as e:
        print(f"❌ 체제 감지 테스트 오류: {e}")
        return None


def test_dynamic_thresholds(regime_result):
    """동적 임계값 테스트"""
    print("\n=== 동적 임계값 테스트 ===")
    
    if not regime_result:
        print("❌ 체제 정보 없음, 테스트 건너뜀")
        return None
    
    try:
        threshold_manager = DynamicThresholdManager()
        
        # RSI 전략의 동적 임계값 계산
        rsi_thresholds = threshold_manager.get_dynamic_thresholds(regime_result, "rsi_momentum")
        
        if rsi_thresholds:
            print(f"✅ RSI 전략 동적 임계값 계산 성공:")
            print(f"   체제: {rsi_thresholds.regime.value}")
            print(f"   신뢰도: {rsi_thresholds.confidence:.3f}")
            print(f"   조정된 파라미터:")
            
            for param_name, adjustment in rsi_thresholds.adjustments.items():
                print(f"     {param_name}: {adjustment.base_value:.3f} -> {adjustment.adjusted_value:.3f} "
                      f"(x{adjustment.adjustment_factor:.2f})")
                print(f"       이유: {adjustment.adjustment_reason}")
            
            return rsi_thresholds
        else:
            print("❌ 동적 임계값 계산 실패")
            return None
            
    except Exception as e:
        print(f"❌ 동적 임계값 테스트 오류: {e}")
        return None


def test_strategy_adapter(regime_result):
    """전략 어댑터 테스트"""
    print("\n=== 전략 어댑터 테스트 ===")
    
    if not regime_result:
        print("❌ 체제 정보 없음, 테스트 건너뜀")
        return None
    
    try:
        upbit_api = UpbitAPI()
        regime_detector = RegimeDetector(upbit_api)
        threshold_manager = DynamicThresholdManager()
        strategy_adapter = StrategyAdapter(regime_detector, threshold_manager)
        
        # RSI 전략 생성
        rsi_strategy = RSIMomentumStrategy()
        
        # 기본 설정
        base_config = {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "momentum_threshold": 0.002
        }
        
        # 가상의 시장 데이터
        market_data = {
            "candles": [],  # 실제로는 캔들 데이터가 필요
            "current_price": 50000000,
            "volume": 1000000
        }
        
        print(f"✅ 전략 어댑터 초기화 성공")
        print(f"   기본 설정: {base_config}")
        
        # 체제 요약 정보
        summary = strategy_adapter.get_regime_summary()
        print(f"   현재 체제: {summary.get('regime', 'Unknown')}")
        print(f"   신뢰도: {summary.get('confidence', 0):.3f}")
        
        return strategy_adapter
        
    except Exception as e:
        print(f"❌ 전략 어댑터 테스트 오류: {e}")
        return None


def test_voting_engine_integration():
    """VotingStrategyEngine 통합 테스트"""
    print("\n=== VotingStrategyEngine 통합 테스트 ===")
    
    try:
        upbit_api = UpbitAPI()
        
        # 기존 VotingStrategyEngine
        voting_engine = VotingStrategyEngine(upbit_api)
        
        # 체제 기반 시스템
        regime_detector = RegimeDetector(upbit_api)
        threshold_manager = DynamicThresholdManager()
        strategy_adapter = StrategyAdapter(regime_detector, threshold_manager)
        
        print(f"✅ 모든 컴포넌트 초기화 성공")
        
        # 체제 감지
        regime_result = regime_detector.detect_regime()
        if regime_result:
            print(f"   현재 체제: {regime_result.primary_regime.value}")
            print(f"   신뢰도: {regime_result.confidence:.3f}")
        
        # 투표 엔진 분석 (기존 방식)
        voting_result = voting_engine.analyze()
        if voting_result:
            print(f"   투표 결과: {voting_result.decision.final_signal.value}")
            print(f"   신뢰도: {voting_result.decision.confidence:.3f}")
            print(f"   투표수: {voting_result.decision.total_votes}")
        
        return {
            "voting_engine": voting_engine,
            "regime_detector": regime_detector,
            "threshold_manager": threshold_manager,
            "strategy_adapter": strategy_adapter,
            "regime_result": regime_result,
            "voting_result": voting_result
        }
        
    except Exception as e:
        print(f"❌ VotingStrategyEngine 통합 테스트 오류: {e}")
        return None


def test_performance_comparison():
    """성능 비교 테스트"""
    print("\n=== 성능 비교 테스트 ===")
    
    try:
        upbit_api = UpbitAPI()
        
        # 체제 기반 시스템 초기화
        regime_detector = RegimeDetector(upbit_api)
        threshold_manager = DynamicThresholdManager()
        
        # 체제 감지 시간 측정
        start_time = datetime.now()
        regime_result = regime_detector.detect_regime()
        detection_time = (datetime.now() - start_time).total_seconds()
        
        if regime_result:
            print(f"✅ 체제 감지 성능:")
            print(f"   감지 시간: {detection_time:.3f}초")
            print(f"   체제: {regime_result.primary_regime.value}")
            print(f"   신뢰도: {regime_result.confidence:.3f}")
            
            # 동적 임계값 계산 시간 측정
            start_time = datetime.now()
            all_thresholds = threshold_manager.get_all_strategy_thresholds(regime_result)
            calculation_time = (datetime.now() - start_time).total_seconds()
            
            print(f"   임계값 계산 시간: {calculation_time:.3f}초")
            print(f"   적용된 전략 수: {len(all_thresholds)}")
            
            # 총 처리 시간
            total_time = detection_time + calculation_time
            print(f"   총 처리 시간: {total_time:.3f}초")
            
            if total_time < 5.0:  # 5초 이내면 양호
                print(f"   ✅ 성능 양호 (5초 이내)")
            else:
                print(f"   ⚠️ 성능 개선 필요 (5초 초과)")
        
        return True
        
    except Exception as e:
        print(f"❌ 성능 비교 테스트 오류: {e}")
        return False


def test_configuration_loading():
    """설정 파일 로딩 테스트"""
    print("\n=== 설정 파일 로딩 테스트 ===")
    
    try:
        import json
        
        # 체제 기반 설정 파일 로드
        with open('config/regime_based_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"✅ 설정 파일 로드 성공")
        print(f"   체제 감지 활성화: {config['regime_detection']['enabled']}")
        print(f"   업데이트 간격: {config['regime_detection']['update_interval_minutes']}분")
        print(f"   신뢰도 임계값: {config['regime_detection']['confidence_threshold']}")
        print(f"   지원 체제 수: {len(config['regime_adjustments'])}")
        print(f"   기본 전략 수: {len(config['base_thresholds'])}")
        
        return config
        
    except Exception as e:
        print(f"❌ 설정 파일 로딩 테스트 오류: {e}")
        return None


def main():
    """메인 테스트 함수"""
    print("🚀 체제 기반 동적 임계값 시스템 통합 테스트 시작")
    print("=" * 60)
    
    # 로깅 설정
    setup_logging()
    
    # 테스트 결과 저장
    test_results = {}
    
    # 1. 설정 파일 로딩 테스트
    config = test_configuration_loading()
    test_results['config_loading'] = config is not None
    
    # 2. 체제 감지 테스트
    regime_result = test_regime_detection()
    test_results['regime_detection'] = regime_result is not None
    
    # 3. 동적 임계값 테스트
    thresholds = test_dynamic_thresholds(regime_result)
    test_results['dynamic_thresholds'] = thresholds is not None
    
    # 4. 전략 어댑터 테스트
    adapter = test_strategy_adapter(regime_result)
    test_results['strategy_adapter'] = adapter is not None
    
    # 5. VotingStrategyEngine 통합 테스트
    integration = test_voting_engine_integration()
    test_results['integration'] = integration is not None
    
    # 6. 성능 비교 테스트
    performance = test_performance_comparison()
    test_results['performance'] = performance
    
    # 테스트 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ 통과" if result else "❌ 실패"
        print(f"   {test_name}: {status}")
    
    print(f"\n총 {total_tests}개 테스트 중 {passed_tests}개 통과")
    
    if passed_tests == total_tests:
        print("🎉 모든 테스트 통과! 체제 기반 동적 임계값 시스템이 정상 작동합니다.")
    else:
        print("⚠️ 일부 테스트 실패. 로그를 확인하여 문제를 해결하세요.")
    
    return test_results


if __name__ == "__main__":
    main()
