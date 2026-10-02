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


def pending_corrections(events):
    """A voided outcome or staged signal replacement needs an outcome or void.

    This preserves the two-event correction workflow even for an older trade
    followed by later trades. It is not permission to reopen historical exposure:
    new paper entries and performance reports stay blocked until corrected.
    """
    active = active_events(events)
    paper_ids = {e['id'] for e in active
                 if e['type'] == 'signal' and e['decision'] == 'paper'}
    closed_ids = {e['signal_id'] for e in active if e['type'] == 'outcome'}
    sources = {e['id']: e for e in events if e['type'] != 'void'}
    voided_outcomes = {sources[e['voids_id']]['signal_id'] for e in events
                      if e['type'] == 'void' and e['voids_id'] in sources
                      and sources[e['voids_id']]['type'] == 'outcome'
                      and sources[e['voids_id']]['signal_id'] in paper_ids - closed_ids}
    staged_signals = {e['id'] for e in active if e['id'] in paper_ids - closed_ids
                     and 'replaces_signal_id' in e}
    return voided_outcomes | staged_signals


def validate_replacement(event, history):
    """Allow a linked correction of an earlier, previously closed paper signal.

    Void the original outcome, then its signal, then append a corrected paper
    signal carrying replaces_signal_id=the voided signal ID. Its outcome links
    the new signal ID and must restore valid full chronological exposure. Until
    then the signal is staged: reports/new entries block, skips remain allowed.
    Only one signal in the original signal's complete replacement lineage can
    remain active. This does not permit inserting a new historical trade.
    """
    if 'replaces_signal_id' not in event:
        return
    reference = event['replaces_signal_id']
    if event['type'] != 'signal' or event.get('decision') != 'paper':
        raise ValueError('replaces_signal_id is only valid on a paper signal correction')
    if not isinstance(reference, str) or not reference:
        raise ValueError('Replacement needs a voided paper signal ID')
    source = next((e for e in history if e['id'] == reference), None)
    active = active_events(history)
    if (source is None or source['type'] != 'signal' or source.get('decision') != 'paper'
            or any(source.get(key) != event.get(key) for key in ('mode', 'strategy', 'symbol'))
            or any(e['id'] == reference for e in active)):
        raise ValueError('Replacement must reference a voided paper signal')
    if not any(e['type'] == 'outcome' and e['signal_id'] == reference for e in history):
        raise ValueError('Replacement source must have a previously recorded outcome')
    sources = {e['id']: e for e in history if e['type'] == 'signal'}
    root = replacement_root(reference, sources)
    if any(e['type'] == 'signal' and replacement_root(e['id'], sources) == root for e in active):
        raise ValueError('The voided paper signal already has an active replacement in its lineage')


def replacement_root(ident, sources):
    """Resolve every ancestor, so an older ID cannot fork another active trade."""
    seen = set()
    while True:
        if ident in seen or ident not in sources:
            raise ValueError('Invalid paper signal replacement lineage')
        seen.add(ident)
        source = sources[ident]
        if 'replaces_signal_id' not in source:
            return ident
        ident = source['replaces_signal_id']


def validate_replacement_links(events):
    history = []
    for event in events:
        validate_replacement(event, history)
        history.append(event)


def timestamp(event):
    stamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Timestamp needs a timezone')
    return stamp


def validate(event, events):
    if event['mode'] != 'paper' or event['strategy'] != 'TPB-v1' or event['symbol'] != 'BTCUSDT':
        raise ValueError('Only TPB-v1 BTCUSDT paper events are supported')
    stamp = timestamp(event)
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
        if any(e['type'] == 'signal' and timestamp(e) == stamp for e in events):
            raise ValueError('Signal already recorded')
        if event['decision'] == 'paper':
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
        if stamp < timestamp(source):
            raise ValueError('Outcome precedes signal')
        dec(event['net_pnl_usdt']); nonnegative(event['observed_cost_usdt'])
        positive(event['exit_price'])
    else:
        raise ValueError('Use signal, outcome, or void event type')


def validate_chronology(events, pending=()):
    """Validate exposure by event time, independently of append order.

    Intervals are [entry, exit), so an exit and next entry may share a timestamp.
    Existing zero-duration outcome fixtures remain valid. An unclosed position
    extends indefinitely; a historical insertion needs a known exit and therefore
    cannot be appended as a new unlinked entry before an already recorded trade.
    A linked replacement of a voided closed signal can be staged for correction.
    Pending trade corrections are excluded only while reports/entries are
    blocked; their replacement must pass the full exposure check before resuming.
    """
    seen = []
    ids = set()
    for event in events:
        if event['id'] in ids:
            raise ValueError('Duplicate event ID')
        validate(event, seen)
        ids.add(event['id'])
        seen.append(event)
    outcomes = {e['signal_id']: e for e in events if e['type'] == 'outcome'}
    entries = sorted((e for e in events if e['type'] == 'signal'
                      and e['decision'] == 'paper' and e['id'] not in pending),
                     key=timestamp)
    for prior, following in zip(entries, entries[1:]):
        outcome = outcomes.get(prior['id'])
        if outcome is None or timestamp(outcome) > timestamp(following):
            raise ValueError('TPB-v1 permits only one paper position at any event time; overlapping exposure')


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
        if pending_corrections(events) and event['type'] == 'signal' and event['decision'] == 'paper':
            raise ValueError('Complete the pending outcome correction before another paper entry')
        event['id'] = str(uuid.uuid4())
        event['recorded_at'] = datetime.now(timezone.utc).isoformat()
        proposed = events + [event]
        validate_replacement_links(proposed)
        validate_chronology(active_events(proposed), pending_corrections(proposed))
        f.write(json.dumps(event, allow_nan=False) + '\n')
        f.flush()
    return event['id']


def report(events):
    events = list(events)
    validate_replacement_links(events)
    if pending_corrections(events):
        raise ValueError('Performance report blocked: complete the pending outcome correction')
    events = active_events(events)
    validate_chronology(events)
    outcomes = sorted((e for e in events if e['type'] == 'outcome'), key=timestamp)
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
