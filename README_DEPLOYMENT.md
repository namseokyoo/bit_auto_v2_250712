# Quantum Trading System - 배포 가이드

## 📋 배포 준비 사항

### 1. GitHub Repository 설정
1. GitHub에 repository 생성 (예: `bit_auto_v2_250712`)
2. 로컬 코드를 GitHub에 푸시:
```bash
cd /Users/namseokyoo/project/bit_auto_v2_250712
git init
git add .
git commit -m "Initial commit: Quantum Trading System with AI feedback"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/bit_auto_v2_250712.git
git push -u origin main
```

### 2. GitHub Secrets 설정
GitHub Repository → Settings → Secrets and variables → Actions에서 다음 시크릿 추가:

- `ORACLE_SSH_KEY`: Oracle 서버 SSH 프라이빗 키
  ```bash
  # SSH 키 내용 복사 (전체 내용 포함)
  cat ~/.ssh/your_oracle_key
  ```

### 3. 환경 변수 설정
`config/.env.example` 파일 참고하여 실제 API 키 설정:
- `UPBIT_ACCESS_KEY`: Upbit API 액세스 키
- `UPBIT_SECRET_KEY`: Upbit API 시크릿 키
- `DEEPSEEK_API_KEY`: sk-ae644f698503467d80dbd125f443fa5d (이미 설정됨)

## 🚀 자동 배포 (GitHub Actions)

### 방법 1: Push를 통한 자동 배포
```bash
# 코드 수정 후
git add .
git commit -m "feat: 기능 설명"
git push origin main
```
→ 자동으로 테스트 실행 후 Oracle 서버에 배포됨

### 방법 2: 수동 배포 트리거
1. GitHub Repository → Actions 탭 이동
2. "Deploy Quantum Trading System" 워크플로우 선택
3. "Run workflow" 버튼 클릭
4. Branch 선택 (main) → "Run workflow" 클릭

## 🖥️ 수동 배포 (서버에서 직접)

### SSH 접속 및 배포
```bash
# 서버 접속
ssh -i ~/.ssh/your_key ubuntu@158.180.82.112

# 프로젝트 디렉토리로 이동
cd /home/ubuntu/bit_auto_v2

# 배포 스크립트 실행
./remote_deploy.sh
```

### 초기 설정 (처음 배포 시)
```bash
# 서버 접속 후
cd /home/ubuntu

# 모든 파일 복사 (로컬에서 서버로)
scp -i ~/.ssh/your_key -r /Users/namseokyoo/project/bit_auto_v2_250712/* ubuntu@158.180.82.112:/home/ubuntu/bit_auto_v2/

# 서버에서 실행
cd /home/ubuntu/bit_auto_v2
chmod +x remote_deploy.sh
./remote_deploy.sh
```

## 📊 시스템 관리

### 상태 확인
```bash
# 프로세스 확인
ps aux | grep python

# 로그 확인
tail -f /home/ubuntu/bit_auto_v2/logs/integrated_system.log

# 대시보드 접속
http://158.180.82.112:8080/
```

### 서비스 제어
```bash
# 중지
pkill -f integrated_trading_system.py

# 시작
cd /home/ubuntu/bit_auto_v2
source venv/bin/activate
nohup python3 integrated_trading_system.py > logs/integrated_system.log 2>&1 &

# 재시작
pkill -f integrated_trading_system.py
sleep 2
nohup python3 integrated_trading_system.py > logs/integrated_system.log 2>&1 &
```

### 대화형 실행 (setup_and_run.sh)
```bash
cd /home/ubuntu/bit_auto_v2
./setup_and_run.sh

# 메뉴 선택:
# 1) Full Integrated System (권장)
# 2) Multi-Coin Trading Only
# 3) AI Feedback System Only
# 4) Original Single-Coin System
# 5) Dashboard Only
# 6) Test Mode (Dry Run)
```

## 🔐 보안 설정

### API 키 업데이트
```bash
# 서버에서
nano /home/ubuntu/bit_auto_v2/config/.env

# 다음 값 업데이트:
UPBIT_ACCESS_KEY=your_actual_access_key
UPBIT_SECRET_KEY=your_actual_secret_key
```

### 거래 모드 변경
```bash
# config/.env 파일에서
TRADING_MODE=dry-run  # 테스트 모드 (기본값)
TRADING_MODE=live     # 실거래 모드 (주의!)
```

## 📈 모니터링

### 대시보드 기능
- **실시간 현황**: http://158.180.82.112:8080/
- **거래 내역**: 모든 거래 기록 확인
- **전략 성과**: 각 전략별 수익률
- **AI 분석**: DeepSeek API를 통한 일일/주간 분석 결과

### 로그 파일 위치
```
/home/ubuntu/bit_auto_v2/logs/
├── integrated_system.log    # 통합 시스템 로그
├── quantum_trading.log      # 퀀텀 트레이딩 로그
├── multi_coin.log          # 멀티코인 거래 로그
├── ai_analysis.log         # AI 분석 로그
└── feedback_scheduler.log  # 피드백 스케줄러 로그
```

## 🔄 백업 및 복구

### 자동 백업
- 배포 시 자동으로 이전 버전 백업
- 위치: `/home/ubuntu/backups/backup_YYYYMMDD_HHMMSS.tar.gz`

### 수동 백업
```bash
cd /home/ubuntu
tar -czf backups/manual_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  -C bit_auto_v2 \
  --exclude='venv' \
  --exclude='__pycache__' \
  .
```

### 복구
```bash
cd /home/ubuntu/bit_auto_v2
tar -xzf ../backups/backup_YYYYMMDD_HHMMSS.tar.gz
./remote_deploy.sh
```

## ⚠️ 문제 해결

### 서비스가 시작되지 않을 때
1. 로그 확인: `tail -100 logs/integrated_system.log`
2. Python 의존성 확인: `source venv/bin/activate && pip list`
3. 설정 파일 확인: `cat config/.env`

### 대시보드 접속 불가
1. 포트 확인: `sudo netstat -tlnp | grep 8080`
2. 방화벽 확인: Oracle Cloud 콘솔에서 포트 8080 열기
3. 프로세스 확인: `ps aux | grep dashboard`

### API 키 오류
1. Upbit API 키 유효성 확인
2. DeepSeek API 키 확인: sk-ae644f698503467d80dbd125f443fa5d
3. 환경 변수 로드 확인: `python3 -c "from dotenv import load_dotenv; import os; load_dotenv('config/.env'); print(os.getenv('UPBIT_ACCESS_KEY'))"`

## 📞 지원

문제가 지속될 경우:
1. 로그 파일 수집
2. 시스템 상태 확인
3. GitHub Issues에 문제 보고