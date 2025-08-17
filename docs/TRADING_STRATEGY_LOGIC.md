# 비트코인 자동매매 전략 로직 문서
## Professional Trading Strategy Logic Documentation

---

## 📊 전략 개요 (Strategy Overview)

본 문서는 비트코인 자동매매 시스템의 16개 전략에 대한 전문적인 구현 로직을 정의합니다.
각 전략은 백테스팅을 통해 검증되며, 시장 상황에 따라 동적으로 조정됩니다.

### 전략 분류
- **시간봉 전략 (Hourly)**: h1-h8 (8개)
- **일봉 전략 (Daily)**: d1-d8 (8개)

---

## 🎯 시간봉 전략 (Hourly Strategies)

### H1: EMA 크로스오버 전략 (EMA Crossover Strategy)

#### 이론적 배경
EMA(지수이동평균)는 최근 가격에 더 큰 가중치를 부여하여 SMA보다 빠른 신호를 제공합니다.

#### 구체적 로직
```python
# 파라미터
fast_ema_period = 12  # 빠른 EMA (적응형: 8-13)
slow_ema_period = 26  # 느린 EMA (적응형: 21-34)
signal_ema = 50       # 필터용 EMA

# 진입 조건
LONG_ENTRY:
  - fast_ema > slow_ema (골든크로스)
  - price > signal_ema (상승 추세 확인)
  - volume > volume_ma20 * 1.5 (거래량 확인)
  - RSI > 40 AND RSI < 70 (과매수 회피)
  - ATR > 0.015 * price (충분한 변동성)

SHORT_ENTRY:
  - fast_ema < slow_ema (데드크로스)
  - price < signal_ema (하락 추세 확인)
  - volume > volume_ma20 * 1.5
  - RSI < 60 AND RSI > 30 (과매도 회피)

# 청산 조건
EXIT_LONG:
  - fast_ema < slow_ema OR
  - RSI > 80 OR
  - trailing_stop_triggered (ATR * 2)

EXIT_SHORT:
  - fast_ema > slow_ema OR
  - RSI < 20 OR
  - trailing_stop_triggered
```

#### 백테스팅 파라미터
- **최적화 기간**: 최근 6개월
- **목표 수익률**: 월 5-10%
- **최대 드로우다운**: 15%
- **승률 목표**: 45% 이상
- **손익비**: 1:1.5 이상

---

### H2: RSI 다이버전스 전략 (RSI Divergence Strategy)

#### 이론적 배경
가격과 RSI의 다이버전스는 추세 전환의 강력한 신호입니다.

#### 구체적 로직
```python
# 파라미터
rsi_period = 14
divergence_lookback = 20  # 다이버전스 탐지 기간
min_divergence_bars = 5   # 최소 다이버전스 봉 수

# 다이버전스 탐지 로직
BULLISH_DIVERGENCE:
  1. 가격: 새로운 저점 < 이전 저점
  2. RSI: 새로운 저점 > 이전 저점
  3. 최소 5봉 이상 간격
  4. RSI < 35 (과매도 구간)
  5. 볼륨 증가 확인

BEARISH_DIVERGENCE:
  1. 가격: 새로운 고점 > 이전 고점
  2. RSI: 새로운 고점 < 이전 고점
  3. 최소 5봉 이상 간격
  4. RSI > 65 (과매수 구간)

# 진입 강도 계산
signal_strength = calculate_divergence_strength(
    price_diff_percent,
    rsi_diff,
    time_between_peaks,
    volume_confirmation
)

# 포지션 크기
position_size = base_size * signal_strength * kelly_fraction
```

#### 필터링 조건
- **Hidden Divergence**: 추세 지속 신호로 활용
- **Multi-Timeframe**: 4H, 1D 차트에서도 확인
- **Volume Profile**: POC 근처에서만 진입

---

### H3: 피봇 포인트 반등 전략 (Pivot Point Bounce Strategy)

#### 이론적 배경
기관 트레이더들이 널리 사용하는 지지/저항 레벨입니다.

#### 구체적 로직
```python
# 피봇 계산 (일일 기준)
PP = (H + L + C) / 3
R1 = 2 * PP - L
R2 = PP + (H - L)
R3 = H + 2 * (PP - L)
S1 = 2 * PP - H
S2 = PP - (H - L)
S3 = L - 2 * (H - PP)

# Camarilla 피봇 (추가)
R4 = C + ((H - L) * 1.1 / 2)
R3 = C + ((H - L) * 1.1 / 4)
S3 = C - ((H - L) * 1.1 / 4)
S4 = C - ((H - L) * 1.1 / 2)

# 진입 조건
SUPPORT_BOUNCE:
  - price touches S1/S2 (오차 0.2%)
  - bullish_candle_pattern (hammer, doji)
  - RSI < 40 (과매도 근처)
  - volume spike > 1.5x average
  - MACD histogram turning positive

RESISTANCE_REJECTION:
  - price touches R1/R2
  - bearish_candle_pattern (shooting star)
  - RSI > 60
  - volume spike
  - MACD histogram turning negative

# 목표가
take_profit_1 = PP (중심 피봇)
take_profit_2 = next_pivot_level
stop_loss = beyond_pivot * 1.005
```

---

### H4: VWAP 되돌림 전략 (VWAP Pullback Strategy)

#### 이론적 배경
VWAP은 기관의 평균 매수가를 나타내며, 중요한 지지/저항선 역할을 합니다.

#### 구체적 로직
```python
# VWAP 계산
typical_price = (H + L + C) / 3
vwap = Σ(typical_price * volume) / Σ(volume)

# 표준편차 밴드
vwap_upper = vwap + (2 * std_dev)
vwap_lower = vwap - (2 * std_dev)

# 진입 조건
VWAP_LONG:
  - price pullback to vwap from above
  - bounce confirmation (2 green candles)
  - trend = uptrend (EMA20 > EMA50)
  - distance_from_vwap < 0.5%
  - cumulative_delta > 0 (매수 우세)

VWAP_SHORT:
  - price rally to vwap from below
  - rejection confirmation
  - trend = downtrend
  - cumulative_delta < 0 (매도 우세)

# Anchored VWAP (특별 이벤트 기준)
- 월초 VWAP
- 주요 뉴스 이벤트 VWAP
- 전고/전저 VWAP
```

---

### H5: MACD 히스토그램 전략 (MACD Histogram Strategy)

#### 이론적 배경
MACD 히스토그램은 모멘텀의 변화를 가장 빠르게 포착합니다.

#### 구체적 로직
```python
# MACD 설정
fast_ema = 12
slow_ema = 26
signal_ema = 9

# 진입 신호
HISTOGRAM_CROSS:
  - histogram crosses zero upward (매수)
  - histogram > prev_histogram (모멘텀 증가)
  - MACD line > signal line
  - price > EMA50
  - ADX > 25 (트렌드 존재)

# 다이버전스 추가
MACD_DIVERGENCE:
  - price_new_low < price_prev_low
  - macd_new_low > macd_prev_low
  - histogram expanding (긍정적)

# 청산
- histogram 색상 변경
- MACD signal line cross
- 다이버전스 발생
```

---

### H6: 볼린저 밴드 스퀴즈 전략 (Bollinger Band Squeeze Strategy)

#### 이론적 배경
변동성 수축 후 확장은 큰 가격 움직임을 예고합니다.

#### 구체적 로직
```python
# 볼린저 밴드
bb_period = 20
bb_std = 2.0

# Keltner Channel
kc_period = 20
kc_atr_mult = 1.5

# 스퀴즈 조건
SQUEEZE_ON:
  - BB_upper < KC_upper AND
  - BB_lower > KC_lower
  - 최소 6봉 이상 지속

SQUEEZE_RELEASE:
  - BB breaks outside KC
  - momentum oscillator 방향 확인
  - volume > 2x average

# TTM Squeeze 지표
momentum = close - SMA(close, 20)
if momentum > 0 and increasing:
    direction = "LONG"

# 진입
- squeeze 해제 + 방향 확인
- first pullback after breakout
- volume confirmation required
```

---

### H7: 미체결약정 & 펀딩비 전략 (Open Interest & Funding Strategy)

#### 이론적 배경
미체결약정과 펀딩비는 시장 센티먼트와 포지션 편향을 보여줍니다.

#### 구체적 로직
```python
# OI 분석
oi_change = (current_oi - prev_oi) / prev_oi

# 시나리오
BULLISH_OI:
  - price UP + OI UP = 신규 매수 (강세)
  - price DOWN + OI DOWN = 숏 청산 (반등 가능)

BEARISH_OI:
  - price DOWN + OI UP = 신규 매도 (약세)
  - price UP + OI DOWN = 롱 청산 (하락 가능)

# 펀딩비 활용
FUNDING_EXTREME:
  - funding > 0.05% = 과도한 롱 (숏 기회)
  - funding < -0.05% = 과도한 숏 (롱 기회)

# Long/Short Ratio
if long_ratio > 70%:
    contrarian_short_signal
elif short_ratio > 70%:
    contrarian_long_signal

# 청산 히트맵
liquidation_levels = calculate_liquidation_clusters()
avoid_entry_near_liquidations(margin=0.5%)
```

---

### H8: 깃발/페넌트 패턴 (Flag/Pennant Pattern Strategy)

#### 이론적 배경
강한 추세 후 짧은 조정은 추세 지속 가능성이 높습니다.

#### 구체적 로직
```python
# 패턴 인식
BULL_FLAG:
  1. 깃대: 20% 이상 급등 (3-5봉)
  2. 깃발: 평행 채널 하락 조정 (5-15봉)
  3. 조정 깊이: 깃대의 38.2-50% 피보나치
  4. 거래량: 깃대 > 깃발 거래량

# 진입 조건
FLAG_BREAKOUT:
  - upper channel break
  - volume > flagpole_volume
  - RSI > 50
  - MACD positive

# 목표가
target = flagpole_base + flagpole_height
stop_loss = flag_low

# 패턴 유효성
- 시간 제한: 20봉 이내 완성
- 조정 각도: 역방향 or 횡보
- 거래량 패턴: 감소 → 폭발
```

---

## 📈 일봉 전략 (Daily Strategies)

### D1: 주봉 필터 + 50일선 전략 (Weekly Filter + MA50 Strategy)

#### 구체적 로직
```python
# 다중 시간대 분석
WEEKLY_TREND:
  - weekly_close > weekly_SMA(20)
  - weekly_RSI > 50
  - weekly_MACD > signal

DAILY_ENTRY:
  - daily_price touches MA50
  - bounce pattern (hammer, bullish engulfing)
  - daily_RSI > 30 and turning up
  - volume > average_volume

# 포지션 관리
- scale in: 3 entries (30%, 40%, 30%)
- trailing stop: 2 * ATR(14)
- time stop: 10 days
```

---

### D2: 일목균형표 구름대 전략 (Ichimoku Cloud Strategy)

#### 구체적 로직
```python
# 일목균형표 설정 (크립토 최적화)
tenkan = 20  # 전환선 (기본 9)
kijun = 60   # 기준선 (기본 26)
senkou_b = 120  # 선행스팬B (기본 52)

# 진입 신호
KUMO_BREAKOUT:
  - price breaks above cloud
  - tenkan > kijun (TK cross)
  - chikou > price_26_ago
  - cloud ahead is green
  - future cloud expanding

# 구름대 반등
KUMO_BOUNCE:
  - price bounces from cloud top
  - strong trend (ADX > 30)
  - cloud thickness > ATR

# Kumo Twist 활용
- 구름 색상 변경 예측
- 미래 구름 분석
```

---

### D3: 볼린저밴드 폭 압축 전략 (Bollinger Band Width Compression)

#### 구체적 로직
```python
# BBW 계산
bbw = (upper_band - lower_band) / middle_band
bbw_percentile = percentile_rank(bbw, 126)  # 6개월

# 압축 조건
COMPRESSION:
  - bbw_percentile < 10 (역사적 저점)
  - ADX < 20 (횡보)
  - volume declining

# 돌파 신호
EXPANSION:
  - price closes outside bands
  - volume > 2x average
  - bbw expanding rapidly
  - momentum confirming direction

# Bollinger Band %B
%B = (price - lower) / (upper - lower)
if %B > 1: overbought
if %B < 0: oversold
```

---

### D4: 공포탐욕 지수 전략 (Fear & Greed Index Strategy)

#### 구체적 로직
```python
# 자체 공포탐욕 지수 계산
def calculate_fear_greed():
    components = {
        'price_momentum': sma_ratio_score(),  # 25%
        'volume': volume_score(),              # 25%
        'volatility': vix_equivalent_score(),  # 15%
        'market_dominance': btc_dominance(),   # 10%
        'social_sentiment': sentiment_score(), # 15%
        'funding_rate': funding_score()        # 10%
    }
    return weighted_average(components)

# 진입 조건
EXTREME_FEAR (< 20):
  - RSI < 30
  - price < BB_lower
  - bullish divergence
  - contrarian LONG

EXTREME_GREED (> 80):
  - RSI > 70
  - price > BB_upper
  - bearish divergence
  - contrarian SHORT

# 센티먼트 반전
- 3일 연속 극단 구간
- 다이버전스 확인
- 거래량 급증
```

---

### D5: 골든크로스 후 첫 눌림목 (Golden Cross First Pullback)

#### 구체적 로직
```python
# 골든크로스 확인
GOLDEN_CROSS:
  - MA50 > MA200
  - first cross in 6 months
  - volume confirmation
  - price > both MAs

# 눌림목 진입
PULLBACK_ENTRY:
  - first touch of MA50 after GC
  - bounce pattern formation
  - RSI oversold bounce
  - MACD histogram turning positive
  - volume on bounce > pullback volume

# Risk Management
- stop: below MA50 or recent low
- target: previous high or 1.5R
- position size: 2% risk
```

---

### D6: MVRV Z-Score 전략 (On-Chain Value Strategy)

#### 구체적 로직
```python
# MVRV Z-Score
market_cap = current_price * circulating_supply
realized_cap = Σ(utxo_value_at_creation)
mvrv = market_cap / realized_cap
z_score = (market_cap - realized_cap) / std_dev

# 신호
UNDERVALUED:
  - z_score < 0.1 (역사적 저점)
  - accumulation phase
  - DCA entry strategy

OVERVALUED:
  - z_score > 7 (역사적 고점)
  - distribution phase
  - DCA exit strategy

# 추가 온체인 지표
- Net Unrealized Profit/Loss (NUPL)
- Spent Output Profit Ratio (SOPR)
- Puell Multiple
- Stock-to-Flow Deviation
```

---

### D7: 스토캐스틱 RSI 전략 (Stochastic RSI Strategy)

#### 구체적 로직
```python
# Stoch RSI 설정
rsi_period = 14
stoch_period = 14
k_smooth = 3
d_smooth = 3

# 진입 조건
OVERSOLD_REVERSAL:
  - StochRSI < 20 for 3+ bars
  - K line crosses above D line
  - price > MA200 (상승 추세)
  - volume confirmation

OVERBOUGHT_REVERSAL:
  - StochRSI > 80 for 3+ bars
  - K line crosses below D line
  - price < MA200 (하락 추세)

# Double Bottom/Top
- StochRSI double bottom in oversold
- price higher low (divergence)
- strong buy signal
```

---

### D8: ADX 추세 강도 메타 전략 (ADX Trend Strength Meta Strategy)

#### 구체적 로직
```python
# ADX 기반 전략 선택
def select_strategy_by_market():
    adx_value = calculate_adx(14)
    
    if adx_value > 30:  # Strong Trend
        return ['golden_cross', 'ema_cross', 'ichimoku']
    elif adx_value < 20:  # Range Bound
        return ['bollinger_bands', 'pivot_points', 'rsi_oversold']
    else:  # Developing Trend
        return ['macd', 'vwap', 'flag_pattern']

# 시장 체제 변화 감지
REGIME_CHANGE:
  - ADX crossing 25 (trend starting)
  - ADX > 40 then declining (trend exhaustion)
  - DI+ and DI- crossover

# 포지션 크기 조정
position_multiplier = min(adx_value / 25, 2.0)
```

---

## 🎯 리스크 관리 매트릭스

### 포지션 사이징
```python
def calculate_position_size(strategy_signal):
    # Kelly Criterion (보수적)
    kelly_f = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win
    conservative_kelly = kelly_f * 0.25
    
    # 변동성 조정
    current_volatility = calculate_atr(14) / price
    vol_adjustment = base_volatility / current_volatility
    
    # 상관관계 조정
    correlation_penalty = calculate_correlation_penalty()
    
    # 최종 포지션
    position = account_balance * conservative_kelly * vol_adjustment * correlation_penalty
    
    # 한계 적용
    position = min(position, account_balance * 0.1)  # 최대 10%
    position = max(position, min_trade_amount)       # 최소 거래량
    
    return position
```

### 손절매 설정
```python
def calculate_stop_loss(entry_price, strategy_type):
    methods = {
        'atr': entry_price - (2.0 * ATR(14)),
        'structure': find_recent_swing_low(),
        'percentage': entry_price * 0.97,
        'volatility': entry_price - (current_volatility * volatility_multiplier)
    }
    
    # 가장 타이트한 손절 선택
    stop_loss = max(methods.values())
    
    # 최대 손실 제한
    max_loss = entry_price * 0.95
    return max(stop_loss, max_loss)
```

### 부분 익절 전략
```python
PARTIAL_EXITS = [
    {'target': 1.5, 'exit_percent': 30},  # 1.5R에서 30% 익절
    {'target': 2.5, 'exit_percent': 30},  # 2.5R에서 30% 익절
    {'target': 4.0, 'exit_percent': 40},  # 4.0R에서 40% 익절
]
```

---

## 📊 백테스팅 파라미터

### 성과 지표 목표
- **샤프 비율**: > 1.5
- **소르티노 비율**: > 2.0
- **최대 드로우다운**: < 20%
- **승률**: > 45%
- **손익비**: > 1.5
- **연간 수익률**: 30-50%

### 최적화 방법
1. **Walk-Forward Analysis**: 6개월 학습, 2개월 검증
2. **Monte Carlo Simulation**: 1000회 시뮬레이션
3. **Stress Testing**: 2020년 3월, 2022년 5월 등 극단 시장
4. **Slippage & Commission**: 0.1% 슬리피지, 0.05% 수수료

---

## 🔄 전략 개선 프로세스

### 주간 리뷰
1. 각 전략별 성과 분석
2. 예상과 실제 결과 비교
3. 시장 체제 변화 확인
4. 파라미터 미세 조정

### 월간 최적화
1. 백테스팅 재실행
2. 새로운 필터 추가/제거
3. 포지션 사이징 조정
4. 상관관계 매트릭스 업데이트

### 분기별 전략 검토
1. 전략 유효성 평가
2. 새로운 전략 추가 검토
3. 저성과 전략 제거/수정
4. 리스크 한도 재설정

---

## 📝 구현 체크리스트

- [ ] 각 전략별 진입/청산 로직 구현
- [ ] 리스크 관리 시스템 통합
- [ ] 백테스팅 프레임워크 구축
- [ ] 실시간 모니터링 대시보드
- [ ] 성과 추적 시스템
- [ ] 알림 시스템 (진입/청산/경고)
- [ ] 전략 파라미터 최적화 도구
- [ ] A/B 테스팅 프레임워크

---

## ⚠️ 주의사항

1. **과최적화 방지**: In-sample과 out-of-sample 성과 차이 모니터링
2. **시장 체제 변화**: 전략이 작동하지 않는 시장 조건 정의
3. **블랙스완 이벤트**: 극단적 시장 상황 대비 (circuit breaker)
4. **상관관계 리스크**: 여러 전략이 동시에 같은 방향 포지션 방지
5. **실행 리스크**: 슬리피지, 부분 체결, 거래소 다운타임 대비

---

이 문서는 지속적으로 업데이트되며, 실제 거래 결과를 바탕으로 개선됩니다.