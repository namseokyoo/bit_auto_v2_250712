# Bitcoin Auto Trading Bot - System Architecture

## 시스템 구조

### 1. 백엔드 (자동 거래 봇)
**완전 독립적으로 실행되는 단일 프로세스**

#### 실행 방법
```bash
python auto_trader_service.py
```

#### 구성 요소
- **auto_trader_service.py**: 메인 실행 파일
- **core/auto_trader.py**: 스케줄링 및 거래 실행
- **core/trading_engine.py**: 거래 로직
- **core/result_manager.py**: 파일 기반 상태/결과 관리

#### 데이터 흐름
1. **설정 읽기**: `config/trading_config.json`
2. **상태 저장**: `data/results/status/current_status.json`
3. **분석 결과**: `data/results/analysis/latest_analysis.json`
4. **거래 기록**: `data/results/trades/trades_YYYYMMDD.jsonl`

### 2. 프론트엔드 (모니터링 대시보드)
**파일을 읽기만 하는 순수 모니터링 도구**

#### 실행 방법
```bash
python main.py --mode web
```

#### 역할
- **상태 모니터링**: status.json 파일 읽어서 표시
- **결과 확인**: analysis 파일들 읽어서 표시
- **설정 변경**: config 파일 수정 (봇이 자동으로 감지)

### 3. 파일 기반 통신

#### 디렉토리 구조
```
data/
├── results/
│   ├── status/
│   │   └── current_status.json      # 현재 봇 상태
│   ├── analysis/
│   │   ├── latest_analysis.json     # 최신 분석 결과
│   │   └── analysis_YYYYMMDD.jsonl  # 일별 분석 기록
│   └── trades/
│       └── trades_YYYYMMDD.jsonl    # 일별 거래 기록
└── trading_data.db                  # 데이터베이스 (선택적)
```

#### current_status.json 구조
```json
{
    "timestamp": "2025-08-18T10:30:00+09:00",
    "running": true,
    "auto_trading_enabled": true,
    "last_execution": "2025-08-18T10:20:00+09:00",
    "next_execution": "2025-08-18T10:30:00+09:00",
    "trade_count_today": 5,
    "last_action": "hold",
    "last_confidence": 0.65
}
```

### 4. 제어 방식

#### 자동 거래 On/Off
1. 대시보드에서 버튼 클릭
2. `config/trading_config.json`의 `trading.enabled` 값 변경
3. 봇이 config 파일 변경 감지
4. 자동으로 거래 활성화/비활성화

#### 설정 변경
1. 대시보드에서 설정 변경
2. config 파일 업데이트
3. 봇이 자동으로 새 설정 적용

### 5. 장점

1. **완전한 분리**: 백엔드와 프론트엔드가 완전히 독립적
2. **안정성**: 한쪽이 죽어도 다른 쪽은 계속 동작
3. **단순성**: 파일 기반으로 복잡한 통신 프로토콜 불필요
4. **투명성**: 모든 상태와 결과가 파일로 저장되어 확인 가능
5. **확장성**: 여러 모니터링 도구를 동시에 사용 가능

### 6. 주의사항

- **대시보드는 절대 거래 로직을 실행하지 않음**
- **대시보드는 파일을 읽기만 함 (config 제외)**
- **모든 시간 계산은 봇에서만 수행**
- **대시보드 새로고침이 봇 동작에 영향을 주지 않음**