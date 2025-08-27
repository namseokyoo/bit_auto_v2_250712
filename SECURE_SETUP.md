# 🔐 보안 설정 가이드

## 중요: API 키 보안

**절대 GitHub에 API 키를 업로드하지 마세요!**

## 1. DeepSeek API 키 설정

서버에 SSH로 접속한 후:

```bash
cd /home/ubuntu/bit_auto_v2/config
nano .env
```

다음 라인을 찾아서 수정:
```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

실제 API 키로 교체:
```
DEEPSEEK_API_KEY=실제_DeepSeek_API_키
```

## 2. Upbit API 키 설정

같은 `.env` 파일에서:

```
UPBIT_ACCESS_KEY=실제_Upbit_액세스_키
UPBIT_SECRET_KEY=실제_Upbit_시크릿_키
```

## 3. GitHub Secrets 설정 (선택사항)

GitHub Actions를 사용하려면:

1. GitHub 저장소 → Settings → Secrets and variables → Actions
2. 다음 시크릿 추가:
   - `ORACLE_SSH_KEY`: SSH 프라이빗 키
   - `DEEPSEEK_API_KEY`: DeepSeek API 키 (선택)

## 4. 환경변수 확인

서버에서 확인:

```bash
cd /home/ubuntu/bit_auto_v2
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv('config/.env')
print('DeepSeek API Key set:', 'Yes' if os.getenv('DEEPSEEK_API_KEY') and len(os.getenv('DEEPSEEK_API_KEY')) > 10 else 'No')
print('Upbit Access Key set:', 'Yes' if os.getenv('UPBIT_ACCESS_KEY') and len(os.getenv('UPBIT_ACCESS_KEY')) > 10 else 'No')
print('Upbit Secret Key set:', 'Yes' if os.getenv('UPBIT_SECRET_KEY') and len(os.getenv('UPBIT_SECRET_KEY')) > 10 else 'No')
"
```

## 5. 권한 설정

`.env` 파일 권한을 제한:

```bash
chmod 600 config/.env
```

## 6. 백업

API 키를 안전한 곳에 별도로 백업하세요.

## ⚠️ 보안 체크리스트

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] GitHub에 API 키가 노출되지 않았는지 확인
- [ ] 서버의 `.env` 파일 권한이 600인지 확인
- [ ] API 키가 실제로 작동하는지 테스트
- [ ] 정기적으로 API 키 교체

## 문제 해결

### API 키가 작동하지 않을 때

1. 키가 올바르게 입력되었는지 확인
2. 앞뒤 공백이 없는지 확인
3. 환경변수가 로드되는지 확인:
   ```python
   import os
   from dotenv import load_dotenv
   load_dotenv('config/.env')
   print(os.getenv('DEEPSEEK_API_KEY'))
   ```

### DeepSeek API 오류

- API 키가 유효한지 확인
- API 사용량 한도를 확인
- 네트워크 연결 상태 확인

### Upbit API 오류

- IP 화이트리스트 설정 확인
- API 권한 설정 확인
- 키가 활성화되어 있는지 확인