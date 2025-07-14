"""
성과 분석 모듈
백테스팅 결과의 상세 분석 및 시각화
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import json
from dataclasses import asdict

# 시각화 라이브러리 선택적 import
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    # 한글 폰트 설정
    plt.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("경고: matplotlib/seaborn이 설치되지 않음 - 시각화 기능 비활성화")

from backtesting.backtester import BacktestMetrics, BacktestTrade

class PerformanceAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger('PerformanceAnalyzer')
        
    def load_backtest_results(self, result_file: str) -> Dict:
        """백테스트 결과 파일 로드"""
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            self.logger.info(f"백테스트 결과 로드됨: {result_file}")
            return results
            
        except Exception as e:
            self.logger.error(f"결과 파일 로드 오류: {e}")
            return {}
    
    def analyze_performance(self, results: Dict) -> Dict:
        """종합 성과 분석"""
        if not results:
            return {}
        
        metrics = results.get('metrics', {})
        trades = results.get('trades', [])
        portfolio_history = results.get('portfolio_history', [])
        
        analysis = {
            'basic_metrics': self._analyze_basic_metrics(metrics),
            'trade_analysis': self._analyze_trades(trades),
            'portfolio_analysis': self._analyze_portfolio(portfolio_history),
            'risk_analysis': self._analyze_risk(portfolio_history),
            'strategy_contribution': self._analyze_strategy_contribution(trades),
            'time_analysis': self._analyze_time_patterns(trades),
            'drawdown_analysis': self._analyze_drawdowns(portfolio_history)
        }
        
        return analysis
    
    def _analyze_basic_metrics(self, metrics: Dict) -> Dict:
        """기본 성과 지표 분석"""
        if not metrics:
            return {}
        
        # 연환산 변동성 (일일 수익률 기준)
        annual_volatility = metrics.get('sharpe_ratio', 0) 
        if annual_volatility > 0 and metrics.get('annualized_return', 0) > 0:
            annual_volatility = metrics['annualized_return'] / metrics['sharpe_ratio']
        
        # 정보 비율 (알파 / 추적 오차)
        alpha = metrics.get('alpha', 0)
        information_ratio = alpha / annual_volatility if annual_volatility > 0 else 0
        
        # 칼마 비율 (연환산 수익률 / 최대 낙폭)
        calmar_ratio = (metrics.get('annualized_return', 0) / 
                       metrics.get('max_drawdown', 0.01)) if metrics.get('max_drawdown', 0) > 0 else 0
        
        return {
            'total_return': metrics.get('total_return', 0),
            'annualized_return': metrics.get('annualized_return', 0),
            'annual_volatility': annual_volatility,
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'calmar_ratio': calmar_ratio,
            'information_ratio': information_ratio,
            'max_drawdown': metrics.get('max_drawdown', 0),
            'win_rate': metrics.get('win_rate', 0),
            'alpha': alpha,
            'performance_grade': self._calculate_performance_grade(metrics)
        }
    
    def _calculate_performance_grade(self, metrics: Dict) -> str:
        """성과 등급 산정"""
        total_return = metrics.get('total_return', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        max_drawdown = metrics.get('max_drawdown', 1)
        win_rate = metrics.get('win_rate', 0)
        
        # 종합 점수 계산
        score = (
            min(total_return * 100, 50) +  # 수익률 (최대 50점)
            min(sharpe_ratio * 10, 30) +   # 샤프비율 (최대 30점)
            min((1 - max_drawdown) * 20, 20) +  # 낙폭 최소화 (최대 20점)
            min(win_rate * 20, 20)  # 승률 (최대 20점)
        )
        
        if score >= 90:
            return "A+ (매우 우수)"
        elif score >= 80:
            return "A (우수)"
        elif score >= 70:
            return "B+ (양호)"
        elif score >= 60:
            return "B (보통)"
        elif score >= 50:
            return "C+ (미흡)"
        else:
            return "C (부족)"
    
    def _analyze_trades(self, trades: List[Dict]) -> Dict:
        """거래 분석"""
        if not trades:
            return {}
        
        buy_trades = [t for t in trades if t['action'] == 'buy']
        sell_trades = [t for t in trades if t['action'] == 'sell']
        
        # 거래 쌍 매칭 (매수-매도)
        trade_pairs = []
        for sell_trade in sell_trades:
            if sell_trade.get('pnl', 0) != 0:
                trade_pairs.append({
                    'pnl': sell_trade['pnl'],
                    'return_pct': sell_trade['pnl'] / sell_trade['amount'] if sell_trade['amount'] > 0 else 0,
                    'hold_time': self._calculate_hold_time(buy_trades, sell_trade)
                })
        
        if not trade_pairs:
            return {}
        
        pnls = [tp['pnl'] for tp in trade_pairs]
        returns = [tp['return_pct'] for tp in trade_pairs]
        hold_times = [tp['hold_time'] for tp in trade_pairs if tp['hold_time'] is not None]
        
        return {
            'total_trades': len(trade_pairs),
            'profitable_trades': len([p for p in pnls if p > 0]),
            'losing_trades': len([p for p in pnls if p < 0]),
            'win_rate': len([p for p in pnls if p > 0]) / len(pnls),
            'avg_profit': np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0,
            'avg_loss': np.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0,
            'profit_factor': abs(sum([p for p in pnls if p > 0]) / sum([p for p in pnls if p < 0])) 
                           if sum([p for p in pnls if p < 0]) < 0 else float('inf'),
            'best_trade': max(pnls),
            'worst_trade': min(pnls),
            'avg_return': np.mean(returns),
            'return_std': np.std(returns),
            'avg_hold_time_hours': np.mean(hold_times) if hold_times else 0,
            'median_hold_time_hours': np.median(hold_times) if hold_times else 0
        }
    
    def _calculate_hold_time(self, buy_trades: List[Dict], sell_trade: Dict) -> Optional[float]:
        """보유 시간 계산"""
        try:
            sell_time = datetime.fromisoformat(sell_trade['timestamp'].replace('Z', '+00:00'))
            
            # 가장 가까운 매수 거래 찾기
            closest_buy = None
            min_time_diff = float('inf')
            
            for buy_trade in buy_trades:
                buy_time = datetime.fromisoformat(buy_trade['timestamp'].replace('Z', '+00:00'))
                if buy_time <= sell_time:
                    time_diff = (sell_time - buy_time).total_seconds()
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        closest_buy = buy_trade
            
            if closest_buy:
                buy_time = datetime.fromisoformat(closest_buy['timestamp'].replace('Z', '+00:00'))
                return (sell_time - buy_time).total_seconds() / 3600  # 시간 단위
            
        except Exception as e:
            self.logger.warning(f"보유 시간 계산 오류: {e}")
        
        return None
    
    def _analyze_portfolio(self, portfolio_history: List[Dict]) -> Dict:
        """포트폴리오 분석"""
        if not portfolio_history:
            return {}
        
        df = pd.DataFrame(portfolio_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # 일일 수익률 계산
        df['daily_return'] = df['total_value'].pct_change().fillna(0)
        
        # 누적 수익률
        df['cumulative_return'] = (df['total_value'] / df['total_value'].iloc[0]) - 1
        
        # 변동성 지표
        daily_vol = df['daily_return'].std()
        annual_vol = daily_vol * np.sqrt(365)
        
        # VaR 계산 (95% 신뢰구간)
        var_95 = np.percentile(df['daily_return'], 5)
        
        return {
            'portfolio_evolution': df.to_dict('records'),
            'daily_volatility': daily_vol,
            'annual_volatility': annual_vol,
            'var_95_daily': var_95,
            'var_95_annual': var_95 * np.sqrt(365),
            'skewness': df['daily_return'].skew(),
            'kurtosis': df['daily_return'].kurtosis(),
            'positive_days': len(df[df['daily_return'] > 0]),
            'negative_days': len(df[df['daily_return'] < 0]),
            'max_daily_gain': df['daily_return'].max(),
            'max_daily_loss': df['daily_return'].min()
        }
    
    def _analyze_risk(self, portfolio_history: List[Dict]) -> Dict:
        """위험 분석"""
        if not portfolio_history:
            return {}
        
        df = pd.DataFrame(portfolio_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # 낙폭 분석
        df['peak'] = df['total_value'].expanding().max()
        df['drawdown'] = (df['total_value'] - df['peak']) / df['peak']
        
        # 낙폭 기간 분석
        drawdown_periods = self._identify_drawdown_periods(df)
        
        # 하방 편차 (Downside Deviation)
        daily_returns = df['total_value'].pct_change().fillna(0)
        negative_returns = daily_returns[daily_returns < 0]
        downside_deviation = negative_returns.std() * np.sqrt(365)
        
        # 소르티노 비율
        excess_return = daily_returns.mean() * 365
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
        
        return {
            'max_drawdown': abs(df['drawdown'].min()),
            'avg_drawdown': abs(df['drawdown'][df['drawdown'] < 0].mean()) if any(df['drawdown'] < 0) else 0,
            'drawdown_periods': len(drawdown_periods),
            'longest_drawdown_days': max([dp['duration_days'] for dp in drawdown_periods]) if drawdown_periods else 0,
            'downside_deviation': downside_deviation,
            'sortino_ratio': sortino_ratio,
            'var_analysis': self._calculate_var_analysis(daily_returns),
            'stress_scenarios': self._stress_test_scenarios(df)
        }
    
    def _identify_drawdown_periods(self, df: pd.DataFrame) -> List[Dict]:
        """낙폭 기간 식별"""
        periods = []
        in_drawdown = False
        start_idx = None
        
        for i, row in df.iterrows():
            if row['drawdown'] < -0.01 and not in_drawdown:  # 1% 이상 낙폭 시작
                in_drawdown = True
                start_idx = i
            elif row['drawdown'] >= 0 and in_drawdown:  # 낙폭 종료
                end_idx = i
                period_df = df.loc[start_idx:end_idx]
                
                periods.append({
                    'start_date': period_df.iloc[0]['timestamp'],
                    'end_date': period_df.iloc[-1]['timestamp'],
                    'duration_days': (period_df.iloc[-1]['timestamp'] - period_df.iloc[0]['timestamp']).days,
                    'max_drawdown': abs(period_df['drawdown'].min()),
                    'recovery_days': 0  # 회복 기간은 별도 계산 필요
                })
                
                in_drawdown = False
        
        return periods
    
    def _calculate_var_analysis(self, returns: pd.Series) -> Dict:
        """VaR 분석"""
        return {
            'var_90': np.percentile(returns, 10),
            'var_95': np.percentile(returns, 5),
            'var_99': np.percentile(returns, 1),
            'cvar_95': returns[returns <= np.percentile(returns, 5)].mean(),  # Conditional VaR
            'extreme_loss_days': len(returns[returns < np.percentile(returns, 1)])
        }
    
    def _stress_test_scenarios(self, df: pd.DataFrame) -> Dict:
        """스트레스 테스트 시나리오"""
        daily_returns = df['total_value'].pct_change().fillna(0)
        
        return {
            'market_crash_10pct': self._simulate_crash(df, -0.10),
            'market_crash_20pct': self._simulate_crash(df, -0.20),
            'volatility_spike_2x': self._simulate_volatility_spike(daily_returns, 2.0),
            'consecutive_loss_scenario': self._simulate_consecutive_losses(daily_returns, 5)
        }
    
    def _simulate_crash(self, df: pd.DataFrame, crash_magnitude: float) -> Dict:
        """시장 급락 시나리오"""
        initial_value = df['total_value'].iloc[-1]
        crashed_value = initial_value * (1 + crash_magnitude)
        
        return {
            'scenario': f"시장 {abs(crash_magnitude)*100:.0f}% 급락",
            'portfolio_impact': crash_magnitude,
            'recovery_target': initial_value,
            'estimated_recovery_days': abs(crash_magnitude) / 0.001 if crash_magnitude < 0 else 0  # 일일 0.1% 회복 가정
        }
    
    def _simulate_volatility_spike(self, returns: pd.Series, multiplier: float) -> Dict:
        """변동성 급증 시나리오"""
        normal_vol = returns.std()
        spiked_vol = normal_vol * multiplier
        
        return {
            'scenario': f"변동성 {multiplier}배 증가",
            'normal_volatility': normal_vol,
            'spiked_volatility': spiked_vol,
            'risk_increase': (spiked_vol - normal_vol) / normal_vol
        }
    
    def _simulate_consecutive_losses(self, returns: pd.Series, days: int) -> Dict:
        """연속 손실 시나리오"""
        avg_loss = returns[returns < 0].mean() if any(returns < 0) else -0.01
        consecutive_impact = (1 + avg_loss) ** days - 1
        
        return {
            'scenario': f"{days}일 연속 손실",
            'avg_daily_loss': avg_loss,
            'cumulative_impact': consecutive_impact,
            'probability': (len(returns[returns < 0]) / len(returns)) ** days
        }
    
    def _analyze_strategy_contribution(self, trades: List[Dict]) -> Dict:
        """전략별 기여도 분석"""
        if not trades:
            return {}
        
        strategy_stats = {}
        
        for trade in trades:
            strategies = trade.get('strategy_signals', [])
            pnl = trade.get('pnl', 0)
            
            for strategy in strategies:
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        'trades': 0,
                        'total_pnl': 0,
                        'wins': 0,
                        'losses': 0
                    }
                
                strategy_stats[strategy]['trades'] += 1
                strategy_stats[strategy]['total_pnl'] += pnl
                
                if pnl > 0:
                    strategy_stats[strategy]['wins'] += 1
                elif pnl < 0:
                    strategy_stats[strategy]['losses'] += 1
        
        # 승률과 평균 수익 계산
        for strategy, stats in strategy_stats.items():
            stats['win_rate'] = stats['wins'] / stats['trades'] if stats['trades'] > 0 else 0
            stats['avg_pnl'] = stats['total_pnl'] / stats['trades'] if stats['trades'] > 0 else 0
        
        return strategy_stats
    
    def _analyze_time_patterns(self, trades: List[Dict]) -> Dict:
        """시간대별 패턴 분석"""
        if not trades:
            return {}
        
        time_analysis = {
            'hourly_distribution': {},
            'daily_distribution': {},
            'monthly_performance': {}
        }
        
        for trade in trades:
            try:
                timestamp = datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00'))
                hour = timestamp.hour
                day = timestamp.strftime('%A')
                month = timestamp.strftime('%B')
                pnl = trade.get('pnl', 0)
                
                # 시간대별
                if hour not in time_analysis['hourly_distribution']:
                    time_analysis['hourly_distribution'][hour] = {'trades': 0, 'total_pnl': 0}
                time_analysis['hourly_distribution'][hour]['trades'] += 1
                time_analysis['hourly_distribution'][hour]['total_pnl'] += pnl
                
                # 요일별
                if day not in time_analysis['daily_distribution']:
                    time_analysis['daily_distribution'][day] = {'trades': 0, 'total_pnl': 0}
                time_analysis['daily_distribution'][day]['trades'] += 1
                time_analysis['daily_distribution'][day]['total_pnl'] += pnl
                
                # 월별
                if month not in time_analysis['monthly_performance']:
                    time_analysis['monthly_performance'][month] = {'trades': 0, 'total_pnl': 0}
                time_analysis['monthly_performance'][month]['trades'] += 1
                time_analysis['monthly_performance'][month]['total_pnl'] += pnl
                
            except Exception as e:
                self.logger.warning(f"시간 패턴 분석 오류: {e}")
        
        return time_analysis
    
    def _analyze_drawdowns(self, portfolio_history: List[Dict]) -> Dict:
        """상세 낙폭 분석"""
        if not portfolio_history:
            return {}
        
        df = pd.DataFrame(portfolio_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # 모든 낙폭 구간 식별
        df['peak'] = df['total_value'].expanding().max()
        df['drawdown'] = (df['total_value'] - df['peak']) / df['peak']
        
        # 낙폭 통계
        drawdown_stats = {
            'max_drawdown': abs(df['drawdown'].min()),
            'avg_drawdown': abs(df['drawdown'][df['drawdown'] < 0].mean()) if any(df['drawdown'] < 0) else 0,
            'drawdown_frequency': len(df[df['drawdown'] < -0.05]) / len(df),  # 5% 이상 낙폭 빈도
            'recovery_analysis': self._analyze_recovery_patterns(df)
        }
        
        return drawdown_stats
    
    def _analyze_recovery_patterns(self, df: pd.DataFrame) -> Dict:
        """회복 패턴 분석"""
        recovery_times = []
        
        # 낙폭 구간별 회복 시간 계산
        in_drawdown = False
        drawdown_start = None
        peak_value = None
        
        for i, row in df.iterrows():
            if row['drawdown'] < -0.05 and not in_drawdown:  # 5% 이상 낙폭 시작
                in_drawdown = True
                drawdown_start = i
                peak_value = row['peak']
            elif row['total_value'] >= peak_value and in_drawdown:  # 신고점 회복
                recovery_days = (row['timestamp'] - df.loc[drawdown_start, 'timestamp']).days
                recovery_times.append(recovery_days)
                in_drawdown = False
        
        return {
            'avg_recovery_days': np.mean(recovery_times) if recovery_times else 0,
            'median_recovery_days': np.median(recovery_times) if recovery_times else 0,
            'max_recovery_days': max(recovery_times) if recovery_times else 0,
            'recovery_success_rate': len(recovery_times) / max(1, len(recovery_times) + (1 if in_drawdown else 0))
        }
    
    def generate_report(self, analysis: Dict, output_path: str = None) -> str:
        """분석 보고서 생성"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"backtesting/reports/performance_report_{timestamp}.html"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        html_content = self._generate_html_report(analysis)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"성과 보고서 생성됨: {output_path}")
        return output_path
    
    def _generate_html_report(self, analysis: Dict) -> str:
        """HTML 보고서 생성"""
        basic_metrics = analysis.get('basic_metrics', {})
        trade_analysis = analysis.get('trade_analysis', {})
        risk_analysis = analysis.get('risk_analysis', {})
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <title>백테스팅 성과 분석 보고서</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ margin: 10px 0; }}
                .section {{ margin: 30px 0; border: 1px solid #ddd; padding: 20px; }}
                .grade-A {{ color: #28a745; font-weight: bold; }}
                .grade-B {{ color: #ffc107; font-weight: bold; }}
                .grade-C {{ color: #dc3545; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>백테스팅 성과 분석 보고서</h1>
            <p>생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="section">
                <h2>기본 성과 지표</h2>
                <div class="metric">성과 등급: <span class="grade-{basic_metrics.get('performance_grade', 'C')[0]}">{basic_metrics.get('performance_grade', 'N/A')}</span></div>
                <div class="metric">총 수익률: {basic_metrics.get('total_return', 0):.2%}</div>
                <div class="metric">연환산 수익률: {basic_metrics.get('annualized_return', 0):.2%}</div>
                <div class="metric">샤프 비율: {basic_metrics.get('sharpe_ratio', 0):.2f}</div>
                <div class="metric">칼마 비율: {basic_metrics.get('calmar_ratio', 0):.2f}</div>
                <div class="metric">최대 낙폭: {basic_metrics.get('max_drawdown', 0):.2%}</div>
                <div class="metric">승률: {basic_metrics.get('win_rate', 0):.1%}</div>
                <div class="metric">알파 (시장 초과수익): {basic_metrics.get('alpha', 0):.2%}</div>
            </div>
            
            <div class="section">
                <h2>거래 분석</h2>
                <div class="metric">총 거래 수: {trade_analysis.get('total_trades', 0)}</div>
                <div class="metric">수익 거래: {trade_analysis.get('profitable_trades', 0)}</div>
                <div class="metric">손실 거래: {trade_analysis.get('losing_trades', 0)}</div>
                <div class="metric">승률: {trade_analysis.get('win_rate', 0):.1%}</div>
                <div class="metric">평균 수익: {trade_analysis.get('avg_profit', 0):,.0f}원</div>
                <div class="metric">평균 손실: {trade_analysis.get('avg_loss', 0):,.0f}원</div>
                <div class="metric">수익 팩터: {trade_analysis.get('profit_factor', 0):.2f}</div>
                <div class="metric">최고 거래: {trade_analysis.get('best_trade', 0):,.0f}원</div>
                <div class="metric">최악 거래: {trade_analysis.get('worst_trade', 0):,.0f}원</div>
                <div class="metric">평균 보유 시간: {trade_analysis.get('avg_hold_time_hours', 0):.1f}시간</div>
            </div>
            
            <div class="section">
                <h2>위험 분석</h2>
                <div class="metric">최대 낙폭: {risk_analysis.get('max_drawdown', 0):.2%}</div>
                <div class="metric">평균 낙폭: {risk_analysis.get('avg_drawdown', 0):.2%}</div>
                <div class="metric">낙폭 기간 수: {risk_analysis.get('drawdown_periods', 0)}</div>
                <div class="metric">최장 낙폭 기간: {risk_analysis.get('longest_drawdown_days', 0)}일</div>
                <div class="metric">하방 편차: {risk_analysis.get('downside_deviation', 0):.2%}</div>
                <div class="metric">소르티노 비율: {risk_analysis.get('sortino_ratio', 0):.2f}</div>
            </div>
        </body>
        </html>
        """
        
        return html


if __name__ == "__main__":
    # 성과 분석 실행 예시
    analyzer = PerformanceAnalyzer()
    
    # 백테스트 결과 파일 경로 (실제 파일 경로로 변경)
    result_file = "backtesting/results/backtest_20250713_120000.json"
    
    try:
        # 결과 로드
        results = analyzer.load_backtest_results(result_file)
        
        if results:
            # 성과 분석
            analysis = analyzer.analyze_performance(results)
            
            # 주요 지표 출력
            basic_metrics = analysis.get('basic_metrics', {})
            print("=== 성과 분석 결과 ===")
            print(f"성과 등급: {basic_metrics.get('performance_grade', 'N/A')}")
            print(f"총 수익률: {basic_metrics.get('total_return', 0):.2%}")
            print(f"샤프 비율: {basic_metrics.get('sharpe_ratio', 0):.2f}")
            print(f"최대 낙폭: {basic_metrics.get('max_drawdown', 0):.2%}")
            
            # 보고서 생성
            report_path = analyzer.generate_report(analysis)
            print(f"상세 보고서 생성됨: {report_path}")
        else:
            print("백테스트 결과를 로드할 수 없습니다.")
            
    except Exception as e:
        print(f"성과 분석 오류: {e}")