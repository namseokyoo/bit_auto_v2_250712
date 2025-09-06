# Gunicorn 설정 파일 (Oracle Cloud 프로덕션용)

import multiprocessing
import os

# 서버 설정
bind = "0.0.0.0:8080"
# 설정 변경의 일관된 반영을 위해 워커 수를 1로 제한하고 preload를 비활성화
workers = 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# 프로세스 이름
proc_name = "bitcoin_auto_trading"

# 로그 설정
accesslog = "/home/ubuntu/bit_auto_v2/logs/gunicorn_access.log"
errorlog = "/home/ubuntu/bit_auto_v2/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 보안 설정
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 프로세스 관리
max_requests = 1000
max_requests_jitter = 100
preload_app = False

# 성능 최적화
worker_tmp_dir = "/dev/shm"

# SSL 설정 (필요시)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

def when_ready(server):
    server.log.info("Bitcoin Auto Trading Server is ready. Listening on %s", server.address)

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")