"""
간단한 웹 관리자 패널 (Flask)
거래 모니터링, 설정 변경, 로그 확인
"""

from core.auto_trader import auto_trader, start_auto_trading, stop_auto_trading, get_auto_trading_status
from core.signal_recorder import signal_recorder
from utils.error_logger import log_error, log_trade, log_system
from core.upbit_api import UpbitAPI
from data.database import db
from config.config_manager import config_manager
from core.strategy_execution_tracker import execution_tracker
import pytz
import logging
from datetime import datetime, timedelta
import json
from flask_cors import CORS
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일 로드를 가장 먼저 수행
load_dotenv()

# KST 시간대 설정
KST = pytz.timezone('Asia/Seoul')


def now_kst():
    """KST 시간으로 현재 시간 반환"""
    return datetime.now(KST)


def check_auto_trader_process():
    """AutoTrader 프로세스 상태 확인 (임시 비활성화)"""
    try:
        # psutil 패키지 문제로 임시 비활성화
        return {
            'running': False,
            'reason': '프로세스 모니터링 임시 비활성화'
        }

    except Exception as e:
        logger.error(f"프로세스 상태 확인 오류: {e}")
        return {'running': False, 'reason': f'확인 오류: {str(e)}'}


def get_system_process_status():
    """시스템 전체 프로세스 상태 확인 (임시 비활성화)"""
    try:
        # psutil 패키지 문제로 임시 비활성화
        return {
            'python_processes': [],
            'total_processes': 0,
            'system_load': 0,
            'memory_percent': 0,
            'status': '프로세스 모니터링 임시 비활성화'
        }

    except Exception as e:
        logger.error(f"시스템 프로세스 상태 확인 오류: {e}")
        return {'error': str(e)}


app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change-me-in-.env')

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/health')
def health():
    try:
        return jsonify({
            'ok': True,
            'system_enabled': config_manager.is_system_enabled(),
            'trading_enabled': config_manager.is_trading_enabled(),
            'mode': config_manager.get_mode(),
        }), 200
    except Exception:
        return jsonify({'ok': False}), 500


@app.route('/')
def dashboard():
    """메인 대시보드"""
    try:
        # KST 시간으로 현재 시간 설정
        current_time_kst = now_kst().strftime('%Y-%m-%d %H:%M:%S KST')

        # 시스템 상태
        system_status = {
            'system_enabled': config_manager.is_system_enabled(),
            'trading_enabled': config_manager.is_trading_enabled(),
            'mode': config_manager.get_config('system.mode'),
            'last_updated': current_time_kst,
            'trading_intervals': {
                'hourly': '1시간',
                'daily': '24시간'
            }
        }

        # AI 스케줄러 상태
        ai_scheduler_status = {}
        try:
            from core.ai_scheduler import ai_scheduler
            ai_config = config_manager.get_config('trading.ai_analysis') or {}
            ai_scheduler_status = {
                'enabled': ai_config.get('enabled', False),
                'interval_minutes': ai_config.get('interval_minutes', 30),
                'is_running': ai_scheduler.is_running() if ai_scheduler else False,
                'last_execution': ai_config.get('last_execution'),
                'auto_on_startup': ai_config.get('auto_on_startup', False)
            }
        except Exception as e:
            logger.error(f"AI 스케줄러 상태 조회 오류: {e}")
            ai_scheduler_status = {
                'enabled': False,
                'interval_minutes': 30,
                'is_running': False,
                'last_execution': None,
                'auto_on_startup': False
            }

        # 대시보드 데이터
        dashboard_data = db.get_dashboard_data()

        # 현재 잔고 (실거래) - .env 파일에서 API 키 로드
        try:
            # 모드 확인
            mode = config_manager.get_config('system.mode')
            is_paper_trading = (mode == 'paper_trading')

            # API 초기화 (.env 파일의 키 자동 사용)
            api = UpbitAPI()

            # 잔고 조회
            balances = {
                'KRW': api.get_balance('KRW'),
                'BTC': api.get_balance('BTC')
            }

            # 현재 BTC 가격
            current_price = api.get_current_price('KRW-BTC')

            # BTC 평가금액 계산
            btc_value = balances['BTC'] * current_price if current_price else 0
            total_value = balances['KRW'] + btc_value

            balances['btc_value'] = btc_value
            balances['total_value'] = total_value

        except Exception as e:
            logger.error(f"잔고 조회 오류: {e}")
            balances = {
                'KRW': 0,
                'BTC': 0,
                'btc_value': 0,
                'total_value': 0
            }
            current_price = 0

        return render_template('dashboard_improved.html',
                               system_status=system_status,
                               dashboard_data=dashboard_data,
                               balances=balances,
                               current_price=current_price,
                               ai_scheduler_status=ai_scheduler_status)
    except Exception as e:
        logger.error(f"대시보드 로드 오류: {e}")
        return f"오류 발생: {e}", 500


@app.route('/settings')
def settings():
    """설정 페이지"""
    try:
        trading_config = config_manager.get_config('trading')
        risk_config = config_manager.get_config('risk_management')
        strategy_config = config_manager.get_config('strategies')

        return render_template('settings.html',
                               trading_config=trading_config,
                               risk_config=risk_config,
                               strategy_config=strategy_config)
    except Exception as e:
        logger.error(f"설정 페이지 로드 오류: {e}")
        return f"오류 발생: {e}", 500


@app.route('/trades')
def trades():
    """거래 내역 페이지"""
    try:
        # 페이지네이션 파라미터
        page = request.args.get('page', 1, type=int)
        per_page = 50

        # 필터 파라미터
        strategy_id = request.args.get('strategy_id')
        status = request.args.get('status')

        # 거래 데이터 조회 (최근 30일)
        start_date = datetime.now() - timedelta(days=30)
        trades_data = db.get_trades(
            strategy_id=strategy_id,
            start_date=start_date,
            status=status
        )

        # 페이지네이션 적용
        total = len(trades_data)
        start = (page - 1) * per_page
        end = start + per_page
        trades_page = trades_data[start:end]

        # 전략 목록 (필터용)
        strategies = list(set(trade['strategy_id'] for trade in trades_data))

        return render_template('trades.html',
                               trades=trades_page,
                               strategies=strategies,
                               current_page=page,
                               total_pages=(total + per_page - 1) // per_page,
                               current_strategy=strategy_id,
                               current_status=status)
    except Exception as e:
        logger.error(f"거래 내역 페이지 로드 오류: {e}")
        return f"오류 발생: {e}", 500


@app.route('/logs')
def logs():
    """로그 페이지"""
    try:
        level = request.args.get('level')
        module = request.args.get('module')

        logs_data = db.get_logs(level=level, module=module, limit=200)

        # 로그 레벨과 모듈 목록
        levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
        modules = list(set(log['module'] for log in logs_data))

        return render_template('logs.html',
                               logs=logs_data,
                               levels=levels,
                               modules=modules,
                               current_level=level,
                               current_module=module)
    except Exception as e:
        logger.error(f"로그 페이지 로드 오류: {e}")
        return f"오류 발생: {e}", 500


@app.route('/performance')
def performance():
    """성과 대시보드 페이지"""
    try:
        # 기본 30일 성과 요약과 시계열은 프런트에서 AJAX로 로드
        return render_template('performance.html')
    except Exception as e:
        logger.error(f"성과 페이지 로드 오류: {e}")
        return f"오류 발생: {e}", 500


@app.route('/strategy_analytics')
def strategy_analytics():
    """전략 분석 페이지"""
    return render_template('strategy_analytics.html')


@app.route('/api/strategy_analytics/summary')
def api_strategy_analytics_summary():
    """전략 분석 요약 API"""
    try:
        from core.strategy_execution_tracker import execution_tracker

        days = request.args.get('days', 7, type=int)
        summary = execution_tracker.get_strategy_summary(days=days)

        return jsonify({
            'success': True,
            'data': summary
        })

    except Exception as e:
        logger.error(f"전략 분석 요약 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/strategy_analytics/executions')
def api_strategy_analytics_executions():
    """전략 실행 이력 API"""
    try:
        from core.strategy_execution_tracker import execution_tracker

        # 필터 파라미터
        strategy_tier = request.args.get('strategy_tier')
        strategy_id = request.args.get('strategy_id')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 50, type=int)

        # 'all' 값은 None으로 처리
        if strategy_tier == 'all':
            strategy_tier = None
        if strategy_id == 'all':
            strategy_id = None

        executions = execution_tracker.get_execution_history(
            strategy_tier=strategy_tier,
            strategy_id=strategy_id,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'success': True,
            'data': executions,
            'total': len(executions)
        })

    except Exception as e:
        logger.error(f"전략 실행 이력 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/strategy_analytics/performance')
def api_strategy_analytics_performance():
    """전략 성과 분석 API"""
    try:
        from core.strategy_execution_tracker import execution_tracker

        strategy_tier = request.args.get('strategy_tier')
        strategy_id = request.args.get('strategy_id')
        days = request.args.get('days', 30, type=int)

        # 'all' 값은 None으로 처리
        if strategy_tier == 'all':
            strategy_tier = None
        if strategy_id == 'all':
            strategy_id = None

        performance = execution_tracker.get_strategy_performance(
            strategy_tier=strategy_tier,
            strategy_id=strategy_id,
            days=days
        )

        return jsonify({
            'success': True,
            'data': performance
        })

    except Exception as e:
        logger.error(f"전략 성과 분석 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/strategy_analytics/hourly')
def api_strategy_analytics_hourly():
    """시간대별 전략 실행 분석 API"""
    try:
        from core.strategy_execution_tracker import execution_tracker

        hours = request.args.get('hours', 24, type=int)

        # 시간대별 실행 데이터 조회
        executions = execution_tracker.get_execution_history(
            hours=hours, limit=1000)

        # 시간대별 집계
        hourly_data = {}
        strategy_hourly = {}

        for execution in executions:
            # 실행 시간에서 시간 추출
            from datetime import datetime
            exec_time = datetime.fromisoformat(execution['execution_time'])
            hour = exec_time.hour

            # 전체 시간대별 집계
            if hour not in hourly_data:
                hourly_data[hour] = 0
            hourly_data[hour] += 1

            # 전략별 시간대별 집계
            strategy_key = f"{execution['strategy_tier']}:{execution['strategy_id']}"
            if strategy_key not in strategy_hourly:
                strategy_hourly[strategy_key] = {}
            if hour not in strategy_hourly[strategy_key]:
                strategy_hourly[strategy_key][hour] = 0
            strategy_hourly[strategy_key][hour] += 1

        # 24시간 배열로 변환
        hourly_array = [hourly_data.get(i, 0) for i in range(24)]

        return jsonify({
            'success': True,
            'data': {
                'hourly_distribution': hourly_array,
                'strategy_hourly': strategy_hourly,
                'total_executions': len(executions)
            }
        })

    except Exception as e:
        logger.error(f"시간대별 분석 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/strategy_config')
def strategy_config():
    """전략 설정 페이지"""
    return render_template('strategy_config.html')


@app.route('/ai_optimization')
def ai_optimization():
    """AI 최적화 시스템 페이지"""
    return render_template('ai_optimization.html')


# =============================================================================
# AI 분석 API 엔드포인트
# =============================================================================

@app.route('/api/ai/market_analysis')
def api_ai_market_analysis():
    """AI 시장 분석 API"""
    try:
        from core.ai_advisor import ai_advisor

        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        analysis = ai_advisor.analyze_market(force_refresh=force_refresh)

        return jsonify({
            'success': True,
            'data': {
                'type': analysis.analysis_type,
                'content': analysis.content,
                'confidence': analysis.confidence,
                'risk_level': analysis.risk_level,
                'timestamp': analysis.timestamp.isoformat(),
                'market_data': analysis.market_data,
                'is_mock': analysis.is_mock
            }
        })

    except Exception as e:
        logger.error(f"AI 시장 분석 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/trading_advice')
def api_ai_trading_advice():
    """AI 거래 조언 API"""
    try:
        from core.ai_advisor import ai_advisor

        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        advice = ai_advisor.get_trading_advice(force_refresh=force_refresh)

        return jsonify({
            'success': True,
            'data': {
                'type': advice.analysis_type,
                'content': advice.content,
                'confidence': advice.confidence,
                'risk_level': advice.risk_level,
                'timestamp': advice.timestamp.isoformat(),
                'recommendations': advice.recommendations or [],
                'is_mock': advice.is_mock
            }
        })

    except Exception as e:
        logger.error(f"AI 거래 조언 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/comprehensive_analysis')
def api_ai_comprehensive_analysis():
    """AI 종합 분석 API"""
    try:
        from core.ai_advisor import ai_advisor

        analysis = ai_advisor.get_comprehensive_analysis()

        return jsonify({
            'success': True,
            'data': {
                'market': {
                    'type': analysis['market'].analysis_type,
                    'content': analysis['market'].content,
                    'confidence': analysis['market'].confidence,
                    'risk_level': analysis['market'].risk_level,
                    'timestamp': analysis['market'].timestamp.isoformat(),
                    'market_data': analysis['market'].market_data
                },
                'trading': {
                    'type': analysis['trading'].analysis_type,
                    'content': analysis['trading'].content,
                    'confidence': analysis['trading'].confidence,
                    'risk_level': analysis['trading'].risk_level,
                    'timestamp': analysis['trading'].timestamp.isoformat(),
                    'recommendations': analysis['trading'].recommendations or []
                },
                'generated_at': analysis['generated_at']
            }
        })

    except Exception as e:
        logger.error(f"AI 종합 분석 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/clear_cache', methods=['POST'])
def api_ai_clear_cache():
    """AI 분석 캐시 초기화 API"""
    try:
        from core.ai_advisor import ai_advisor

        ai_advisor.clear_cache()

        return jsonify({
            'success': True,
            'message': 'AI 분석 캐시가 초기화되었습니다.'
        })

    except Exception as e:
        logger.error(f"AI 캐시 초기화 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/scheduler/status')
def api_ai_scheduler_status():
    """AI 스케줄러 상태 조회"""
    try:
        from core.ai_scheduler import ai_scheduler

        ai_config = config_manager.get_config('trading.ai_analysis') or {}

        return jsonify({
            'success': True,
            'data': {
                'enabled': ai_config.get('enabled', False),
                'interval_minutes': ai_config.get('interval_minutes', 30),
                'is_running': ai_scheduler.is_running(),
                'last_execution': ai_config.get('last_execution'),
                'auto_on_startup': ai_config.get('auto_on_startup', False)
            }
        })

    except Exception as e:
        logger.error(f"AI 스케줄러 상태 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/scheduler/toggle', methods=['POST'])
def api_ai_scheduler_toggle():
    """AI 스케줄러 시작/중지"""
    try:
        from core.ai_scheduler import ai_scheduler

        data = request.get_json() or {}
        action = data.get('action', 'toggle')  # 'start', 'stop', 'toggle'

        ai_config = config_manager.get_config('trading.ai_analysis') or {}
        current_enabled = ai_config.get('enabled', False)

        if action == 'start' or (action == 'toggle' and not current_enabled):
            # 스케줄러 시작
            config_manager.update_config({
                'trading.ai_analysis.enabled': True
            })
            ai_scheduler.start()
            new_status = True
            message = 'AI 분석 스케줄러가 시작되었습니다.'

        elif action == 'stop' or (action == 'toggle' and current_enabled):
            # 스케줄러 중지
            config_manager.update_config({
                'trading.ai_analysis.enabled': False
            })
            ai_scheduler.stop()
            new_status = False
            message = 'AI 분석 스케줄러가 중지되었습니다.'

        else:
            return jsonify({
                'success': False,
                'error': '잘못된 액션입니다.'
            }), 400

        return jsonify({
            'success': True,
            'data': {
                'enabled': new_status,
                'is_running': ai_scheduler.is_running()
            },
            'message': message
        })

    except Exception as e:
        logger.error(f"AI 스케줄러 토글 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/scheduler/execute', methods=['POST'])
def api_ai_scheduler_execute():
    """AI 분석 즉시 실행"""
    try:
        from core.ai_scheduler import ai_scheduler

        success = ai_scheduler.execute_now()

        if success:
            return jsonify({
                'success': True,
                'message': 'AI 분석이 성공적으로 실행되었습니다.',
                'data': {
                    'last_execution': ai_scheduler.get_last_execution().isoformat() if ai_scheduler.get_last_execution() else None
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'AI 분석 실행 중 오류가 발생했습니다.'
            }), 500

    except Exception as e:
        logger.error(f"AI 분석 즉시 실행 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai/scheduler/config', methods=['POST'])
def api_ai_scheduler_config():
    """AI 스케줄러 설정 업데이트"""
    try:
        data = request.get_json() or {}

        # 설정 업데이트
        updates = {}
        if 'interval_minutes' in data:
            interval = int(data['interval_minutes'])
            if 5 <= interval <= 1440:  # 5분 ~ 24시간
                updates['trading.ai_analysis.interval_minutes'] = interval
            else:
                return jsonify({
                    'success': False,
                    'error': '실행 주기는 5분에서 24시간(1440분) 사이여야 합니다.'
                }), 400

        if 'auto_on_startup' in data:
            updates['trading.ai_analysis.auto_on_startup'] = bool(
                data['auto_on_startup'])

        if updates:
            config_manager.update_config(updates)

        return jsonify({
            'success': True,
            'message': '설정이 업데이트되었습니다.',
            'data': config_manager.get_config('trading.ai_analysis') or {}
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': '잘못된 설정 값입니다.'
        }), 400
    except Exception as e:
        logger.error(f"AI 스케줄러 설정 업데이트 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API 엔드포인트들


@app.route('/api/system/status')
def api_system_status():
    """시스템 상태 API (프로세스 상태 포함)"""
    try:
        # 기본 시스템 상태
        basic_status = {
            'system_enabled': config_manager.is_system_enabled(),
            'trading_enabled': config_manager.is_trading_enabled(),
            'mode': config_manager.get_config('system.mode'),
            'last_updated': now_kst().isoformat()
        }

        # AutoTrader 프로세스 상태 확인
        process_status = check_auto_trader_process()

        # AutoTrader 내부 상태 (가능한 경우)
        auto_trader_status = {'running': False, 'error': 'AutoTrader 모듈 접근 불가'}
        try:
            from core.auto_trader import get_auto_trading_status
            auto_trader_status = get_auto_trading_status()
        except Exception as e:
            auto_trader_status = {'running': False, 'error': str(e)}

        # 통합 상태
        return jsonify({
            **basic_status,
            'process_status': process_status,
            'auto_trader_status': auto_trader_status,
            'process_running': process_status.get('running', False),
            'auto_trader_running': auto_trader_status.get('running', False)
        })

    except Exception as e:
        logger.error(f"시스템 상태 API 오류: {e}")
        return jsonify({
            'error': str(e),
            'system_enabled': False,
            'trading_enabled': False,
            'process_running': False,
            'auto_trader_running': False
        }), 500


@app.route('/api/system/process_status')
def api_process_status():
    """프로세스 상태 상세 API (웹 앱 내부 상태 우선 확인)"""
    try:
        # 먼저 웹 애플리케이션 내부의 AutoTrader 상태 확인
        internal_status = {'running': False, 'reason': '내부 상태 확인 불가'}
        try:
            from core.auto_trader import get_auto_trading_status
            internal_status = get_auto_trading_status()
        except Exception as e:
            internal_status = {'running': False,
                               'reason': f'내부 상태 오류: {str(e)}'}

        # 외부 프로세스 상태 확인
        external_process = check_auto_trader_process()
        system_status = get_system_process_status()

        # 통합 상태 결정
        is_running = internal_status.get(
            'running', False) or external_process.get('running', False)

        return jsonify({
            'success': True,
            'auto_trader_process': {
                'running': is_running,
                'internal_status': internal_status,
                'external_process': external_process,
                'detection_method': 'internal' if internal_status.get('running') else 'external'
            },
            'system_status': system_status,
            'timestamp': now_kst().isoformat()
        })

    except Exception as e:
        logger.error(f"프로세스 상태 API 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': now_kst().isoformat()
        }), 500


@app.route('/api/market/current_price')
def api_current_price():
    """실시간 비트코인 현재가격 조회 API"""
    try:
        import requests

        # Upbit API 직접 호출
        response = requests.get(
            'https://api.upbit.com/v1/ticker?markets=KRW-BTC', timeout=10)

        if response.status_code != 200:
            return jsonify({
                'success': False,
                'message': f'Upbit API 호출 실패: {response.status_code}'
            })

        ticker_data = response.json()

        if not ticker_data or len(ticker_data) == 0:
            return jsonify({
                'success': False,
                'message': 'ticker 데이터가 비어있음'
            })

        ticker = ticker_data[0]
        current_price = float(ticker['trade_price'])

        # 시장 정보 생성
        response_data = {
            'success': True,
            'data': {
                'price': current_price,
                'formatted_price': f"₩ {current_price:,.0f}",
                'change_rate': ticker.get('signed_change_rate', 0) * 100,
                'change_price': ticker.get('signed_change_price', 0),
                'high_price': float(ticker.get('high_price', 0)),
                'low_price': float(ticker.get('low_price', 0)),
                'prev_closing_price': float(ticker.get('prev_closing_price', 0)),
                'trade_volume': float(ticker.get('acc_trade_volume_24h', 0)),
                'timestamp': datetime.now().isoformat()
            }
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"현재가 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/market/chart_data')
def api_chart_data():
    """실시간 차트 데이터 조회 API"""
    try:
        import requests

        # 최근 24시간 5분봉 데이터 (288개) 직접 호출
        response = requests.get(
            'https://api.upbit.com/v1/candles/minutes/5?market=KRW-BTC&count=288', timeout=15)

        if response.status_code != 200:
            return jsonify({
                'success': False,
                'message': f'Upbit 캔들 API 호출 실패: {response.status_code}'
            })

        candles = response.json()

        if candles:
            chart_data = []
            for candle in candles:
                chart_data.append({
                    'time': candle['candle_date_time_kst'],
                    'open': float(candle['opening_price']),
                    'high': float(candle['high_price']),
                    'low': float(candle['low_price']),
                    'close': float(candle['trade_price']),
                    'volume': float(candle['candle_acc_trade_volume'])
                })

            # 시간순 정렬 (오래된 것부터)
            chart_data.reverse()

            return jsonify({
                'success': True,
                'data': chart_data
            })
        else:
            return jsonify({
                'success': False,
                'message': '차트 데이터 조회 실패'
            })

    except Exception as e:
        logger.error(f"차트 데이터 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# AI 최적화 시스템 API 엔드포인트
# =============================================================================

@app.route('/api/ai_optimization/status')
def api_ai_optimization_status():
    """AI 최적화 시스템 상태 조회 API"""
    try:
        from core.ai_optimization_manager import ai_optimization_manager

        status = ai_optimization_manager.get_optimization_status()

        return jsonify({
            'success': True,
            'data': status
        })

    except Exception as e:
        logger.error(f"AI 최적화 상태 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/execute', methods=['POST'])
def api_ai_optimization_execute():
    """AI 최적화 실행 API"""
    try:
        from core.ai_optimization_manager import ai_optimization_manager, OptimizationMode

        request_data = request.get_json() or {}
        mode = request_data.get('mode', 'balanced')

        # 모드 검증
        if mode not in [m.value for m in OptimizationMode]:
            return jsonify({
                'success': False,
                'message': f'유효하지 않은 모드: {mode}'
            }), 400

        optimization_mode = OptimizationMode(mode)
        result = ai_optimization_manager.execute_full_optimization(
            optimization_mode)

        return jsonify(result)

    except Exception as e:
        logger.error(f"AI 최적화 실행 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/configure', methods=['POST'])
def api_ai_optimization_configure():
    """AI 최적화 설정 API"""
    try:
        from core.ai_optimization_manager import ai_optimization_manager

        config_data = request.get_json() or {}

        success = ai_optimization_manager.configure_optimization(config_data)

        if success:
            return jsonify({
                'success': True,
                'message': '설정이 업데이트되었습니다'
            })
        else:
            return jsonify({
                'success': False,
                'message': '설정 업데이트 실패'
            }), 400

    except Exception as e:
        logger.error(f"AI 최적화 설정 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/history')
def api_ai_optimization_history():
    """AI 최적화 이력 조회 API"""
    try:
        from core.ai_optimization_manager import ai_optimization_manager

        limit = request.args.get('limit', 10, type=int)
        history = ai_optimization_manager.get_optimization_history(limit)

        return jsonify({
            'success': True,
            'data': history
        })

    except Exception as e:
        logger.error(f"AI 최적화 이력 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/performance_analysis')
def api_ai_performance_analysis():
    """AI 성과 분석 API"""
    try:
        from core.ai_performance_analyzer import ai_performance_analyzer

        days = request.args.get('days', 30, type=int)

        # 포트폴리오 성과 요약
        portfolio_summary = ai_performance_analyzer.get_portfolio_performance_summary(
            days)

        # 활성 전략 목록
        active_strategies = config_manager.get_config(
            'independent_strategies.strategies', {})
        strategy_metrics = {}

        for strategy_id, config in active_strategies.items():
            if config.get('enabled', True):
                metrics = ai_performance_analyzer.analyze_strategy_performance(
                    strategy_id, days)
                if metrics:
                    strategy_metrics[strategy_id] = metrics.to_dict()

        return jsonify({
            'success': True,
            'data': {
                'portfolio_summary': portfolio_summary,
                'strategy_metrics': strategy_metrics,
                'analysis_period': days
            }
        })

    except Exception as e:
        logger.error(f"AI 성과 분석 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/weight_optimization', methods=['POST'])
def api_weight_optimization():
    """가중치 최적화 API"""
    try:
        from core.dynamic_weight_optimizer import dynamic_weight_optimizer, WeightAdjustmentStrategy

        request_data = request.get_json() or {}
        method = request_data.get('method', 'performance_based')

        # 방법 검증
        if method not in [s.value for s in WeightAdjustmentStrategy]:
            return jsonify({
                'success': False,
                'message': f'유효하지 않은 최적화 방법: {method}'
            }), 400

        strategy = WeightAdjustmentStrategy(method)
        result = dynamic_weight_optimizer.optimize_portfolio_weights(strategy)

        if result:
            # 자동 적용 여부 확인
            auto_apply = request_data.get('auto_apply', False)
            if auto_apply:
                applied = dynamic_weight_optimizer.apply_weight_adjustments(
                    result)
                return jsonify({
                    'success': True,
                    'data': result.to_dict() if hasattr(result, 'to_dict') else result,
                    'applied': applied
                })
            else:
                return jsonify({
                    'success': True,
                    'data': result.to_dict() if hasattr(result, 'to_dict') else result
                })
        else:
            return jsonify({
                'success': False,
                'message': '가중치 최적화 결과 없음'
            })

    except Exception as e:
        logger.error(f"가중치 최적화 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/trading_optimization', methods=['POST'])
def api_trading_optimization():
    """거래 최적화 API"""
    try:
        from core.adaptive_trading_optimizer import adaptive_trading_optimizer

        result = adaptive_trading_optimizer.auto_optimize()

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"거래 최적화 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai_optimization/parameter_tuning', methods=['POST'])
def api_parameter_tuning():
    """파라미터 튜닝 API"""
    try:
        from core.ai_parameter_tuner import ai_parameter_tuner, TuningObjective

        request_data = request.get_json() or {}
        objective = request_data.get('objective', 'balance_risk_return')
        strategy_id = request_data.get('strategy_id')

        # 목표 검증
        if objective not in [obj.value for obj in TuningObjective]:
            return jsonify({
                'success': False,
                'message': f'유효하지 않은 튜닝 목표: {objective}'
            }), 400

        tuning_objective = TuningObjective(objective)

        if strategy_id:
            # 특정 전략 튜닝
            results = ai_parameter_tuner.tune_strategy_parameters(
                strategy_id, tuning_objective)

            # 자동 적용 여부 확인
            auto_apply = request_data.get('auto_apply', False)
            if auto_apply and results:
                application_results = ai_parameter_tuner.apply_tuning_results(
                    results)
                return jsonify({
                    'success': True,
                    'data': {
                        'tuning_results': [r.to_dict() for r in results],
                        'application_results': application_results
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'data': [r.to_dict() for r in results]
                })
        else:
            # 전체 전략 튜닝
            result = ai_parameter_tuner.auto_tune_all_strategies(
                tuning_objective)
            return jsonify({
                'success': True,
                'data': result
            })

    except Exception as e:
        logger.error(f"파라미터 튜닝 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/system/toggle', methods=['POST'])
def api_toggle_system():
    """시스템 온/오프 토글"""
    try:
        action = request.json.get('action')  # 'enable' or 'disable'

        if action == 'enable':
            config_manager.enable_system()
            # 시스템 활성화 시 자동 거래 스케줄러 시작
            start_auto_trading()
            message = "시스템이 활성화되었습니다."
        elif action == 'disable':
            config_manager.disable_system()
            # 시스템 비활성화 시 자동 거래 스케줄러 정지
            stop_auto_trading()
            message = "시스템이 비활성화되었습니다."
        else:
            return jsonify({'success': False, 'message': '잘못된 액션입니다.'}), 400

        # 로그 기록
        db.insert_log('INFO', 'WebInterface', f'시스템 {action}됨',
                      f'사용자에 의해 {action}됨')

        # 현재 상태 포함 반환
        return jsonify({'success': True, 'message': message, 'status': {
            'system_enabled': config_manager.is_system_enabled(),
            'trading_enabled': config_manager.is_trading_enabled(),
            'mode': config_manager.get_config('system.mode')
        }})
    except Exception as e:
        logger.error(f"시스템 토글 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/trading/toggle', methods=['POST'])
def api_toggle_trading():
    """자동거래 온/오프 토글"""
    try:
        action = request.json.get('action')  # 'enable' or 'disable'

        if action == 'enable':
            config_manager.enable_trading()
            # 시스템이 켜져 있고 스케줄러가 꺼져 있으면 시작
            if config_manager.is_system_enabled() and not auto_trader.running:
                start_auto_trading()
            message = "자동거래가 활성화되었습니다."
        elif action == 'disable':
            config_manager.disable_trading()
            message = "자동거래가 비활성화되었습니다."
        else:
            return jsonify({'success': False, 'message': '잘못된 액션입니다.'}), 400

        # 로그 기록
        db.insert_log('INFO', 'WebInterface', f'자동거래 {action}됨',
                      f'사용자에 의해 {action}됨')

        return jsonify({'success': True, 'message': message, 'status': {
            'system_enabled': config_manager.is_system_enabled(),
            'trading_enabled': config_manager.is_trading_enabled(),
            'mode': config_manager.get_config('system.mode')
        }})
    except Exception as e:
        logger.error(f"자동거래 토글 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/settings/update', methods=['POST'])
def api_update_settings():
    """설정 업데이트"""
    try:
        settings_data = request.json

        for key, value in settings_data.items():
            old_value = config_manager.get_config(key)
            config_manager.set_config(key, value)

            # 변경 이력 저장
            db.log_config_change(key, str(old_value), str(value), 'web_user')

        return jsonify({'success': True, 'message': '설정이 업데이트되었습니다.'})
    except Exception as e:
        logger.error(f"설정 업데이트 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/emergency_stop', methods=['POST'])
def api_emergency_stop():
    """긴급 정지"""
    try:
        # 즉시 모든 자동 실행 중단 및 상태 비활성화
        try:
            stop_auto_trading()
        except Exception:
            pass
        config_manager.disable_trading()
        config_manager.disable_system()

        # 긴급 정지 로그
        db.insert_log('CRITICAL', 'WebInterface', '긴급 정지 실행됨',
                      '사용자에 의한 긴급 정지')

        # 현재 상태를 함께 반환하여 프론트가 즉시 반영하도록 함
        return jsonify({
            'success': True,
            'message': '긴급 정지가 실행되었습니다.',
            'status': {
                'system_enabled': config_manager.is_system_enabled(),
                'trading_enabled': config_manager.is_trading_enabled(),
                'mode': config_manager.get_config('system.mode')
            }
        })
    except Exception as e:
        logger.error(f"긴급 정지 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/voting_engine/status')
def api_voting_engine_status():
    """투표 기반 전략 엔진 상태 API"""
    try:
        from core.auto_trader import auto_trader

        if auto_trader.voting_engine:
            status = auto_trader.voting_engine.get_engine_status()

            return jsonify({
                'success': True,
                'status': status
            })
        else:
            return jsonify({
                'success': False,
                'message': 'VotingStrategyEngine이 초기화되지 않았습니다.'
            }), 500

    except Exception as e:
        logger.error(f"투표 엔진 상태 조회 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/voting_engine/analyze', methods=['POST'])
def api_voting_engine_analyze():
    """투표 기반 전략 분석 실행 API"""
    try:
        from core.auto_trader import auto_trader

        if not auto_trader.voting_engine:
            return jsonify({
                'success': False,
                'message': 'VotingStrategyEngine이 초기화되지 않았습니다.'
            }), 500

        # 분석 실행
        result = auto_trader.voting_engine.analyze()

        if result:
            # JSON 직렬화 안전 변환
            def safe_serialize(obj):
                """JSON 직렬화 안전 변환"""
                if isinstance(obj, dict):
                    return {k: safe_serialize(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [safe_serialize(item) for item in obj]
                elif isinstance(obj, bool):
                    return bool(obj)
                elif isinstance(obj, (int, float, str)):
                    return obj
                elif obj is None:
                    return None
                else:
                    return str(obj)

            response_data = {
                'success': True,
                'decision': {
                    'signal': result.decision.final_signal.value,
                    'confidence': float(result.decision.confidence),
                    'total_votes': int(result.decision.total_votes),
                    'vote_distribution': safe_serialize(result.decision.vote_distribution),
                    'reasoning': str(result.decision.reasoning),
                    'timestamp': result.execution_time.isoformat()
                },
                'strategies': [
                    {
                        'strategy_id': str(vote.strategy_id),
                        'strategy_name': str(vote.strategy_name),
                        'signal': vote.signal.value,
                        'confidence': float(vote.confidence),
                        'strength': float(vote.strength),
                        'reasoning': str(vote.reasoning),
                        'indicators': safe_serialize(vote.indicators)
                    }
                    for vote in result.decision.contributing_strategies
                ],
                'market_summary': safe_serialize(result.market_data_summary)
            }

            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'message': '분석 결과를 생성할 수 없습니다.'
            })

    except Exception as e:
        logger.error(f"투표 엔진 분석 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/voting_engine/recent_decisions')
def api_voting_engine_recent_decisions():
    """최근 투표 결정 내역 API"""
    try:
        from core.auto_trader import auto_trader

        if not auto_trader.voting_engine:
            return jsonify({
                'success': False,
                'message': 'VotingStrategyEngine이 초기화되지 않았습니다.'
            }), 500

        hours = request.args.get('hours', 24, type=int)
        decisions = auto_trader.voting_engine.get_recent_decisions(hours)

        return jsonify({
            'success': True,
            'decisions': decisions,
            'total_count': len(decisions)
        })

    except Exception as e:
        logger.error(f"최근 결정 조회 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/voting_engine/weights', methods=['POST'])
def api_voting_engine_update_weights():
    """전략 가중치 업데이트 API"""
    try:
        from core.auto_trader import auto_trader

        if not auto_trader.voting_engine:
            return jsonify({
                'success': False,
                'message': 'VotingStrategyEngine이 초기화되지 않았습니다.'
            }), 500

        data = request.get_json()
        weights = data.get('weights', {})

        if not weights:
            return jsonify({
                'success': False,
                'message': '가중치 데이터가 필요합니다.'
            }), 400

        # 가중치 업데이트
        auto_trader.voting_engine.update_strategy_weights(weights)

        # 설정 파일에도 저장
        config_manager.update_config({
            'independent_strategies.strategy_weights': weights
        })

        return jsonify({
            'success': True,
            'message': '전략 가중치가 업데이트되었습니다.',
            'weights': weights
        })

    except Exception as e:
        logger.error(f"가중치 업데이트 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/analysis/latest')
def api_latest_analysis():
    """최근 분석 결과 조회 API (파일 기반)"""
    try:
        from core.result_manager import result_manager

        # 파일에서 분석 이력 조회
        analyses = result_manager.get_analysis_history(days=1)

        # 최대 개수 제한
        limit = request.args.get('limit', 10, type=int)
        analyses = analyses[:limit]

        return jsonify({
            'success': True,
            'analyses': analyses
        })
    except Exception as e:
        logger.error(f"분석 결과 조회 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/auto_trading_status')
def api_auto_trading_status():
    """자동 거래 상태 API (개선된 AutoTrader 기반)"""
    try:
        from core.auto_trader import auto_trader, get_auto_trading_status

        # 실제 AutoTrader에서 상태 가져오기
        status = get_auto_trading_status()

        # 추가적인 상태 정보 보강
        enhanced_status = {
            'running': status['running'],
            'auto_trading_enabled': config_manager.is_trading_enabled(),
            'system_enabled': config_manager.is_system_enabled(),
            'last_execution': status.get('last_execution_time'),
            'next_execution': status.get('next_execution_time'),
            'server_time': now_kst().isoformat(),  # 서버 현재 시간을 KST로 제공
            'last_started_at': status.get('last_started_at'),
            'success_rate': status.get('success_rate', 0),
            'total_executions': status.get('total_executions', 0),
            'mode': config_manager.get_config('system.mode'),
            'last_updated': now_kst().isoformat()
        }

        # next_execution이 비어있을 때, 설정된 주기 기준으로 계산하여 제공
        try:
            if not enhanced_status.get('next_execution'):
                trading_cfg = config_manager.get_trading_config()
                interval_minutes = trading_cfg.get(
                    'trade_interval_minutes', 10)

                now = now_kst()
                base = now.replace(second=0, microsecond=0)

                # 기본 계산: 다음 인터벌 경계 시각
                if interval_minutes >= 60:
                    # 시간 단위 이상이면 단순히 interval 만큼 더함
                    next_time = base + timedelta(minutes=interval_minutes)
                else:
                    remainder = now.minute % interval_minutes
                    add_minutes = interval_minutes if remainder == 0 else (
                        interval_minutes - remainder)
                    next_time = base + timedelta(minutes=add_minutes)

                enhanced_status['next_execution'] = next_time.isoformat()
        except Exception as calc_err:
            logger.error(f"다음 실행 시간 계산 오류: {calc_err}")

        return jsonify({
            'success': True,
            'status': enhanced_status
        })
    except Exception as e:
        logger.error(f"자동 거래 상태 조회 오류: {e}")
        # 백업 상태 반환
        return jsonify({
            'success': True,
            'status': {
                'running': False,
                'auto_trading_enabled': config_manager.is_trading_enabled(),
                'system_enabled': config_manager.is_system_enabled(),
                'last_execution': None,
                'next_execution': None,
                'mode': config_manager.get_config('system.mode'),
                'error': str(e)
            }
        })


@app.route('/api/auto_trader/start', methods=['POST'])
def api_start_auto_trader():
    """웹 프로세스에서 AutoTrader 강제 시작"""
    try:
        from core.auto_trader import auto_trader

        # 시스템 활성화만 확인 (거래 비활성화여도 스케줄/전략 계산은 진행)
        if not config_manager.is_system_enabled():
            return jsonify({
                'success': False,
                'message': '시스템이 비활성화되어 있습니다. 먼저 시스템을 활성화하세요.'
            }), 400

        # AutoTrader 시작
        if auto_trader.running:
            return jsonify({
                'success': True,
                'message': 'AutoTrader가 이미 실행 중입니다.',
                'status': auto_trader.get_status()
            })

        logger.info("웹 프로세스에서 AutoTrader 시작 시도")
        success = auto_trader.start()

        if success:
            status = auto_trader.get_status()
            logger.info(f"AutoTrader 시작 성공: {status}")

            # 성공 로그 기록
            db.insert_log('INFO', 'WebInterface', 'AutoTrader 시작',
                          f'웹에서 시작됨 - 다음 실행: {status.get("next_execution_time")}')

            return jsonify({
                'success': True,
                'message': 'AutoTrader가 성공적으로 시작되었습니다.',
                'status': status
            })
        else:
            logger.error("AutoTrader 시작 실패")
            return jsonify({
                'success': False,
                'message': 'AutoTrader 시작에 실패했습니다. 로그를 확인하세요.'
            }), 500

    except Exception as e:
        logger.error(f"AutoTrader 시작 API 오류: {e}")
        return jsonify({
            'success': False,
            'message': f'AutoTrader 시작 중 오류 발생: {str(e)}'
        }), 500


@app.route('/api/auto_trader/stop', methods=['POST'])
def api_stop_auto_trader():
    """웹 프로세스에서 AutoTrader 정지"""
    try:
        from core.auto_trader import auto_trader

        if not auto_trader.running:
            return jsonify({
                'success': True,
                'message': 'AutoTrader가 이미 정지되어 있습니다.',
                'status': auto_trader.get_status()
            })

        logger.info("웹 프로세스에서 AutoTrader 정지 시도")
        auto_trader.stop()

        status = auto_trader.get_status()
        logger.info(f"AutoTrader 정지 완료: {status}")

        # 정지 로그 기록
        db.insert_log('INFO', 'WebInterface', 'AutoTrader 정지', '웹에서 정지됨')

        return jsonify({
            'success': True,
            'message': 'AutoTrader가 성공적으로 정지되었습니다.',
            'status': status
        })

    except Exception as e:
        logger.error(f"AutoTrader 정지 API 오류: {e}")
        return jsonify({
            'success': False,
            'message': f'AutoTrader 정지 중 오류 발생: {str(e)}'
        }), 500


@app.route('/api/balance')
def api_balance():
    """잔고 조회 API"""
    try:
        api = UpbitAPI()
        balances = {
            'KRW': api.get_balance('KRW'),
            'BTC': api.get_balance('BTC')
        }
        current_price = api.get_current_price('KRW-BTC')

        # BTC 평가금액 계산
        btc_value = balances['BTC'] * current_price if current_price else 0
        total_value = balances['KRW'] + btc_value

        return jsonify({
            'balances': balances,
            'current_price': current_price,
            'btc_value': btc_value,
            'total_value': total_value
        })
    except Exception as e:
        logger.error(f"잔고 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard_data')
def api_dashboard_data():
    """대시보드 데이터 API"""
    try:
        dashboard_data = db.get_dashboard_data()

        # 5분 캔들 데이터 상태 추가
        try:
            from core.data_collection_scheduler import data_scheduler
            data_status = data_scheduler.get_status()
            dashboard_data['data_collection'] = {
                'active': data_status.get('running', False),
                'last_collection': data_status.get('last_collection'),
                'timeframes': data_status.get('timeframes', []),
                'collection_stats': data_status.get('stats', {})
            }
        except Exception as e:
            logger.warning(f"데이터 수집 상태 조회 실패: {e}")
            dashboard_data['data_collection'] = {
                'active': False, 'error': str(e)}

        return jsonify(dashboard_data)
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades')
def api_trades():
    """거래 내역 API (최근 30일, 선택적 필터)"""
    try:
        strategy_id = request.args.get('strategy_id')
        status = request.args.get('status')
        days = request.args.get('days', 30, type=int)

        start_date = datetime.now() - timedelta(days=days)
        trades = db.get_trades(strategy_id=strategy_id,
                               start_date=start_date, status=status)

        return jsonify({
            'success': True,
            'total': len(trades),
            'trades': trades
        })
    except Exception as e:
        logger.error(f"거래 내역 API 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/trading_activity')
def api_trading_activity():
    """통합 거래 활동 API - 전략 계산 결과와 실제 거래를 통합"""
    try:
        from core.strategy_execution_tracker import execution_tracker
        # KST 변환 헬퍼
        from datetime import datetime
        import pytz
        kst_tz = pytz.timezone('Asia/Seoul')

        def _to_kst(ts):
            if not ts:
                return ts
            # ts가 datetime이면 그대로 처리, 아니면 ISO 문자열 파싱
            if isinstance(ts, datetime):
                dt = ts
            else:
                try:
                    dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                except Exception:
                    return str(ts)
            # naive인 경우 UTC로 가정 후 KST로 변환
            if dt.tzinfo is None:
                try:
                    dt = pytz.utc.localize(dt)
                except Exception:
                    pass
            try:
                return dt.astimezone(kst_tz).isoformat()
            except Exception:
                return str(ts)

        # 파라미터
        days = request.args.get('days', 7, type=int)
        limit = request.args.get('limit', 100, type=int)
        strategy_tier = request.args.get('strategy_tier')
        action_filter = request.args.get('action')  # 'buy', 'sell', 'hold'

        # 전략 실행 이력 조회
        hours = days * 24
        executions = execution_tracker.get_execution_history(
            strategy_tier=strategy_tier,
            hours=hours,
            limit=limit
        )

        # 실제 거래 내역 조회
        start_date = datetime.now() - timedelta(days=days)
        actual_trades = db.get_trades(start_date=start_date)

        # 통합 활동 리스트 생성
        activities = []

        # 전략 실행 결과 추가
        for exec_data in executions:
            # indicators를 details로 파싱
            indicators_raw = exec_data.get('indicators', '{}')
            details = {}

            try:
                if isinstance(indicators_raw, str):
                    details = json.loads(indicators_raw)
                elif isinstance(indicators_raw, dict):
                    details = indicators_raw
            except (json.JSONDecodeError, TypeError):
                details = {}

            activity = {
                'type': 'strategy_execution',
                'timestamp': _to_kst(exec_data.get('execution_time')),
                'strategy_tier': exec_data.get('strategy_tier'),
                'strategy_id': exec_data.get('strategy_id'),
                'action': exec_data.get('signal_action'),
                'confidence': exec_data.get('confidence'),
                'strength': exec_data.get('strength', 0),
                'reasoning': exec_data.get('reasoning', ''),
                'market_regime': exec_data.get('market_regime', ''),
                'trade_executed': exec_data.get('trade_executed', False),
                'trade_id': exec_data.get('trade_id'),
                'pnl': exec_data.get('pnl', 0),
                'details': details,  # indicators를 details로 변환
                'indicators': indicators_raw  # 원본도 유지 (호환성)
            }

            # 액션 필터 적용
            if action_filter and activity['action'] != action_filter:
                continue

            activities.append(activity)

        # 실제 거래 추가 (전략과 연결되지 않은 수동 거래 등)
        for trade in actual_trades:
            # 이미 전략 실행에서 연결된 거래는 제외
            if not any(a.get('trade_id') == trade.get('id') for a in activities):
                activity = {
                    'type': 'manual_trade',
                    'timestamp': _to_kst(trade.get('timestamp')),
                    'strategy_tier': 'manual',
                    'strategy_id': 'manual_trade',
                    'action': trade.get('action'),
                    'confidence': 100,  # 수동 거래는 100% 확신
                    'strength': 100,
                    'reasoning': f"수동 거래: {trade.get('note', '')}",
                    'market_regime': 'unknown',
                    'trade_executed': True,
                    'trade_id': trade.get('id'),
                    'pnl': trade.get('pnl', 0),
                    'price': trade.get('price'),
                    'amount': trade.get('amount'),
                    'fee': trade.get('fee', 0)
                }
                activities.append(activity)

        # 시간순 정렬 (최신 순)
        activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        # 제한 적용
        activities = activities[:limit]

        # 통계 계산
        total_executions = len(
            [a for a in activities if a['type'] == 'strategy_execution'])
        total_trades = len([a for a in activities if a['trade_executed']])
        execution_rate = (total_trades / max(1, total_executions)) * 100

        buy_signals = len([a for a in activities if a['action'] == 'buy'])
        sell_signals = len([a for a in activities if a['action'] == 'sell'])
        hold_signals = len([a for a in activities if a['action'] == 'hold'])

        return jsonify({
            'success': True,
            'activities': activities,
            'statistics': {
                'total_activities': len(activities),
                'total_executions': total_executions,
                'total_trades': total_trades,
                'execution_rate': execution_rate,
                'signal_distribution': {
                    'buy': buy_signals,
                    'sell': sell_signals,
                    'hold': hold_signals
                }
            },
            'filters': {
                'days': days,
                'strategy_tier': strategy_tier,
                'action_filter': action_filter
            }
        })

    except Exception as e:
        logger.error(f"거래 활동 API 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/performance/summary')
def api_performance_summary():
    """성과 요약 API (30일 기본)"""
    try:
        days = request.args.get('days', 30, type=int)
        strategy_id = request.args.get('strategy_id')

        perf = db.get_strategy_performance(strategy_id=strategy_id, days=days)

        # 집계
        total_trades = sum(p.get('total_trades', 0) for p in perf)
        winning_trades = sum(p.get('winning_trades', 0) for p in perf)
        total_pnl = sum(p.get('total_pnl', 0) for p in perf)
        win_rate = (winning_trades / total_trades *
                    100) if total_trades > 0 else 0
        sharpe_avg = sum(p.get('sharpe_ratio', 0)
                         for p in perf) / len(perf) if perf else 0
        max_dd = min((p.get('max_drawdown', 0) for p in perf), default=0)

        return jsonify({
            'success': True,
            'summary': {
                'days': days,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_sharpe_ratio': sharpe_avg,
                'max_drawdown': max_dd
            }
        })
    except Exception as e:
        logger.error(f"성과 요약 API 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/performance/timeseries')
def api_performance_timeseries():
    """성과 시계열 API (일별 성과 목록)"""
    try:
        days = request.args.get('days', 90, type=int)
        strategy_id = request.args.get('strategy_id')
        perf = db.get_strategy_performance(strategy_id=strategy_id, days=days)

        # 날짜 내림차순이므로 프런트 가독성을 위해 오름차순 정렬
        perf_sorted = sorted(perf, key=lambda x: x.get('date'))

        return jsonify({
            'success': True,
            'timeseries': perf_sorted
        })
    except Exception as e:
        logger.error(f"성과 시계열 API 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/candle_data')
def api_candle_data():
    """5분 캔들 데이터 API"""
    try:
        timeframe = request.args.get('timeframe', '5m')
        count = int(request.args.get('count', 100))

        from core.candle_data_collector import candle_collector

        # DataFrame으로 데이터 조회
        df = candle_collector.get_dataframe(timeframe, count)

        if df is None or df.empty:
            return jsonify({
                'success': False,
                'message': '캔들 데이터가 없습니다.',
                'data': []
            })

        # JSON 직렬화 가능한 형태로 변환
        data = []
        for index, row in df.iterrows():
            data.append({
                'timestamp': index.isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume'])
            })

        return jsonify({
            'success': True,
            'timeframe': timeframe,
            'count': len(data),
            'data': data
        })

    except Exception as e:
        logger.error(f"캔들 데이터 API 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/data_collection/status')
def api_data_collection_status():
    """데이터 수집 상태 API"""
    try:
        from core.data_collection_scheduler import data_scheduler
        from core.candle_data_collector import candle_collector

        status = data_scheduler.get_status()

        # 최신 가격 정보 추가
        latest_price = candle_collector.get_latest_price()

        # 수집 통계 요약
        stats_summary = {}
        if 'stats' in status:
            for date, timeframes in status['stats'].items():
                for tf, stat in timeframes.items():
                    if tf not in stats_summary:
                        stats_summary[tf] = {
                            'total_collected': 0,
                            'total_failed': 0,
                            'avg_success_rate': 0
                        }

                    stats_summary[tf]['total_collected'] += stat['collected']
                    stats_summary[tf]['total_failed'] += stat['failed']

        # 평균 성공률 계산
        for tf, summary in stats_summary.items():
            total = summary['total_collected'] + summary['total_failed']
            if total > 0:
                summary['avg_success_rate'] = summary['total_collected'] / total

        return jsonify({
            'success': True,
            'status': {
                'scheduler_running': status.get('running', False),
                'collector_running': status.get('collection_active', False),
                'timeframes': status.get('timeframes', []),
                'last_collection': status.get('last_collection'),
                'latest_price': latest_price,
                'collection_summary': stats_summary
            }
        })

    except Exception as e:
        logger.error(f"데이터 수집 상태 API 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/regime/status')
def api_regime_status():
    """체제 기반 동적 임계값 시스템 상태 API"""
    try:
        from core.voting_strategy_engine import VotingStrategyEngine
        from core.upbit_api import UpbitAPI

        # VotingStrategyEngine 인스턴스 생성
        upbit_api = UpbitAPI()
        voting_engine = VotingStrategyEngine(upbit_api)

        # 체제 정보 조회
        regime_info = voting_engine.get_regime_info()

        # 임계값 조정사항 조회
        threshold_adjustments = voting_engine.get_threshold_adjustments()

        return jsonify({
            'success': True,
            'regime_info': regime_info,
            'threshold_adjustments': threshold_adjustments,
            'timestamp': now_kst().isoformat()
        })

    except Exception as e:
        logger.error(f"체제 상태 API 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'regime_info': {'status': 'error', 'message': str(e)},
            'threshold_adjustments': {'status': 'error', 'message': str(e)}
        }), 500


@app.route('/api/parameter_logs/recent')
def api_parameter_logs_recent():
    """최근 파라미터 조정 로그 조회 API"""
    try:
        from core.parameter_logger import parameter_logger

        hours = request.args.get('hours', 24, type=int)
        recent_adjustments = parameter_logger.get_recent_adjustments(hours)

        return jsonify({
            'success': True,
            'adjustments': recent_adjustments,
            'count': len(recent_adjustments),
            'period_hours': hours,
            'timestamp': now_kst().isoformat()
        })

    except Exception as e:
        logger.error(f"파라미터 로그 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'adjustments': [],
            'count': 0
        }), 500


@app.route('/api/parameter_logs/regime_history')
def api_regime_history():
    """체제 변경 이력 조회 API"""
    try:
        from core.parameter_logger import parameter_logger

        days = request.args.get('days', 7, type=int)
        regime_history = parameter_logger.get_regime_history(days)

        return jsonify({
            'success': True,
            'regime_changes': regime_history,
            'count': len(regime_history),
            'period_days': days,
            'timestamp': now_kst().isoformat()
        })

    except Exception as e:
        logger.error(f"체제 이력 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'regime_changes': [],
            'count': 0
        }), 500


@app.route('/api/parameter_logs/summary')
def api_parameter_logs_summary():
    """파라미터 조정 요약 리포트 API"""
    try:
        from core.parameter_logger import parameter_logger

        summary_report = parameter_logger.generate_summary_report()

        return jsonify({
            'success': True,
            'summary': summary_report,
            'timestamp': now_kst().isoformat()
        })

    except Exception as e:
        logger.error(f"파라미터 요약 리포트 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'summary': {}
        }), 500


@app.route('/api/trading_config')
def api_trading_config():
    """거래 설정 조회 API"""
    try:
        trading_config = config_manager.get_config('trading')
        return jsonify({
            'success': True,
            'trade_interval_minutes': trading_config.get('trade_interval_minutes', 10),
            'auto_trade_enabled': trading_config.get('auto_trade_enabled', False)
        })
    except Exception as e:
        logger.error(f"거래 설정 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/multi_tier_status')
def api_multi_tier_status():
    """다층 전략 상태 API"""
    try:
        from core.multi_tier_strategy_engine import multi_tier_engine

        # 다층 전략 분석 실행
        decision = multi_tier_engine.analyze()

        # 각 계층별 세부 정보 수집
        scalping_signals = multi_tier_engine.scalping_layer.analyze()
        trend_analysis = multi_tier_engine.trend_filter.analyze()
        macro_analysis = multi_tier_engine.macro_direction.analyze()

        # 결과 구성
        status = {
            'final_decision': {
                'action': decision.final_action,
                'confidence': round(decision.confidence, 3),
                'market_regime': decision.market_regime.value,
                'reasoning': decision.reasoning,
                'risk_score': round(decision.risk_score, 3),
                'suggested_amount': decision.suggested_amount
            },
            'layer_analysis': {
                'scalping': {
                    'signals_count': len(scalping_signals),
                    'signals': [
                        {
                            'strategy': signal.strategy_id,
                            'action': signal.action,
                            'confidence': round(signal.confidence, 3),
                            'strength': round(signal.strength, 3),
                            'reasoning': signal.reasoning[:100] + '...' if len(signal.reasoning) > 100 else signal.reasoning
                        }
                        for signal in scalping_signals
                    ]
                },
                'trend_filter': {
                    'trend': trend_analysis.get('trend', 'neutral'),
                    'strength': round(trend_analysis.get('strength', 0.5), 3),
                    'regime': trend_analysis.get('regime', 'sideways').value if hasattr(trend_analysis.get('regime'), 'value') else str(trend_analysis.get('regime', 'sideways')),
                    'volatility': round(trend_analysis.get('volatility', 0.02), 4),
                    'ema_trend': trend_analysis.get('ema_trend', {}),
                    'vwap_position': trend_analysis.get('vwap_position', {}),
                    'momentum_strength': trend_analysis.get('momentum_strength', {})
                },
                'macro_direction': {
                    'direction': macro_analysis.get('direction', 'neutral'),
                    'strength': round(macro_analysis.get('strength', 0.5), 3),
                    'regime': macro_analysis.get('regime', 'sideways').value if hasattr(macro_analysis.get('regime'), 'value') else str(macro_analysis.get('regime', 'sideways')),
                    'trend_alignment': macro_analysis.get('trend_alignment', {}),
                    'volatility_regime': macro_analysis.get('volatility_regime', {}),
                    'market_structure': macro_analysis.get('market_structure', {})
                }
            },
            'tier_contributions': {
                tier.value: round(contribution, 3)
                for tier, contribution in decision.tier_contributions.items()
            },
            'weights': {
                tier.value: weight
                for tier, weight in multi_tier_engine.tier_weights.items()
            },
            'timestamp': decision.timestamp.isoformat()
        }

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        logger.error(f"다층 전략 상태 API 오류: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'fallback_status': {
                'final_decision': {
                    'action': 'hold',
                    'confidence': 0.5,
                    'market_regime': 'sideways',
                    'reasoning': f'분석 오류: {str(e)}',
                    'risk_score': 0.8
                }
            }
        }), 500


@app.route('/api/manual_trading/analyze', methods=['POST'])
def api_manual_analyze():
    """수동 전략 분석 실행"""
    try:
        from strategy_manager import StrategyManager
        from core.upbit_api import UpbitAPI, MarketData
        from core.signal_manager import TradingSignal, MarketCondition
        from datetime import datetime

        # Strategy Manager 인스턴스 생성
        strategy_manager = StrategyManager()

        # 활성 전략들 조회
        active_strategies = strategy_manager.get_active_strategies('hourly')
        logger.info(f"활성 전략 수: {len(active_strategies)}")

        # API 인스턴스 생성 (실거래)
        api = UpbitAPI()

        # API 활용 여부 확인 (초기값 설정)
        api_status = "SIMULATION"  # 기본값
        try:
            # 실제 API 연결 테스트
            test_price = api.get_current_price("KRW-BTC")
            if test_price is not None:
                api_status = "REAL_API"
        except Exception as e:
            api_status = "SIMULATION"
            logger.warning(f"API 연결 실패, 시뮬레이션 모드로 전환: {e}")

        # 분석 결과 반환
        result = {
            'timestamp': datetime.now().isoformat(),
            'individual_signals': [],
            'consolidated_signal': None,
            'active_strategies_count': len(active_strategies),
            'market_data_available': True,
            'api_status': api_status  # API 활용 여부 추가
        }

        # 시장 데이터 시뮬레이션 (실제 API 호출 실패 시)
        try:
            current_price = api.get_current_price("KRW-BTC")
            market_data = MarketData(
                market="KRW-BTC",
                price=current_price or 95000000,  # 기본값 9500만원
                volume=100.0,
                timestamp=datetime.now(),
                high=current_price * 1.02 if current_price else 96900000,
                low=current_price * 0.98 if current_price else 93100000,
                open=current_price * 0.999 if current_price else 94905000,
                prev_close=current_price * 0.998 if current_price else 94810000
            )
        except Exception as e:
            logger.warning(f"실제 시장 데이터 조회 실패, 시뮬레이션 사용: {e}")
            market_data = MarketData(
                market="KRW-BTC",
                price=95000000,
                volume=100.0,
                timestamp=datetime.now(),
                high=96900000,
                low=93100000,
                open=94905000,
                prev_close=94810000
            )
            result['market_data_available'] = False
            api_status = "SIMULATION"  # 시장 데이터 실패 시 시뮬레이션으로 설정
            result['api_status'] = api_status  # 결과 업데이트

        # 실제 전략별 신호 생성
        from core.real_strategy_signals import RealStrategySignals
        real_signals = RealStrategySignals(api)

        strategy_signals = {}

        for strategy_id, strategy in active_strategies.items():
            try:
                signal = None

                # 실제 전략별 신호 생성
                if strategy_id == 'ema_cross':
                    signal = real_signals.generate_ema_cross_signal(strategy)
                elif strategy_id == 'rsi_divergence':
                    signal = real_signals.generate_rsi_divergence_signal(
                        strategy)
                elif strategy_id == 'vwap_pullback':
                    signal = real_signals.generate_vwap_pullback_signal(
                        strategy)
                elif strategy_id == 'macd_zero_cross':
                    signal = real_signals.generate_macd_zero_cross_signal(
                        strategy)
                elif strategy_id == 'bollinger_band_strategy':
                    signal = real_signals.generate_bollinger_band_signal(
                        strategy)
                elif strategy_id == 'pivot_points':
                    signal = real_signals.generate_pivot_points_signal(
                        strategy)
                elif strategy_id == 'open_interest':
                    signal = real_signals.generate_open_interest_signal(
                        strategy)
                elif strategy_id == 'flag_pennant':
                    signal = real_signals.generate_flag_pennant_signal(
                        strategy)
                else:
                    # 아직 구현되지 않은 전략들은 기본 홀드 신호
                    signal = real_signals._create_hold_signal(
                        strategy_id, f"{strategy_id} 전략 구현 예정")

                if signal:
                    strategy_signals[strategy_id] = signal

                    result['individual_signals'].append({
                        'strategy_id': strategy_id,
                        'strategy_name': strategy.get('name', strategy_id),
                        'action': signal.action,
                        'confidence': round(signal.confidence, 3),
                        'reasoning': signal.reasoning,
                        'suggested_amount': signal.suggested_amount,
                        'price': signal.price
                    })

            except Exception as e:
                logger.error(f"전략 {strategy_id} 신호 생성 오류: {e}")
                # 오류 발생 시 홀드 신호 생성
                signal = real_signals._create_hold_signal(
                    strategy_id, f"오류: {str(e)}")
                strategy_signals[strategy_id] = signal

                result['individual_signals'].append({
                    'strategy_id': strategy_id,
                    'strategy_name': strategy.get('name', strategy_id),
                    'action': signal.action,
                    'confidence': round(signal.confidence, 3),
                    'reasoning': signal.reasoning,
                    'suggested_amount': signal.suggested_amount,
                    'price': signal.price
                })

        # 개별 신호를 데이터베이스에 저장
        for signal_data in result['individual_signals']:
            try:
                signal_recorder.record_signal({
                    'strategy_id': signal_data['strategy_id'],
                    'action': signal_data['action'],
                    'confidence': signal_data['confidence'],
                    'price': signal_data['price'],
                    'suggested_amount': signal_data['suggested_amount'],
                    'reasoning': signal_data['reasoning'],
                    'market_data': {
                        'price': market_data.price,
                        'volume': market_data.volume,
                        'high': market_data.high,
                        'low': market_data.low
                    }
                }, executed=False)  # 분석만 하고 실행하지 않음
            except Exception as e:
                logger.error(f"신호 저장 오류: {e}")

        # 통합 신호 생성 (개선된 알고리즘)
        if strategy_signals:
            buy_signals = [s for s in strategy_signals.values()
                           if s.action == 'buy']
            sell_signals = [s for s in strategy_signals.values()
                            if s.action == 'sell']
            hold_signals = [s for s in strategy_signals.values()
                            if s.action == 'hold']

            # 개선된 점수 계산: 해당 신호의 평균 신뢰도 사용
            buy_score = (sum(s.confidence for s in buy_signals) /
                         len(buy_signals)) if buy_signals else 0
            sell_score = (sum(s.confidence for s in sell_signals) /
                          len(sell_signals)) if sell_signals else 0
            hold_score = (sum(s.confidence for s in hold_signals) /
                          len(hold_signals)) if hold_signals else 0

            # 신호 개수 가중치 (더 많은 전략이 동의할수록 가중치 증가)
            buy_weight = len(buy_signals) / len(strategy_signals)
            sell_weight = len(sell_signals) / len(strategy_signals)
            hold_weight = len(hold_signals) / len(strategy_signals)

            # 최종 점수 = 신뢰도 * 신호 비율
            final_buy_score = buy_score * buy_weight
            final_sell_score = sell_score * sell_weight
            final_hold_score = hold_score * hold_weight

            # 결정 로직 (임계값 낮춤: 0.25)
            min_threshold = 0.25

            if final_buy_score > final_sell_score and final_buy_score > final_hold_score and final_buy_score > min_threshold:
                consolidated_action = 'buy'
                consolidated_confidence = final_buy_score
                contributing_strategies = [s.strategy_id for s in buy_signals]
                reasoning = f"매수 신호 우세 (신뢰도:{buy_score:.2f}, 비율:{buy_weight:.2f}, 최종점수:{final_buy_score:.2f})"
            elif final_sell_score > final_buy_score and final_sell_score > final_hold_score and final_sell_score > min_threshold:
                consolidated_action = 'sell'
                consolidated_confidence = final_sell_score
                contributing_strategies = [s.strategy_id for s in sell_signals]
                reasoning = f"매도 신호 우세 (신뢰도:{sell_score:.2f}, 비율:{sell_weight:.2f}, 최종점수:{final_sell_score:.2f})"
            else:
                consolidated_action = 'hold'
                consolidated_confidence = max(
                    final_buy_score, final_sell_score, final_hold_score)
                contributing_strategies = list(strategy_signals.keys())
                reasoning = f"신호 혼재 또는 약함 (매수:{final_buy_score:.2f}, 매도:{final_sell_score:.2f}, 홀드:{final_hold_score:.2f})"

            # 거래 설정 사용을 위해 트레이딩 설정 로드
            trading_config = config_manager.get_config('trading') or {}

            result['consolidated_signal'] = {
                'action': consolidated_action,
                'confidence': round(consolidated_confidence, 3),
                'suggested_amount': int(trading_config.get('max_trade_amount', 100000) * 0.7) if consolidated_action == 'buy' else 0,
                'reasoning': reasoning,
                'contributing_strategies': contributing_strategies,
                'market_condition': 'trending_up' if market_data.price > market_data.prev_close else 'trending_down',
                'buy_count': len(buy_signals),
                'sell_count': len(sell_signals),
                'hold_count': len(hold_signals),
                'buy_avg_confidence': round(buy_score, 3),
                'sell_avg_confidence': round(sell_score, 3),
                'hold_avg_confidence': round(hold_score, 3),
                'final_buy_score': round(final_buy_score, 3),
                'final_sell_score': round(final_sell_score, 3),
                'final_hold_score': round(final_hold_score, 3)
            }

            # 통합 신호도 데이터베이스에 저장
            try:
                signal_recorder.record_consolidated_signal({
                    'action': consolidated_action,
                    'confidence': consolidated_confidence,
                    'suggested_amount': int(trading_config.get('max_trade_amount', 100000) * 0.7) if consolidated_action == 'buy' else 0,
                    'reasoning': reasoning,
                    'contributing_strategies': contributing_strategies,
                    'market_condition': 'trending_up' if market_data.price > market_data.prev_close else 'trending_down',
                    'signal_distribution': {
                        'buy_count': len(buy_signals),
                        'sell_count': len(sell_signals),
                        'hold_count': len(hold_signals)
                    }
                }, executed=False)
            except Exception as e:
                logger.error(f"통합 신호 저장 오류: {e}")

        # 분석 세션 기록
        try:
            session_id = signal_recorder.record_analysis_session({
                'auto_trade_enabled': config_manager.is_trading_enabled(),
                'strategies_analyzed': len(active_strategies),
                'signals_generated': len(strategy_signals),
                'decision': consolidated_action if 'consolidated_action' in locals() else 'hold',
                'metadata': {
                    'api_status': api_status,
                    'market_price': market_data.price,
                    'timestamp': datetime.now().isoformat()
                }
            })
            logger.info(f"분석 세션 기록 완료: ID={session_id}")
        except Exception as e:
            logger.error(f"분석 세션 기록 오류: {e}")

        logger.info(f"수동 전략 분석 완료: {len(strategy_signals)}개 전략 분석")
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.error(f"수동 전략 분석 오류: {e}")
        log_error(e, {
            'endpoint': '/api/manual_trading/analyze',
            'user_action': 'manual_trading_analyze',
            'active_strategies_count': len(active_strategies) if 'active_strategies' in locals() else 0
        }, 'WebApp')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/signal_history')
def api_signal_history():
    """신호 히스토리 조회"""
    try:
        strategy_id = request.args.get('strategy_id')
        days = request.args.get('days', 7, type=int)

        history = signal_recorder.get_signal_history(strategy_id, days)
        performance = signal_recorder.analyze_signal_performance(days)

        return jsonify({
            'success': True,
            'history': history,
            'performance': performance
        })
    except Exception as e:
        logger.error(f"신호 히스토리 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/strategy_accuracy/<strategy_id>')
def api_strategy_accuracy(strategy_id):
    """전략 정확도 조회"""
    try:
        days = request.args.get('days', 30, type=int)
        accuracy = signal_recorder.get_strategy_accuracy(strategy_id, days)

        return jsonify({
            'success': True,
            'strategy_id': strategy_id,
            'accuracy': accuracy
        })
    except Exception as e:
        logger.error(f"전략 정확도 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/manual_trading/execute', methods=['POST'])
def api_manual_execute():
    """수동 매매 실행 (락 체크 포함)"""
    try:
        from core.trading_engine import TradingEngine
        from core.result_manager import result_manager

        data = request.json
        action = data.get('action')  # 'buy', 'sell', 'analyze_and_execute'

        if not action:
            return jsonify({'success': False, 'message': '액션이 지정되지 않았습니다.'}), 400

        # 자동 거래가 실행 중인지 확인
        if result_manager.is_trading_locked():
            return jsonify({
                'success': False,
                'message': '자동 거래가 실행 중입니다. 잠시 후 다시 시도하세요.'
            }), 400

        # 수동 거래를 위한 락 획득
        if not result_manager.acquire_trading_lock(timeout=5):
            return jsonify({
                'success': False,
                'message': '거래 락을 획득할 수 없습니다. 다른 거래가 진행 중입니다.'
            }), 400

        engine = TradingEngine()

        if action == 'analyze_and_execute':
            # 다층 전략 시스템 사용하여 분석 실행
            from core.multi_tier_strategy_engine import multi_tier_engine

            multi_tier_decision = multi_tier_engine.analyze()

            # 다층 결정을 ConsolidatedSignal로 변환
            consolidated_signal = engine._convert_multitier_to_consolidated(
                multi_tier_decision)

            # 전략별 신호 상세 정보 수집 (다층 전략 결과)
            strategy_details = []

            # 다층 전략 시스템의 계층별 기여도 정보 사용
            for tier, contribution in multi_tier_decision.tier_contributions.items():
                strategy_details.append({
                    'strategy_id': f"{tier.value}_layer",
                    'action': multi_tier_decision.final_action,
                    'confidence': round(contribution, 3),
                    'reasoning': f"{tier.value} 계층 기여도: {contribution:.1%}",
                    'price': 0,  # 다층 전략에서는 별도 가격 없음
                    'suggested_amount': multi_tier_decision.suggested_amount if tier == max(multi_tier_decision.tier_contributions, key=multi_tier_decision.tier_contributions.get) else 0
                })

            # 통합 결정 정보도 추가
            strategy_details.append({
                'strategy_id': 'integrated_decision',
                'action': multi_tier_decision.final_action,
                'confidence': round(multi_tier_decision.confidence, 3),
                'reasoning': multi_tier_decision.reasoning[:100] + ('...' if len(multi_tier_decision.reasoning) > 100 else ''),
                'price': 0,
                'suggested_amount': multi_tier_decision.suggested_amount
            })

            # 실행 결과와 분석 정보
            analysis_data = {
                'strategy_count': len(strategy_details),
                'strategy_details': strategy_details,
                'consolidated_action': consolidated_signal.action if consolidated_signal else 'hold',
                'consolidated_confidence': round(consolidated_signal.confidence, 3) if consolidated_signal else 0,
                'consolidated_reasoning': consolidated_signal.reasoning if consolidated_signal else '신호 없음'
            }

            if consolidated_signal and consolidated_signal.action != 'hold':
                engine._process_consolidated_signal(consolidated_signal)
                message = f"분석 후 {consolidated_signal.action} 실행 완료 (신뢰도: {consolidated_signal.confidence:.2f})"
                analysis_data['executed'] = True
            else:
                message = "분석 결과 홀드 신호 - 거래 실행하지 않음"
                analysis_data['executed'] = False

            # 추가 데이터를 응답에 포함
            return jsonify({
                'success': True,
                'message': message,
                'analysis': analysis_data
            })

        elif action == 'buy':
            # 강제 매수
            from core.upbit_api import UpbitAPI
            api = UpbitAPI()  # 실거래 모드
            current_price = api.get_current_price("KRW-BTC")
            amount = data.get('amount', 10000)  # 기본 1만원

            result = api.place_buy_order(
                "KRW-BTC", current_price, amount=amount)
            
            if result.success:
                message = f"수동 매수 성공: 주문 ID {result.order_id}"
            else:
                message = f"수동 매수 실패: {result.message}"
            # 거래 기록 (성공/실패 모두 기록하여 추적)
            try:
                trade_data = {
                    'strategy_id': 'manual',
                    'order_id': result.order_id if hasattr(result, 'order_id') else None,
                    'symbol': 'KRW-BTC',
                    'side': 'buy',
                    'entry_time': datetime.now(),
                    'entry_price': current_price,
                    'quantity': (amount / current_price) if amount and current_price else 0,
                    'amount': amount,
                    'fees': 0,
                    'pnl': None,
                    'status': 'open' if result.success else 'failed',
                    'reasoning': f'manual buy via web api - {result.message}'
                }
                logger.info(f"거래 기록 시도: {trade_data}")
                trade_id = db.insert_trade(trade_data)
                logger.info(f"거래 기록 성공: ID {trade_id}")

                # 통계 즉시 업데이트를 위한 로그
                db.insert_log('INFO', 'ManualTrading',
                              f'수동 매수 DB 기록 완료', f'거래 ID: {trade_id}')

            except Exception as e:
                logger.error(f"수동 매수 DB 기록 실패: {e}")
                # 기록 실패도 로그에 남김
                db.insert_log('ERROR', 'ManualTrading',
                              f'수동 매수 DB 기록 실패', str(e))

        elif action == 'sell':
            # 강제 매도 (전량)
            from core.upbit_api import UpbitAPI
            api = UpbitAPI()  # 실거래 모드
            btc_balance = api.get_balance("BTC")
            current_price = api.get_current_price("KRW-BTC")

            if btc_balance > 0.0001:
                result = api.place_sell_order(
                    "KRW-BTC", current_price, btc_balance)
                
                if result.success:
                    message = f"수동 매도 성공: 주문 ID {result.order_id}"
                else:
                    message = f"수동 매도 실패: {result.message}"
                try:
                    trade_data = {
                        'strategy_id': 'manual',
                        'order_id': result.order_id if hasattr(result, 'order_id') else None,
                        'symbol': 'KRW-BTC',
                        'side': 'sell',
                        'entry_time': datetime.now(),
                        'entry_price': current_price,
                        'quantity': btc_balance,
                        'amount': current_price * btc_balance,
                        'fees': 0,
                        'pnl': None,
                        'status': 'closed' if result.success else 'failed',
                        'reasoning': f'manual sell via web api - {result.message}'
                    }
                    logger.info(f"매도 거래 기록 시도: {trade_data}")
                    trade_id = db.insert_trade(trade_data)
                    logger.info(f"매도 거래 기록 성공: ID {trade_id}")

                    # 통계 즉시 업데이트를 위한 로그
                    db.insert_log('INFO', 'ManualTrading',
                                  f'수동 매도 DB 기록 완료', f'거래 ID: {trade_id}')

                except Exception as e:
                    logger.error(f"수동 매도 DB 기록 실패: {e}")
                    # 기록 실패도 로그에 남김
                    db.insert_log('ERROR', 'ManualTrading',
                                  f'수동 매도 DB 기록 실패', str(e))
            else:
                message = "매도할 BTC 잔고가 부족합니다."
        else:
            return jsonify({'success': False, 'message': '지원하지 않는 액션입니다.'}), 400

        # 로그 기록
        db.insert_log('INFO', 'ManualTrading', f'수동 거래 실행: {action}', message)

        # 거래 로그 기록 (거래 액션인 경우만)
        if action in ['buy', 'sell'] and 'result' in locals() and hasattr(result, 'success'):
            log_trade(
                action=action,
                symbol="KRW-BTC",
                amount=data.get(
                    'amount', 0) if action == 'buy' else btc_balance if action == 'sell' else 0,
                price=current_price if 'current_price' in locals() else 0,
                strategy="manual",
                success=result.success,
                message=message
            )

        logger.info(f"수동 거래 실행: {action} - {message}")

        # 락 해제
        result_manager.release_trading_lock()

        return jsonify({'success': True, 'message': message})

    except Exception as e:
        logger.error(f"수동 거래 실행 오류: {e}")

        # 오류 시에도 락 해제
        try:
            from core.result_manager import result_manager
            result_manager.release_trading_lock()
        except:
            pass

        log_error(e, {
            'endpoint': '/api/manual_trading/execute',
            'user_action': 'manual_trading_execute',
            'action': data.get('action') if 'data' in locals() else 'unknown'
        }, 'WebApp')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/trading_lock/status', methods=['GET'])
def api_trading_lock_status():
    """거래 락 상태 확인"""
    try:
        from core.result_manager import result_manager
        return jsonify({
            'success': True,
            'data': result_manager.get_lock_status()
        })
    except Exception as e:
        logger.error(f"거래 락 상태 확인 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/trading_lock/release', methods=['POST'])
def api_trading_lock_release():
    """거래 락 강제 해제"""
    try:
        from core.result_manager import result_manager
        result_manager.release_trading_lock()
        logger.info("거래 락 강제 해제됨")
        return jsonify({
            'success': True,
            'message': '거래 락이 해제되었습니다.'
        })
    except Exception as e:
        logger.error(f"거래 락 해제 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backtesting/run', methods=['POST'])
def api_run_backtesting():
    """백테스팅 실행"""
    try:
        from backtesting.backtester import Backtester
        from datetime import datetime, timedelta

        data = request.json
        # 'basic', 'optimization', 'comprehensive'
        mode = data.get('mode', 'basic')
        days = data.get('days', 30)

        logger.info(f"백테스팅 실행 요청: 모드={mode}, 기간={days}일")

        # 백테스트 실행
        backtester = Backtester(initial_capital=1000000)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 기본 백테스트 실행
        metrics = backtester.run_backtest(start_date, end_date)

        # 결과 저장
        output_file = backtester.save_results(metrics)

        # 응답 데이터 구성
        result = {
            'success': True,
            'mode': mode,
            'period_days': days,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'metrics': {
                'total_return': f"{metrics.total_return:.2%}",
                'annualized_return': f"{metrics.annualized_return:.2%}",
                'max_drawdown': f"{metrics.max_drawdown:.2%}",
                'sharpe_ratio': f"{metrics.sharpe_ratio:.2f}",
                'win_rate': f"{metrics.win_rate:.1%}",
                'total_trades': metrics.total_trades,
                'buy_and_hold_return': f"{metrics.buy_and_hold_return:.2%}",
                'alpha': f"{metrics.alpha:.2%}",
                'performance_grade': 'A' if metrics.total_return > 0.05 else 'B' if metrics.total_return > 0 else 'C'
            },
            'output_file': output_file,
            'execution_time': datetime.now().isoformat()
        }

        logger.info(f"백테스팅 완료: 수익률 {metrics.total_return:.2%}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"백테스팅 실행 오류: {e}")
        log_error(e, {
            'endpoint': '/api/backtesting/run',
            'user_action': 'backtesting_run',
            'mode': data.get('mode') if 'data' in locals() else 'unknown',
            'days': data.get('days') if 'data' in locals() else 0
        }, 'WebApp')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backtesting/history')
def api_backtesting_history():
    """백테스팅 결과 히스토리 조회"""
    try:
        import os
        import json
        from datetime import datetime

        results_dir = 'backtesting/results'
        if not os.path.exists(results_dir):
            return jsonify({'results': []})

        history = []
        for filename in os.listdir(results_dir):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(results_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    metrics = data.get('metrics', {})
                    history.append({
                        'filename': filename,
                        'date': filename.split('_')[1] + '_' + filename.split('_')[2].replace('.json', ''),
                        'total_return': metrics.get('total_return', 0),
                        'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                        'max_drawdown': metrics.get('max_drawdown', 0),
                        'total_trades': metrics.get('total_trades', 0),
                        'filepath': filepath
                    })
                except Exception as e:
                    logger.warning(f"백테스팅 히스토리 파일 {filename} 로드 실패: {e}")

        # 날짜순 정렬 (최신순)
        history.sort(key=lambda x: x['date'], reverse=True)

        return jsonify({'results': history[:10]})  # 최근 10개만 반환

    except Exception as e:
        logger.error(f"백테스팅 히스토리 조회 오류: {e}")
        return jsonify({'results': []}), 500


@app.route('/api/strategy/<strategy_id>/details', methods=['GET'])
def api_strategy_details(strategy_id):
    """전략별 세부 정보 조회"""
    try:
        from core.upbit_api import UpbitAPI
        from core.real_strategy_signals import RealStrategySignals
        from core.technical_indicators import TechnicalIndicators

        # API 인스턴스 생성
        api = UpbitAPI()
        real_signals = RealStrategySignals(api)
        indicators = TechnicalIndicators()

        # 전략별 세부 데이터 수집
        details = {}

        if strategy_id == 'ema_cross':
            # EMA 크로스 전략 세부 정보
            candles = real_signals._get_candles_cached("minutes", 60, 150)
            if candles and len(candles) >= 50:
                ema12 = indicators.calculate_ema(candles, 12)
                ema26 = indicators.calculate_ema(candles, 26)

                if ema12 and ema26:
                    details = {
                        'strategy_name': 'EMA 골든/데드크로스',
                        'description': '12일 EMA와 26일 EMA의 교차점을 이용한 매매 신호',
                        'current_values': {
                            'EMA12': round(ema12[-1], 0),
                            'EMA26': round(ema26[-1], 0),
                            'current_price': round(float(candles[-1]['trade_price']), 0),
                            'cross_difference': round(ema12[-1] - ema26[-1], 0),
                            'prev_cross_difference': round(ema12[-2] - ema26[-2], 0) if len(ema12) >= 2 else 0
                        },
                        'calculation_method': {
                            'EMA12': 'EMA(12) = 이전EMA × (1-2/13) + 현재가 × (2/13)',
                            'EMA26': 'EMA(26) = 이전EMA × (1-2/27) + 현재가 × (2/27)',
                            'signal_logic': '골든크로스: EMA12 > EMA26 (매수), 데드크로스: EMA12 < EMA26 (매도)'
                        },
                        'additional_filters': {
                            'trend_filter': '4시간 EMA50 위/아래 확인',
                            'volume_filter': '최근 10개 봉 평균 거래량 대비 1.5배 이상'
                        }
                    }

        elif strategy_id == 'rsi_divergence':
            # RSI 다이버전스 전략
            candles = real_signals._get_candles_cached("minutes", 60, 100)
            if candles and len(candles) >= 50:
                rsi_values = indicators.calculate_rsi(candles, 14)
                sr_data = indicators.detect_support_resistance(candles)

                if rsi_values:
                    details = {
                        'strategy_name': 'RSI 다이버전스',
                        'description': 'RSI 과매수/과매도 구간에서 지지/저항선 확인 후 매매',
                        'current_values': {
                            'RSI': round(rsi_values[-1], 1),
                            'current_price': round(float(candles[-1]['trade_price']), 0),
                            'nearest_support': round(sr_data.get('nearest_support', 0), 0),
                            'nearest_resistance': round(sr_data.get('nearest_resistance', 0), 0),
                            'support_distance': round(abs(float(candles[-1]['trade_price']) - sr_data.get('nearest_support', 0)) / float(candles[-1]['trade_price']) * 100, 2) if sr_data.get('nearest_support') else 0,
                            'resistance_distance': round(abs(sr_data.get('nearest_resistance', 0) - float(candles[-1]['trade_price'])) / float(candles[-1]['trade_price']) * 100, 2) if sr_data.get('nearest_resistance') else 0
                        },
                        'calculation_method': {
                            'RSI': 'RSI = 100 - (100 / (1 + RS)), RS = 평균상승폭 / 평균하락폭',
                            'signal_logic': 'RSI < 30 + 지지선 근처 (매수), RSI > 70 + 저항선 근처 (매도)'
                        },
                        'thresholds': {
                            'oversold': 30,
                            'overbought': 70,
                            'support_resistance_distance': '2% 이내'
                        }
                    }

        elif strategy_id == 'vwap_pullback':
            # VWAP 되돌림 전략
            candles = real_signals._get_candles_cached("minutes", 15, 96)
            if candles and len(candles) >= 50:
                vwap = indicators.calculate_vwap(candles)
                current_price = float(candles[-1]['trade_price'])
                vwap_distance = (current_price - vwap) / vwap * 100

                details = {
                    'strategy_name': 'VWAP 되돌림',
                    'description': '가격이 VWAP 상/하단에서 중심선으로 되돌아오는 특성 이용',
                    'current_values': {
                        'VWAP': round(vwap, 0),
                        'current_price': round(current_price, 0),
                        'distance_from_vwap': round(vwap_distance, 2),
                        'distance_threshold': 0.2
                    },
                    'calculation_method': {
                        'VWAP': 'VWAP = Σ(Price × Volume) / Σ(Volume)',
                        'signal_logic': 'VWAP 하단(-0.2% 이하) 반등 매수, VWAP 상단(+0.2% 이상) 반발 매도'
                    },
                    'additional_filters': {
                        'trend_filter': '1시간 EMA20 기울기로 트렌드 확인',
                        'rsi_filter': '15분 RSI 50 이상/이하 확인'
                    }
                }

        elif strategy_id == 'macd_zero_cross':
            # MACD 제로크로스 전략
            candles = real_signals._get_candles_cached("minutes", 60, 100)
            if candles and len(candles) >= 60:
                macd_data = indicators.calculate_macd(candles, 12, 26, 9)
                if macd_data:
                    details = {
                        'strategy_name': 'MACD 제로크로스',
                        'description': 'MACD 히스토그램이 0선을 교차할 때의 매매 신호',
                        'current_values': {
                            'MACD': round(macd_data['macd'], 0),
                            'Signal': round(macd_data['signal'], 0),
                            'Histogram': round(macd_data['histogram'], 0),
                            'current_price': round(float(candles[-1]['trade_price']), 0)
                        },
                        'calculation_method': {
                            'MACD': 'MACD = EMA12 - EMA26',
                            'Signal': 'Signal = EMA(MACD, 9)',
                            'Histogram': 'Histogram = MACD - Signal',
                            'signal_logic': '히스토그램 > 0 상승 (매수), 히스토그램 < 0 하락 (매도)'
                        },
                        'additional_filters': {
                            'trend_filter': '1시간 EMA50 위/아래 확인',
                            'histogram_slope': '히스토그램 기울기 확인'
                        }
                    }

        elif strategy_id == 'bollinger_band_strategy':
            # 볼린저 밴드 전략
            candles = real_signals._get_candles_cached("minutes", 60, 80)
            if candles and len(candles) >= 50:
                bb_data = indicators.calculate_bollinger_bands(candles, 20, 2)
                if bb_data:
                    details = {
                        'strategy_name': '볼린저 밴드',
                        'description': '볼린저 밴드 상/하단에서의 반등/반발 매매',
                        'current_values': {
                            'upper_band': round(bb_data['upper'], 0),
                            'middle_band': round(bb_data['middle'], 0),
                            'lower_band': round(bb_data['lower'], 0),
                            'current_price': round(bb_data['current_price'], 0),
                            'position': bb_data['position'],
                            'bandwidth': round((bb_data['upper'] - bb_data['lower']) / bb_data['middle'] * 100, 2)
                        },
                        'calculation_method': {
                            'middle_band': 'Middle = SMA(20)',
                            'upper_band': 'Upper = Middle + (2 × StdDev)',
                            'lower_band': 'Lower = Middle - (2 × StdDev)',
                            'signal_logic': '하단 터치 반등 (매수), 상단 터치 반발 (매도)'
                        },
                        'additional_filters': {
                            'trend_filter': '가격 변동성으로 트렌딩/레인징 구분',
                            'rsi_filter': 'RSI 40 이하 (매수), RSI 60 이상 (매도)'
                        }
                    }

        elif strategy_id == 'pivot_points':
            # 피봇 포인트 전략
            daily_candles = real_signals._get_candles_cached("days", 1, 30)
            if daily_candles and len(daily_candles) >= 5:
                yesterday = daily_candles[-2]
                high = float(yesterday['high_price'])
                low = float(yesterday['low_price'])
                close = float(yesterday['trade_price'])

                pivot = (high + low + close) / 3
                r1 = 2 * pivot - low
                r2 = pivot + (high - low)
                s1 = 2 * pivot - high
                s2 = pivot - (high - low)

                current_price = float(daily_candles[-1]['trade_price'])

                details = {
                    'strategy_name': '피봇 포인트',
                    'description': '전일 고가/저가/종가를 이용한 지지/저항선 계산',
                    'current_values': {
                        'current_price': round(current_price, 0),
                        'pivot': round(pivot, 0),
                        'resistance1': round(r1, 0),
                        'resistance2': round(r2, 0),
                        'support1': round(s1, 0),
                        'support2': round(s2, 0),
                        'yesterday_high': round(high, 0),
                        'yesterday_low': round(low, 0),
                        'yesterday_close': round(close, 0)
                    },
                    'calculation_method': {
                        'pivot': 'PP = (H + L + C) / 3',
                        'resistance1': 'R1 = 2 × PP - L',
                        'resistance2': 'R2 = PP + (H - L)',
                        'support1': 'S1 = 2 × PP - H',
                        'support2': 'S2 = PP - (H - L)',
                        'signal_logic': '지지선 근처 반등 (매수), 저항선 근처 반발 (매도)'
                    },
                    'additional_filters': {
                        'pattern_filter': '15분봉 강세/약세 패턴 확인',
                        'distance_threshold': '0.5% 이내 근접'
                    }
                }

        elif strategy_id == 'open_interest':
            # 거래량 분석 전략
            candles = real_signals._get_candles_cached("minutes", 60, 50)
            if candles and len(candles) >= 20:
                volumes = [float(c['candle_acc_trade_volume'])
                           for c in candles]
                prices = [float(c['trade_price']) for c in candles]

                current_volume = volumes[-1]
                avg_volume_20 = sum(volumes[-20:]) / 20
                volume_ratio = current_volume / avg_volume_20

                price_change_1h = (
                    prices[-1] - prices[-2]) / prices[-2] * 100 if len(prices) >= 2 else 0
                price_change_4h = (
                    prices[-1] - prices[-5]) / prices[-5] * 100 if len(prices) >= 5 else 0

                details = {
                    'strategy_name': '거래량 분석',
                    'description': '가격 변동과 거래량 증감의 상관관계 분석',
                    'current_values': {
                        'current_volume': round(current_volume, 2),
                        'average_volume_20': round(avg_volume_20, 2),
                        'volume_ratio': round(volume_ratio, 2),
                        'price_change_1h': round(price_change_1h, 2),
                        'price_change_4h': round(price_change_4h, 2),
                        'current_price': round(prices[-1], 0)
                    },
                    'calculation_method': {
                        'volume_ratio': '현재거래량 / 20기간 평균거래량',
                        'price_change': '(현재가 - 과거가) / 과거가 × 100',
                        'signal_logic': '가격상승 + 거래량증가 (매수), 가격하락 + 거래량증가 (매도)'
                    },
                    'thresholds': {
                        'volume_surge': '1.5배 이상',
                        'price_change_1h': '±1% 이상',
                        'price_change_4h': '±2% 이상'
                    }
                }

        elif strategy_id == 'flag_pennant':
            # 깃발/페넌트 패턴 전략
            candles = real_signals._get_candles_cached("minutes", 60, 100)
            if candles and len(candles) >= 50:
                closes = [float(c['trade_price']) for c in candles]
                volumes = [float(c['candle_acc_trade_volume'])
                           for c in candles]

                # flagpole 검색
                flagpole_strength = 0
                flagpole_direction = None

                for i in range(-20, -5):
                    if i + 10 < len(closes):
                        price_move = (closes[i + 5] -
                                      closes[i]) / closes[i] * 100
                        if abs(price_move) > 5:
                            flagpole_strength = abs(price_move)
                            flagpole_direction = "상승" if price_move > 0 else "하락"
                            break

                # 횡보 구간 분석
                recent_highs = [float(c['high_price']) for c in candles[-10:]]
                recent_lows = [float(c['low_price']) for c in candles[-10:]]
                consolidation_range = (
                    max(recent_highs) - min(recent_lows)) / closes[-1] * 100

                details = {
                    'strategy_name': '깃발/페넌트 패턴',
                    'description': '급격한 가격 변동(flagpole) 후 횡보 구간 돌파 매매',
                    'current_values': {
                        'current_price': round(closes[-1], 0),
                        'flagpole_strength': round(flagpole_strength, 2),
                        'flagpole_direction': flagpole_direction or "없음",
                        'consolidation_range': round(consolidation_range, 2),
                        'resistance_level': round(max(recent_highs), 0),
                        'support_level': round(min(recent_lows), 0),
                        'current_volume': round(volumes[-1], 2),
                        'volume_ratio': round(volumes[-1] / (sum(volumes[-20:-10]) / 10), 2) if sum(volumes[-20:-10]) > 0 else 1
                    },
                    'calculation_method': {
                        'flagpole_detection': '20~5봉 전 구간에서 5% 이상 가격 변동 검색',
                        'consolidation': '최근 10봉 고가-저가 범위 / 현재가 × 100',
                        'signal_logic': '저항선 돌파 + 거래량 증가 (매수), 지지선 이탈 + 거래량 증가 (매도)'
                    },
                    'thresholds': {
                        'flagpole_minimum': '5% 이상',
                        'consolidation_maximum': '3% 이내',
                        'volume_surge': '1.5배 이상',
                        'breakout_threshold': '±0.2%'
                    }
                }

        if not details:
            return jsonify({'error': '해당 전략을 찾을 수 없습니다.'}), 404

        return jsonify({'success': True, 'details': details})

    except Exception as e:
        logger.error(f"전략 세부 정보 조회 오류: {e}")
        log_error(e, {
            'endpoint': '/api/strategy/<strategy_id>/details',
            'strategy_id': strategy_id
        }, 'WebApp')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/strategy/execution_history')
def api_strategy_execution_history():
    """전략 실행 이력 API"""
    try:
        # 파라미터 가져오기
        strategy_tier = request.args.get('tier', None)
        strategy_id = request.args.get('id', None)
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 100))

        # 실행 이력 조회
        history = execution_tracker.get_execution_history(
            strategy_tier=strategy_tier,
            strategy_id=strategy_id,
            hours=hours,
            limit=limit
        )

        return jsonify({
            'success': True,
            'data': history,
            'count': len(history),
            'filters': {
                'tier': strategy_tier,
                'id': strategy_id,
                'hours': hours,
                'limit': limit
            }
        })

    except Exception as e:
        logger.error(f"전략 실행 이력 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/strategy/performance')
def api_strategy_performance():
    """전략 성과 API"""
    try:
        # 파라미터 가져오기
        strategy_tier = request.args.get('tier', None)
        strategy_id = request.args.get('id', None)
        days = int(request.args.get('days', 30))

        # 성과 데이터 조회
        performance = execution_tracker.get_strategy_performance(
            strategy_tier=strategy_tier,
            strategy_id=strategy_id,
            days=days
        )

        return jsonify({
            'success': True,
            'data': performance,
            'count': len(performance),
            'filters': {
                'tier': strategy_tier,
                'id': strategy_id,
                'days': days
            }
        })

    except Exception as e:
        logger.error(f"전략 성과 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/strategy/summary')
def api_strategy_summary():
    """전략 요약 통계 API"""
    try:
        # 파라미터 가져오기
        days = int(request.args.get('days', 7))

        # 요약 통계 조회
        summary = execution_tracker.get_strategy_summary(days=days)

        return jsonify({
            'success': True,
            'data': summary,
            'period_days': days
        })

    except Exception as e:
        logger.error(f"전략 요약 통계 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/current')
def api_config_current():
    """현재 설정 조회 API"""
    try:
        # 전체 설정 불러오기
        current_config = {
            'strategies': {
                'tier_weights': config_manager.get_config('strategies.tier_weights') or {
                    'scalping': 0.4,
                    'trend': 0.35,
                    'macro': 0.25
                },
                'scalping_strategies': config_manager.get_config('strategies.scalping_strategies') or {},
                'trend_strategies': config_manager.get_config('strategies.trend_strategies') or {},
                'macro_strategies': config_manager.get_config('strategies.macro_strategies') or {}
            },
            'trading': {
                'trade_interval_minutes': config_manager.get_config('trading.trade_interval_minutes') or 10
            }
        }

        return jsonify({
            'success': True,
            'config': current_config
        })

    except Exception as e:
        logger.error(f"현재 설정 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/update', methods=['PUT'])
def api_config_update():
    """설정 업데이트 API"""
    try:
        new_config = request.get_json()

        if not new_config:
            return jsonify({
                'success': False,
                'error': '설정 데이터가 없습니다.'
            }), 400

        # 설정 검증
        validation_result = validate_strategy_config(new_config)
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'error': f"설정 검증 실패: {validation_result['errors']}"
            }), 400

        # 설정 업데이트
        updated_keys = []

        if 'strategies' in new_config:
            strategies = new_config['strategies']

            # 계층별 가중치 업데이트
            if 'tier_weights' in strategies:
                config_manager.set_config(
                    'strategies.tier_weights', strategies['tier_weights'])
                updated_keys.append('strategies.tier_weights')

            # 스캘핑 전략 업데이트
            if 'scalping_strategies' in strategies:
                config_manager.set_config(
                    'strategies.scalping_strategies', strategies['scalping_strategies'])
                updated_keys.append('strategies.scalping_strategies')

            # 트렌드 전략 업데이트
            if 'trend_strategies' in strategies:
                config_manager.set_config(
                    'strategies.trend_strategies', strategies['trend_strategies'])
                updated_keys.append('strategies.trend_strategies')

            # 매크로 전략 업데이트
            if 'macro_strategies' in strategies:
                config_manager.set_config(
                    'strategies.macro_strategies', strategies['macro_strategies'])
                updated_keys.append('strategies.macro_strategies')

        # 거래 설정 업데이트
        if 'trading' in new_config and 'trade_interval_minutes' in new_config['trading']:
            config_manager.set_config(
                'trading.trade_interval_minutes', new_config['trading']['trade_interval_minutes'])
            updated_keys.append('trading.trade_interval_minutes')

        logger.info(f"설정 업데이트 완료: {updated_keys}")

        return jsonify({
            'success': True,
            'message': '설정이 성공적으로 업데이트되었습니다.',
            'updated_keys': updated_keys
        })

    except Exception as e:
        logger.error(f"설정 업데이트 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/strategy/preview', methods=['POST'])
def api_strategy_preview():
    """전략 미리보기 API (임시 설정으로 테스트)"""
    try:
        test_config = request.get_json()

        if not test_config:
            return jsonify({
                'success': False,
                'error': '테스트 설정이 없습니다.'
            }), 400

        # 임시로 다층 전략 엔진에 테스트 설정 적용하여 분석 실행
        # 실제 설정은 변경하지 않고 메모리상에서만 테스트
        from core.multi_tier_strategy_engine import MultiTierStrategyEngine

        # 임시 엔진 생성 (실제 config는 변경하지 않음)
        temp_engine = MultiTierStrategyEngine()

        # BTC-KRW 시장 데이터로 분석 수행
        analysis_result = temp_engine.analyze("KRW-BTC")

        return jsonify({
            'success': True,
            'data': analysis_result
        })

    except Exception as e:
        logger.error(f"전략 미리보기 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def validate_strategy_config(config):
    """전략 설정 검증"""
    errors = []

    try:
        if 'strategies' in config:
            strategies = config['strategies']

            # 가중치 검증
            if 'tier_weights' in strategies:
                tier_weights = strategies['tier_weights']
                weight_sum = sum(tier_weights.values())
                if abs(weight_sum - 1.0) > 0.01:
                    errors.append(f"계층별 가중치 합계가 1.0이 아닙니다: {weight_sum:.3f}")

                for tier, weight in tier_weights.items():
                    if not (0 <= weight <= 1):
                        errors.append(f"가중치가 범위를 벗어났습니다 ({tier}: {weight})")

            # 스캘핑 전략 검증
            if 'scalping_strategies' in strategies:
                scalping = strategies['scalping_strategies']

                # RSI 파라미터 검증
                if 'rsi_momentum' in scalping:
                    rsi = scalping['rsi_momentum']
                    if 'rsi_period' in rsi and not (5 <= rsi['rsi_period'] <= 50):
                        errors.append("RSI 기간이 유효 범위(5-50)를 벗어났습니다.")
                    if 'oversold' in rsi and not (10 <= rsi['oversold'] <= 40):
                        errors.append("RSI 과매도 임계값이 유효 범위(10-40)를 벗어났습니다.")
                    if 'overbought' in rsi and not (60 <= rsi['overbought'] <= 90):
                        errors.append("RSI 과매수 임계값이 유효 범위(60-90)를 벗어났습니다.")

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    except Exception as e:
        return {
            'valid': False,
            'errors': [f"설정 검증 중 오류: {str(e)}"]
        }


@app.route('/api/debug/config_sync', methods=['GET'])
def api_debug_config_sync():
    """ConfigManager 동기화 상태 디버깅"""
    import os
    try:
        # 메모리 상태
        memory_auto_trade = config_manager.get_config(
            'trading.auto_trade_enabled')
        memory_system = config_manager.get_config('system.enabled')

        # 파일 직접 읽기
        config_file_path = config_manager.config_file
        file_exists = os.path.exists(config_file_path)

        file_auto_trade = None
        file_system = None
        file_last_modified = None
        file_error = None

        if file_exists:
            try:
                import json
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                file_auto_trade = file_data.get(
                    'trading', {}).get('auto_trade_enabled')
                file_system = file_data.get('system', {}).get('enabled')
                file_last_modified = os.path.getmtime(config_file_path)
            except Exception as e:
                file_error = str(e)

        # ConfigManager 내부 상태
        cm_last_modified = config_manager.last_modified

        return jsonify({
            'success': True,
            'debug_info': {
                'memory_state': {
                    'auto_trade_enabled': memory_auto_trade,
                    'system_enabled': memory_system
                },
                'file_state': {
                    'exists': file_exists,
                    'auto_trade_enabled': file_auto_trade,
                    'system_enabled': file_system,
                    'last_modified': file_last_modified,
                    'error': file_error
                },
                'config_manager': {
                    'last_modified': cm_last_modified,
                    'config_file_path': str(config_file_path)
                },
                'sync_status': {
                    'auto_trade_synced': memory_auto_trade == file_auto_trade,
                    'system_synced': memory_system == file_system
                }
            }
        })
    except Exception as e:
        logger.error(f"설정 동기화 디버깅 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


if __name__ == '__main__':
    # 템플릿 디렉토리 생성
    os.makedirs('web/templates', exist_ok=True)
    os.makedirs('web/static', exist_ok=True)

    # 시스템이 활성화되어 있으면 자동 거래 스케줄러 시작
    if config_manager.is_system_enabled():
        start_auto_trading()
        logger.info("자동 거래 스케줄러가 시작되었습니다")

    port = int(os.getenv('FLASK_PORT', 5000))
    print("=== Bitcoin Auto Trading 관리자 패널 ===")
    print("웹 서버 시작 중...")
    print(f"접속 주소: http://localhost:{port}")

    app.run(host='0.0.0.0', port=port, debug=True)
