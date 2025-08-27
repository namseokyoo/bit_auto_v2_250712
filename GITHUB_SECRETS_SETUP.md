# GitHub Secrets 설정 가이드

## 필요한 Secrets 설정

GitHub Actions 자동 배포를 위해 다음 시크릿들을 설정해야 합니다.

### 1. GitHub 저장소 설정 페이지로 이동
```
https://github.com/namseokyoo/bit_auto_v2_250712/settings/secrets/actions
```

### 2. 필수 Secrets 추가

#### `ORACLE_HOST`
- **값**: `158.180.82.112`
- **설명**: Oracle Cloud 서버의 IP 주소

#### `ORACLE_USER`
- **값**: `ubuntu`
- **설명**: SSH 접속 사용자명

#### `ORACLE_PORT` (선택사항)
- **값**: `22`
- **설명**: SSH 포트 (기본값 22)

#### `ORACLE_SSH_KEY` ⭐ 가장 중요!
- **설명**: Oracle 서버 접속용 SSH 개인키
- **설정 방법**:

1. 로컬에서 SSH 키 확인:
```bash
# 기존 키가 있는지 확인
ls ~/.ssh/

# 키가 없으면 새로 생성
ssh-keygen -t ed25519 -C "github-actions@bit-auto" -f ~/.ssh/oracle_deploy
```

2. 공개키를 Oracle 서버에 추가:
```bash
# 공개키 내용 복사
cat ~/.ssh/oracle_deploy.pub

# Oracle 서버에 SSH로 접속
ssh ubuntu@158.180.82.112

# authorized_keys에 추가
echo "복사한_공개키_내용" >> ~/.ssh/authorized_keys
```

3. 개인키를 GitHub Secret으로 추가:
```bash
# 개인키 내용 복사 (전체 내용 포함)
cat ~/.ssh/oracle_deploy

# GitHub Secrets 페이지에서:
# Name: ORACLE_SSH_KEY
# Value: -----BEGIN OPENSSH PRIVATE KEY-----부터 -----END OPENSSH PRIVATE KEY-----까지 전체 복사
```

### 3. SSH 키 형식 예시
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
... (중간 내용) ...
QyNTUxOQAAACDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
-----END OPENSSH PRIVATE KEY-----
```

## 테스트 방법

### 1. 로컬에서 SSH 연결 테스트
```bash
# 설정한 키로 직접 연결 테스트
ssh -i ~/.ssh/oracle_deploy ubuntu@158.180.82.112 "echo 'Connection successful!'"
```

### 2. GitHub Actions 수동 실행
1. GitHub 저장소 페이지에서 Actions 탭 클릭
2. "Deploy to Oracle Cloud" 워크플로우 선택
3. "Run workflow" 버튼 클릭
4. 실행 로그 확인

## 문제 해결

### 오류: Permission denied (publickey)
- **원인**: SSH 키가 올바르게 설정되지 않음
- **해결**:
  1. 개인키가 올바른 형식인지 확인
  2. 공개키가 서버의 authorized_keys에 있는지 확인
  3. 키 권한 확인 (서버에서):
     ```bash
     chmod 700 ~/.ssh
     chmod 600 ~/.ssh/authorized_keys
     ```

### 오류: Host key verification failed
- **원인**: SSH 호스트 키 검증 실패
- **해결**: deploy.yml에 이미 `StrictHostKeyChecking no` 설정됨

### 오류: Connection timeout
- **원인**: 방화벽이나 네트워크 문제
- **해결**:
  1. Oracle Cloud 보안 그룹에서 포트 22 열려있는지 확인
  2. 서버에서 SSH 서비스 상태 확인:
     ```bash
     sudo systemctl status ssh
     ```

## 확인 사항 체크리스트

- [ ] GitHub Secrets 4개 모두 설정됨 (ORACLE_HOST, ORACLE_USER, ORACLE_SSH_KEY, ORACLE_PORT)
- [ ] SSH 개인키가 올바른 형식으로 저장됨 (줄바꿈 포함)
- [ ] Oracle 서버의 authorized_keys에 공개키가 추가됨
- [ ] 로컬에서 SSH 연결 테스트 성공
- [ ] GitHub Actions에서 수동 실행 테스트 성공

## 보안 주의사항

⚠️ **절대 하지 말아야 할 것들**:
- SSH 개인키를 코드나 public 저장소에 커밋하지 마세요
- SSH 개인키를 다른 사람과 공유하지 마세요
- Production 서버의 root 계정을 사용하지 마세요

✅ **권장 사항**:
- 배포 전용 SSH 키 사용
- 정기적으로 SSH 키 교체
- GitHub Actions 전용 제한된 권한의 사용자 계정 사용