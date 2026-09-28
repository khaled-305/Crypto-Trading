"""Read-only Bybit spot collector. No credentials, SDK, redirects, or orders."""
import argparse
import hashlib
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tools.risk import positive, nonnegative

HOST = 'https://api.bybit.com'
PATHS = {'/v5/market/kline', '/v5/market/orderbook', '/v5/market/instruments-info'}
SYMBOLS = {'BTCUSDT', 'ETHUSDT'}


def failure_detail(exc):
    """Classify failures without printing remote bodies or local proxy credentials."""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 403:
            return 'access_denied', 'HTTP 403: exchange/network access denied; do not bypass it.'
        if exc.code == 429:
            return 'rate_limited', 'HTTP 429: stop requests and respect the exchange rate limit.'
        return 'http_error', f'HTTP {exc.code}: no data accepted.'
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, socket.gaierror):
        return 'dns', 'Name resolution failed for the approved API host.'
    if isinstance(reason, ssl.SSLError):
        return 'tls', 'TLS verification/handshake failed; do not disable certificate checks.'
    if isinstance(reason, (TimeoutError, subprocess.TimeoutExpired)):
        return 'timeout', 'Network deadline exceeded; DNS, connection, or response may be stalled.'
    if isinstance(reason, OSError):
        return 'connection', 'Connection failed before a valid response was received.'
    return 'invalid_data', str(exc)[:300]


def bounded_request(path, params):
    """Historical pagination uses one bounded child per request, including DNS."""
    child = subprocess.run([sys.executable, '-m', 'tools.market', '--request-worker',
                            json.dumps({'path': path, 'params': params})],
                           capture_output=True, text=True, timeout=15)
    if child.returncode:
        raise ValueError(child.stderr[:500].strip())
    return json.loads(child.stdout)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect refused; review destination before use')


def request(path, params):
    if path not in PATHS or params.get('category') != 'spot' or params.get('symbol') not in SYMBOLS:
        raise ValueError('Endpoint, category, or symbol outside reviewed scope')
    url = HOST + path + '?' + urllib.parse.urlencode(params)
    # Ignore environment proxy settings to avoid accidentally routing through an unreviewed proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(url, headers={'User-Agent': 'TradingResearch/1.0', 'Accept': 'application/json'})
    with opener.open(req, timeout=10) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Response exceeds size limit')
    obj = json.loads(raw)
    if obj.get('retCode') != 0:
        raise ValueError('Bybit returned an error; no usable data')
    age = int(time.time() * 1000) - int(obj['time'])
    if not -5000 <= age <= 60000:
        raise ValueError('Stale or future API response')
    result = obj['result']
    if path != '/v5/market/orderbook' and result.get('category') != 'spot':
        raise ValueError('Wrong market category')
    return {'url': url, 'received_at': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(raw).hexdigest(), 'response': obj}


def candles(rows, interval, asof):
    duration = interval * 60000
    clean = []
    seen = set()
    for row in rows:
        if len(row) != 7:
            raise ValueError('Unexpected candle schema')
        stamp = int(row[0])
        if stamp % duration or stamp in seen or stamp > asof:
            raise ValueError('Duplicate, unaligned, or future candle')
        seen.add(stamp)
        o, h, low, c = [positive(v) for v in row[1:5]]
        nonnegative(row[5]); nonnegative(row[6])
        if low > min(o, c) or h < max(o, c) or low > h:
            raise ValueError('Invalid OHLC data')
        if stamp + duration <= asof:
            clean.append([stamp, *row[1:]])
    clean.sort(key=lambda row: row[0])
    if not clean or any(b[0] - a[0] != duration for a, b in zip(clean, clean[1:])):
        raise ValueError('Empty candle history or gaps')
    if clean[-1][0] + duration != (asof // duration) * duration:
        raise ValueError('Latest completed candle missing')
    return clean


def collect(symbol):
    if symbol not in SYMBOLS:
        raise ValueError('Symbol not allowed')
    base = {'category': 'spot', 'symbol': symbol}
    jobs = [('h1', '/v5/market/kline', dict(base, interval='60', limit=1000)),
            ('h4', '/v5/market/kline', dict(base, interval='240', limit=1000)),
            ('book', '/v5/market/orderbook', dict(base, limit=50)),
            ('instrument', '/v5/market/instruments-info', base)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(name, pool.submit(request, path, params)) for name, path, params in jobs]
        data = {name: future.result() for name, future in futures}
    for name, interval in [('h1', 60), ('h4', 240)]:
        obj = data[name]['response']
        if obj['result'].get('symbol') != symbol:
            raise ValueError('Wrong candle symbol')
        data[name]['closed_candles'] = candles(obj['result']['list'], interval, int(obj['time']))
    instruments = data['instrument']['response']['result']['list']
    if len(instruments) != 1 or instruments[0]['symbol'] != symbol or instruments[0]['status'] != 'Trading':
        raise ValueError('Instrument is missing or not trading')
    book = data['book']['response']['result']
    if book['s'] != symbol or not book['b'] or not book['a']:
        raise ValueError('Invalid order book')
    if not -5000 <= int(time.time()*1000) - int(book['ts']) <= 60000:
        raise ValueError('Stale order book')
    bids = [(positive(p), positive(q)) for p, q in book['b']]
    asks = [(positive(p), positive(q)) for p, q in book['a']]
    if bids != sorted(bids, reverse=True) or asks != sorted(asks) or bids[0][0] >= asks[0][0]:
        raise ValueError('Unsorted or crossed book')
    return {'schema_version': 1, 'symbol': symbol, 'category': 'spot',
            'collected_at': datetime.now(timezone.utc).isoformat(), 'sources': data,
            'live_eligible': False, 'note': 'Recent research window, not a full backtest dataset.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', choices=sorted(SYMBOLS), default='BTCUSDT')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--request-worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.request_worker:
            spec = json.loads(args.request_worker)
            print(json.dumps(request(spec['path'], spec['params'])))
            sys.exit(0)
        if args.worker:
            print(json.dumps(collect(args.symbol)))
            sys.exit(0)
        if args.out is None:
            raise ValueError('--out is required')
        if args.out.exists():
            raise ValueError('Output already exists; use a new filename')
        # Bound DNS/TLS hangs too: socket timeout alone does not bound the OS resolver.
        child = subprocess.run([sys.executable, '-m', 'tools.market', '--worker',
                                '--symbol', args.symbol], capture_output=True,
                               text=True, timeout=25)
        if child.returncode:
            raise ValueError('Collection failed; no data accepted. ' + child.stderr[:500].strip())
        result = json.loads(child.stdout)
        # Exclusive creation: never overwrite a previous observation.
        with args.out.open('x') as f:
            json.dump(result, f, indent=2)
        print(f'Saved research snapshot: {args.out}')
    except Exception as exc:
        kind, message = failure_detail(exc)
        parser.exit(2, f'DATA UNAVAILABLE [{kind}]: {message}\n')
