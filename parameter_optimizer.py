#!/usr/bin/env python3
"""
파라미터 최적화 시스템
- Grid Search
- Random Search
- Bayesian Optimization
- 유전 알고리즘
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from itertools import product
import random
from concurrent.futures import ProcessPoolExecutor, as_completed

from backtest_runner import StrategyTester

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ParameterOptimizer:
    """파라미터 최적화 시스템"""
    
    def __init__(self):
        self.tester = StrategyTester()
        self.optimization_results = []
        self.best_params = {}
        self.db_path = "data/optimization_results.db"
        self._init_database()
        
    def _init_database(self):
        """최적화 결과 저장용 데이터베이스 초기화"""
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                days INTEGER NOT NULL,
                method TEXT NOT NULL,
                parameters TEXT NOT NULL,
                roi REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                win_rate REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                fitness_score REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def define_parameter_space(self, strategy_name: str) -> Dict:
        """각 전략별 파라미터 공간 정의"""
        
        parameter_spaces = {
            "momentum_scalping": {
                "momentum_period": [10, 15, 20, 25, 30],
                "entry_threshold": [0.001, 0.0015, 0.002, 0.0025, 0.003],
                "stop_loss": [-0.002, -0.003, -0.004, -0.005],
                "take_profit": [0.002, 0.003, 0.004, 0.005]
            },
            "mean_reversion": {
                "bb_period": [15, 20, 25, 30],
                "bb_std": [1.5, 2.0, 2.5, 3.0],
                "rsi_oversold": [20, 25, 30, 35],
                "rsi_overbought": [65, 70, 75, 80]
            },
            "trend_following": {
                "sma_short": [10, 15, 20, 25],
                "sma_long": [40, 50, 60, 70],
                "macd_fast": [8, 10, 12, 14],
                "macd_slow": [20, 24, 26, 30]
            },
            "ml_prediction": {
                "n_estimators": [50, 100, 150, 200],
                "max_depth": [3, 5, 7, 10],
                "probability_threshold": [0.55, 0.6, 0.65, 0.7],
                "lookback_periods": [20, 30, 40, 50]
            },
            "statistical_arbitrage": {
                "lookback": [30, 45, 60, 75, 90],
                "entry_zscore": [1.5, 2.0, 2.5, 3.0],
                "exit_zscore": [0.25, 0.5, 0.75, 1.0]
            },
            "orderbook_imbalance": {
                "window": [10, 15, 20, 25, 30],
                "imbalance_threshold": [0.2, 0.3, 0.4, 0.5],
                "volume_threshold": [1.3, 1.5, 1.7, 2.0],
                "momentum_period": [5, 10, 15, 20]
            },
            "vwap_trading": {
                "std_period": [15, 20, 25, 30],
                "band_multiplier": [1.5, 2.0, 2.5, 3.0],
                "trend_period": [30, 40, 50, 60],
                "mean_reversion": [True, False]
            },
            "ichimoku_cloud": {
                "tenkan_period": [7, 9, 11],
                "kijun_period": [22, 26, 30],
                "senkou_b_period": [44, 52, 60],
                "use_cloud_filter": [True, False]
            },
            "combined_signal": {
                "signal_threshold": [0.3, 0.4, 0.5, 0.6],
                "weight_momentum": [0.1, 0.2, 0.3, 0.4],
                "weight_reversion": [0.1, 0.2, 0.3, 0.4],
                "weight_vwap": [0.1, 0.2, 0.3, 0.4],
                "weight_ichimoku": [0.1, 0.2, 0.3, 0.4]
            }
        }
        
        return parameter_spaces.get(strategy_name, {})
    
    def calculate_fitness(self, result: Dict) -> float:
        """결과의 적합도 점수 계산"""
        if 'error' in result or result['metrics']['total_trades'] < 10:
            return -1000  # 패널티
        
        # 가중치 설정
        weights = {
            'roi': 0.3,
            'sharpe': 0.25,
            'drawdown': 0.2,
            'win_rate': 0.15,
            'trades': 0.1
        }
        
        # 정규화된 점수 계산
        roi_score = min(result['metrics']['roi'] / 10, 1.0)  # 10% ROI = 1.0
        sharpe_score = min(result['metrics']['sharpe_ratio'] / 2, 1.0)  # Sharpe 2.0 = 1.0
        drawdown_score = max(1 - result['metrics']['max_drawdown'] / 20, 0)  # 20% DD = 0
        winrate_score = result['metrics']['win_rate'] / 100
        trades_score = min(result['metrics']['total_trades'] / 200, 1.0)  # 200 trades = 1.0
        
        fitness = (
            weights['roi'] * roi_score +
            weights['sharpe'] * sharpe_score +
            weights['drawdown'] * drawdown_score +
            weights['win_rate'] * winrate_score +
            weights['trades'] * trades_score
        )
        
        return fitness * 100  # 0-100 scale
    
    def grid_search(self,
                   strategy_name: str,
                   symbol: str = "KRW-BTC",
                   days: int = 30,
                   initial_capital: float = 1_000_000,
                   max_combinations: int = 100) -> Dict:
        """Grid Search 최적화"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Grid Search 시작: {strategy_name}")
        logger.info(f"{'='*60}")
        
        # 파라미터 공간 정의
        param_space = self.define_parameter_space(strategy_name)
        if not param_space:
            return {"error": f"파라미터 공간이 정의되지 않음: {strategy_name}"}
        
        # 모든 조합 생성
        param_names = list(param_space.keys())
        param_values = list(param_space.values())
        all_combinations = list(product(*param_values))
        
        # 조합 수 제한
        if len(all_combinations) > max_combinations:
            all_combinations = random.sample(all_combinations, max_combinations)
            logger.info(f"총 {len(all_combinations)}개 조합 (제한됨)")
        else:
            logger.info(f"총 {len(all_combinations)}개 조합")
        
        best_fitness = -float('inf')
        best_params = None
        best_result = None
        results = []
        
        # 각 조합 테스트
        for i, combination in enumerate(all_combinations):
            params = dict(zip(param_names, combination))
            
            logger.info(f"\n진행 [{i+1}/{len(all_combinations)}]: {params}")
            
            # 백테스트 실행
            result = self.tester.run_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                days=days,
                initial_capital=initial_capital,
                position_size=0.1,
                params=params
            )
            
            # 적합도 계산
            fitness = self.calculate_fitness(result)
            
            results.append({
                'params': params,
                'fitness': fitness,
                'metrics': result.get('metrics', {})
            })
            
            # 최고 성능 업데이트
            if fitness > best_fitness:
                best_fitness = fitness
                best_params = params
                best_result = result
                logger.info(f"✨ 새로운 최적 파라미터! Fitness: {fitness:.2f}")
        
        # 결과 저장
        self._save_optimization_result(
            strategy_name=strategy_name,
            symbol=symbol,
            days=days,
            method="grid_search",
            best_params=best_params,
            best_result=best_result,
            fitness=best_fitness
        )
        
        return {
            'method': 'grid_search',
            'strategy': strategy_name,
            'best_params': best_params,
            'best_fitness': best_fitness,
            'best_metrics': best_result.get('metrics', {}),
            'total_tested': len(all_combinations),
            'all_results': sorted(results, key=lambda x: x['fitness'], reverse=True)[:10]  # Top 10
        }
    
    def random_search(self,
                     strategy_name: str,
                     symbol: str = "KRW-BTC",
                     days: int = 30,
                     initial_capital: float = 1_000_000,
                     n_iterations: int = 50) -> Dict:
        """Random Search 최적화"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Random Search 시작: {strategy_name}")
        logger.info(f"반복 횟수: {n_iterations}")
        logger.info(f"{'='*60}")
        
        param_space = self.define_parameter_space(strategy_name)
        if not param_space:
            return {"error": f"파라미터 공간이 정의되지 않음: {strategy_name}"}
        
        best_fitness = -float('inf')
        best_params = None
        best_result = None
        results = []
        
        for i in range(n_iterations):
            # 랜덤 파라미터 선택
            params = {}
            for param_name, param_values in param_space.items():
                params[param_name] = random.choice(param_values)
            
            logger.info(f"\n진행 [{i+1}/{n_iterations}]: {params}")
            
            # 백테스트 실행
            result = self.tester.run_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                days=days,
                initial_capital=initial_capital,
                position_size=0.1,
                params=params
            )
            
            # 적합도 계산
            fitness = self.calculate_fitness(result)
            
            results.append({
                'params': params,
                'fitness': fitness,
                'metrics': result.get('metrics', {})
            })
            
            # 최고 성능 업데이트
            if fitness > best_fitness:
                best_fitness = fitness
                best_params = params
                best_result = result
                logger.info(f"✨ 새로운 최적 파라미터! Fitness: {fitness:.2f}")
        
        # 결과 저장
        self._save_optimization_result(
            strategy_name=strategy_name,
            symbol=symbol,
            days=days,
            method="random_search",
            best_params=best_params,
            best_result=best_result,
            fitness=best_fitness
        )
        
        return {
            'method': 'random_search',
            'strategy': strategy_name,
            'best_params': best_params,
            'best_fitness': best_fitness,
            'best_metrics': best_result.get('metrics', {}),
            'total_tested': n_iterations,
            'all_results': sorted(results, key=lambda x: x['fitness'], reverse=True)[:10]
        }
    
    def genetic_algorithm(self,
                         strategy_name: str,
                         symbol: str = "KRW-BTC",
                         days: int = 30,
                         initial_capital: float = 1_000_000,
                         population_size: int = 20,
                         n_generations: int = 10,
                         mutation_rate: float = 0.1) -> Dict:
        """유전 알고리즘 최적화"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"유전 알고리즘 시작: {strategy_name}")
        logger.info(f"인구 크기: {population_size}, 세대: {n_generations}")
        logger.info(f"{'='*60}")
        
        param_space = self.define_parameter_space(strategy_name)
        if not param_space:
            return {"error": f"파라미터 공간이 정의되지 않음: {strategy_name}"}
        
        # 초기 인구 생성
        population = []
        for _ in range(population_size):
            individual = {}
            for param_name, param_values in param_space.items():
                individual[param_name] = random.choice(param_values)
            population.append(individual)
        
        best_overall_fitness = -float('inf')
        best_overall_params = None
        best_overall_result = None
        generation_history = []
        
        for generation in range(n_generations):
            logger.info(f"\n세대 {generation + 1}/{n_generations}")
            
            # 적합도 평가
            fitness_scores = []
            for i, individual in enumerate(population):
                result = self.tester.run_backtest(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    days=days,
                    initial_capital=initial_capital,
                    position_size=0.1,
                    params=individual
                )
                
                fitness = self.calculate_fitness(result)
                fitness_scores.append((individual, fitness, result))
                
                if fitness > best_overall_fitness:
                    best_overall_fitness = fitness
                    best_overall_params = individual.copy()
                    best_overall_result = result
                    logger.info(f"✨ 새로운 최적! Fitness: {fitness:.2f}")
            
            # 세대 통계
            avg_fitness = np.mean([f[1] for f in fitness_scores])
            max_fitness = max([f[1] for f in fitness_scores])
            generation_history.append({
                'generation': generation + 1,
                'avg_fitness': avg_fitness,
                'max_fitness': max_fitness
            })
            logger.info(f"평균 적합도: {avg_fitness:.2f}, 최고: {max_fitness:.2f}")
            
            # 다음 세대 생성
            if generation < n_generations - 1:
                # 선택 (상위 50% 선택)
                fitness_scores.sort(key=lambda x: x[1], reverse=True)
                parents = [f[0] for f in fitness_scores[:population_size//2]]
                
                # 교차 및 변이
                new_population = parents.copy()  # 엘리트 보존
                
                while len(new_population) < population_size:
                    # 부모 선택
                    parent1 = random.choice(parents)
                    parent2 = random.choice(parents)
                    
                    # 교차
                    child = {}
                    for param_name in param_space.keys():
                        if random.random() < 0.5:
                            child[param_name] = parent1[param_name]
                        else:
                            child[param_name] = parent2[param_name]
                    
                    # 변이
                    if random.random() < mutation_rate:
                        mutate_param = random.choice(list(param_space.keys()))
                        child[mutate_param] = random.choice(param_space[mutate_param])
                    
                    new_population.append(child)
                
                population = new_population
        
        # 결과 저장
        self._save_optimization_result(
            strategy_name=strategy_name,
            symbol=symbol,
            days=days,
            method="genetic_algorithm",
            best_params=best_overall_params,
            best_result=best_overall_result,
            fitness=best_overall_fitness
        )
        
        return {
            'method': 'genetic_algorithm',
            'strategy': strategy_name,
            'best_params': best_overall_params,
            'best_fitness': best_overall_fitness,
            'best_metrics': best_overall_result.get('metrics', {}),
            'total_tested': population_size * n_generations,
            'generation_history': generation_history
        }
    
    def _save_optimization_result(self,
                                 strategy_name: str,
                                 symbol: str,
                                 days: int,
                                 method: str,
                                 best_params: Dict,
                                 best_result: Dict,
                                 fitness: float):
        """최적화 결과 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        metrics = best_result.get('metrics', {})
        
        cursor.execute("""
            INSERT INTO optimization_results (
                timestamp, strategy, symbol, days, method, parameters,
                roi, sharpe_ratio, max_drawdown, win_rate, total_trades, fitness_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            strategy_name,
            symbol,
            days,
            method,
            json.dumps(best_params),
            metrics.get('roi', 0),
            metrics.get('sharpe_ratio', 0),
            metrics.get('max_drawdown', 0),
            metrics.get('win_rate', 0),
            metrics.get('total_trades', 0),
            fitness
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"최적화 결과 저장 완료")
    
    def get_optimization_history(self, strategy_name: Optional[str] = None) -> List[Dict]:
        """최적화 히스토리 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if strategy_name:
            cursor.execute("""
                SELECT * FROM optimization_results 
                WHERE strategy = ?
                ORDER BY fitness_score DESC
                LIMIT 20
            """, (strategy_name,))
        else:
            cursor.execute("""
                SELECT * FROM optimization_results 
                ORDER BY fitness_score DESC
                LIMIT 50
            """)
        
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for row in results:
            history.append({
                'id': row[0],
                'timestamp': row[1],
                'strategy': row[2],
                'symbol': row[3],
                'days': row[4],
                'method': row[5],
                'parameters': json.loads(row[6]),
                'roi': row[7],
                'sharpe_ratio': row[8],
                'max_drawdown': row[9],
                'win_rate': row[10],
                'total_trades': row[11],
                'fitness_score': row[12]
            })
        
        return history
    
    def compare_optimization_methods(self,
                                    strategy_name: str,
                                    symbol: str = "KRW-BTC",
                                    days: int = 30,
                                    initial_capital: float = 1_000_000) -> Dict:
        """여러 최적화 방법 비교"""
        
        results = {}
        
        # Grid Search
        logger.info("\n1. Grid Search 실행")
        results['grid_search'] = self.grid_search(
            strategy_name, symbol, days, initial_capital, max_combinations=30
        )
        
        # Random Search
        logger.info("\n2. Random Search 실행")
        results['random_search'] = self.random_search(
            strategy_name, symbol, days, initial_capital, n_iterations=30
        )
        
        # Genetic Algorithm
        logger.info("\n3. 유전 알고리즘 실행")
        results['genetic_algorithm'] = self.genetic_algorithm(
            strategy_name, symbol, days, initial_capital,
            population_size=10, n_generations=5
        )
        
        # 비교 결과
        comparison = pd.DataFrame({
            'Method': ['Grid Search', 'Random Search', 'Genetic Algorithm'],
            'Best Fitness': [
                results['grid_search'].get('best_fitness', 0),
                results['random_search'].get('best_fitness', 0),
                results['genetic_algorithm'].get('best_fitness', 0)
            ],
            'ROI (%)': [
                results['grid_search'].get('best_metrics', {}).get('roi', 0),
                results['random_search'].get('best_metrics', {}).get('roi', 0),
                results['genetic_algorithm'].get('best_metrics', {}).get('roi', 0)
            ],
            'Sharpe Ratio': [
                results['grid_search'].get('best_metrics', {}).get('sharpe_ratio', 0),
                results['random_search'].get('best_metrics', {}).get('sharpe_ratio', 0),
                results['genetic_algorithm'].get('best_metrics', {}).get('sharpe_ratio', 0)
            ]
        })
        
        print("\n" + "="*60)
        print("최적화 방법 비교")
        print("="*60)
        print(comparison.to_string(index=False))
        print("="*60)
        
        return results


def main():
    """메인 실행 함수"""
    optimizer = ParameterOptimizer()
    
    # 단일 전략 최적화
    result = optimizer.grid_search(
        strategy_name="momentum_scalping",
        symbol="KRW-BTC",
        days=7,
        initial_capital=1_000_000,
        max_combinations=20
    )
    
    print(f"\n최적 파라미터: {result['best_params']}")
    print(f"적합도: {result['best_fitness']:.2f}")
    print(f"ROI: {result['best_metrics']['roi']:.2f}%")
    
    # 여러 최적화 방법 비교
    # comparison = optimizer.compare_optimization_methods(
    #     strategy_name="mean_reversion",
    #     symbol="KRW-BTC",
    #     days=7
    # )


if __name__ == "__main__":
    main()