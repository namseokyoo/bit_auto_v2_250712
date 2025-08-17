# GitHub Secrets 설정 가이드

## 1. GitHub 저장소로 이동
https://github.com/namseokyoo/bit_auto_v2_250712

## 2. Settings → Secrets and variables → Actions

## 3. 다음 3개의 Secret 추가:

### ORACLE_HOST
- Name: `ORACLE_HOST`
- Value: `158.180.82.112`

### ORACLE_USER  
- Name: `ORACLE_USER`
- Value: `ubuntu` (또는 실제 사용자명)

### ORACLE_SSH_KEY
- Name: `ORACLE_SSH_KEY`
- Value: ssh-key-2025-07-14.key 파일의 전체 내용
  ```
  -----BEGIN RSA PRIVATE KEY-----
  (전체 키 내용)
  -----END RSA PRIVATE KEY-----
  ```

## 4. 설정 확인
모든 Secrets가 추가되었는지 확인

## 주의사항
- SSH 키는 절대 공개 저장소에 커밋하지 마세요
- Secrets는 한 번 저장하면 내용을 볼 수 없습니다 (수정만 가능)