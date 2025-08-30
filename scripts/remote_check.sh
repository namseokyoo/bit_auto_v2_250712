#!/usr/bin/env bash
set -euo pipefail

cd /opt/bitcoin_auto_trading || { echo "missing /opt/bitcoin_auto_trading"; exit 1; }

echo "=== HEALTH ==="
curl -sS --max-time 10 http://127.0.0.1:9000/health | cat || true

echo "\n=== STATUS ==="
curl -sS --max-time 10 http://127.0.0.1:9000/api/system/status | cat || true

echo "\n=== TRADES COUNT & LAST 3 ==="
python3 - <<'PY'
import sqlite3, os
path='data/trading_data.db'
print('db_path:', os.path.abspath(path))
conn=sqlite3.connect(path)
conn.row_factory=sqlite3.Row
cur=conn.cursor()
try:
  cur.execute('select count(*) from trades')
  print('trades:', cur.fetchone()[0])
  rows=conn.execute('select strategy_id, side, entry_time, amount, status from trades order by id desc limit 3').fetchall()
  print('last3:', [dict(r) for r in rows])
except Exception as e:
  print('error:', e)
finally:
  conn.close()
PY

echo "\n=== CONFIG KEYS ==="
python3 - <<'PY'
import json
from pathlib import Path
p=Path('config/trading_config.json')
if p.exists():
  cfg=json.loads(p.read_text())
  print({
    'system.enabled': cfg.get('system',{}).get('enabled'),
    'system.mode': cfg.get('system',{}).get('mode'),
    'trading.auto_trade_enabled': cfg.get('trading',{}).get('auto_trade_enabled')
  })
else:
  print('missing config/trading_config.json')
PY

echo "\n=== APP VERSION (GIT HEAD) ==="
if [ -d .git ]; then
  git rev-parse --short HEAD || true
else
  echo "no .git"
fi


