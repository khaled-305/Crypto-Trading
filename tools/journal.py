"""Append-only paper signal/outcome ledger. Reports never imply live eligibility."""
import argparse
import fcntl
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tools.risk import dec, positive, nonnegative


def active_events(events):
    voided = {e['voids_id'] for e in events if e['type'] == 'void'}
    return [e for e in events if e['type'] != 'void' and e['id'] not in voided]


def validate(event, events):
    if event['mode'] != 'paper' or event['strategy'] != 'TPB-v1' or event['symbol'] != 'BTCUSDT':
        raise ValueError('Only TPB-v1 BTCUSDT paper events are supported')
    stamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timestamp needs a timezone')
    if not isinstance(event['reason'], str) or not event['reason'].strip():
        raise ValueError('Reason is required')
    if event['type'] == 'void':
        source = next((e for e in events if e['id'] == event['voids_id']), None)
        if not source:
            raise ValueError('Correction must reference an active event')
        if source['type'] == 'signal' and any(e['type'] == 'outcome' and e['signal_id'] == source['id'] for e in events):
            raise ValueError('Void its outcome first before correcting the signal')
        return
    if event['type'] == 'signal':
        if event['decision'] not in ('paper', 'skip', 'missed'):
            raise ValueError('Invalid signal decision')
        if any(e['type'] == 'signal' and datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) == stamp for e in events):
            raise ValueError('Signal already recorded')
        if event['decision'] == 'paper':
            closed_ids = {e['signal_id'] for e in events if e['type'] == 'outcome'}
            if any(e['type'] == 'signal' and e['decision'] == 'paper' and e['id'] not in closed_ids for e in events):
                raise ValueError('TPB-v1 permits only one open paper position')
            positive(event['initial_risk_usdt'])
            for key in ('entry', 'stop', 'target', 'quantity'):
                positive(event[key])
            if not dec(event['stop']) < dec(event['entry']) < dec(event['target']):
                raise ValueError('Invalid paper plan levels')
            nonnegative(event['estimated_cost_usdt'])
    elif event['type'] == 'outcome':
        source = next((e for e in events if e['id'] == event['signal_id']), None)
        if not source or source['type'] != 'signal' or source['decision'] != 'paper':
            raise ValueError('Outcome must link to a paper-entry signal')
        if any(e['type'] == 'outcome' and e['signal_id'] == source['id'] for e in events):
            raise ValueError('Outcome already recorded')
        if stamp < datetime.fromisoformat(source['timestamp'].replace('Z', '+00:00')):
            raise ValueError('Outcome precedes signal')
        dec(event['net_pnl_usdt']); nonnegative(event['observed_cost_usdt'])
        positive(event['exit_price'])
    else:
        raise ValueError('Use signal, outcome, or void event type')


def append(path, event):
    event = dict(event)
    # Serialization also rejects executable objects; there is no eval or CSV formula export.
    encoded = json.dumps(event, allow_nan=False)
    if len(encoded) > 20000:
        raise ValueError('Event too large')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        events = [json.loads(line) for line in f if line.strip()]
        validate(event, active_events(events))
        event['id'] = str(uuid.uuid4())
        event['recorded_at'] = datetime.now(timezone.utc).isoformat()
        f.write(json.dumps(event, allow_nan=False) + '\n')
        f.flush()
    return event['id']


def report(events):
    events = active_events(events)
    outcomes = sorted((e for e in events if e['type'] == 'outcome'), key=lambda e: datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')))
    signals = {e['id']: e for e in events if e['type'] == 'signal'}
    pnl = [dec(e['net_pnl_usdt']) for e in outcomes]
    wins, losses = [x for x in pnl if x > 0], [x for x in pnl if x < 0]
    rs = [dec(e['net_pnl_usdt']) / positive(signals[e['signal_id']]['initial_risk_usdt']) for e in outcomes]
    running = peak = drawdown = dec(0)
    for x in pnl:
        running += x
        peak = max(peak, running)
        drawdown = max(drawdown, peak - running)
    return {'mode': 'paper', 'live_eligible': False, 'signals': len(signals),
            'skipped_or_missed': sum(e['decision'] != 'paper' for e in signals.values()),
            'closed_trades': len(pnl), 'net_pnl_usdt': sum(pnl, dec(0)),
            'win_rate': dec(len(wins))/len(pnl) if pnl else None,
            'mean_net_pnl_usdt': sum(pnl)/len(pnl) if pnl else None,
            'mean_net_r': sum(rs)/len(rs) if rs else None,
            'average_net_win': sum(wins)/len(wins) if wins else None,
            'average_loss_magnitude': -sum(losses)/len(losses) if losses else None,
            'closed_trade_drawdown_usdt': drawdown,
            'limitations': 'Descriptive only: no intratrade drawdown, uncertainty estimate, benchmark, or edge certification. Small/dependent samples can mislead.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['append', 'report'])
    parser.add_argument('--ledger', type=Path, default=Path('journal/paper.jsonl'))
    parser.add_argument('--event', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'append':
            if args.event is None:
                raise ValueError('--event is required')
            print(append(args.ledger, json.loads(args.event.read_text())))
        else:
            events = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()] if args.ledger.exists() else []
            print(json.dumps(report(events), default=str, indent=2))
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError) as exc:
        parser.exit(2, f'REJECTED: {exc}\n')
