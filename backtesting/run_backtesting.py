"""
백테스팅 실행 스크립트
통합 백테스팅 시스템의 실행 진입점
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from backtesting.backtester import Backtester
from backtesting.strategy_optimizer import StrategyOptimizer, WalkForwardOptimizer
from backtesting.performance_analyzer import PerformanceAnalyzer

# 로그 디렉토리 생성
os.makedirs('backtesting/logs', exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backtesting/logs/backtesting.log')
    ]
)

logger = logging.getLogger('BacktestingRunner')

class BacktestingRunner:
    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.logger = logger
        
        # 결과 저장 디렉토리 생성
        os.makedirs('backtesting/results', exist_ok=True)
        os.makedirs('backtesting/optimization', exist_ok=True)
        os.makedirs('backtesting/reports', exist_ok=True)
        os.makedirs('backtesting/logs', exist_ok=True)
    
    def run_basic_backtest(self, days: int = 90, save_results: bool = True) -> Dict:
        """기본 백테스트 실행"""
        self.logger.info(f"기본 백테스트 시작 - {days}일 기간")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            backtester = Backtester(self.initial_capital)
            metrics = backtester.run_backtest(start_date, end_date)
            
            results = {
                'type': 'basic_backtest',
                'period_days': days,
                'metrics': metrics,
                'trades': backtester.trades,
                'portfolio_history': backtester.portfolio_history,
                'execution_time': datetime.now().isoformat()
            }
            
            if save_results:
                output_file = backtester.save_results(metrics)
                results['output_file'] = output_file
                self.logger.info(f"백테스트 결과 저장됨: {output_file}")
            
            # 간단한 결과 출력
            self._print_basic_results(metrics)
            
            return results
            
        except Exception as e:
            self.logger.error(f"기본 백테스트 실행 오류: {e}")
            raise
    
    def run_optimization(self, optimization_days: int = 90, save_results: bool = True) -> Dict:
        """전략 최적화 실행"""
        self.logger.info(f"전략 최적화 시작 - {optimization_days}일 기간")
        
        try:
            optimizer = StrategyOptimizer(self.initial_capital)
            results = optimizer.run_comprehensive_optimization(optimization_days)
            
            if save_results:
                output_file = optimizer.save_optimization_results(results)
                results['output_file'] = output_file
                self.logger.info(f"최적화 결과 저장됨: {output_file}")
            
            # 최적화 결과 출력
            self._print_optimization_results(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"전략 최적화 실행 오류: {e}")
            raise
    
    def run_walk_forward_test(self, total_days: int = 180, 
                            optimization_window: int = 60, 
                            test_window: int = 30) -> Dict:
        """워크 포워드 테스트 실행"""
        self.logger.info(f"워크 포워드 테스트 시작 - 총 {total_days}일")
        
        try:
            optimizer = StrategyOptimizer(self.initial_capital)
            wf_optimizer = WalkForwardOptimizer(optimizer)
            
            results = wf_optimizer.run_walk_forward_test(
                total_days, optimization_window, test_window
            )
            
            # 워크 포워드 결과 출력
            self._print_walk_forward_results(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"워크 포워드 테스트 실행 오류: {e}")
            raise
    
    def run_performance_analysis(self, result_file: str) -> Dict:
        """성과 분석 실행"""
        self.logger.info(f"성과 분석 시작 - {result_file}")
        
        try:
            analyzer = PerformanceAnalyzer()
            
            # 결과 로드
            results = analyzer.load_backtest_results(result_file)
            if not results:
                raise ValueError("백테스트 결과를 로드할 수 없습니다")
            
            # 성과 분석
            analysis = analyzer.analyze_performance(results)
            
            # 보고서 생성
            report_file = analyzer.generate_report(analysis)
            
            # 주요 지표 출력
            self._print_analysis_results(analysis)
            
            return {
                'analysis': analysis,
                'report_file': report_file
            }
            
        except Exception as e:
            self.logger.error(f"성과 분석 실행 오류: {e}")
            raise
    
    def run_comprehensive_analysis(self, days: int = 90) -> Dict:
        """종합 분석 실행 (백테스트 + 최적화 + 분석)"""
        self.logger.info(f"종합 분석 시작 - {days}일 기간")
        
        comprehensive_results = {
            'execution_time': datetime.now().isoformat(),
            'analysis_period_days': days
        }
        
        try:
            # 1. 기본 백테스트
            self.logger.info("1/4 - 기본 백테스트 실행 중...")
            basic_results = self.run_basic_backtest(days, save_results=True)
            comprehensive_results['basic_backtest'] = basic_results
            
            # 2. 전략 최적화
            self.logger.info("2/4 - 전략 최적화 실행 중...")
            optimization_results = self.run_optimization(days, save_results=True)
            comprehensive_results['optimization'] = optimization_results
            
            # 3. 워크 포워드 테스트
            self.logger.info("3/4 - 워크 포워드 테스트 실행 중...")
            wf_results = self.run_walk_forward_test(days * 2, days // 3, days // 6)
            comprehensive_results['walk_forward'] = wf_results
            
            # 4. 성과 분석
            self.logger.info("4/4 - 성과 분석 실행 중...")
            if 'output_file' in basic_results:
                analysis_results = self.run_performance_analysis(basic_results['output_file'])
                comprehensive_results['performance_analysis'] = analysis_results
            
            # 종합 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"backtesting/reports/comprehensive_analysis_{timestamp}.json"
            
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(comprehensive_results, f, indent=2, default=str, ensure_ascii=False)
            
            comprehensive_results['output_file'] = output_file
            
            self.logger.info(f"종합 분석 완료 - 결과 저장됨: {output_file}")
            self._print_comprehensive_summary(comprehensive_results)
            
            return comprehensive_results
            
        except Exception as e:
            self.logger.error(f"종합 분석 실행 오류: {e}")
            raise
    
    def _print_basic_results(self, metrics):
        """기본 백테스트 결과 출력"""
        print("\n=== 기본 백테스트 결과 ===")
        print(f"기간: {metrics.start_date.date()} ~ {metrics.end_date.date()}")
        print(f"총 수익률: {metrics.total_return:.2%}")
        print(f"연환산 수익률: {metrics.annualized_return:.2%}")
        print(f"최대 낙폭: {metrics.max_drawdown:.2%}")
        print(f"샤프 비율: {metrics.sharpe_ratio:.2f}")
        print(f"승률: {metrics.win_rate:.1%}")
        print(f"총 거래 수: {metrics.total_trades}")
        print(f"Buy & Hold 수익률: {metrics.buy_and_hold_return:.2%}")
        print(f"알파 (초과수익): {metrics.alpha:.2%}")
    
    def _print_optimization_results(self, results):
        """최적화 결과 출력"""
        print("\n=== 전략 최적화 결과 ===")
        print(f"최적화 기간: {results['optimization_period']}")
        
        if 'performance_comparison' in results:
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
    
    def _print_walk_forward_results(self, results):
        """워크 포워드 결과 출력"""
        print("\n=== 워크 포워드 테스트 결과 ===")
        
        if 'summary_stats' in results:
            summary = results['summary_stats']
            print(f"테스트 기간 수: {summary['total_periods']}")
            print(f"평균 수익률: {summary['avg_return']:.2%}")
            print(f"수익률 표준편차: {summary['std_return']:.2%}")
            print(f"평균 샤프비율: {summary['avg_sharpe']:.2f}")
            print(f"승률: {summary['win_rate']:.1%}")
    
    def _print_analysis_results(self, analysis):
        """성과 분석 결과 출력"""
        print("\n=== 성과 분석 결과 ===")
        
        if 'basic_metrics' in analysis:
            basic = analysis['basic_metrics']
            print(f"성과 등급: {basic.get('performance_grade', 'N/A')}")
            print(f"총 수익률: {basic.get('total_return', 0):.2%}")
            print(f"샤프 비율: {basic.get('sharpe_ratio', 0):.2f}")
            print(f"칼마 비율: {basic.get('calmar_ratio', 0):.2f}")
        
        if 'trade_analysis' in analysis:
            trade = analysis['trade_analysis']
            print(f"총 거래 수: {trade.get('total_trades', 0)}")
            print(f"승률: {trade.get('win_rate', 0):.1%}")
            print(f"수익 팩터: {trade.get('profit_factor', 0):.2f}")
    
    def _print_comprehensive_summary(self, results):
        """종합 분석 요약 출력"""
        print("\n=== 종합 분석 완료 ===")
        
        if 'basic_backtest' in results:
            basic = results['basic_backtest']['metrics']
            print(f"기본 백테스트 수익률: {basic.total_return:.2%}")
        
        if 'optimization' in results and 'performance_comparison' in results['optimization']:
            opt_perf = results['optimization']['performance_comparison']['optimized']
            print(f"최적화 후 수익률: {opt_perf['total_return']:.2%}")
        
        if 'walk_forward' in results and 'summary_stats' in results['walk_forward']:
            wf_stats = results['walk_forward']['summary_stats']
            print(f"워크 포워드 평균 수익률: {wf_stats['avg_return']:.2%}")
        
        print(f"상세 결과: {results.get('output_file', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description='Bitcoin Auto Trading 백테스팅 시스템')
    parser.add_argument('--mode', choices=['basic', 'optimize', 'walk_forward', 'analyze', 'comprehensive'], 
                       default='basic', help='실행 모드')
    parser.add_argument('--days', type=int, default=90, help='분석 기간 (일)')
    parser.add_argument('--capital', type=float, default=1000000, help='초기 자본금 (원)')
    parser.add_argument('--file', type=str, help='분석할 백테스트 결과 파일 경로')
    
    args = parser.parse_args()
    
    try:
        runner = BacktestingRunner(args.capital)
        
        if args.mode == 'basic':
            runner.run_basic_backtest(args.days)
        
        elif args.mode == 'optimize':
            runner.run_optimization(args.days)
        
        elif args.mode == 'walk_forward':
            runner.run_walk_forward_test(args.days * 2)
        
        elif args.mode == 'analyze':
            if not args.file:
                print("분석 모드에서는 --file 옵션이 필요합니다.")
                return
            runner.run_performance_analysis(args.file)
        
        elif args.mode == 'comprehensive':
            runner.run_comprehensive_analysis(args.days)
        
        print("\n백테스팅 완료!")
        
    except Exception as e:
        logger.error(f"백테스팅 실행 오류: {e}")
        print(f"오류 발생: {e}")


if __name__ == "__main__":
    main()