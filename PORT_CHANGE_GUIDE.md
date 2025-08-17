# 📌 포트 변경 완료 안내

## ✅ 포트가 5000으로 통일되었습니다!

### 🌐 새로운 접속 주소
```
http://158.180.82.112:5000
```

### ⚠️ Oracle Cloud 보안 그룹 설정 필요

1. **Oracle Cloud Console 접속**
   - https://cloud.oracle.com/

2. **Compute → Instances → 해당 인스턴스 클릭**

3. **Primary VNIC → Subnet 클릭**

4. **Security Lists → Default Security List 클릭**

5. **Ingress Rules 수정:**
   - **기존 9000 포트 규칙 삭제** (있다면)
   - **새로운 5000 포트 규칙 추가:**
     - Source CIDR: `0.0.0.0/0`
     - IP Protocol: `TCP`
     - Destination Port Range: `5000`
     - Description: `Trading Web Interface`

### 📝 변경 내역
- ✅ 서버 .env 파일: FLASK_PORT=5000
- ✅ 서버 방화벽(iptables): 5000 포트 열림
- ✅ 웹 서비스: 5000 포트에서 실행 중
- ✅ 소스 코드: 기본 포트 5000으로 통일
- ⚠️ Oracle Cloud 보안 그룹: 수동 변경 필요

### 🔍 확인 방법
서버에서 포트 상태 확인:
```bash
ssh -i ssh-key-2025-07-14.key ubuntu@158.180.82.112
sudo ss -tlnp | grep 5000
```

### 🎯 최종 확인
Oracle Cloud 보안 그룹에서 5000 포트를 열면 다음 주소로 접속 가능:
```
http://158.180.82.112:5000
```