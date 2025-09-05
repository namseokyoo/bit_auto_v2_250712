#!/bin/bash

# Bitcoin Auto Trading System 테스트 스크립트
# 백그라운드 실행 및 빠른 상태 체크

set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
PROJECT_DIR="/home/ubuntu/bit_auto_v2"
SERVICE_NAME="bitcoin-auto-trading.service"
WEB_URL="http://158.180.82.112:8080"
SSH_KEY="ssh-key-2025-07-14.key"
SSH_HOST="ubuntu@158.180.82.112"

# 함수들
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

# 서비스 상태 체크
check_service_status() {
    print_status "서비스 상태 확인 중..."
    
    local status=$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl is-active $SERVICE_NAME" 2>/dev/null || echo "inactive")
    
    if [ "$status" = "active" ]; then
        print_success "서비스가 실행 중입니다"
        return 0
    else
        print_error "서비스가 실행되지 않았습니다"
        return 1
    fi
}

# 웹 서버 상태 체크
check_web_status() {
    print_status "웹 서버 상태 확인 중..."
    
    local response=$(curl -s --max-time 10 "$WEB_URL/health" 2>/dev/null || echo "error")
    
    if [ "$response" = "error" ]; then
        print_error "웹 서버에 접근할 수 없습니다"
        return 1
    else
        print_success "웹 서버가 정상 동작 중입니다"
        return 0
    fi
}

# API 상태 체크
check_api_status() {
    print_status "API 상태 확인 중..."
    
    local response=$(curl -s --max-time 10 "$WEB_URL/api/system/status" 2>/dev/null || echo "error")
    
    if [ "$response" = "error" ]; then
        print_error "API에 접근할 수 없습니다"
        return 1
    else
        local system_enabled=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('system_enabled', False))" 2>/dev/null || echo "False")
        local trading_enabled=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('trading_enabled', False))" 2>/dev/null || echo "False")
        
        if [ "$system_enabled" = "True" ] && [ "$trading_enabled" = "True" ]; then
            print_success "시스템과 거래가 활성화되어 있습니다"
            return 0
        else
            print_warning "시스템 또는 거래가 비활성화되어 있습니다"
            return 1
        fi
    fi
}

# 체제 정보 체크
check_regime_status() {
    print_status "체제 기반 시스템 상태 확인 중..."
    
    local response=$(curl -s --max-time 10 "$WEB_URL/api/regime/status" 2>/dev/null || echo "error")
    
    if [ "$response" = "error" ]; then
        print_error "체제 정보를 가져올 수 없습니다"
        return 1
    else
        local regime=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('regime_info', {}).get('regime', 'unknown'))" 2>/dev/null || echo "unknown")
        local confidence=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('regime_info', {}).get('confidence', 0))" 2>/dev/null || echo "0")
        
        print_success "현재 체제: $regime (신뢰도: $(echo "$confidence * 100" | bc -l | cut -d. -f1)%)"
        return 0
    fi
}

# 전체 시스템 상태 체크
check_full_status() {
    print_status "전체 시스템 상태 체크 시작..."
    echo "=================================="
    
    local all_good=true
    
    # 서비스 상태
    if ! check_service_status; then
        all_good=false
    fi
    echo
    
    # 웹 서버 상태
    if ! check_web_status; then
        all_good=false
    fi
    echo
    
    # API 상태
    if ! check_api_status; then
        all_good=false
    fi
    echo
    
    # 체제 정보
    if ! check_regime_status; then
        all_good=false
    fi
    echo
    
    echo "=================================="
    if [ "$all_good" = true ]; then
        print_success "모든 시스템이 정상 동작 중입니다! 🎉"
        return 0
    else
        print_error "일부 시스템에 문제가 있습니다"
        return 1
    fi
}

# 서비스 시작
start_service() {
    print_status "서비스 시작 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl start $SERVICE_NAME"
    
    sleep 5
    
    if check_service_status; then
        print_success "서비스가 성공적으로 시작되었습니다"
        return 0
    else
        print_error "서비스 시작에 실패했습니다"
        return 1
    fi
}

# 서비스 중지
stop_service() {
    print_status "서비스 중지 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl stop $SERVICE_NAME"
    
    sleep 2
    
    print_success "서비스가 중지되었습니다"
}

# 서비스 재시작
restart_service() {
    print_status "서비스 재시작 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo systemctl restart $SERVICE_NAME"
    
    sleep 5
    
    if check_service_status; then
        print_success "서비스가 성공적으로 재시작되었습니다"
        return 0
    else
        print_error "서비스 재시작에 실패했습니다"
        return 1
    fi
}

# 로그 확인
show_logs() {
    print_status "최근 로그 확인 중..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo journalctl -u $SERVICE_NAME --no-pager -n 20"
}

# 실시간 로그 모니터링
monitor_logs() {
    print_status "실시간 로그 모니터링 시작... (Ctrl+C로 종료)"
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 \
        "$SSH_HOST" "sudo journalctl -u $SERVICE_NAME -f"
}

# 도움말
show_help() {
    echo "Bitcoin Auto Trading System 테스트 스크립트"
    echo
    echo "사용법: $0 [명령어]"
    echo
    echo "명령어:"
    echo "  status     - 전체 시스템 상태 체크"
    echo "  start      - 서비스 시작"
    echo "  stop       - 서비스 중지"
    echo "  restart    - 서비스 재시작"
    echo "  logs       - 최근 로그 확인"
    echo "  monitor    - 실시간 로그 모니터링"
    echo "  help       - 도움말 표시"
    echo
    echo "예시:"
    echo "  $0 status    # 시스템 상태 체크"
    echo "  $0 restart   # 서비스 재시작"
    echo "  $0 monitor   # 실시간 로그 모니터링"
}

# 메인 로직
main() {
    case "${1:-status}" in
        "status")
            check_full_status
            ;;
        "start")
            start_service
            ;;
        "stop")
            stop_service
            ;;
        "restart")
            restart_service
            ;;
        "logs")
            show_logs
            ;;
        "monitor")
            monitor_logs
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
