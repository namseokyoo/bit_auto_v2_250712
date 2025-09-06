"""
즉시 임계값 조정 스크립트
현재 전략들이 너무 보수적이어서 HOLD만 나오는 문제를 해결하기 위한 긴급 조정
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any

from config.config_manager import config_manager


class ImmediateThresholdAdjuster:
    """즉시 임계값 조정기"""
    
    def __init__(self):
        self.logger = logging.getLogger('ImmediateThresholdAdjuster')
        self.config = config_manager
        
        # 더 적극적인 임계값 설정
        self.aggressive_thresholds = {
            'rsi_momentum': {
                'oversold': 40,  # 30 → 40 (더 쉽게 매수 신호)
                'overbought': 60,  # 70 → 60 (더 쉽게 매도 신호)
                'momentum_threshold': 0.015,  # 0.02 → 0.015 (더 작은 움직임도 감지)
                'volume_threshold': 1.2  # 1.5 → 1.2 (더 낮은 거래량도 허용)
            },
            'bollinger_band': {
                'std_dev': 1.8,  # 2.0 → 1.8 (더 좁은 밴드)
                'volume_threshold': 1.1,  # 1.3 → 1.1
                'breakout_threshold': 0.008  # 0.01 → 0.008 (더 작은 브레이크아웃도 감지)
            },
            'support_resistance': {
                'strength_threshold': 0.7,  # 0.8 → 0.7 (더 약한 지지저항도 인정)
                'volume_threshold': 1.1,  # 1.2 → 1.1
                'break_threshold': 0.004  # 0.005 → 0.004
            },
            'ema_crossover': {
                'volume_threshold': 1.1,  # 1.2 → 1.1
                'min_crossover_strength': 0.0008  # 0.001 → 0.0008 (더 약한 크로스오버도 감지)
            },
            'macd': {
                'signal_threshold': 0.00008,  # 0.0001 → 0.00008
                'volume_threshold': 1.05,  # 1.1 → 1.05
                'divergence_threshold': 0.4  # 0.5 → 0.4
            },
            'stochastic': {
                'oversold': 25,  # 20 → 25
                'overbought': 75,  # 80 → 75
                'volume_threshold': 1.1  # 1.2 → 1.1
            },
            'williams_r': {
                'oversold': -75,  # -80 → -75
                'overbought': -25,  # -20 → -25
                'volume_threshold': 1.05  # 1.1 → 1.05
            },
            'cci': {
                'oversold': -80,  # -100 → -80
                'overbought': 80,  # 100 → 80
                'volume_threshold': 1.05  # 1.1 → 1.05
            },
            'volume_surge': {
                'surge_threshold': 1.5,  # 2.0 → 1.5 (더 낮은 거래량 급증도 감지)
                'price_threshold': 0.008  # 0.01 → 0.008
            },
            'price_action': {
                'breakout_threshold': 0.006,  # 0.008 → 0.006
                'volume_threshold': 1.1  # 1.3 → 1.1
            }
        }
        
        self.logger.info("ImmediateThresholdAdjuster 초기화 완료")
    
    def apply_aggressive_thresholds(self) -> bool:
        """적극적인 임계값 적용"""
        try:
            self.logger.info("🚀 적극적인 임계값 적용 시작...")
            
            applied_count = 0
            
            for strategy_id, thresholds in self.aggressive_thresholds.items():
                for param, new_value in thresholds.items():
                    # 설정 파일에 저장
                    config_key = f"strategies.{strategy_id}.{param}"
                    old_value = self.config.get_config(config_key)
                    
                    self.config.set_config(config_key, new_value)
                    applied_count += 1
                    
                    self.logger.info(
                        f"임계값 조정: {strategy_id}.{param} "
                        f"{old_value} → {new_value}"
                    )
            
            # 투표 엔진 설정도 조정
            self._adjust_voting_settings()
            
            self.logger.info(f"✅ 적극적인 임계값 적용 완료: {applied_count}개 조정")
            return True
            
        except Exception as e:
            self.logger.error(f"임계값 적용 오류: {e}")
            return False
    
    def _adjust_voting_settings(self):
        """투표 엔진 설정 조정"""
        try:
            # 투표 엔진을 더 적극적으로 설정
            voting_config = {
                'min_confidence': 0.3,  # 기본값보다 낮춤
                'min_votes': 3,  # 기본값보다 낮춤
                'weight_threshold': 0.4,  # 기본값보다 낮춤
                'enabled': True
            }
            
            for key, value in voting_config.items():
                self.config.set_config(f"voting_engine.{key}", value)
            
            self.logger.info("투표 엔진 설정 조정 완료")
            
        except Exception as e:
            self.logger.error(f"투표 엔진 설정 조정 오류: {e}")
    
    def create_backup(self) -> str:
        """현재 설정 백업"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"config/threshold_backup_{timestamp}.json"
            
            # 현재 설정 백업
            backup_data = {}
            for strategy_id in self.aggressive_thresholds.keys():
                strategy_config = {}
                for param in self.aggressive_thresholds[strategy_id].keys():
                    config_key = f"strategies.{strategy_id}.{param}"
                    strategy_config[param] = self.config.get_config(config_key)
                backup_data[strategy_id] = strategy_config
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"설정 백업 완료: {backup_file}")
            return backup_file
            
        except Exception as e:
            self.logger.error(f"백업 생성 오류: {e}")
            return ""
    
    def get_threshold_summary(self) -> Dict[str, Any]:
        """임계값 요약 정보"""
        summary = {
            'adjustment_time': datetime.now().isoformat(),
            'strategies': {},
            'total_adjustments': 0
        }
        
        try:
            for strategy_id, thresholds in self.aggressive_thresholds.items():
                strategy_summary = {
                    'parameters': thresholds,
                    'adjustment_count': len(thresholds)
                }
                summary['strategies'][strategy_id] = strategy_summary
                summary['total_adjustments'] += len(thresholds)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"요약 생성 오류: {e}")
            return summary


# 전역 인스턴스
immediate_adjuster = ImmediateThresholdAdjuster()


def apply_immediate_threshold_adjustment():
    """즉시 임계값 조정 실행"""
    try:
        # 백업 생성
        backup_file = immediate_adjuster.create_backup()
        
        # 적극적인 임계값 적용
        success = immediate_adjuster.apply_aggressive_thresholds()
        
        if success:
            summary = immediate_adjuster.get_threshold_summary()
            print(f"✅ 즉시 임계값 조정 완료!")
            print(f"📊 총 {summary['total_adjustments']}개 파라미터 조정")
            print(f"💾 백업 파일: {backup_file}")
            return True
        else:
            print("❌ 임계값 조정 실패")
            return False
            
    except Exception as e:
        print(f"❌ 임계값 조정 오류: {e}")
        return False


if __name__ == "__main__":
    # 직접 실행시 즉시 조정 적용
    apply_immediate_threshold_adjustment()
