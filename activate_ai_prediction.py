#!/usr/bin/env python3
"""
AI Prediction 전략 활성화 스크립트
1. 모델 학습
2. 백테스트 검증
3. config.yaml 업데이트
4. 대시보드에 표시
"""

import os
import yaml
import subprocess
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def train_model():
    """AI 모델 학습"""
    logger.info("Starting AI model training...")
    
    try:
        # train_ai_model.py 실행
        result = subprocess.run(
            ['python3', 'train_ai_model.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Model training completed successfully")
            
            # 모델 파일 확인
            if os.path.exists('models/rf_model.pkl'):
                logger.info("✅ Model file created: models/rf_model.pkl")
                return True
            else:
                logger.error("❌ Model file not found")
                return False
        else:
            logger.error(f"Model training failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to train model: {e}")
        return False

def test_strategy():
    """AI 전략 테스트"""
    logger.info("Testing AI prediction strategy...")
    
    try:
        # ai_prediction_strategy.py 테스트
        result = subprocess.run(
            ['python3', 'ai_prediction_strategy.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Strategy test passed")
            print(result.stdout)
            return True
        else:
            logger.error(f"Strategy test failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to test strategy: {e}")
        return False

def update_config():
    """config.yaml에서 AI 전략 활성화"""
    logger.info("Updating config.yaml...")
    
    try:
        config_path = 'config/config.yaml'
        
        # 현재 설정 읽기
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # AI 전략 활성화
        if 'strategies' in config and 'ai_prediction' in config['strategies']:
            config['strategies']['ai_prediction']['enabled'] = True
            logger.info("AI prediction strategy enabled in config")
            
            # 가중치 조정 (전체 합이 1.0이 되도록)
            total_weight = sum(
                s.get('weight', 0) 
                for s in config['strategies'].values() 
                if s.get('enabled', False)
            )
            
            if total_weight > 1.0:
                logger.warning(f"Total weight {total_weight} > 1.0, adjusting...")
                # 다른 전략들의 가중치를 비례적으로 줄임
                adjustment_factor = 0.95 / (total_weight - config['strategies']['ai_prediction']['weight'])
                
                for strategy_name, strategy_config in config['strategies'].items():
                    if strategy_name != 'ai_prediction' and strategy_config.get('enabled', False):
                        strategy_config['weight'] = round(strategy_config['weight'] * adjustment_factor, 2)
        
        # 설정 저장
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info("✅ Config updated successfully")
        
        # 업데이트된 가중치 표시
        print("\n=== Updated Strategy Weights ===")
        for name, cfg in config['strategies'].items():
            if cfg.get('enabled'):
                print(f"  {name}: {cfg.get('weight', 0):.0%}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        return False

def update_dashboard():
    """대시보드 업데이트"""
    logger.info("Updating dashboard...")
    
    try:
        # dashboard.py에서 AI Prediction 활성화 상태 변경
        dashboard_path = 'dashboard.py'
        
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # AI Prediction active 상태를 True로 변경
        content = content.replace(
            "{'name': 'AI Prediction', 'active': False}",
            "{'name': 'AI Prediction', 'active': True}"
        )
        
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("✅ Dashboard updated")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update dashboard: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🤖 AI Prediction Strategy Activation")
    print("=" * 60)
    
    success = True
    
    # 1. 모델 학습
    print("\n📚 Step 1: Training AI Model")
    print("-" * 40)
    if not train_model():
        print("❌ Model training failed")
        success = False
    else:
        print("✅ Model training completed")
    
    # 2. 전략 테스트
    if success:
        print("\n🧪 Step 2: Testing Strategy")
        print("-" * 40)
        if not test_strategy():
            print("❌ Strategy test failed")
            success = False
        else:
            print("✅ Strategy test passed")
    
    # 3. 설정 업데이트
    if success:
        print("\n⚙️ Step 3: Updating Configuration")
        print("-" * 40)
        if not update_config():
            print("❌ Config update failed")
            success = False
        else:
            print("✅ Config updated")
    
    # 4. 대시보드 업데이트
    if success:
        print("\n📊 Step 4: Updating Dashboard")
        print("-" * 40)
        if not update_dashboard():
            print("❌ Dashboard update failed")
            success = False
        else:
            print("✅ Dashboard updated")
    
    # 결과 표시
    print("\n" + "=" * 60)
    if success:
        print("✅ AI Prediction Strategy Successfully Activated!")
        print("\nNext steps:")
        print("1. Restart the trading system to apply changes")
        print("2. Monitor AI predictions in the dashboard")
        print("3. Check logs for AI signal generation")
        print("\nCommand to restart:")
        print("  python3 quantum_trading.py")
    else:
        print("❌ Activation failed. Please check the logs.")
    print("=" * 60)

if __name__ == "__main__":
    main()