"""Bounded FBR-v1 coverage observations, never orders, alerts or paper fills.

One supplied prospective watch; without one, collect hourly BTC spot baselines.
Run in the foreground. --report reads local evidence without network requests.
"""
import argparse
from collections import Counter
from decimal import Decimal
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
import uuid

from tools.market import (SYMBOLS, bounded_request, candles, failure_detail,
                          validate_h1_h4_overlap, validate_m15_overlap)

ROOT = Path(__file__).resolve().parent.parent
HOUR = 3_600_000
M15 = 900_000
MAX_HOURS = DEFAULT_HOURS = 6
MAX_CHECKS = 25
SNAPSHOT_SECONDS = 25
BOOK_SECONDS = 15
QUOTE_AGE_MS = 60_000
TERMINAL = {'INVALIDATED', 'EXPIRED', 'MISSED_WINDOW'}
FALSE_CAPABILITIES = {'live_eligible': False, 'orders_placed': False,
                      'paper_positions_opened': 0}


def now_ms():
    return int(time.time() * 1000)


def iso(stamp):
    return datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat()


def utc_ms(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an explicit UTC ISO string')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.utcoffset() is None or date.utcoffset().total_seconds() != 0:
        raise ValueError('Timestamp must use UTC')
    return int(date.timestamp() * 1000)


def number(value):
    if isinstance(value, bool):
        raise ValueError('Price must be positive and finite')
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise ValueError('Price must be positive and finite')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_new(path, value):
    """Publish complete evidence atomically and refuse replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def code_hashes():
    names = ('tools/manual_observer.py', 'tools/market.py', 'tools/risk.py', 'manual-setups.md')
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def validate_watch(value, accepted_ms):
    """Local acceptance, never an input timestamp, begins eligible breakout bars."""
    required = {'watch_id', 'symbol', 'registered_at', 'expires_at', 'zone',
                'support', 'overhead_resistance'}
    if not isinstance(value, dict) or not required <= value.keys():
        raise ValueError('Watch lacks required registration fields')
    if value.keys() - required - {'event_cutoff', 'overhead_resistance_basis'}:
        raise ValueError('Unknown watch fields; account or credential data are not accepted')
    if not isinstance(value['watch_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', value['watch_id']):
        raise ValueError('watch_id must be a short filename-safe unique identifier')
    if value['symbol'] not in SYMBOLS:
        raise ValueError('Watch symbol is not an approved spot pair')
    registered = utc_ms(value['registered_at'])
    expires = utc_ms(value['expires_at'])
    if not 0 <= accepted_ms - registered <= QUOTE_AGE_MS:
        raise ValueError('Registration must be no more than 60 seconds old and not future-dated')
    if not accepted_ms < expires <= registered + MAX_HOURS * HOUR:
        raise ValueError('Watch expiry must be future and within six hours of supplied registration')
    zone = value['zone']
    if not isinstance(zone, dict) or set(zone) != {'lower', 'upper'}:
        raise ValueError('zone requires exactly lower and upper')
    lower, upper = number(zone['lower']), number(zone['upper'])
    support, overhead = number(value['support']), number(value['overhead_resistance'])
    if not lower < upper < overhead:
        raise ValueError('Require zone lower < zone upper < overhead resistance')
    cutoff = utc_ms(value['event_cutoff']) if value.get('event_cutoff') is not None else expires
    if cutoff <= accepted_ms:
        raise ValueError('Event cutoff has already passed')
    basis = value.get('overhead_resistance_basis')
    if basis is not None and (not isinstance(basis, str) or not basis.strip() or len(basis) > 1000):
        raise ValueError('Closer chart resistance requires a short recorded basis')
    return {'watch_id': value['watch_id'], 'symbol': value['symbol'], 'setup': 'FBR-v1',
            'mode': 'paper_observation_only', 'input_registered_at': value['registered_at'],
            'registered_ms': accepted_ms, 'registered_at': iso(accepted_ms),
            'expires_ms': expires, 'expires_at': iso(expires),
            'deadline_ms': min(expires, cutoff), 'event_cutoff': value.get('event_cutoff'),
            'zone': {'lower': str(lower), 'upper': str(upper)}, 'support': str(support),
            'overhead_resistance': str(overhead), 'overhead_resistance_basis': basis,
            'input_sha256': digest(value), **FALSE_CAPABILITIES}


def snapshot(symbol, include_m15):
    command = [sys.executable, '-m', 'tools.market', '--worker', '--symbol', symbol]
    if include_m15:
        command.append('--include-m15')
    child = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                           timeout=SNAPSHOT_SECONDS)
    if child.returncode:
        raise ValueError('Snapshot unavailable: ' + child.stderr[:500].strip())
    return json.loads(child.stdout)


def closed_sources(snap, symbol, decision_ms):
    """Validate each source's completed-bar boundary and cross-timeframe OHLC."""
    if snap.get('category') != 'spot' or snap.get('symbol') != symbol:
        raise ValueError('Wrong snapshot symbol or category')
    result = {}
    for name, minutes in (('h1', 60), ('h4', 240), ('m15', 15)):
        source = snap['sources'].get(name)
        if source is None:
            if name == 'm15':
                continue
            raise ValueError('Missing required candle source: ' + name)
        response = source['response']
        observed = int(response['time'])
        if not 0 <= decision_ms - observed <= QUOTE_AGE_MS:
            raise ValueError('Stale or future candle response')
        duration = minutes * 60_000
        if observed // duration != decision_ms // duration:
            raise ValueError(f'Snapshot crossed the current {name} candle boundary')
        payload = response['result']
        if response.get('retCode') != 0 or payload.get('category') != 'spot' or payload.get('symbol') != symbol:
            raise ValueError('Wrong candle response market')
        result[name] = candles(payload['list'], minutes, min(observed, decision_ms))
    validate_h1_h4_overlap(result['h1'], result['h4'])
    if 'm15' in result:
        validate_m15_overlap(result['m15'], result['h1'])
    instrument = snap['sources']['instrument']['response']['result']['list']
    if len(instrument) != 1 or instrument[0].get('symbol') != symbol or instrument[0].get('status') != 'Trading':
        raise ValueError('Instrument is missing, wrong or not trading')
    result['tick'] = str(number(instrument[0]['priceFilter']['tickSize']))
    return result


def swings(rows, duration, index):
    result = []
    for offset in range(2, len(rows) - 2):
        row = rows[offset]
        peers = rows[offset - 2:offset] + rows[offset + 1:offset + 3]
        price = number(row[index])
        if all(price > number(p[index]) if index == 2 else price < number(p[index]) for p in peers):
            result.append({'start_ms': row[0], 'confirmed_ms': rows[offset + 2][0] + duration,
                           'price': str(price)})
    return result


def registration_context(watch, series):
    """Only candles complete when the immutable watch was accepted select levels."""
    registered = watch['registered_ms']
    h1 = [r for r in series['h1'] if r[0] + HOUR <= registered]
    h4 = [r for r in series['h4'] if r[0] + 4 * HOUR <= registered]
    highs, lows = swings(h4, 4 * HOUR, 2), swings(h4, 4 * HOUR, 3)
    if len(highs) < 2 or len(lows) < 2 or not h1:
        raise ValueError('Missing two confirmed four-hour highs/lows or hourly context')
    support = number(lows[-1]['price'])
    if number(watch['support']) != support or number(h4[-1][4]) <= support:
        raise ValueError('Premarked support differs from latest confirmed low or is already broken')
    hourly_highs = swings(h1, HOUR, 2)
    candidates = [s for s in hourly_highs if number(s['price']) > number(h1[-1][4])]
    if not candidates:
        raise ValueError('No confirmed hourly high above registration close')
    level, tick = candidates[-1], number(series['tick'])
    if (number(watch['zone']['lower']) != number(level['price']) - tick or
            number(watch['zone']['upper']) != number(level['price']) + tick):
        raise ValueError('Premarked zone does not surround latest eligible hourly high by one tick')
    overheads = [s for s in hourly_highs + highs if number(s['price']) > number(watch['zone']['upper'])]
    if not overheads:
        raise ValueError('No confirmed overhead resistance in registration history')
    nearest = min(overheads, key=lambda s: number(s['price']))
    supplied, confirmed = number(watch['overhead_resistance']), number(nearest['price'])
    if supplied > confirmed or (supplied < confirmed and not watch.get('overhead_resistance_basis')):
        raise ValueError('Overhead must be nearest confirmed resistance or a documented closer barrier')
    high_rise = number(highs[-1]['price']) > number(highs[-2]['price'])
    low_rise = number(lows[-1]['price']) > number(lows[-2]['price'])
    high_fall = number(highs[-1]['price']) < number(highs[-2]['price'])
    low_fall = number(lows[-1]['price']) < number(lows[-2]['price'])
    return {'asof_ms': registered, 'h4_highs': highs[-2:], 'h4_lows': lows[-2:],
            'structure': 'rising' if high_rise and low_rise else 'falling' if high_fall and low_fall else 'mixed',
            'hourly_level': level, 'nearest_confirmed_overhead': nearest, 'tick': str(tick),
            'watch_sha256': digest(watch)}


def evaluate(watch, context, series, decision_ms):
    """Chronological candle evidence only. No prices are modeled as fills."""
    registered = watch['registered_ms']
    lower, upper = number(watch['zone']['lower']), number(watch['zone']['upper'])
    support, tick = number(watch['support']), number(context['tick'])
    result = {'state': 'WAIT_BREAKOUT', 'reason': 'WAIT_BREAKOUT',
              'watch_id': watch['watch_id'], 'quote_eligible': False, **FALSE_CAPABILITIES}
    if number(series['tick']) != tick:
        return {**result, 'state': 'INVALIDATED', 'reason': 'ORDER_CONSTRAINT_TICK_CHANGED'}
    # Do not infer anything from an already forming breakout at registration.
    events = []
    for name, duration, priority in (('h4', 4 * HOUR, 0), ('h1', HOUR, 1), ('m15', M15, 2)):
        for row in series[name]:
            close = row[0] + duration
            if registered < close <= decision_ms:
                events.append((close, priority, name, row))
    events.sort(key=lambda item: (item[0], item[1]))
    previous_m15 = {r[0] + M15: r for r in series['m15']}
    breakout = retest = confirmation = None
    lowest = None
    for close, _, frame, row in events:
        if close > watch['deadline_ms']:
            break
        # Preserve the first terminal event; later candles cannot repair or relabel
        # a missed attempt. Bars closing exactly on the deadline still describe
        # the preceding eligible interval and may establish an invalidation.
        if confirmation is not None and close > result['entry_deadline_ms']:
            return {**result, 'state': 'MISSED_WINDOW', 'reason': 'CONFIRMATION_ENTRY_WINDOW_ELAPSED'}
        if retest is not None and confirmation is None and close > retest + HOUR:
            return {**result, 'state': 'EXPIRED', 'reason': 'CONFIRMATION_DEADLINE'}
        if breakout is not None and retest is None and close > breakout + 2 * HOUR:
            return {**result, 'state': 'EXPIRED', 'reason': 'RETEST_DEADLINE'}
        price, low, high = number(row[4]), number(row[3]), number(row[2])
        if frame == 'h4' and price <= support:
            return {**result, 'state': 'INVALIDATED', 'reason': 'FOUR_HOUR_SUPPORT_BROKEN',
                    'invalidated_ms': close}
        if frame == 'h1':
            if breakout is None:
                if row[0] >= registered and price > upper:
                    breakout = close
                    result.update(state='WAIT_RETEST', reason='WAIT_RETEST', breakout_close_ms=close)
                continue
            if price < lower:
                return {**result, 'state': 'INVALIDATED', 'reason': 'HOURLY_ZONE_BROKEN',
                        'invalidated_ms': close}
            if retest is None and close <= breakout + 2 * HOUR and low <= upper and high >= lower:
                if price <= upper:
                    return {**result, 'state': 'INVALIDATED', 'reason': 'FIRST_RETEST_FAILED',
                            'invalidated_ms': close}
                retest, lowest = close, low
                result.update(state='WAIT_CONFIRMATION', reason='WAIT_CONFIRMATION',
                              retest_close_ms=close, retest_low=str(low))
        if frame == 'm15' and retest is not None and row[0] >= retest:
            if price < lower:
                return {**result, 'state': 'INVALIDATED', 'reason': 'M15_ZONE_BROKEN',
                        'invalidated_ms': close}
            if confirmation is not None:
                if low <= number(result['stop']):
                    return {**result, 'state': 'INVALIDATED', 'reason': 'STOP_BREACHED_BEFORE_ENTRY',
                            'invalidated_ms': close}
                continue
            if close <= retest + HOUR:
                lowest = min(lowest, low)
                preceding = previous_m15.get(row[0])
                if preceding is None:
                    raise ValueError('Immediately preceding 15-minute candle is missing')
                if price > upper and price > number(preceding[2]):
                    confirmation = close
                    stop = lowest - tick
                    if stop <= 0:
                        return {**result, 'state': 'INVALIDATED', 'reason': 'NONPOSITIVE_STRUCTURAL_STOP'}
                    result.update(state='TRIGGER_RISK_UNVERIFIED', reason='ACCOUNT_CARD_RISK_UNVERIFIED',
                                  confirmation_close_ms=close, stop=str(stop),
                                  target=str(number(watch['overhead_resistance']) - tick),
                                  entry_deadline_ms=min(close + M15, watch['deadline_ms']))
    if confirmation is not None:
        if decision_ms >= result['entry_deadline_ms']:
            return {**result, 'state': 'MISSED_WINDOW', 'reason': 'CONFIRMATION_ENTRY_WINDOW_ELAPSED'}
        if watch.get('event_cutoff') and utc_ms(watch['event_cutoff']) - decision_ms < 30 * 60_000:
            return {**result, 'state': 'EXPIRED', 'reason': 'EVENT_CUTOFF_LESS_THAN_30_MINUTES'}
        return result
    if decision_ms >= watch['deadline_ms']:
        return {**result, 'state': 'EXPIRED', 'reason': 'WATCH_DEADLINE'}
    if retest is not None and decision_ms >= retest + HOUR:
        return {**result, 'state': 'EXPIRED', 'reason': 'CONFIRMATION_DEADLINE'}
    if breakout is not None and retest is None and decision_ms >= breakout + 2 * HOUR:
        return {**result, 'state': 'EXPIRED', 'reason': 'RETEST_DEADLINE'}
    return result


def quote_values(source, symbol, confirmation_ms, received_ms):
    response = source['response']
    book = response['result']
    if response.get('retCode') != 0 or book.get('s') != symbol:
        raise ValueError('Wrong or invalid book market')
    stamp, response_ms = int(book['ts']), int(response['time'])
    if (not confirmation_ms <= stamp <= response_ms <= received_ms or
            received_ms - stamp > QUOTE_AGE_MS):
        raise ValueError('Stale, future or pre-confirmation order book')
    bids = [(number(p), number(q)) for p, q in book['b']]
    asks = [(number(p), number(q)) for p, q in book['a']]
    if not bids or not asks or bids != sorted(bids, reverse=True) or asks != sorted(asks) or bids[0][0] >= asks[0][0]:
        raise ValueError('Empty, unsorted or crossed order book')
    bid, ask = bids[0][0], asks[0][0]
    spread = (ask - bid) / ask
    return {'exchange_quote_ms': stamp, 'response_ms': response_ms,
            'received_ms': received_ms, 'age_ms': received_ms - stamp,
            'bid': str(bid), 'ask': str(ask), 'spread_fraction': str(spread),
            'spread_threshold_pass': spread <= Decimal('0.001'),
            'visible_asks': [[str(p), str(q)] for p, q in asks],
            'depth_for_planned_quantity': 'UNVERIFIED_NO_QUANTITY',
            'quote_eligible': False}


def error_record(exc):
    kind, detail = failure_detail(exc)
    # Child errors retain these reviewed, sanitized status labels.
    for text, replacement in (('403', 'access_denied'), ('access_denied', 'access_denied'),
                              ('429', 'rate_limited'), ('rate_limited', 'rate_limited')):
        if text in str(exc):
            kind = replacement
            break
    return {'kind': kind, 'message': detail[:500], 'halt': kind in {'access_denied', 'rate_limited'}}


def observe(watch, context=None, get_snapshot=None, get_quote=None, clock=None,
            remaining_seconds=None):
    clock = clock or now_ms
    started = clock()
    symbol = watch['symbol'] if watch else 'BTCUSDT'
    event = {'schema_version': 1, 'setup': 'FBR-v1', 'mode': 'paper_observation_only',
             'symbol': symbol, 'category': 'spot', 'started_ms': started,
             'observed_at': iso(started), 'state': 'WAIT_BREAKOUT' if watch else None,
             'coverage': 'DATA_MISSING', 'reason': 'DATA_MISSING', **FALSE_CAPABILITIES}
    try:
        snap = (get_snapshot or snapshot)(symbol, watch is not None)
        event['snapshot'] = snap
        checked = clock()
        event['checked_ms'] = checked
        event['candle_checked_ms'] = checked
        series = closed_sources(snap, symbol, checked)
        event['hourly_baseline'] = {'latest_h1_close_ms': series['h1'][-1][0] + HOUR,
                                    'latest_h4_close_ms': series['h4'][-1][0] + 4 * HOUR}
        if watch is None:
            return {**event, 'coverage': 'OBSERVED', 'reason': 'BASELINE_ONLY_NO_REGISTERED_WATCH'}
        if context is None:
            context = registration_context(watch, series)
            event['registration_context'] = context
        if 'm15' not in series:
            event['source_errors'] = snap.get('source_errors', {'m15': {'kind': 'missing'}})
            event['reason'] = 'M15_DATA_MISSING'
            event['halt'] = any(error.get('kind') in {'access_denied', 'rate_limited'}
                                for error in event['source_errors'].values())
            return event
        result = evaluate(watch, context, series, checked)
        event.update(result, coverage='OBSERVED')
        if result['state'] != 'TRIGGER_RISK_UNVERIFIED':
            return event
        # Preserve detection even if the subsequent quote fails or arrives late.
        # A detected trigger is an opportunity observation, never a modeled entry.
        event['trigger_observed_ms'] = checked
        # One new post-trigger book, never retries or later quotes to improve evidence.
        if remaining_seconds is not None and remaining_seconds() < BOOK_SECONDS:
            return {**event, 'quote_error': 'RUN_DEADLINE_NO_TIME_FOR_BOOK', 'quote_eligible': False}
        event['quote_requested_ms'] = clock()
        source = (get_quote or (lambda: bounded_request('/v5/market/orderbook',
                  {'category': 'spot', 'symbol': symbol, 'limit': 50})))()
        received = clock()
        event['quote_source'] = source
        event['checked_ms'] = received
        event['quote_received_ms'] = received
        if received >= result['entry_deadline_ms']:
            return {**event, 'state': 'MISSED_WINDOW', 'reason': 'QUOTE_RECEIVED_AFTER_ENTRY_WINDOW'}
        try:
            event['quote'] = quote_values(source, symbol, result['confirmation_close_ms'], received)
            if number(event['quote']['bid']) <= number(result['stop']):
                return {**event, 'state': 'INVALIDATED', 'reason': 'OBSERVED_BID_AT_OR_BELOW_STOP'}
            event['quote_freshness_pass'] = True
            event['outstanding_checks'] = ['complete_paper_card', 'current_shadow_account_and_halts',
                'fees_inventory_rounding', 'net_reward_risk_and_max_ask', 'quantity_and_depth',
                'instrument_order_constraints', 'macro_events_and_stop_path_since_confirmation']
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            event['quote_error'] = error_record(exc)
            event['quote_freshness_pass'] = False
        return event
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError, subprocess.TimeoutExpired) as exc:
        event['error'] = error_record(exc)
        event['halt'] = event['error']['halt']
        event['reason'] = 'DATA_MISSING'
        return event


def report(directory):
    """Offline coverage counts. Repeated checks are never additional opportunities."""
    checks = [json.loads(p.read_text()) for p in sorted((directory / 'runs').glob('*/checks/*.json'))]
    runs = [json.loads(p.read_text()) for p in sorted((directory / 'runs').glob('*/run.json'))]
    gaps = [json.loads(p.read_text()) for p in sorted((directory / 'runs').glob('*/gaps/*.json'))]
    watches = [json.loads(p.read_text()) for p in sorted((directory / 'registrations').glob('*.json'))]
    triggers = {(e['watch_id'], e['confirmation_close_ms']) for e in checks
                if e.get('confirmation_close_ms') is not None and e.get('trigger_first_observed_in_window')}
    return {'runs': len(runs), 'registered_watches': len(watches), 'checks': len(checks),
            'coverage': dict(Counter(e['coverage'] for e in checks)),
            'states': dict(Counter(e['state'] for e in checks if e.get('state'))),
            'distinct_triggers_observed_in_window': len(triggers),
            'missed_scheduled_checks': sum(g['missing_checks'] for g in gaps),
            'data_missing_checks': sum(e['coverage'] == 'DATA_MISSING' for e in checks),
            'actual_check_times': [iso(e.get('checked_ms', e['started_ms'])) for e in checks],
            'unmonitored_between_runs': True, **FALSE_CAPABILITIES,
            'note': 'Discrete coverage only, not continuously monitored hours. No fills, returns or expectancy.'}


def record_gap(run_dir, accounted_slot, until_ms, cadence, recorded_ms, deadline_ms):
    """Count elapsed scheduled slots strictly before the cutoff, at most once."""
    until = min(until_ms, deadline_ms)
    first = accounted_slot + cadence
    last = (until - 1) // cadence * cadence
    if first > last:
        return accounted_slot
    save_new(run_dir / 'gaps' / f'{first}-{until}.json',
             {'from_ms': first, 'until_ms': until, 'recorded_ms': recorded_ms,
              'missing_checks': (last - first) // cadence + 1,
              'reason': 'OBSERVATION_GAP_NO_BACKFILLED_CHECKS'})
    return last


def known_window(watch, entry_deadline, breakout_close=None, retest_close=None):
    """Latest possible entry from observed stages, allowing unseen later stages."""
    if watch is None:
        return None, {}
    if entry_deadline is not None and entry_deadline <= watch['deadline_ms']:
        return entry_deadline, {'state': 'MISSED_WINDOW',
                'reason': 'CONFIRMATION_ENTRY_WINDOW_ELAPSED', 'entry_deadline_ms': entry_deadline}
    # With missing candles, a retest on its last eligible close can still
    # confirm an hour later, and a confirmation on its last close has another
    # 15 minutes for entry. Do not expire at an unobserved stage's raw cutoff.
    latest_entry = (retest_close + HOUR + M15 if retest_close is not None else
                    breakout_close + 3 * HOUR + M15 if breakout_close is not None else None)
    if latest_entry is not None and latest_entry <= watch['deadline_ms']:
        return latest_entry, {'state': 'EXPIRED', 'reason': 'POSSIBLE_ENTRY_WINDOW_ELAPSED',
                'latest_possible_entry_ms': latest_entry, 'confirmation_status': 'NOT_OBSERVED'}
    return watch['deadline_ms'], {'state': 'EXPIRED', 'reason': 'WATCH_DEADLINE'}


def known_expiry(watch, entry_deadline, checked_ms, breakout_close=None, retest_close=None):
    """Observed stage deadlines remain enforceable when market data are missing."""
    deadline, expiry = known_window(watch, entry_deadline, breakout_close, retest_close)
    return expiry if deadline is not None and checked_ms >= deadline else {}


def run_observer(directory, hours=DEFAULT_HOURS, once=False, watch_path=None):
    if not math.isfinite(hours) or not 0 < hours <= MAX_HOURS:
        raise ValueError('Duration must be finite, positive and at most six hours')
    if hours * 3600 < SNAPSHOT_SECONDS:
        raise ValueError('Duration must allow the bounded 25-second snapshot')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'observer.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another manual observer owns this directory') from None
        start = now_ms()
        stop_monotonic = time.monotonic() + hours * 3600
        run_deadline_ms = start + int(hours * HOUR)
        run_id = f'{start}-{uuid.uuid4().hex[:12]}'
        run_dir = directory / 'runs' / run_id
        hashes = code_hashes()
        watch = None
        if watch_path is not None:
            with Path(watch_path).open('rb') as handle:
                raw = handle.read(32_001)
            if len(raw) > 32_000:
                raise ValueError('Watch input exceeds 32KB limit')
            value = json.loads(raw)
            watch = validate_watch(value, start)
            watch['source_file_sha256'] = hashlib.sha256(raw).hexdigest()
            watch['run_id'] = run_id
            save_new(directory / 'registrations' / (watch['watch_id'] + '.json'), watch)
            save_new(run_dir / 'watch-input.json', value)
            save_new(run_dir / 'registered-watch.json', watch)
        save_new(run_dir / 'run.json', {'run_id': run_id, 'started_ms': start, 'started_at': iso(start),
                 'stop_at': iso(run_deadline_ms), 'hours': hours, 'once': once,
                 'pid': os.getpid(), 'code_sha256': hashes, 'watch_sha256': digest(watch) if watch else None,
                 'scope': 'Public read-only snapshots, no account data, alerts, orders or modeled fills',
                 **FALSE_CAPABILITIES})
        cadence = M15 if watch else HOUR
        coverage_deadline_ms = min(run_deadline_ms, watch['deadline_ms']) if watch else run_deadline_ms
        last_slot = None
        accounted_slot = start // cadence * cadence
        coverage_stopped_ms = None
        context = None
        previous_state = 'WAIT_BREAKOUT' if watch else None
        previous_entry_deadline = None
        stage_evidence = {}
        trigger_seen = False
        checks = 0
        reason = 'RUN_DEADLINE'
        try:
            while checks < MAX_CHECKS:
                # The wall-clock bound also catches suspension on platforms whose
                # monotonic clock excludes sleep; it never extends the run window.
                remaining = lambda: min(stop_monotonic - time.monotonic(),
                                        (run_deadline_ms - now_ms()) / 1000)
                if remaining() < SNAPSHOT_SECONDS:
                    break
                if code_hashes() != hashes:
                    raise ValueError('Reviewed code or frozen setup changed during run')
                current = now_ms()
                slot = current // cadence * cadence
                if current < start or (last_slot is not None and slot < last_slot):
                    raise ValueError('Clock moved backwards; stopping observation')
                expiry = known_expiry(watch, previous_entry_deadline, current,
                                      stage_evidence.get('breakout_close_ms'),
                                      stage_evidence.get('retest_close_ms'))
                if not expiry and last_slot is not None and slot == last_slot:
                    time.sleep(min(1, max(0.01, remaining())))
                    continue
                if not once:
                    accounted_slot = record_gap(run_dir, accounted_slot, slot, cadence,
                                                 current, coverage_deadline_ms)
                if expiry:
                    event = {'started_ms': current, 'checked_ms': current, 'coverage': 'NOT_CHECKED',
                             **expiry, 'watch_id': watch['watch_id'],
                             **FALSE_CAPABILITIES}
                else:
                    event = observe(watch, context, remaining_seconds=remaining)
                event.update(run_id=run_id, slot_ms=slot, recorded_ms=now_ms(), code_sha256=hashes,
                             watch_sha256=digest(watch) if watch else None)
                if watch:
                    event['watch_id'] = watch['watch_id']
                for key in ('breakout_close_ms', 'retest_close_ms'):
                    if key in event:
                        stage_evidence[key] = event[key]
                    elif key in stage_evidence:
                        # Keep the original candle timestamps, including on
                        # outage checks; this does not assert a later trigger.
                        event[key] = stage_evidence[key]
                if event['coverage'] == 'DATA_MISSING':
                    event['observation_gap'] = True
                    if event.get('state') not in TERMINAL:
                        event['state'] = previous_state
                if event.get('state') not in TERMINAL:
                    # Any request can finish after a known deadline. In
                    # particular, a failed book leaves valid candle coverage
                    # behind; preserve that evidence without retaining an
                    # actionable-looking state after the entry window closes.
                    expiry = known_expiry(watch, event.get('entry_deadline_ms', previous_entry_deadline),
                                          event['recorded_ms'],
                                          stage_evidence.get('breakout_close_ms'),
                                          stage_evidence.get('retest_close_ms'))
                    if expiry:
                        event['pre_expiry_state'] = event.get('state')
                        event['pre_expiry_reason'] = event['reason']
                        if event['coverage'] == 'DATA_MISSING' or event.get('error'):
                            event['data_missing_reason'] = event['reason']
                        event.update(expiry, checked_ms=event['recorded_ms'])
                if 'registration_context' in event:
                    context = event['registration_context']
                    save_new(run_dir / 'registration-context.json', context)
                trigger_observed = event.get('trigger_observed_ms')
                observed_trigger = (trigger_observed is not None and
                                    event.get('confirmation_close_ms') is not None and
                                    event['confirmation_close_ms'] <= trigger_observed <
                                    event.get('entry_deadline_ms', 0))
                event['trigger_first_observed_in_window'] = observed_trigger and not trigger_seen
                trigger_seen = trigger_seen or observed_trigger
                # A non-quarter-hour watch cutoff can occur in a slot already
                # checked; append the local expiry without replacing that check.
                check_id = f'{current}-deadline' if slot == last_slot else str(slot)
                save_new(run_dir / 'checks' / f'{check_id}.json', event)
                checks += 1
                last_slot = slot
                accounted_slot = max(accounted_slot, slot)
                previous_state = event.get('state')
                previous_entry_deadline = event.get('entry_deadline_ms', previous_entry_deadline)
                known_deadline, _ = known_window(watch, previous_entry_deadline,
                                                stage_evidence.get('breakout_close_ms'),
                                                stage_evidence.get('retest_close_ms'))
                if known_deadline is not None:
                    coverage_deadline_ms = min(coverage_deadline_ms, known_deadline)
                print(json.dumps({key: event.get(key) for key in ('run_id', 'state', 'reason', 'coverage')}), flush=True)
                if event.get('halt'):
                    reason = 'ACCESS_OR_RATE_LIMIT_HALT'
                    coverage_stopped_ms = event.get('checked_ms', current)
                    break
                if once:
                    reason = 'ONCE_COMPLETE'
                    coverage_stopped_ms = event.get('checked_ms', current)
                    break
                if event.get('state') in TERMINAL:
                    reason = 'WATCH_TERMINAL'
                    coverage_stopped_ms = event.get('checked_ms', current)
                    break
            else:
                reason = 'CHECK_LIMIT'
        except KeyboardInterrupt:
            reason = 'USER_INTERRUPTED'
        except Exception:
            reason = 'ERROR_STOPPED'
            raise
        finally:
            stopped = now_ms()
            # Do not erase trailing downtime when no later snapshot can observe it.
            # Early cancellation/terminal observations end the expected coverage;
            # the unobserved remainder of a planned run is not a missing check.
            # --once schedules only the immediate request, even if it finishes
            # or is interrupted after an hourly/quarter-hour boundary.
            if not once:
                record_gap(run_dir, accounted_slot,
                           stopped if coverage_stopped_ms is None else coverage_stopped_ms,
                           cadence, stopped, coverage_deadline_ms)
            if watch and previous_state not in TERMINAL:
                previous_state = known_expiry(watch, previous_entry_deadline, stopped,
                                             stage_evidence.get('breakout_close_ms'),
                                             stage_evidence.get('retest_close_ms')).get('state', previous_state)
            save_new(run_dir / 'stopped.json', {'stopped_at': iso(stopped), 'reason': reason,
                     'checks': checks, 'watch_state': previous_state, **FALSE_CAPABILITIES})
        return run_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('observations/manual-fbr-v1'))
    parser.add_argument('--hours', type=float, default=DEFAULT_HOURS)
    parser.add_argument('--watch-input', type=Path, help='One prospectively dated local watch; no credentials')
    parser.add_argument('--once', action='store_true', help='One bounded observation, then exit')
    parser.add_argument('--report', action='store_true', help='Read only local observation evidence; no network')
    args = parser.parse_args()
    try:
        if args.report:
            print(json.dumps(report(args.directory), indent=2))
        else:
            run_observer(args.directory, args.hours, args.once, args.watch_input)
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError) as exc:
        parser.exit(2, f'MANUAL OBSERVER STOPPED: {exc}\n')


if __name__ == '__main__':
    main()
