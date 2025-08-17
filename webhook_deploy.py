#!/usr/bin/env python3
"""
GitHub Webhook을 받아 자동 배포하는 스크립트
Oracle Cloud 서버에서 실행
"""

from flask import Flask, request
import subprocess
import hmac
import hashlib
import os

app = Flask(__name__)

# GitHub Webhook Secret (GitHub에서 설정)
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-secret-key')

def verify_webhook(data, signature):
    """GitHub Webhook 서명 검증"""
    expected = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f'sha256={expected}', signature)

@app.route('/webhook', methods=['POST'])
def github_webhook():
    """GitHub push 이벤트 처리"""
    
    # 서명 검증
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_webhook(request.data, signature):
        return 'Unauthorized', 401
    
    # main 브랜치 push인지 확인
    payload = request.json
    if payload.get('ref') != 'refs/heads/main':
        return 'Not main branch', 200
    
    # 배포 실행
    try:
        result = subprocess.run([
            'sudo', '/opt/btc-trading/deploy/auto_deploy.sh'
        ], capture_output=True, text=True)
        
        return f'Deployed successfully: {result.stdout}', 200
    except Exception as e:
        return f'Deployment failed: {e}', 500

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)