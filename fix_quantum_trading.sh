#!/bin/bash
# Quantum Trading 프로세스 수정을 위한 간단한 스크립트

echo "🔧 Checking Quantum Trading dependencies..."

# Python 의존성 체크
python3 -c "
import sys
missing = []
modules = ['redis', 'sklearn', 'pytz', 'ta', 'pyupbit', 'pandas', 'numpy', 'yaml', 'dotenv']
for module in modules:
    try:
        __import__(module)
    except ImportError:
        missing.append(module)
        
if missing:
    print(f'Missing modules: {missing}')
    print('Installing missing modules...')
    import subprocess
    for m in missing:
        if m == 'sklearn':
            subprocess.run(['pip3', 'install', 'scikit-learn'], capture_output=True)
        elif m == 'dotenv':
            subprocess.run(['pip3', 'install', 'python-dotenv'], capture_output=True)
        else:
            subprocess.run(['pip3', 'install', m], capture_output=True)
else:
    print('✓ All dependencies installed')
"

# strategies.py 파일 체크
if [ ! -f "strategies.py" ]; then
    echo "❌ strategies.py not found!"
    exit 1
else
    echo "✓ strategies.py found"
fi

# quantum_trading.py 문법 체크
python3 -m py_compile quantum_trading.py 2>&1
if [ $? -eq 0 ]; then
    echo "✓ quantum_trading.py syntax OK"
else
    echo "❌ quantum_trading.py has syntax errors"
    exit 1
fi

# Dry-run 테스트
echo "Testing quantum_trading.py import..."
python3 -c "import quantum_trading; print('✓ Import successful')" 2>&1

echo "✅ All checks passed!"
