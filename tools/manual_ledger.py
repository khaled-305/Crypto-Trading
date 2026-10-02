"""Local manual PAPER evidence ledger; no network, signals, or exchange orders."""
import argparse
import copy
import fcntl
import json
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.risk import dec, nonnegative, positive, size_plan

ARMS = ('MPB-v1', 'MBR-v1', 'FBR-v1')
SYMBOLS = {'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'LINKUSDT', 'SUIUSDT'}
LAGOS = ZoneInfo('Africa/Lagos')
IDENTIFIER = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp with timezone required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp with timezone required')
    return result.astimezone(timezone.utc)


def bounds(low, high=None):
    low, high = nonnegative(low), nonnegative(low if high is None else high)
    if low > high:
        raise ValueError('Inverted bounds')
    return {'lower': low, 'upper': high}


def initial_state():
    return {'mode': 'paper', 'live_eligible': False, 'event_ids': [], 'arms': {
        arm: {'cash': bounds(100), 'equity': bounds(100), 'position': None,
              'day': None, 'week': None, 'day_start': bounds(100),
              'week_start': bounds(100), 'day_halted': False, 'week_halted': False,
              'setup_review_required': False, 'reviews': [],
              'last_at': None, 'trades': []} for arm in ARMS}}


def marked_equity(account, bid):
    cash, position = account['cash'], account['position']
    if position is None:
        return dict(cash)
    inventory_value = position['quantity'] * positive(bid)
    alternatives = [inventory_value] + position['possible_net_proceeds']
    return bounds(cash['lower'] + min(alternatives), cash['upper'] + max(alternatives))


def latch_halts(account):
    for period, rate in (('day', Decimal('.02')), ('week', Decimal('.04'))):
        start = account[f'{period}_start']
        # Interval arithmetic deliberately uses the adverse combination, not an average.
        loss = max(Decimal(0), start['upper'] - account['equity']['lower'])
        if loss >= start['lower'] * rate:
            account[f'{period}_halted'] = True


def advance_periods(account, event, at):
    local = at.astimezone(LAGOS)
    day = local.date().isoformat()
    week = (local.date() - timedelta(days=local.weekday())).isoformat()
    changing = [(p, v) for p, v in (('day', day), ('week', week)) if account[p] != v]
    if not changing:
        return
    if account['position'] is not None:
        if event['type'] != 'boundary' or (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
            raise ValueError('Open/uncertain exposure requires dated Lagos midnight boundary evidence')
        if account['day'] is not None:
            previous = datetime.fromisoformat(account['day']).date()
            if local.date() != previous + timedelta(days=1):
                raise ValueError('Missing boundary evidence: reconcile each crossed day in order')
        # Apply this mark to the ending period before resetting its budget/flags.
        account['equity'] = marked_equity(account, event['bid'])
        latch_halts(account)
    else:
        account['equity'] = dict(account['cash'])
    for period, key in changing:
        account[period] = key
        account[f'{period}_start'] = dict(account['equity'])
        account[f'{period}_halted'] = False


def _entry(account, event, at):
    if account['position'] is not None:
        raise ValueError('One-position limit: exposure is open or not known flat')
    if account['day_halted'] or account['week_halted']:
        raise ValueError('Daily or weekly halt remains active')
    if account['setup_review_required']:
        raise ValueError('Setup review required after a planned-risk overshoot')
    if event['symbol'] not in SYMBOLS:
        raise ValueError('Unsupported spot pair')
    plan = dict(event['plan'])
    quote_at = timestamp(plan['as_of'])
    confirmation = timestamp(event['confirmation_at'])
    expiry = timestamp(event['entry_expires_at'])
    interval = 900 if event['arm'] == 'FBR-v1' else 3600
    latest_expiry = datetime.fromtimestamp((int(confirmation.timestamp()) // interval + 1) * interval, timezone.utc)
    if confirmation > quote_at or quote_at > at or not (confirmation <= at < expiry <= latest_expiry):
        raise ValueError('Quote must follow confirmation and entry must precede its candle expiry')
    bid, ask = positive(event['bid']), positive(plan['entry'])
    if bid >= ask or ask > positive(event['max_entry_ask']):
        raise ValueError('Invalid book or ask above predeclared maximum')
    spread = (ask - bid) / ask
    if spread > Decimal('.001'):
        raise ValueError('Observed spread exceeds the frozen 0.10% paper limit')
    if (dec(plan['buy_fee_rate']) != Decimal('.001')
            or dec(plan['sell_fee_rate']) != Decimal('.001')
            or plan['buy_fee_currency'] != 'base' or plan['sell_fee_currency'] != 'quote'):
        raise ValueError('Paper fee model is frozen; different assumptions require a reviewed version')
    allowance = 1 - (1 - spread / 2) * (1 - Decimal('.0005'))
    if dec(plan['slippage_rate']) != allowance:
        raise ValueError('Paper slippage must equal the frozen allowance from the observed spread')
    cash = account['cash']['lower']
    if cash <= 0:
        raise ValueError('No conservative cash available')
    risk_account = {'as_of': event['at'], 'reconciled': True,
                    'equity_usdt': cash, 'available_usdt': cash,
                    'open_and_pending_risk_usdt': '0',
                    'day_start_equity_usdt': account['day_start']['lower'],
                    'week_start_equity_usdt': account['week_start']['lower'],
                    'day_net_external_flows_usdt': '0', 'week_net_external_flows_usdt': '0',
                    'day_halted': False, 'week_halted': False}
    period_remaining = {}
    for period, rate in (('day', Decimal('.02')), ('week', Decimal('.04'))):
        start = account[f'{period}_start']
        period_remaining[period] = start['lower'] * rate - max(Decimal(0), start['upper'] - cash)
    conservative_cap = min(period_remaining.values())
    if conservative_cap <= 0:
        raise ValueError('No conservative period risk allowance remains')
    result = size_plan({'mode': 'paper', 'account': risk_account, 'plan': plan}, now=at,
                       risk_cap_usdt=conservative_cap)
    for remaining in period_remaining.values():
        if result['planned_loss_usdt'] > remaining:
            raise ValueError('Conservative period bounds leave insufficient risk for this size')
    spent, qty = result['cash_spent_usdt'], result['protected_sell_quantity']
    account['cash'] = bounds(account['cash']['lower'] - spent, account['cash']['upper'] - spent)
    account['position'] = {'entry_id': event['id'], 'symbol': event['symbol'],
                            'quantity': qty, 'spent': spent,
                            'planned_risk': result['planned_loss_usdt'],
                            'exposure': 'open', 'possible_net_proceeds': [],
                            'assessment_history': [],
                            'entry_calculation': result, 'card_reference': event['card_reference']}
    account['equity'] = marked_equity(account, bid)


def _outcomes(event):
    outcomes = event.get('outcomes')
    if not isinstance(outcomes, list) or not outcomes or len(outcomes) > 32:
        raise ValueError('Provide 1–32 supported full-exit outcomes')
    labels, proceeds = [], []
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise ValueError('Each full-exit outcome must be an object')
        label = outcome.get('label')
        if not isinstance(label, str) or not label.strip() or label in labels:
            raise ValueError('Unique nonempty outcome labels required')
        labels.append(label)
        proceeds.append(nonnegative(outcome['net_proceeds_usdt']))
    return labels, proceeds


def _record_assessment(position, event, labels, proceeds):
    record = {field: event[field] for field in ('id', 'type', 'at', 'exposure', 'evidence')}
    record['outcomes'] = [{'label': label, 'net_proceeds_usdt': value}
                          for label, value in zip(labels, proceeds)]
    if proceeds:
        record['net_proceeds_bounds'] = bounds(min(proceeds), max(proceeds))
    if event['type'] == 'reconcile_exposure':
        record['supersedes_assessment_id'] = event['assessment_id']
        record['resolution_reason'] = event['resolution_reason']
    position['assessment_history'].append(record)


def _assessment(account, event, reconciled=False):
    position = account['position']
    if position is None or event.get('entry_id') != position['entry_id']:
        raise ValueError('Outcome must reference the outstanding entry exactly once')
    labels, proceeds = _outcomes(event)
    prior = position['possible_net_proceeds']
    if not reconciled and prior and (min(proceeds) > min(prior) or max(proceeds) < max(prior)):
        raise ValueError('Do not discard an earlier possible exit without linked resolving evidence')
    if position['spent'] - min(proceeds) > position['planned_risk']:
        account['setup_review_required'] = True
    exposure = event.get('exposure')
    if exposure not in ('open_or_flat', 'flat'):
        raise ValueError('Exposure must be flat or open_or_flat; partial exits unsupported')
    _record_assessment(position, event, labels, proceeds)
    if exposure == 'open_or_flat':
        position['exposure'] = exposure
        position['possible_net_proceeds'] = proceeds
        account['equity'] = marked_equity(account, event['bid'])
        return
    low, high = min(proceeds), max(proceeds)
    pnl_low, pnl_high = low - position['spent'], high - position['spent']
    certain = low == high
    account['cash'] = bounds(account['cash']['lower'] + low, account['cash']['upper'] + high)
    account['equity'] = dict(account['cash'])
    account['trades'].append({'entry_id': position['entry_id'], 'assessment_id': event['id'],
                              'symbol': position['symbol'], 'exposure': 'flat',
                              'outcome_certainty': 'resolved' if certain else 'bounded',
                              'net_pnl_usdt': pnl_low if certain else None,
                              'net_r': pnl_low / position['planned_risk'] if certain else None,
                              'net_pnl_bounds': {'lower': pnl_low, 'upper': pnl_high},
                              'net_proceeds_bounds': bounds(low, high),
                              'spent': position['spent'],
                              'planned_risk': position['planned_risk'],
                              'outcome_labels': labels, 'evidence': event['evidence'],
                              'assessment_history': copy.deepcopy(position['assessment_history'])})
    account['position'] = None


def _reconcile_exposure(account, event):
    position = account['position']
    if position is None or event.get('entry_id') != position['entry_id']:
        raise ValueError('Reconciliation must reference the outstanding entry')
    if position['exposure'] != 'open_or_flat':
        raise ValueError('Reconciliation requires outstanding uncertain exposure')
    latest = position['assessment_history'][-1]
    if event.get('assessment_id') != latest['id']:
        raise ValueError('Reconciliation must link the latest outstanding assessment')
    if not isinstance(event.get('resolution_reason'), str) or not event['resolution_reason'].strip():
        raise ValueError('Reconciliation requires a resolution reason')
    if event['evidence'].strip() == latest['evidence'].strip():
        raise ValueError('Reconciliation requires new evidence distinct from the assessment')
    exposure = event.get('exposure')
    if exposure == 'flat':
        # Full-exit paths can narrow only with the new evidence and exact link above.
        # Existing cash has never included these proceeds; _assessment adds them once.
        _assessment(account, event, reconciled=True)
    elif exposure == 'open':
        if 'outcomes' in event or 'net_proceeds_usdt' in event:
            raise ValueError('Proven-open exposure must not declare exit proceeds')
        positive(event['bid'])
        _record_assessment(position, event, [], [])
        position['possible_net_proceeds'] = []
        position['exposure'] = 'open'
        account['equity'] = marked_equity(account, event['bid'])
    else:
        raise ValueError('Reconcile only proven open or flat exposure; partial exits unsupported')
    # An earlier possible loss already triggered any applicable halts/review.
    # Resolving its path does not undo those latches or rewrite period-start budgets.


def _resolve_outcome(account, event):
    matches = [t for t in account['trades'] if t['entry_id'] == event.get('entry_id')]
    if len(matches) != 1 or matches[0]['outcome_certainty'] != 'bounded':
        raise ValueError('Resolution must reference one previously bounded flat trade')
    trade = matches[0]
    proceeds = nonnegative(event['net_proceeds_usdt'])
    previous = trade['net_proceeds_bounds']
    if not previous['lower'] <= proceeds <= previous['upper']:
        raise ValueError('Resolution outside previous bounds requires a reviewed correction')
    account['cash'] = bounds(account['cash']['lower'] + proceeds - previous['lower'],
                             account['cash']['upper'] - previous['upper'] + proceeds)
    trade['outcome_certainty'] = 'resolved'
    trade['net_pnl_usdt'] = proceeds - trade['spent']
    trade['net_r'] = trade['net_pnl_usdt'] / trade['planned_risk']
    trade['original_net_proceeds_bounds'] = dict(previous)
    trade['net_proceeds_bounds'] = bounds(proceeds)
    trade['net_pnl_bounds'] = {'lower': trade['net_pnl_usdt'], 'upper': trade['net_pnl_usdt']}
    trade['resolution_id'] = event['id']
    trade['resolution_evidence'] = event['evidence']
    account['equity'] = marked_equity(account, event.get('bid'))


def _review(account, event):
    if not account['setup_review_required']:
        raise ValueError('No outstanding setup review')
    for field in ('corrective_action', 'resumption_reason'):
        if not isinstance(event.get(field), str) or not event[field].strip():
            raise ValueError('Review requires corrective action and a reason for resumption')
    account['reviews'].append({field: event[field] for field in
                               ('id', 'at', 'evidence', 'corrective_action', 'resumption_reason')})
    account['setup_review_required'] = False


def apply_event(state, event):
    """Replay explicit operator evidence; this does not verify chart signals/fills."""
    if not isinstance(event, dict) or event.get('mode') != 'paper':
        raise ValueError('Only explicit paper events are supported')
    if (event.get('arm') not in ARMS or not isinstance(event.get('id'), str)
            or not IDENTIFIER.fullmatch(event['id'])):
        raise ValueError('Invalid arm or event ID')
    if event['id'] in state['event_ids']:
        raise ValueError('Duplicate event ID')
    if not isinstance(event.get('evidence'), str) or not event['evidence'].strip():
        raise ValueError('Evidence reference required; model assumptions are not exchange fills')
    if event.get('type') not in {'entry', 'mark', 'boundary', 'exit_assessment',
                                'reconcile_exposure', 'resolve_outcome', 'review'}:
        raise ValueError('Unsupported event type; no resets, deposits or arbitrary balance edits')
    result = copy.deepcopy(state)
    account = result['arms'][event['arm']]
    at = timestamp(event['at'])
    if account['last_at'] is not None and at < timestamp(account['last_at']):
        raise ValueError('Backdated arm event')
    advance_periods(account, event, at)
    if event['type'] == 'entry':
        if not isinstance(event.get('card_reference'), str) or not event['card_reference'].strip():
            raise ValueError('Frozen paper card reference required')
        _entry(account, event, at)
    elif event['type'] == 'exit_assessment':
        _assessment(account, event)
    elif event['type'] == 'reconcile_exposure':
        _reconcile_exposure(account, event)
    elif event['type'] == 'resolve_outcome':
        _resolve_outcome(account, event)
    elif event['type'] == 'review':
        _review(account, event)
    else:
        account['equity'] = marked_equity(account, event.get('bid'))
    latch_halts(account)
    account['last_at'] = at.isoformat()
    result['event_ids'].append(event['id'])
    return result


def replay(events):
    state = initial_state()
    for event in events:
        state = apply_event(state, event)
    return state


def read_events(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def report(state):
    result = copy.deepcopy(state)
    for account in result['arms'].values():
        resolved = [t for t in account['trades'] if t['outcome_certainty'] == 'resolved']
        account['resolved_count'] = len(resolved)
        account['bounded_count'] = len(account['trades']) - len(resolved)
        account['mean_resolved_r'] = (sum(t['net_r'] for t in resolved) / len(resolved)) if resolved else None
        account['exposure'] = account['position']['exposure'] if account['position'] else 'flat'
        account['cash_available_for_sizing'] = account['cash']['lower'] if account['position'] is None else Decimal(0)
    result['limitations'] = ('Operator-supplied paper evidence; no automatic signal, exit inference, '
                            'exchange acceptance or full-fill verification. Cash/equity bounds use '
                            'conservative interval arithmetic. Bounded trades excluded from mean R. '
                            'Partial exits/arbitrary corrections/transfers unsupported and must not be guessed.')
    return result


def _check_append_time(event, now):
    observed = timestamp(event['at'])
    if observed > now + timedelta(seconds=5):
        raise ValueError('Future observation')
    if event.get('type') == 'entry':
        if not timedelta(0) <= now - observed <= timedelta(seconds=60):
            raise ValueError('Paper entries must be appended prospectively within 60 seconds')
        quote_at = timestamp(event['plan']['as_of'])
        if not timedelta(0) <= now - quote_at <= timedelta(seconds=60):
            raise ValueError('Paper entry quote must remain fresh within 60 seconds at append')
        if now >= timestamp(event['entry_expires_at']):
            raise ValueError('Paper entry must be appended before its entry expiry')


def append_event(path, event, now=None, *, clock=None):
    """Append evidence while locked; `now`/`clock` are deterministic test overrides."""
    if now is not None and clock is not None:
        raise ValueError('Use either a fixed now or a clock, not both')
    if clock is None:
        clock = (lambda: now) if now is not None else (lambda: datetime.now(timezone.utc))
    _check_append_time(event, clock())
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sidecar lock persists; kernel releases ownership on crash. No PID-file stale-lock guessing.
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _check_append_time(event, clock())
        events = read_events(path)
        result = apply_event(replay(events), event)
        encoded = json.dumps(event, allow_nan=False, separators=(',', ':')) + '\n'
        # A complete final JSON object can survive a crash without its newline.
        # Append a separator without rewriting any existing evidence.
        if path.exists() and path.stat().st_size:
            with path.open('rb') as stream:
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b'\n':
                    encoded = '\n' + encoded
        # Lock contention, replay, serialization or suspension can consume the
        # remaining window. Do not change the observed timestamp to revive it.
        _check_append_time(event, clock())
        with path.open('a') as stream:
            _check_append_time(event, clock())
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('append', 'report'))
    parser.add_argument('--ledger', type=Path, default=Path('observations/manual-ledger/events.jsonl'))
    parser.add_argument('--event', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'append':
            if args.event is None:
                raise ValueError('--event is required')
            result = append_event(args.ledger, json.loads(args.event.read_text()))
        else:
            result = replay(read_events(args.ledger))
        print(json.dumps(report(result), default=str, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError) as exc:
        parser.exit(2, f'REJECTED: {exc}\n')


if __name__ == '__main__':
    main()
