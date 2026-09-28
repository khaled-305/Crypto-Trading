"""Evaluate TPB-v1 research signals from a saved spot snapshot; never place orders."""
import argparse
import bisect
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tools.market import candles
from tools.risk import dec, positive, floor_step

VERSION = 'TPB-v1'


def ema(values, period):
    result = [None] * len(values)
    if len(values) < period:
        return result
    result[period - 1] = sum(values[:period]) / period
    alpha = dec(2) / (period + 1)
    for i in range(period, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def evaluate(h1, h4, tick):
    tick = positive(tick)
    c1, c4 = [dec(r[4]) for r in h1], [dec(r[4]) for r in h4]
    e1, e4 = ema(c1, 20), ema(c4, 50)
    ends4 = [int(r[0]) + 14400000 for r in h4]
    results = []
    for i in range(59, len(h1)):
        end = int(h1[i][0]) + 3600000
        j = bisect.bisect_right(ends4, end) - 1
        if j < 199:
            continue
        tests = {'h4_close_above_ema50': c4[j] > e4[j],
                 'h4_ema50_rising': e4[j] > e4[j - 3],
                 'previous_h1_closed_below_ema20': c1[i - 1] <= e1[i - 1],
                 'h1_reclaims_ema20': c1[i] > e1[i],
                 'h1_closes_above_previous_high': c1[i] > dec(h1[i - 1][2])}
        if all(tests.values()):
            stop = floor_step(min(dec(r[3]) for r in h1[i - 2:i + 1]), tick) - tick
            reference = c1[i]
            target = floor_step(reference + 3 * (reference - stop), tick)
            if stop <= 0 or stop >= reference:
                continue
            results.append({'strategy': VERSION, 'signal_close_ms': end,
                            'signal_close_utc': datetime.fromtimestamp(end/1000, timezone.utc).isoformat(),
                            'entry_deadline_ms': end + 60000, 'reference_close': str(reference),
                            'stop': str(stop), 'target': str(target),
                            'max_entry_quote': str(reference), 'time_exit_after_hours': 12,
                            'conditions': tests, 'live_eligible': False,
                            'status': 'signal_only_requires_execution_and_risk_checks'})
    return results


def scan(snapshot):
    if snapshot['category'] != 'spot' or snapshot['symbol'] != 'BTCUSDT':
        raise ValueError('TPB-v1 only evaluates BTCUSDT spot')
    data = snapshot['sources']
    rows = {}
    for key, interval in [('h1', 60), ('h4', 240)]:
        obj = data[key]['response']
        if obj['result']['category'] != 'spot' or obj['result']['symbol'] != 'BTCUSDT':
            raise ValueError('Wrong candle market')
        rows[key] = candles(obj['result']['list'], interval, int(obj['time']))
    if len(rows['h1']) < 60 or len(rows['h4']) < 200:
        raise ValueError('Insufficient EMA warmup history')
    instrument = data['instrument']['response']['result']['list'][0]
    if instrument['symbol'] != 'BTCUSDT':
        raise ValueError('Wrong instrument')
    signals = evaluate(rows['h1'], rows['h4'], instrument['priceFilter']['tickSize'])
    return {'strategy': VERSION, 'live_eligible': False, 'signals': signals,
            'closed_h1_bars': len(rows['h1']), 'closed_h4_bars': len(rows['h4']),
            'note': 'Historical signals only. This is not a backtest or a profit estimate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = args.snapshot.read_bytes()
        result = scan(json.loads(raw))
        result['snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
        with args.out.open('x') as f:
            json.dump(result, f, indent=2)
        print(f'Saved {len(result["signals"])} research signals: {args.out}')
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError) as exc:
        parser.exit(2, f'REJECTED: {exc}\n')
