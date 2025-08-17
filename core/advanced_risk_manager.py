"""
고급 리스크 관리 시스템
ATR 기반 동적 손절매, 포지션 상관관계 관리, 손실 한도 제어
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import talib
import logging
from dataclasses import dataclass

@dataclass
class RiskMetrics:
    """리스크 메트릭스"""
    position_size: float
    stop_loss: float
    take_profits: List[Tuple[float, float]]
    max_risk_amount: float
    risk_reward_ratio: float
    correlation_score: float
    kelly_fraction: float

class AdvancedRiskManager:
    """고급 리스크 관리자"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger('AdvancedRiskManager')
        
        # 손실 추적
        self.daily_loss = 0
        self.weekly_loss = 0
        self.monthly_loss = 0
        self.last_reset = {
            'daily': datetime.now().date(),
            'weekly': datetime.now().date(),
            'monthly': datetime.now().date()
        }
        
        # 포지션 상관관계
        self.active_positions = {}
        self.correlation_matrix = pd.DataFrame()
        
        # 성과 추적
        self.trade_history = []
        self.equity_curve = []
        
    def calculate_atr_stop_loss(self, 
                               df: pd.DataFrame,
                               entry_price: float,
                               direction: str = 'long',
                               multiplier: float = 1.5) -> float:
        """
        ATR 기반 동적 손절매 계산
        """
        # ATR 계산
        atr = talib.ATR(
            df['high'].values, 
            df['low'].values, 
            df['close'].values, 
            timeperiod=14
        )
        current_atr = atr[-1]
        
        # 변동성 조정 (높은 변동성일 때 더 넓은 손절)
        volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
        volatility_adj = 1 + (volatility * 2)  # 변동성에 비례하여 조정
        
        adjusted_multiplier = multiplier * volatility_adj
        
        if direction == 'long':
            stop_loss = entry_price - (current_atr * adjusted_multiplier)
            
            # 최근 스윙 로우 확인
            recent_low = df['low'].rolling(10).min().iloc[-1]
            stop_loss = max(stop_loss, recent_low * 0.995)  # 스윙 로우 아래
            
        else:  # short
            stop_loss = entry_price + (current_atr * adjusted_multiplier)
            
            # 최근 스윙 하이 확인
            recent_high = df['high'].rolling(10).max().iloc[-1]
            stop_loss = min(stop_loss, recent_high * 1.005)  # 스윙 하이 위
        
        self.logger.info(f"ATR Stop Loss: {stop_loss:.2f} (ATR: {current_atr:.2f}, Multiplier: {adjusted_multiplier:.2f})")
        
        return stop_loss
    
    def calculate_volume_profile_poc(self, df: pd.DataFrame, period: int = 100) -> Dict:
        """
        볼륨 프로파일 POC (Point of Control) 계산
        """
        # 최근 N개 봉의 가격대별 거래량 분석
        recent_df = df.tail(period).copy()
        
        # 가격 구간 설정 (50개 구간)
        price_bins = 50
        min_price = recent_df['low'].min()
        max_price = recent_df['high'].max()
        price_range = max_price - min_price
        bin_size = price_range / price_bins
        
        # 각 구간별 거래량 계산
        volume_profile = {}
        
        for i in range(price_bins):
            bin_low = min_price + (i * bin_size)
            bin_high = bin_low + bin_size
            
            # 해당 구간에서의 거래량
            mask = (recent_df['close'] >= bin_low) & (recent_df['close'] < bin_high)
            volume_in_bin = recent_df.loc[mask, 'volume'].sum()
            
            volume_profile[f"{bin_low:.0f}-{bin_high:.0f}"] = {
                'volume': volume_in_bin,
                'price': (bin_low + bin_high) / 2
            }
        
        # POC 찾기 (가장 많은 거래량이 발생한 가격대)
        poc_range = max(volume_profile.items(), key=lambda x: x[1]['volume'])
        poc_price = poc_range[1]['price']
        
        # Value Area 계산 (전체 거래량의 70%가 발생한 구간)
        total_volume = sum(v['volume'] for v in volume_profile.values())
        sorted_profile = sorted(volume_profile.items(), key=lambda x: x[1]['volume'], reverse=True)
        
        cumulative_volume = 0
        value_area_high = 0
        value_area_low = float('inf')
        
        for range_key, data in sorted_profile:
            cumulative_volume += data['volume']
            value_area_high = max(value_area_high, data['price'])
            value_area_low = min(value_area_low, data['price'])
            
            if cumulative_volume >= total_volume * 0.7:
                break
        
        current_price = df['close'].iloc[-1]
        poc_distance = abs(current_price - poc_price) / poc_price
        
        return {
            'poc_price': poc_price,
            'poc_distance': poc_distance,
            'value_area_high': value_area_high,
            'value_area_low': value_area_low,
            'in_value_area': value_area_low <= current_price <= value_area_high,
            'above_poc': current_price > poc_price
        }
    
    def check_position_correlation(self, 
                                  new_symbol: str,
                                  new_direction: str,
                                  correlation_data: pd.DataFrame = None) -> Dict:
        """
        포지션 간 상관관계 체크
        """
        if not self.active_positions:
            return {'allowed': True, 'correlation_score': 0, 'reason': '활성 포지션 없음'}
        
        # 상관관계 임계값
        max_correlation = self.config.get_config('risk_management.max_correlation', 0.7)
        max_correlated_positions = self.config.get_config('risk_management.max_correlated_positions', 2)
        
        # 현재 활성 포지션과의 상관관계 계산
        high_correlation_count = 0
        correlation_scores = []
        
        for position_id, position_data in self.active_positions.items():
            # 같은 방향의 포지션만 체크
            if position_data['direction'] == new_direction:
                # 실제로는 가격 데이터로 상관관계 계산
                # 여기서는 예시로 랜덤 값 사용
                correlation = self._calculate_correlation(new_symbol, position_data['symbol'])
                correlation_scores.append(correlation)
                
                if correlation > max_correlation:
                    high_correlation_count += 1
        
        avg_correlation = np.mean(correlation_scores) if correlation_scores else 0
        
        # 상관관계가 높은 포지션이 너무 많으면 거부
        if high_correlation_count >= max_correlated_positions:
            return {
                'allowed': False,
                'correlation_score': avg_correlation,
                'reason': f'상관관계 높은 포지션 {high_correlation_count}개 (한도: {max_correlated_positions})'
            }
        
        return {
            'allowed': True,
            'correlation_score': avg_correlation,
            'reason': f'상관관계 체크 통과 (평균: {avg_correlation:.2f})'
        }
    
    def _calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        두 심볼 간 상관관계 계산
        실제 구현에서는 과거 가격 데이터 사용
        """
        # 임시로 고정값 반환
        if symbol1 == symbol2:
            return 1.0
        return np.random.uniform(0.3, 0.8)
    
    def check_loss_limits(self) -> Dict:
        """
        일일/주간/월간 손실 한도 체크
        """
        self._reset_periods()
        
        # 한도 설정
        daily_limit = self.config.get_config('risk_management.daily_loss_limit', 50000)
        weekly_limit = self.config.get_config('risk_management.weekly_loss_limit', 150000)
        monthly_limit = self.config.get_config('risk_management.monthly_loss_limit', 300000)
        
        checks = {
            'daily': {
                'loss': self.daily_loss,
                'limit': daily_limit,
                'exceeded': self.daily_loss >= daily_limit,
                'remaining': daily_limit - self.daily_loss
            },
            'weekly': {
                'loss': self.weekly_loss,
                'limit': weekly_limit,
                'exceeded': self.weekly_loss >= weekly_limit,
                'remaining': weekly_limit - self.weekly_loss
            },
            'monthly': {
                'loss': self.monthly_loss,
                'limit': monthly_limit,
                'exceeded': self.monthly_loss >= monthly_limit,
                'remaining': monthly_limit - self.monthly_loss
            }
        }
        
        # 거래 가능 여부
        can_trade = not any(check['exceeded'] for check in checks.values())
        
        # 가장 제한적인 남은 한도
        min_remaining = min(check['remaining'] for check in checks.values())
        
        return {
            'can_trade': can_trade,
            'checks': checks,
            'max_risk_amount': max(min_remaining, 0),
            'reason': self._get_limit_reason(checks)
        }
    
    def _reset_periods(self):
        """기간별 손실 리셋"""
        now = datetime.now().date()
        
        # 일일 리셋
        if now != self.last_reset['daily']:
            self.daily_loss = 0
            self.last_reset['daily'] = now
            self.logger.info("일일 손실 카운터 리셋")
        
        # 주간 리셋 (월요일)
        if now.weekday() == 0 and (now - self.last_reset['weekly']).days >= 7:
            self.weekly_loss = 0
            self.last_reset['weekly'] = now
            self.logger.info("주간 손실 카운터 리셋")
        
        # 월간 리셋
        if now.month != self.last_reset['monthly'].month:
            self.monthly_loss = 0
            self.last_reset['monthly'] = now
            self.logger.info("월간 손실 카운터 리셋")
    
    def _get_limit_reason(self, checks: Dict) -> str:
        """손실 한도 이유 생성"""
        reasons = []
        for period, check in checks.items():
            if check['exceeded']:
                reasons.append(f"{period} 한도 초과 ({check['loss']:,.0f}/{check['limit']:,.0f})")
        
        if reasons:
            return ", ".join(reasons)
        return "모든 손실 한도 내"
    
    def calculate_position_size_kelly(self,
                                     win_rate: float,
                                     avg_win: float,
                                     avg_loss: float,
                                     account_balance: float,
                                     signal_strength: float = 1.0,
                                     volatility: float = 0.02) -> float:
        """
        Kelly Criterion을 사용한 포지션 크기 계산
        """
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0
        
        # Kelly Formula: f = (p * b - q) / b
        # p = win_rate, q = 1 - win_rate, b = avg_win / avg_loss
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (p * b - q) / b
        
        # Kelly의 25%만 사용 (보수적)
        conservative_kelly = kelly_fraction * 0.25
        
        # 변동성 조정 (변동성이 높을수록 포지션 축소)
        volatility_adjustment = 1 / (1 + volatility * 10)
        
        # 신호 강도 조정
        signal_adjustment = signal_strength ** 2
        
        # 최종 포지션 크기
        position_fraction = conservative_kelly * volatility_adjustment * signal_adjustment
        
        # 한계 설정
        max_position = self.config.get_config('risk_management.max_position_size_percent', 10) / 100
        position_fraction = max(min(position_fraction, max_position), 0)
        
        position_size = account_balance * position_fraction
        
        # 손실 한도 체크
        loss_limits = self.check_loss_limits()
        if not loss_limits['can_trade']:
            return 0
        
        # 최대 리스크 금액으로 제한
        max_risk = loss_limits['max_risk_amount']
        if position_size > max_risk:
            position_size = max_risk
            self.logger.warning(f"포지션 크기를 손실 한도로 제한: {position_size:,.0f}")
        
        return position_size
    
    def calculate_take_profits(self,
                             entry_price: float,
                             atr: float,
                             direction: str = 'long',
                             risk_reward_targets: List[float] = None) -> List[Tuple[float, float]]:
        """
        부분 익절 목표가 계산
        """
        if risk_reward_targets is None:
            risk_reward_targets = [1.5, 2.5, 4.0]  # 리스크 대비 배수
        
        take_profits = []
        
        if direction == 'long':
            for i, rr in enumerate(risk_reward_targets):
                target_price = entry_price + (atr * rr)
                if i == 0:
                    percentage = 0.3  # 첫 목표: 30%
                elif i == 1:
                    percentage = 0.3  # 두 번째: 30%
                else:
                    percentage = 0.4  # 나머지: 40%
                
                take_profits.append((target_price, percentage))
        
        else:  # short
            for i, rr in enumerate(risk_reward_targets):
                target_price = entry_price - (atr * rr)
                if i == 0:
                    percentage = 0.3
                elif i == 1:
                    percentage = 0.3
                else:
                    percentage = 0.4
                
                take_profits.append((target_price, percentage))
        
        return take_profits
    
    def update_position(self, position_id: str, pnl: float):
        """포지션 업데이트 및 손실 추적"""
        if pnl < 0:
            loss = abs(pnl)
            self.daily_loss += loss
            self.weekly_loss += loss
            self.monthly_loss += loss
            
            self.logger.warning(f"손실 발생: {loss:,.0f} (일일: {self.daily_loss:,.0f})")
        
        # 포지션 제거
        if position_id in self.active_positions:
            del self.active_positions[position_id]
    
    def add_position(self, position_id: str, symbol: str, direction: str, size: float):
        """새 포지션 추가"""
        self.active_positions[position_id] = {
            'symbol': symbol,
            'direction': direction,
            'size': size,
            'entry_time': datetime.now()
        }
    
    def get_risk_metrics(self,
                        df: pd.DataFrame,
                        entry_price: float,
                        direction: str,
                        signal_strength: float,
                        account_balance: float) -> RiskMetrics:
        """
        종합 리스크 메트릭 계산
        """
        # ATR 기반 손절매
        stop_loss = self.calculate_atr_stop_loss(df, entry_price, direction)
        
        # ATR 계산
        atr = talib.ATR(
            df['high'].values,
            df['low'].values, 
            df['close'].values,
            timeperiod=14
        )[-1]
        
        # 부분 익절 목표
        take_profits = self.calculate_take_profits(entry_price, atr, direction)
        
        # Kelly 포지션 크기
        # 실제 백테스팅 결과 사용 필요
        win_rate = 0.55
        avg_win = 0.025
        avg_loss = 0.015
        volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
        
        position_size = self.calculate_position_size_kelly(
            win_rate, avg_win, avg_loss, account_balance,
            signal_strength, volatility
        )
        
        # 리스크/리워드 비율
        risk = abs(entry_price - stop_loss) / entry_price
        reward = abs(take_profits[-1][0] - entry_price) / entry_price
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # 최대 리스크 금액
        max_risk_amount = position_size * risk
        
        # Kelly fraction
        b = avg_win / avg_loss
        kelly_fraction = (win_rate * b - (1 - win_rate)) / b
        
        return RiskMetrics(
            position_size=position_size,
            stop_loss=stop_loss,
            take_profits=take_profits,
            max_risk_amount=max_risk_amount,
            risk_reward_ratio=risk_reward_ratio,
            correlation_score=0,  # 별도 계산 필요
            kelly_fraction=kelly_fraction
        )