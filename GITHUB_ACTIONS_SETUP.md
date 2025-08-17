# 🚀 GitHub Actions 자동 배포 설정 가이드

## 📝 설정 순서

### 1️⃣ GitHub Secrets 설정 (필수!)

1. **GitHub 저장소 페이지 열기**
   ```
   https://github.com/namseokyoo/bit_auto_v2_250712
   ```

2. **Settings → Secrets and variables → Actions 이동**

3. **"New repository secret" 버튼 클릭하여 3개 추가:**

   #### Secret 1: ORACLE_HOST
   - **Name:** `ORACLE_HOST`
   - **Value:** `158.180.82.112`

   #### Secret 2: ORACLE_USER
   - **Name:** `ORACLE_USER`
   - **Value:** `ubuntu`

   #### Secret 3: ORACLE_SSH_KEY
   - **Name:** `ORACLE_SSH_KEY`
   - **Value:** SSH 키 전체 내용 복사/붙여넣기
   
   터미널에서 이 명령어로 복사:
   ```bash
   cat ssh-key-2025-07-14.key | pbcopy
   ```
   그리고 GitHub Secret Value 필드에 붙여넣기

### 2️⃣ 서버 확인 (선택사항)

```bash
# 서버 설정 상태 확인
./check_server_setup.sh
```

### 3️⃣ 첫 배포 테스트

#### 방법 1: 코드 변경 후 Push
```bash
# 작은 변경사항 만들기
echo "# Deploy test $(date)" >> README.md
git add .
git commit -m "Test GitHub Actions deployment"
git push origin main
```

#### 방법 2: GitHub에서 수동 실행
1. GitHub 저장소 → Actions 탭
2. "Deploy to Oracle Cloud" 워크플로우 선택
3. "Run workflow" 버튼 클릭

### 4️⃣ 배포 상태 확인

GitHub Actions 페이지에서 실시간으로 확인:
```
https://github.com/namseokyoo/bit_auto_v2_250712/actions
```

## ✅ 체크리스트

- [ ] GitHub Secrets 3개 모두 설정됨
- [ ] SSH 키가 올바르게 복사됨
- [ ] 서버에 Git 저장소가 설정됨
- [ ] 서버에 sudo 권한이 있음

## 🔍 문제 해결

### "Permission denied" 에러
```bash
# 서버에서 실행
sudo chown -R ubuntu:ubuntu /opt/btc-trading
sudo chmod 600 ~/.ssh/authorized_keys
```

### "Git repository not found" 에러
```bash
# 서버에서 실행
cd /opt/btc-trading
sudo git init
sudo git remote add origin https://github.com/namseokyoo/bit_auto_v2_250712.git
sudo git fetch
sudo git checkout -t origin/main
```

### 서비스 재시작 실패
```bash
# 서버에서 직접 확인
sudo journalctl -u btc-trading-engine -n 50
sudo systemctl status btc-trading-engine
```

## 🎯 배포 후 확인사항

1. **웹 인터페이스 접속**
   ```
   http://158.180.82.112:5000
   ```

2. **서비스 상태 확인**
   ```bash
   ssh -i ssh-key-2025-07-14.key ubuntu@158.180.82.112
   sudo systemctl status btc-trading-engine
   sudo systemctl status btc-trading-web
   ```

3. **로그 확인**
   ```bash
   sudo tail -f /opt/btc-trading/logs/trading_engine.log
   ```

## 📌 이후 사용법

코드 수정 후 자동 배포:
```bash
git add .
git commit -m "Update: 기능 설명"
git push origin main
# → GitHub Actions가 자동으로 배포 시작!
```

배포 진행 상황은 GitHub Actions 페이지에서 실시간 확인 가능합니다! 🎉