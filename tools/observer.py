"""Bounded read-only TPB-v1 forward quote observer; never submits orders."""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.market import bounded_request, failure_detail
from tools.risk import dec, positive, size_plan
from tools.strategy import scan, VERSION

HOUR = 3600000
WINDOW = 60000
MAX_QUOTE_AGE = 2000
ROOT = Path(__file__).resolve().parent.parent


def now_ms():
    return int(time.time()*1000)


def iso(stamp):
    return datetime.fromtimestamp(stamp/1000, timezone.utc).isoformat()


def code_hashes():
    return {name:hashlib.sha256((ROOT/'tools'/name).read_bytes()).hexdigest()
            for name in ('observer.py','market.py','strategy.py','risk.py')}


def save_new(path, value):
    """Publish complete JSON atomically without replacing any previous evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,default=str,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.link(tmp,path)
    finally:
        os.unlink(tmp)


def snapshot():
    child = subprocess.run([sys.executable,'-m','tools.market','--worker','--symbol','BTCUSDT'],
                           cwd=ROOT,capture_output=True,text=True,timeout=25)
    if child.returncode:
        raise ValueError('Snapshot unavailable: '+child.stderr[:500].strip())
    return json.loads(child.stdout)


def quote_values(source, signal_close, received_ms):
    obj=source['response']; book=obj['result']
    if obj.get('retCode') != 0 or book.get('s') != 'BTCUSDT':
        raise ValueError('Wrong or invalid quote market')
    stamp=int(book['ts'])
    # Clock skew and pre-close quotes are not accepted as post-signal evidence.
    if not signal_close <= stamp <= received_ms or received_ms-stamp > MAX_QUOTE_AGE:
        raise ValueError('Stale, future, or pre-signal quote')
    bids=[(positive(p),positive(q)) for p,q in book['b']]
    asks=[(positive(p),positive(q)) for p,q in book['a']]
    if not bids or not asks or bids != sorted(bids,reverse=True) or asks != sorted(asks) or bids[0][0]>=asks[0][0]:
        raise ValueError('Empty, unsorted or crossed order book')
    bid,ask=bids[0][0],asks[0][0]
    return {'bid':str(bid),'ask':str(ask),'spread':str(ask-bid),
            'exchange_quote_ms':stamp,'received_ms':received_ms,'age_ms':received_ms-stamp,
            'latency_from_signal_close_ms':received_ms-signal_close}


def assess(signal, quote, risk_input=None, now=None):
    """First observed quote only; never search later quotes to rescue a failed entry."""
    if quote['received_ms'] >= signal['entry_deadline_ms']:
        return {'decision':'missed','reason':'entry_window_expired'}
    if dec(quote['ask'])>dec(signal['max_entry_quote']):
        return {'decision':'missed','reason':'first_observed_ask_above_maximum'}
    if risk_input is None:
        return {'decision':'quote_pass_risk_unverified','reason':'fresh_paper_risk_input_missing'}
    data=json.loads(json.dumps(risk_input))
    plan=data['plan']
    # Input assumptions/account timestamps must already be independently fresh.
    plan.update(entry=quote['ask'],stop=signal['stop'],target=signal['target'])
    try:
        result=size_plan(data,now or datetime.fromtimestamp(quote['received_ms']/1000,timezone.utc))
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
        return {'decision':'skip','reason':'risk_or_order_constraint','detail':str(exc)[:300]}
    return {'decision':'paper_math_pass','reason':'quote_and_supplied_risk_checks_pass',
            'sizing':result,'note':'Not a simulated fill or paper position; depth and protective order mechanics remain unverified.'}


def observe(boundary, get_snapshot=snapshot, get_quote=None, clock=now_ms, risk_input=None):
    started=clock()
    event={'schema_version':1,'strategy':VERSION,'symbol':'BTCUSDT','category':'spot',
           'boundary_ms':boundary,'boundary_utc':iso(boundary),'started_ms':started,
           'live_eligible':False,'orders_placed':False}
    if started < boundary:
        raise ValueError('Cannot observe a future candle close')
    # Do not backfill or generate a signal from data collected after its entry window.
    if started >= boundary+WINDOW:
        return {**event,'decision':'missed_check','reason':'observer_started_after_entry_window'}
    try:
        snap=get_snapshot()
        data=snap['sources']
        for name,interval in (('h1',HOUR),('h4',4*HOUR)):
            obj=data[name]['response']
            if int(obj['time'])//interval*interval != boundary//interval*interval:
                raise ValueError('Snapshot belongs to a different candle boundary')
        result=scan(snap)
        event['snapshot']=snap
        event['indicator_basis']='Rolling source snapshot; exact candle history retained. EMA seed can vary between checks.'
        signals=[s for s in result['signals'] if s['signal_close_ms']==boundary]
        if len(signals)>1:
            raise ValueError('Duplicate signal for candle close')
        event['signal']=signals[0] if signals else None
        if clock()>=boundary+WINDOW:
            return {**event,'decision':'missed_check','reason':'collection_finished_after_entry_window'}
        if not signals:
            return {**event,'decision':'no_signal','reason':'frozen_setup_conditions_not_met'}
        # The snapshot's concurrent book may predate completed signal evaluation.
        # Obtain one new book only after the signal is known.
        event['quote_request_ms']=clock()
        get_quote=get_quote or (lambda:bounded_request('/v5/market/orderbook',
                                      {'category':'spot','symbol':'BTCUSDT','limit':50}))
        source=get_quote()
        received=clock(); event['quote_source']=source
        quote=quote_values(source,boundary,received)
        event['quote']=quote
        if risk_input is not None:
            instrument=data['instrument']['response']['result']['list'][0]
            lots=instrument['lotSizeFilter']; supplied=risk_input['plan']
            if (dec(supplied['price_tick'])!=dec(instrument['priceFilter']['tickSize']) or
                dec(supplied['quantity_step'])!=dec(lots['basePrecision']) or
                dec(supplied['min_notional'])<dec(lots['minOrderAmt']) or
                dec(supplied['max_quantity'])>dec(lots['maxMarketOrderQty'])):
                return {**event,'decision':'skip','reason':'risk_input_instrument_mismatch'}
            event['risk_input_sha256']=hashlib.sha256(
                json.dumps(risk_input,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        event.update(assess(signals[0],quote,risk_input))
        return event
    except (ValueError,KeyError,TypeError,ArithmeticError,OSError,subprocess.TimeoutExpired) as exc:
        kind,detail=failure_detail(exc)
        return {**event,'decision':'data_unavailable','reason':kind,'detail':detail[:500]}


def previous_boundary(directory):
    values=[]
    for p in (directory/'checks').glob('*.json'):
        value=json.loads(p.read_text())
        boundary=int(p.stem)
        if value.get('boundary_ms')!=boundary or boundary%HOUR:
            raise ValueError('Corrupted observation history')
        values.append(boundary)
    return max(values) if values else None


def report(directory):
    from collections import Counter
    events=[json.loads(p.read_text()) for p in sorted((directory/'checks').glob('*.json'))]
    counts=Counter(e['decision'] for e in events)
    return {'recorded_hours':len(events),'decisions':dict(counts),
            'signals_observed':sum(e.get('signal') is not None for e in events),
            'quote_checks':sum('quote' in e for e in events),
            'last_recorded_boundary':events[-1]['boundary_utc'] if events else None,
            'paper_positions_opened':0,'orders_placed':0,'live_eligible':False,
            'note':'Quote eligibility observations only; no simulated fills, trade returns or automatic position tracking.'}


def run_observer(directory, hours, once=False, risk_path=None):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'observer.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another observer owns this directory')
        registered=now_ms(); hashes=code_hashes()
        save_new(directory/'runs'/f'{registered}.json',
                 {'started_at':iso(registered),'pid':os.getpid(),'duration_hours':hours,
                  'once':once,'code_sha256':hashes,'risk_input_supplied':risk_path is not None,
                  'scope':'Public data only; no orders or automatic paper positions',
                  'stop_at':iso(registered+int(hours*HOUR))})
        until=time.monotonic()+hours*3600
        last=previous_boundary(directory)
        while True:
            if code_hashes()!=hashes:raise ValueError('Observer code changed during run; stopping')
            current=now_ms(); boundary=current//HOUR*HOUR
            if last is not None and boundary<last:raise ValueError('Clock moved behind recorded history')
            if (last is None or boundary>last) and (once or current>=boundary+2000):
                if last is not None:
                    for missing in range(last+HOUR,boundary,HOUR):
                        save_new(directory/'checks'/f'{missing}.json',
                                 {'boundary_ms':missing,'boundary_utc':iso(missing),'decision':'missed_check',
                                  'reason':'observer_downtime','recorded_at':iso(current),'live_eligible':False})
                risk_input=None
                if risk_path:
                    if risk_path.stat().st_size>100000:raise ValueError('Risk input too large')
                    risk_input=json.loads(risk_path.read_text())
                event=observe(boundary,risk_input=risk_input)
                event['finished_ms']=now_ms()
                event['code_sha256']=hashes
                save_new(directory/'checks'/f'{boundary}.json',event)
                last=boundary
                print(json.dumps({k:event[k] for k in ('boundary_utc','decision','reason')}),flush=True)
            if once or time.monotonic()>=until:break
            # UTC whole-hour candle boundaries, plus two seconds for publication.
            wait=max(.2,min(1,(boundary+HOUR+2000-now_ms())/1000))
            time.sleep(wait)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('observations/tpb-v1'))
    parser.add_argument('--hours',type=float,default=168)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--report',action='store_true',help='Summarize existing local observations without network access')
    parser.add_argument('--risk-input',type=Path,help='Optional fresh, local paper risk input; no credentials')
    args=parser.parse_args()
    try:
        if not 0 < args.hours <= 168:raise ValueError('Duration must be above zero and at most 168 hours')
        if args.report:print(json.dumps(report(args.directory),indent=2))
        else:run_observer(args.directory,args.hours,args.once,args.risk_input)
    except KeyboardInterrupt:
        print('Observer stopped; recorded observations preserved.',file=sys.stderr)
    except (ValueError,KeyError,TypeError,ArithmeticError,OSError) as exc:
        parser.exit(2,f'OBSERVER STOPPED: {exc}\n')
