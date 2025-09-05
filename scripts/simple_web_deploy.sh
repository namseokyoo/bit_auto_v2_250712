#!/bin/bash

# 간단한 웹 대시보드 배포 스크립트
# 기존 프로세스 종료 후 백그라운드에서 Gunicorn 실행

set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 서버에서 실행할 명령어
deploy_commands() {
    cat << 'EOF'
#!/bin/bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/bit_auto_v2"
WEB_PORT=8080

echo "=== 웹 대시보드 배포 시작 ==="

# 기존 프로세스 종료
echo "기존 웹 프로세스 종료 중..."
sudo pkill -f 'python3.*web.app' || true
sudo pkill -f 'gunicorn.*web.app' || true
sleep 3

# 로그 디렉토리 생성
echo "로그 디렉토리 생성 중..."
cd "$PROJECT_DIR"
mkdir -p logs
chmod 755 logs

# Gunicorn 설정 파일 생성
echo "Gunicorn 설정 파일 생성 중..."
cat > gunicorn.conf.py << 'GUNICORN_EOF'
import multiprocessing
import os

# 서버 소켓
bind = '0.0.0.0:8080'
backlog = 2048

# Worker 프로세스
workers = 2
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# 로깅
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'info'

# 프로세스 이름
proc_name = 'bitcoin-auto-trading-web'

# 환경 변수
raw_env = [
    'PYTHONPATH=/home/ubuntu/bit_auto_v2',
]

# 성능
max_requests = 1000
max_requests_jitter = 50
preload_app = True
GUNICORN_EOF

# 가상환경 활성화 및 Gunicorn 실행
echo "Gunicorn 웹서버 시작 중..."
source venv/bin/activate
export PYTHONPATH="$PROJECT_DIR"

# 백그라운드에서 Gunicorn 실행
nohup gunicorn --config gunicorn.conf.py web.app:app > logs/gunicorn_startup.log 2>&1 &
GUNICORN_PID=$!

echo "Gunicorn PID: $GUNICORN_PID"
sleep 5

# 프로세스 확인
if ps -p $GUNICORN_PID > /dev/null; then
    echo "✅ 웹 대시보드가 성공적으로 시작되었습니다!"
    echo "🌐 접속 URL: http://158.180.82.112:8080"
    echo "📋 로그 파일: $PROJECT_DIR/logs/gunicorn_*.log"
else
    echo "❌ 웹 대시보드 시작에 실패했습니다"
    echo "📋 오류 로그 확인: cat $PROJECT_DIR/logs/gunicorn_startup.log"
    exit 1
fi

echo "=== 웹 대시보드 배포 완료 ==="
EOF
}

# 로컬에서 서버로 배포 실행
deploy_to_server() {
    print_status "서버에 웹 대시보드 배포 중..."
    
    # 임시 스크립트 파일 생성
    local temp_script=$(mktemp)
    deploy_commands > "$temp_script"
    
    # 서버로 스크립트 전송 및 실행
    scp -i ssh-key-2025-07-14.key -o StrictHostKeyChecking=no "$temp_script" ubuntu@158.180.82.112:/tmp/deploy_web.sh
    ssh -i ssh-key-2025-07-14.key -o StrictHostKeyChecking=no ubuntu@158.180.82.112 "chmod +x /tmp/deploy_web.sh && /tmp/deploy_web.sh"
    
    # 임시 파일 정리
    rm "$temp_script"
    
    print_success "웹 대시보드 배포 완료!"
}

# 웹 서버 상태 확인
check_web_status() {
    print_status "웹 서버 상태 확인 중..."
    
    local response=$(curl -s --max-time 10 "http://158.180.82.112:8080/health" 2>/dev/null || echo "error")
    
    if [ "$response" = "error" ]; then
        print_error "웹 서버에 접근할 수 없습니다"
        return 1
    else
        print_success "웹 서버가 정상 동작 중입니다"
        return 0
    fi
}

# 웹 서버 중지
stop_web_server() {
    print_status "웹 서버 중지 중..."
    
    ssh -i ssh-key-2025-07-14.key -o StrictHostKeyChecking=no ubuntu@158.180.82.112 \
        "sudo pkill -f 'gunicorn.*web.app' || true; sleep 2"
    
    print_success "웹 서버가 중지되었습니다"
}

# 도움말
show_help() {
    echo "간단한 웹 대시보드 배포 스크립트"
    echo
    echo "사용법: $0 [명령어]"
    echo
    echo "명령어:"
    echo "  deploy     - 웹 대시보드 배포 (기존 프로세스 종료 + 새로 시작)"
    echo "  status     - 웹 서버 상태 확인"
    echo "  stop       - 웹 서버 중지"
    echo "  help       - 도움말 표시"
    echo
    echo "예시:"
    echo "  $0 deploy   # 웹 대시보드 배포"
    echo "  $0 status   # 상태 확인"
}

# 메인 로직
main() {
    case "${1:-deploy}" in
        "deploy")
            deploy_to_server
            ;;
        "status")
            check_web_status
            ;;
        "stop")
            stop_web_server
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "알 수 없는 명령어: $1"
            show_help
            exit 1
            ;;
    esac
}

# 스크립트 실행
main "$@"
