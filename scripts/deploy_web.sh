#!/bin/bash

# 웹 대시보드 배포 및 관리 스크립트
# Gunicorn을 사용한 프로덕션 웹서버 설정

set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 설정
PROJECT_DIR="/home/ubuntu/bit_auto_v2"
WEB_SERVICE_NAME="bitcoin-auto-trading-web.service"
WEB_PORT=8080
SSH_KEY="ssh-key-2025-07-14.key"
SSH_HOST="ubuntu@158.180.82.112"

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 기존 웹 프로세스 종료
kill_existing_web_processes() {
    print_status "기존 웹 프로세스 종료 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo pkill -f 'python3.*web.app' || true; sudo pkill -f 'gunicorn.*web.app' || true; sleep 2"
    
    print_success "기존 웹 프로세스 종료 완료"
}

# Gunicorn 설정 파일 생성
create_gunicorn_config() {
    print_status "Gunicorn 설정 파일 생성 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "cd $PROJECT_DIR && cat > gunicorn.conf.py << 'EOF'
import multiprocessing
import os

# 서버 소켓
bind = '0.0.0.0:$WEB_PORT'
backlog = 2048

# Worker 프로세스
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# 로깅
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\"'

# 프로세스 이름
proc_name = 'bitcoin-auto-trading-web'

# 데몬 모드 (백그라운드 실행)
daemon = False

# 환경 변수
raw_env = [
    'PYTHONPATH=$PROJECT_DIR',
]

# 보안
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 성능
max_requests = 1000
max_requests_jitter = 50
preload_app = True
EOF"
    
    print_success "Gunicorn 설정 파일 생성 완료"
}

# systemd 웹 서비스 생성
create_web_service() {
    print_status "웹 서비스 systemd 설정 생성 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo tee /etc/systemd/system/$WEB_SERVICE_NAME > /dev/null << 'EOF'
[Unit]
Description=Bitcoin Auto Trading Web Dashboard
After=network.target bitcoin-auto-trading.service
Requires=bitcoin-auto-trading.service

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
Environment=PYTHONPATH=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --config $PROJECT_DIR/gunicorn.conf.py web.app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 보안 설정
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_DIR/logs

[Install]
WantedBy=multi-user.target
EOF"
    
    print_success "웹 서비스 systemd 설정 생성 완료"
}

# 로그 디렉토리 생성
create_log_directories() {
    print_status "로그 디렉토리 생성 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "cd $PROJECT_DIR && mkdir -p logs && chmod 755 logs"
    
    print_success "로그 디렉토리 생성 완료"
}

# 웹 서비스 시작
start_web_service() {
    print_status "웹 서비스 시작 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl daemon-reload && sudo systemctl enable $WEB_SERVICE_NAME && sudo systemctl start $WEB_SERVICE_NAME"
    
    sleep 5
    
    if check_web_service_status; then
        print_success "웹 서비스가 성공적으로 시작되었습니다"
        return 0
    else
        print_error "웹 서비스 시작에 실패했습니다"
        return 1
    fi
}

# 웹 서비스 상태 체크
check_web_service_status() {
    local status=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl is-active $WEB_SERVICE_NAME" 2>/dev/null || echo "inactive")
    
    if [ "$status" = "active" ]; then
        return 0
    else
        return 1
    fi
}

# 웹 서비스 중지
stop_web_service() {
    print_status "웹 서비스 중지 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl stop $WEB_SERVICE_NAME"
    
    sleep 2
    
    print_success "웹 서비스가 중지되었습니다"
}

# 웹 서비스 재시작
restart_web_service() {
    print_status "웹 서비스 재시작 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl restart $WEB_SERVICE_NAME"
    
    sleep 5
    
    if check_web_service_status; then
        print_success "웹 서비스가 성공적으로 재시작되었습니다"
        return 0
    else
        print_error "웹 서비스 재시작에 실패했습니다"
        return 1
    fi
}

# 웹 서비스 로그 확인
show_web_logs() {
    print_status "웹 서비스 로그 확인 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo journalctl -u $WEB_SERVICE_NAME --no-pager -n 20"
}

# 웹 서비스 실시간 로그 모니터링
monitor_web_logs() {
    print_status "웹 서비스 실시간 로그 모니터링 시작... (Ctrl+C로 종료)"
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo journalctl -u $WEB_SERVICE_NAME -f"
}

# 전체 배포 (기존 프로세스 종료 + 새로 시작)
deploy_web() {
    print_status "웹 대시보드 전체 배포 시작..."
    echo "=================================="
    
    # 기존 프로세스 종료
    kill_existing_web_processes
    echo
    
    # 로그 디렉토리 생성
    create_log_directories
    echo
    
    # Gunicorn 설정 생성
    create_gunicorn_config
    echo
    
    # systemd 서비스 생성
    create_web_service
    echo
    
    # 웹 서비스 시작
    start_web_service
    echo
    
    echo "=================================="
    print_success "웹 대시보드 배포 완료! 🎉"
    echo -e "${BLUE}🌐 웹 대시보드: http://158.180.82.112:$WEB_PORT${NC}"
}

# 웹 서비스 상태 확인
status_web() {
    print_status "웹 서비스 상태 확인 중..."
    echo "=================================="
    
    if check_web_service_status; then
        print_success "웹 서비스가 실행 중입니다"
    else
        print_error "웹 서비스가 실행되지 않았습니다"
    fi
    
    # 포트 확인
    local port_status=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "ss -tlnp | grep :$WEB_PORT || echo 'not_listening'")
    
    if [[ "$port_status" == *"$WEB_PORT"* ]]; then
        print_success "포트 $WEB_PORT가 정상적으로 리스닝 중입니다"
    else
        print_error "포트 $WEB_PORT가 리스닝되지 않습니다"
    fi
    
    # 웹 응답 확인
    local web_response=$(curl -s --max-time 10 "http://158.180.82.112:$WEB_PORT/health" 2>/dev/null || echo "error")
    if [ "$web_response" != "error" ]; then
        print_success "웹 서버가 정상적으로 응답합니다"
    else
        print_error "웹 서버 응답에 문제가 있습니다"
    fi
    
    echo "=================================="
}

# 도움말
show_help() {
    echo "Bitcoin Auto Trading Web Dashboard 배포 스크립트"
    echo
    echo "사용법: $0 [명령어]"
    echo
    echo "명령어:"
    echo "  deploy     - 전체 웹 대시보드 배포 (기존 프로세스 종료 + 새로 시작)"
    echo "  start      - 웹 서비스 시작"
    echo "  stop       - 웹 서비스 중지"
    echo "  restart    - 웹 서비스 재시작"
    echo "  status     - 웹 서비스 상태 확인"
    echo "  logs       - 웹 서비스 로그 확인"
    echo "  monitor    - 웹 서비스 실시간 로그 모니터링"
    echo "  kill       - 기존 웹 프로세스 강제 종료"
    echo "  help       - 도움말 표시"
    echo
    echo "예시:"
    echo "  $0 deploy   # 전체 배포"
    echo "  $0 restart # 서비스 재시작"
    echo "  $0 status  # 상태 확인"
}

# 메인 로직
main() {
    case "${1:-deploy}" in
        "deploy")
            deploy_web
            ;;
        "start")
            start_web_service
            ;;
        "stop")
            stop_web_service
            ;;
        "restart")
            restart_web_service
            ;;
        "status")
            status_web
            ;;
        "logs")
            show_web_logs
            ;;
        "monitor")
            monitor_web_logs
            ;;
        "kill")
            kill_existing_web_processes
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
