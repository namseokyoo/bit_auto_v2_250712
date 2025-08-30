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
        kst = pytz.timezone('Asia/Seoul')
        current_time_kst = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S KST')

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

        # 대시보드 데이터
        dashboard_data = db.get_dashboard_data()

        # 현재 잔고 (실거래) - .env 파일에서 API 키 로드
        try:
            # 모드 확인
            mode = config_manager.get_config('system.mode')
            is_paper_trading = (mode == 'paper_trading')

            # API 초기화 (.env 파일의 키 자동 사용)
            api = UpbitAPI(paper_trading=is_paper_trading)

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

        return render_template('dashboard.html',
                               system_status=system_status,
                               dashboard_data=dashboard_data,
                               balances=balances,
                               current_price=current_price)
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

# API 엔드포인트들


@app.route('/api/system/status')
def api_system_status():
    """시스템 상태 API"""
    # 최신 상태 즉시 반영
    return jsonify({
        'system_enabled': config_manager.is_system_enabled(),
        'trading_enabled': config_manager.is_trading_enabled(),
        'mode': config_manager.get_config('system.mode'),
        'last_updated': datetime.now().isoformat()
    })


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
            # 자동 거래 스케줄러가 실행 중이 아니면 시작
            if not auto_trader.running:
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
        config_manager.emergency_stop()

        # 긴급 정지 로그
        db.insert_log('CRITICAL', 'WebInterface', '긴급 정지 실행됨',
                      '사용자에 의한 긴급 정지')

        return jsonify({'success': True, 'message': '긴급 정지가 실행되었습니다.'})
    except Exception as e:
        logger.error(f"긴급 정지 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


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
            'last_started_at': status.get('last_started_at'),
            'success_rate': status.get('success_rate', 0),
            'total_executions': status.get('total_executions', 0),
            'mode': config_manager.get_config('system.mode'),
            'last_updated': datetime.now().isoformat()
        }

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


@app.route('/api/balance')
def api_balance():
    """잔고 조회 API"""
    try:
        api = UpbitAPI(paper_trading=False)
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
        return jsonify(db.get_dashboard_data())
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
        api = UpbitAPI(paper_trading=False)

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
            # 전략 분석 후 자동 실행
            strategy_signals = engine._collect_all_signals('hourly')
            consolidated_signal = engine._consolidate_signals(strategy_signals)

            if consolidated_signal and consolidated_signal.action != 'hold':
                engine._process_consolidated_signal(consolidated_signal)
                message = f"분석 후 {consolidated_signal.action} 실행 완료 (신뢰도: {consolidated_signal.confidence:.2f})"
            else:
                message = "분석 결과 홀드 신호 - 거래 실행하지 않음"

        elif action == 'buy':
            # 강제 매수
            from core.upbit_api import UpbitAPI
            api = UpbitAPI(paper_trading=False)
            current_price = api.get_current_price("KRW-BTC")
            amount = data.get('amount', 50000)  # 기본 5만원

            result = api.place_buy_order(
                "KRW-BTC", current_price, amount=amount)
            message = f"수동 매수 {'성공' if result.success else '실패'}: {result.message}"
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
            api = UpbitAPI(paper_trading=False)
            btc_balance = api.get_balance("BTC")
            current_price = api.get_current_price("KRW-BTC")

            if btc_balance > 0.0001:
                result = api.place_sell_order(
                    "KRW-BTC", current_price, btc_balance)
                message = f"수동 매도 {'성공' if result.success else '실패'}: {result.message}"
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
        api = UpbitAPI(paper_trading=False)
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
