#!/bin/bash

echo "🔍 배포 전 체크리스트"

# 1. 테스트 실행
echo "✓ 단위 테스트 실행..."
python -m pytest tests/ || { echo "❌ 테스트 실패"; exit 1; }

# 2. 설정 파일 검증
echo "✓ 설정 파일 검증..."
python -c "from config.config_manager import config_manager; print('Config OK')" || { echo "❌ 설정 오류"; exit 1; }

# 3. 문법 검사
echo "✓ Python 문법 검사..."
python -m py_compile main.py core/*.py || { echo "❌ 문법 오류"; exit 1; }

# 4. 의존성 확인
echo "✓ 의존성 확인..."
pip freeze > requirements_current.txt
diff requirements.txt requirements_current.txt || echo "⚠️  의존성 변경 감지"

echo "✅ 모든 체크 통과! 배포 준비 완료"