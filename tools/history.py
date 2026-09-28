"""Fetch bounded, paginated, gap-checked public Bybit spot OHLCV history."""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from tools.market import bounded_request, candles, failure_detail


def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Date/time must include timezone, e.g. 2026-09-01T00:00:00Z')
    return int(dt.timestamp()*1000)


def historical_rows(rows, interval, start, end):
    duration = interval*60000
    if start % duration or end % duration or end <= start:
        raise ValueError('History boundaries must align to the candle interval')
    if len(rows) != (end-start)//duration:
        raise ValueError('Incomplete history: candle count does not cover the requested range')
    clean = candles(rows, interval, end)
    if clean[0][0] != start or clean[-1][0]+duration != end:
        raise ValueError('History boundaries do not match the requested range')
    return clean


def fetch_interval(interval, start, end, max_pages=100, fetch=bounded_request, pause=time.sleep):
    cursor, rows, pages = end-1, {}, []
    for _ in range(max_pages):
        params = {'category':'spot','symbol':'BTCUSDT','interval':str(interval),
                  'start':start,'end':cursor,'limit':1000}
        page = fetch('/v5/market/kline', params)
        result = page['response']['result']
        if result.get('category') != 'spot' or result.get('symbol') != 'BTCUSDT':
            raise ValueError('Historical response has the wrong market')
        batch = result['list']
        if not batch or len(batch)>1000:
            raise ValueError('Empty or oversized historical page')
        seen = set()
        for row in batch:
            t = int(row[0])
            if t in seen or not start <= t <= cursor or t in rows:
                raise ValueError('Duplicate or out-of-range historical candle')
            seen.add(t); rows[t] = row
        pages.append({k:page[k] for k in ('url','received_at','sha256')})
        oldest = min(seen)
        if oldest == start:
            return historical_rows(list(rows.values()), interval, start, end), pages
        if oldest > cursor:
            raise ValueError('Historical pagination made no progress')
        cursor = oldest-1
        pause(.25)
    raise ValueError('Historical page limit reached; request a shorter range')


def download(start, end, interval=1, fetch=bounded_request):
    if interval not in (1,60) or start % 14400000 or end % 14400000:
        raise ValueError('Use interval 1 or 60 and UTC 4-hour-aligned start/end boundaries')
    if end <= start or end > int(time.time()*1000):
        raise ValueError('Require a completed historical interval')
    # Bound request volume and memory. Longer studies combine reviewed chronological chunks.
    if (end-start)//(interval*60000) > 90000:
        raise ValueError('At most 90,000 execution bars per file; shorten the range')
    warmup = start-800*3600000
    if warmup < 0:
        raise ValueError('Invalid history start')
    h1, p1 = fetch_interval(60,warmup,end,fetch=fetch)
    h4, p4 = fetch_interval(240,warmup,end,fetch=fetch)
    execution, pe = fetch_interval(interval,start,end,fetch=fetch)
    return {'schema_version':2,'kind':'bybit_spot_ohlcv','category':'spot','symbol':'BTCUSDT',
            'evaluation_start_ms':start,'evaluation_end_ms':end,'warmup_start_ms':warmup,
            'execution_interval_minutes':interval,'h1':h1,'h4':h4,'execution':execution,
            'collected_at':datetime.now(timezone.utc).isoformat(),'pages':{'h1':p1,'h4':p4,'execution':pe},
            'live_eligible':False,'limitations':['OHLCV is not historical bid/ask or order-book data.',
            'Historical instrument rules/fees must be supplied separately; current rules are not historical evidence.']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',required=True)
    parser.add_argument('--end',required=True)
    parser.add_argument('--execution-interval',type=int,choices=[1,60],default=1)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.out.exists(): raise ValueError('Output exists; choose a new filename')
        data=download(timestamp(args.start),timestamp(args.end),args.execution_interval)
        encoded=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
        with args.out.open('xb') as f: f.write(encoded)
        print(json.dumps({'saved':str(args.out),'sha256':hashlib.sha256(encoded).hexdigest(),
                          'execution_bars':len(data['execution']),'live_eligible':False}))
    except (ValueError,KeyError,TypeError,ArithmeticError,OSError,subprocess.TimeoutExpired) as exc:
        kind,message=failure_detail(exc)
        parser.exit(2,f'HISTORY UNAVAILABLE [{kind}]: {message}\n')
