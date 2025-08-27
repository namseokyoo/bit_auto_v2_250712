# GitHub Secrets 설정 가이드

## 필수 설정 항목

GitHub Repository → Settings → Secrets and variables → Actions에서 다음 시크릿 추가:

### 1. ORACLE_HOST
- **값**: `158.180.82.112`
- **설명**: Oracle Cloud 서버 IP 주소

### 2. ORACLE_USER
- **값**: `ubuntu`
- **설명**: SSH 접속 사용자명

### 3. ORACLE_SSH_KEY
- **값**: SSH 개인키 전체 내용
- **설정 방법**:
  ```bash
  # 로컬에서 SSH 키 내용 복사
  cat /Users/namseokyoo/project/bit_auto_v2_250712/ssh-key-2025-07-14.key
  ```
  - 출력된 전체 내용을 복사 (-----BEGIN RSA PRIVATE KEY----- 부터 -----END RSA PRIVATE KEY----- 까지)
  - GitHub Secrets에 붙여넣기

## 설정 확인

1. GitHub Repository 페이지 방문
2. Settings 탭 클릭
3. 왼쪽 메뉴에서 "Secrets and variables" → "Actions" 클릭
4. 위 3개 시크릿이 모두 추가되었는지 확인

## 테스트

```bash
# 로컬에서 테스트 커밋
git add .
git commit -m "test: GitHub Actions deployment"
git push origin main
```

GitHub Actions 탭에서 배포 상태 확인