"""
전략 최적화 모듈
백테스팅 결과를 바탕으로 전략 파라미터를 자동 최적화
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import logging
import json
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy

from backtesting.backtester import Backtester, BacktestMetrics
from strategy_manager import StrategyManager

class StrategyOptimizer:
    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.logger = logging.getLogger('StrategyOptimizer')
        self.strategy_manager = StrategyManager()
        
        # 최적화 대상 파라미터 정의
        self.optimization_space = {
            'ema_cross': {
                'fast_period': [8, 10, 12, 14, 16],
                'slow_period': [21, 24, 26, 28, 30],
                'volume_threshold': [1.2, 1.5, 1.8, 2.0]
            },
            'rsi_divergence': {
                'rsi_period': [12, 14, 16, 18],
                'oversold_threshold': [25, 30, 35],
                'overbought_threshold': [65, 70, 75],
                'support_resistance_tolerance': [0.015, 0.02, 0.025]
            },
            'bollinger_band_strategy': {
                'period': [15, 20, 25],
                'std_multiplier': [1.5, 2.0, 2.5],
                'rsi_threshold': [35, 40, 45]
            },
            'macd_zero_cross': {
                'fast_period': [10, 12, 14],
                'slow_period': [24, 26, 28],
                'signal_period': [8, 9, 10]
            }
        }
        
        # 가중치 최적화 공간
        self.weight_space = {
            'h1_weight': [0.3, 0.4, 0.5, 0.6],
            'h4_weight': [0.2, 0.3, 0.4],
            'd1_weight': [0.1, 0.2, 0.3]
        }
    
    def optimize_single_strategy(self, strategy_id: str, start_date: datetime, 
                               end_date: datetime, max_combinations: int = 50) -> Dict:
        """단일 전략 파라미터 최적화"""
        self.logger.info(f"전략 {strategy_id} 최적화 시작")
        
        if strategy_id not in self.optimization_space:
            self.logger.warning(f"전략 {strategy_id}는 최적화 공간이 정의되지 않음")
            return {}
        
        param_space = self.optimization_space[strategy_id]
        
        # 파라미터 조합 생성
        param_names = list(param_space.keys())
        param_values = list(param_space.values())
        
        # 조합 수 제한
        all_combinations = list(itertools.product(*param_values))
        if len(all_combinations) > max_combinations:
            # 랜덤 샘플링
            np.random.seed(42)
            combinations = [all_combinations[i] for i in np.random.choice(
                len(all_combinations), max_combinations, replace=False)]
        else:
            combinations = all_combinations
        
        best_params = None
        best_score = -float('inf')
        results = []
        
        for i, combination in enumerate(combinations):
            try:
                # 파라미터 설정
                params = dict(zip(param_names, combination))
                
                # 전략 설정 업데이트
                strategy_config = self._create_strategy_config(strategy_id, params)
                
                # 백테스트 실행
                backtester = Backtester(self.initial_capital)
                metrics = backtester.run_backtest(start_date, end_date, strategy_config)
                
                # 점수 계산 (샤프 비율 + 수익률 조합)
                score = self._calculate_optimization_score(metrics)
                
                results.append({
                    'params': params,
                    'metrics': metrics,
                    'score': score
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
                
                self.logger.info(f"조합 {i+1}/{len(combinations)} - 점수: {score:.4f}")
                
            except Exception as e:
                self.logger.error(f"최적화 조합 {i+1} 실행 오류: {e}")
        
        return {
            'strategy_id': strategy_id,
            'best_params': best_params,
            'best_score': best_score,
            'all_results': results,
            'optimization_period': f"{start_date.date()} ~ {end_date.date()}"
        }
    
    def optimize_portfolio_weights(self, start_date: datetime, end_date: datetime) -> Dict:
        """포트폴리오 가중치 최적화"""
        self.logger.info("포트폴리오 가중치 최적화 시작")
        
        # 가중치 조합 생성
        weight_combinations = []
        
        for h1_w in self.weight_space['h1_weight']:
            for h4_w in self.weight_space['h4_weight']:
                for d1_w in self.weight_space['d1_weight']:
                    # 가중치 합이 1이 되도록 정규화
                    total = h1_w + h4_w + d1_w
                    if total > 0:
                        normalized_weights = {
                            'h1_weight': h1_w / total,
                            'h4_weight': h4_w / total,
                            'd1_weight': d1_w / total
                        }
                        weight_combinations.append(normalized_weights)
        
        best_weights = None
        best_score = -float('inf')
        results = []
        
        for i, weights in enumerate(weight_combinations):
            try:
                # 가중치 설정으로 백테스트
                config = self._create_weight_config(weights)
                
                backtester = Backtester(self.initial_capital)
                metrics = backtester.run_backtest(start_date, end_date, config)
                
                score = self._calculate_optimization_score(metrics)
                
                results.append({
                    'weights': weights,
                    'metrics': metrics,
                    'score': score
                })
                
                if score > best_score:
                    best_score = score
                    best_weights = weights
                
                self.logger.info(f"가중치 조합 {i+1}/{len(weight_combinations)} - 점수: {score:.4f}")
                
            except Exception as e:
                self.logger.error(f"가중치 최적화 {i+1} 실행 오류: {e}")
        
        return {
            'best_weights': best_weights,
            'best_score': best_score,
            'all_results': results
        }
    
    def run_comprehensive_optimization(self, optimization_period_days: int = 90) -> Dict:
        """종합 최적화 실행"""
        self.logger.info("종합 전략 최적화 시작")
        
        # 최적화 기간 설정
        end_date = datetime.now()
        start_date = end_date - timedelta(days=optimization_period_days)
        
        results = {
            'optimization_period': f"{start_date.date()} ~ {end_date.date()}",
            'strategy_optimizations': {},
            'weight_optimization': {},
            'final_config': {},
            'performance_comparison': {}
        }
        
        # 1. 개별 전략 최적화
        strategies_to_optimize = ['ema_cross', 'rsi_divergence', 'bollinger_band_strategy', 'macd_zero_cross']
        
        for strategy_id in strategies_to_optimize:
            self.logger.info(f"전략 {strategy_id} 최적화 중...")
            strategy_result = self.optimize_single_strategy(strategy_id, start_date, end_date)
            results['strategy_optimizations'][strategy_id] = strategy_result
        
        # 2. 포트폴리오 가중치 최적화
        self.logger.info("포트폴리오 가중치 최적화 중...")
        weight_result = self.optimize_portfolio_weights(start_date, end_date)
        results['weight_optimization'] = weight_result
        
        # 3. 최적화된 설정 생성
        optimized_config = self._generate_optimized_config(results)
        results['final_config'] = optimized_config
        
        # 4. 성능 비교 (원본 vs 최적화)
        performance_comparison = self._compare_performance(
            start_date, end_date, optimized_config)
        results['performance_comparison'] = performance_comparison
        
        return results
    
    def _create_strategy_config(self, strategy_id: str, params: Dict) -> Dict:
        """파라미터로 전략 설정 생성"""
        # 기본 전략 설정 로드
        base_strategies = self.strategy_manager.get_active_strategies('hourly')
        
        # 특정 전략만 활성화하고 파라미터 적용
        config = {
            'strategies': {
                strategy_id: {
                    **base_strategies.get(strategy_id, {}),
                    'active': True,
                    'parameters': params
                }
            }
        }
        
        # 다른 전략들은 비활성화
        for other_id in base_strategies:
            if other_id != strategy_id:
                config['strategies'][other_id] = {
                    **base_strategies[other_id],
                    'active': False
                }
        
        return config
    
    def _create_weight_config(self, weights: Dict) -> Dict:
        """가중치 설정 생성"""
        base_strategies = self.strategy_manager.get_active_strategies('hourly')
        
        config = {
            'strategies': base_strategies,
            'weights': weights
        }
        
        return config
    
    def _calculate_optimization_score(self, metrics: BacktestMetrics) -> float:
        """최적화 점수 계산"""
        # 다중 목표 최적화: 샤프 비율 + 수익률 + 낙폭 고려
        score = (
            metrics.sharpe_ratio * 0.4 +  # 위험 조정 수익률
            metrics.total_return * 0.3 +   # 절대 수익률
            (1 - metrics.max_drawdown) * 0.2 +  # 낙폭 최소화
            metrics.win_rate * 0.1        # 승률
        )
        
        return score
    
    def _generate_optimized_config(self, optimization_results: Dict) -> Dict:
        """최적화 결과로부터 최종 설정 생성"""
        config = {
            'strategies': {},
            'weights': optimization_results['weight_optimization'].get('best_weights', {}),
            'optimization_metadata': {
                'optimization_date': datetime.now().isoformat(),
                'optimization_period': optimization_results['optimization_period']
            }
        }
        
        # 최적화된 전략 파라미터 적용
        base_strategies = self.strategy_manager.get_active_strategies('hourly')
        
        for strategy_id, strategy_config in base_strategies.items():
            if strategy_id in optimization_results['strategy_optimizations']:
                opt_result = optimization_results['strategy_optimizations'][strategy_id]
                best_params = opt_result.get('best_params', {})
                
                config['strategies'][strategy_id] = {
                    **strategy_config,
                    'parameters': best_params,
                    'optimization_score': opt_result.get('best_score', 0)
                }
            else:
                config['strategies'][strategy_id] = strategy_config
        
        return config
    
    def _compare_performance(self, start_date: datetime, end_date: datetime, 
                           optimized_config: Dict) -> Dict:
        """원본 설정 vs 최적화 설정 성능 비교"""
        # 원본 설정으로 백테스트
        original_backtester = Backtester(self.initial_capital)
        original_metrics = original_backtester.run_backtest(start_date, end_date)
        
        # 최적화 설정으로 백테스트
        optimized_backtester = Backtester(self.initial_capital)
        optimized_metrics = optimized_backtester.run_backtest(start_date, end_date, optimized_config)
        
        comparison = {
            'original': {
                'total_return': original_metrics.total_return,
                'sharpe_ratio': original_metrics.sharpe_ratio,
                'max_drawdown': original_metrics.max_drawdown,
                'win_rate': original_metrics.win_rate,
                'total_trades': original_metrics.total_trades
            },
            'optimized': {
                'total_return': optimized_metrics.total_return,
                'sharpe_ratio': optimized_metrics.sharpe_ratio,
                'max_drawdown': optimized_metrics.max_drawdown,
                'win_rate': optimized_metrics.win_rate,
                'total_trades': optimized_metrics.total_trades
            },
            'improvements': {
                'return_improvement': optimized_metrics.total_return - original_metrics.total_return,
                'sharpe_improvement': optimized_metrics.sharpe_ratio - original_metrics.sharpe_ratio,
                'drawdown_improvement': original_metrics.max_drawdown - optimized_metrics.max_drawdown,
                'win_rate_improvement': optimized_metrics.win_rate - original_metrics.win_rate
            }
        }
        
        return comparison
    
    def save_optimization_results(self, results: Dict, output_path: str = None):
        """최적화 결과 저장"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"backtesting/optimization/optimization_results_{timestamp}.json"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 직렬화 가능한 형태로 변환
        serializable_results = self._make_serializable(results)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2, default=str, ensure_ascii=False)
        
        self.logger.info(f"최적화 결과 저장됨: {output_path}")
        return output_path
    
    def _make_serializable(self, obj):
        """객체를 JSON 직렬화 가능한 형태로 변환"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(v) for v in obj]
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        else:
            return obj
    
    def apply_optimized_config(self, config: Dict):
        """최적화된 설정을 실제 시스템에 적용"""
        try:
            # 전략 설정 업데이트
            if 'strategies' in config:
                self.strategy_manager.update_strategies(config['strategies'])
            
            # 가중치 설정 업데이트
            if 'weights' in config:
                # config_manager를 통해 가중치 업데이트
                from config.config_manager import config_manager
                config_manager.set_config('strategy_weights', config['weights'])
            
            self.logger.info("최적화된 설정이 적용되었습니다")
            return True
            
        except Exception as e:
            self.logger.error(f"최적화 설정 적용 실패: {e}")
            return False


class WalkForwardOptimizer:
    """워크 포워드 최적화 - 시간에 따른 설정 변화 감지"""
    
    def __init__(self, optimizer: StrategyOptimizer):
        self.optimizer = optimizer
        self.logger = logging.getLogger('WalkForwardOptimizer')
    
    def run_walk_forward_test(self, total_period_days: int = 180, 
                            optimization_window: int = 60, 
                            test_window: int = 30) -> Dict:
        """워크 포워드 테스트 실행"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=total_period_days)
        
        results = []
        current_date = start_date
        
        while current_date + timedelta(days=optimization_window + test_window) <= end_date:
            # 최적화 기간
            opt_start = current_date
            opt_end = current_date + timedelta(days=optimization_window)
            
            # 테스트 기간
            test_start = opt_end
            test_end = opt_end + timedelta(days=test_window)
            
            self.logger.info(f"워크포워드 구간: 최적화 {opt_start.date()}~{opt_end.date()}, "
                           f"테스트 {test_start.date()}~{test_end.date()}")
            
            try:
                # 해당 기간 최적화
                opt_results = self.optimizer.run_comprehensive_optimization(optimization_window)
                
                # 최적화된 설정으로 테스트 기간 백테스트
                test_backtester = Backtester(self.optimizer.initial_capital)
                test_metrics = test_backtester.run_backtest(
                    test_start, test_end, opt_results['final_config'])
                
                results.append({
                    'optimization_period': f"{opt_start.date()}~{opt_end.date()}",
                    'test_period': f"{test_start.date()}~{test_end.date()}",
                    'optimized_config': opt_results['final_config'],
                    'test_performance': test_metrics
                })
                
            except Exception as e:
                self.logger.error(f"워크포워드 구간 처리 오류: {e}")
            
            # 다음 구간으로 이동
            current_date += timedelta(days=test_window)
        
        return {
            'walk_forward_results': results,
            'summary_stats': self._calculate_walk_forward_summary(results)
        }
    
    def _calculate_walk_forward_summary(self, results: List[Dict]) -> Dict:
        """워크포워드 테스트 요약 통계"""
        if not results:
            return {}
        
        test_returns = [r['test_performance'].total_return for r in results]
        test_sharpes = [r['test_performance'].sharpe_ratio for r in results]
        test_drawdowns = [r['test_performance'].max_drawdown for r in results]
        
        return {
            'total_periods': len(results),
            'avg_return': np.mean(test_returns),
            'std_return': np.std(test_returns),
            'avg_sharpe': np.mean(test_sharpes),
            'avg_drawdown': np.mean(test_drawdowns),
            'winning_periods': len([r for r in test_returns if r > 0]),
            'win_rate': len([r for r in test_returns if r > 0]) / len(test_returns)
        }


if __name__ == "__main__":
    # 최적화 실행 예시
    optimizer = StrategyOptimizer(initial_capital=1000000)
    
    try:
        # 종합 최적화 실행
        results = optimizer.run_comprehensive_optimization(optimization_period_days=90)
        
        print("=== 최적화 결과 ===")
        print(f"최적화 기간: {results['optimization_period']}")
        
        # 성능 비교
        comparison = results['performance_comparison']
        print(f"\n원본 성능:")
        print(f"  수익률: {comparison['original']['total_return']:.2%}")
        print(f"  샤프비율: {comparison['original']['sharpe_ratio']:.2f}")
        
        print(f"\n최적화 성능:")
        print(f"  수익률: {comparison['optimized']['total_return']:.2%}")
        print(f"  샤프비율: {comparison['optimized']['sharpe_ratio']:.2f}")
        
        print(f"\n개선도:")
        print(f"  수익률 개선: {comparison['improvements']['return_improvement']:.2%}")
        print(f"  샤프비율 개선: {comparison['improvements']['sharpe_improvement']:.2f}")
        
        # 결과 저장
        output_file = optimizer.save_optimization_results(results)
        print(f"\n최적화 결과 저장됨: {output_file}")
        
        # 워크 포워드 테스트
        print("\n=== 워크 포워드 테스트 ===")
        wf_optimizer = WalkForwardOptimizer(optimizer)
        wf_results = wf_optimizer.run_walk_forward_test(total_period_days=180)
        
        summary = wf_results['summary_stats']
        print(f"테스트 기간 수: {summary['total_periods']}")
        print(f"평균 수익률: {summary['avg_return']:.2%}")
        print(f"승률: {summary['win_rate']:.1%}")
        
    except Exception as e:
        print(f"최적화 실행 오류: {e}")