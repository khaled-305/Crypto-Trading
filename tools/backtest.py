"""Exploratory TPB-v1 OHLC simulator. Approximate executions, never live approval."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tools.history import historical_rows
from tools.risk import dec, positive, nonnegative, ceil_step, floor_step, size_plan
from tools.strategy import evaluate, VERSION

LAGOS = timezone(timedelta(hours=1), 'Africa/Lagos')


def iso(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()


def aggregate(rows, minutes):
    buckets = defaultdict(list)
    span = minutes*60000
    for row in rows:
        buckets[int(row[0])//span*span].append(row)
    result = []
    for stamp, group in sorted(buckets.items()):
        result.append([stamp, str(group[0][1]), str(max(dec(r[2]) for r in group)),
                       str(min(dec(r[3]) for r in group)), str(group[-1][4]),
                       str(sum(dec(r[5]) for r in group)), str(sum(dec(r[6]) for r in group))])
    return result


def check_ohlc_match(derived, originals):
    indexed = {int(r[0]):r for r in originals}
    for row in derived:
        other = indexed.get(row[0])
        if other is None or any(dec(a) != dec(b) for a,b in zip(row[1:5],other[1:5])):
            raise ValueError('OHLC mismatch between timeframes; dataset rejected')


def validate_dataset(dataset):
    if (dataset.get('schema_version') != 2 or dataset.get('kind') != 'bybit_spot_ohlcv'
            or dataset.get('category') != 'spot' or dataset.get('symbol') != 'BTCUSDT'):
        raise ValueError('Require schema-2 Bybit BTCUSDT spot history')
    start, end, warmup = [int(dataset[k]) for k in ('evaluation_start_ms','evaluation_end_ms','warmup_start_ms')]
    interval = dataset['execution_interval_minutes']
    if interval not in (1,60) or start % 14400000 or end % 14400000 or warmup > start-800*3600000:
        raise ValueError('Invalid execution interval, boundaries, or indicator warmup')
    h1 = historical_rows(dataset['h1'],60,warmup,end)
    h4 = historical_rows(dataset['h4'],240,warmup,end)
    execution = historical_rows(dataset['execution'],interval,start,end)
    check_ohlc_match(aggregate(h1,240),h4)
    check_ohlc_match(aggregate(execution,60),h1)
    return h1,h4,execution,start,end


def settings(config):
    required = {'purpose','initial_equity_usdt','buy_fee_rate','sell_fee_rate','buy_fee_currency',
                'sell_fee_currency','spread_rate','slippage_rate','quantity_step','price_tick',
                'min_quantity','max_quantity','min_notional','max_notional','fee_basis','instrument_basis'}
    if set(config) != required:
        raise ValueError('Configuration fields must match the documented example exactly; no credentials')
    if config['purpose'] != 'exploratory':
        raise ValueError('This simulator supports exploratory reports only')
    for key in ('fee_basis','instrument_basis'):
        if not isinstance(config[key],str) or not config[key].strip():
            raise ValueError('Declare fee and historical instrument assumptions')
    for key in ('initial_equity_usdt','quantity_step','price_tick','max_quantity','min_notional','max_notional'):
        positive(config[key])
    nonnegative(config['min_quantity'])
    if config['buy_fee_currency'] not in ('base','quote') or config['sell_fee_currency'] != 'quote':
        raise ValueError('Unsupported fee currencies')
    for key in ('buy_fee_rate','sell_fee_rate','spread_rate','slippage_rate'):
        if nonnegative(config[key]) >= dec('.1'):
            raise ValueError('Rates must be decimal fractions below 0.1')
    drag = dec(config['spread_rate'])/2 + dec(config['slippage_rate'])
    if drag >= dec('.1'):
        raise ValueError('Combined execution drag too large')
    return drag


class Account:
    def __init__(self, initial):
        self.cash = initial
        self.day = self.week = None
        self.day_start = self.week_start = initial
        self.day_halted = self.week_halted = False
        self.peak = initial
        self.drawdown = self.drawdown_pct = dec(0)
        self.halts = []

    def boundary(self, stamp, prior_equity):
        local = datetime.fromtimestamp(stamp/1000,LAGOS)
        day, week = str(local.date()), tuple(local.isocalendar()[:2])
        if day != self.day:
            self.day, self.day_start, self.day_halted = day,prior_equity,False
        if week != self.week:
            self.week, self.week_start, self.week_halted = week,prior_equity,False

    def mark(self, equity, stamp):
        self.peak = max(self.peak,equity)
        self.drawdown = max(self.drawdown,self.peak-equity)
        self.drawdown_pct = max(self.drawdown_pct,(self.peak-equity)/self.peak)
        for period,rate in [('day',dec('.02')),('week',dec('.04'))]:
            if not getattr(self,period+'_halted') and equity <= getattr(self,period+'_start')*(1-rate):
                setattr(self,period+'_halted',True)
                self.halts.append({'period':period,'observed_in_bar_ms':stamp,'equity_usdt':equity})

    def for_sizing(self, stamp):
        return {'as_of':iso(stamp),'reconciled':True,'equity_usdt':self.cash,'available_usdt':self.cash,
                'open_and_pending_risk_usdt':0,'day_start_equity_usdt':self.day_start,
                'week_start_equity_usdt':self.week_start,'day_net_external_flows_usdt':0,
                'week_net_external_flows_usdt':0,'day_halted':self.day_halted,'week_halted':self.week_halted}


def execution_settings(value=None):
    """Deterministic stress assumptions, not estimates of exchange fill probabilities."""
    value = dict(value) if value is not None else {
        'entry_delay_ms': 0, 'exit_first_fill_fraction': '1', 'residual_retry_delay_bars': 1}
    if set(value) != {'entry_delay_ms','exit_first_fill_fraction','residual_retry_delay_bars'}:
        raise ValueError('Unexpected execution stress fields')
    # One-minute OHLC cannot identify a quote at an arbitrary subminute delay.
    if type(value['entry_delay_ms']) is not int or value['entry_delay_ms'] not in (0,60000):
        raise ValueError('Entry delay must be 0 or 60000 ms; subminute quotes are unavailable')
    if not 0 <= dec(value['exit_first_fill_fraction']) <= 1:
        raise ValueError('Exit first-fill fraction must be between zero and one')
    if type(value['residual_retry_delay_bars']) is not int or not 1 <= value['residual_retry_delay_bars'] <= 60:
        raise ValueError('Residual retry delay must be 1 to 60 bars')
    return value


def simulate(signals, execution, config, start, end, execution_model=None):
    """Internal event engine; the CLI validates source history before calling this."""
    drag = settings(config)
    model = execution_settings(execution_model)
    tick, fee = positive(config['price_tick']), dec(config['sell_fee_rate'])
    step = positive(config['quantity_step'])
    initial = positive(config['initial_equity_usdt'])
    account = Account(initial)
    position = None
    trades, decisions, equity_curve = [],[],[]
    groups = defaultdict(list)
    for signal in signals:
        if start <= signal['signal_close_ms'] < end:
            groups[signal['signal_close_ms']].append(signal)
    previous_close = dec(execution[0][1])

    def marked(price):
        return account.cash + (position['quantity']*price if position else 0)

    def close_position(reference, reason, stamp, bar_end):
        nonlocal position
        fill = max(dec(0),floor_step(reference*(1-drag),tick))
        retry = position['pending_exit'] is not None
        quantity = position['quantity'] if retry else floor_step(
            position['quantity']*dec(model['exit_first_fill_fraction']),step)
        # A partial execution of an already accepted order may be below its
        # minimum; a new residual order must independently meet restrictions.
        if retry and (quantity < dec(config['min_quantity']) or
                      quantity*fill < dec(config['min_notional']) or
                      quantity > dec(config['max_quantity']) or
                      quantity*fill > dec(config['max_notional'])):
            position['residual_rejections'] += 1
            position['retry_at_ms'] = stamp+duration*model['residual_retry_delay_bars']
            return
        proceeds = quantity*fill*(1-fee)
        account.cash += proceeds
        position['quantity'] -= quantity
        position['partial_proceeds_usdt'] += proceeds
        position['exit_fills'].append({'bar_start_ms':stamp,'time_upper_bound_ms':bar_end,
                                      'quantity':quantity,'price':fill,'fee_usdt':quantity*fill*fee})
        if position['quantity']:
            position['pending_exit'] = reason
            position['retry_at_ms'] = stamp+duration*model['residual_retry_delay_bars']
            account.mark(marked(reference),stamp)
            return
        proceeds = position['partial_proceeds_usdt']
        pnl = proceeds-position['cash_spent']
        total_fee = sum((f['fee_usdt'] for f in position['exit_fills']),dec(0))
        average_fill = sum((f['quantity']*f['price'] for f in position['exit_fills']),dec(0))/position['initial_quantity']
        trades.append({**position,'quantity':position['initial_quantity'],
                       'exit_price':average_fill,'exit_reason':position['pending_exit'] or reason,
                       'exit_bar_start_ms':stamp,'exit_time_upper_bound_ms':bar_end,
                       'net_proceeds_usdt':proceeds,'net_pnl_usdt':pnl,
                       'net_r':pnl/position['initial_risk_usdt'],
                       'exit_fee_usdt':total_fee,
                       'execution':'modeled_full_fill_not_observed' if dec(model['exit_first_fill_fraction'])==1
                                   else 'hypothetical_partial_or_failed_exit_then_residual_retry'})
        position = None
        account.mark(account.cash,stamp)

    # Execution OHLC reveals a range, not exact intrabar order. Model high->low for
    # surviving positions, and stop before target on ambiguous bars. Label drawdown accordingly.
    duration = (int(execution[1][0])-int(execution[0][0])) if len(execution)>1 else end-start
    if execution_model is not None and duration != 60000:
        raise ValueError('Execution stress scenarios require one-minute bars')
    for raw in execution:
        stamp = int(raw[0]); o,h,low,c = map(dec,raw[1:5])
        prior_equity = marked(previous_close)
        account.boundary(stamp,prior_equity)
        account.mark(marked(o),stamp)
        if position and position['pending_exit'] is not None and stamp >= position['retry_at_ms']:
            close_position(o,position['pending_exit'],stamp,stamp)
        if position and position['pending_exit'] is None and stamp >= position['time_exit_ms']:
            close_position(o,'time_exit',stamp,stamp)
        for signal in groups.pop(stamp,[]):
            decision = {'signal_close_ms':stamp,'strategy':VERSION}
            if model['entry_delay_ms'] >= 60000:
                decisions.append({**decision,'decision':'missed','reason':'entry_window_expired_by_delay'})
                continue
            if position:
                decisions.append({**decision,'decision':'skip','reason':'position_already_open'})
                continue
            if account.day_halted or account.week_halted or account.cash <= 0:
                decisions.append({**decision,'decision':'skip','reason':'account_halt'})
                continue
            ask_proxy = ceil_step(o*(1+dec(config['spread_rate'])/2),tick)
            if ask_proxy > dec(signal['max_entry_quote']):
                decisions.append({**decision,'decision':'missed','reason':'opening_ask_proxy_above_maximum'})
                continue
            # Entry at the first execution-bar open is an optimistic timing proxy,
            # not evidence of an executable quote inside the real 60-second window.
            plan = {k:config[k] for k in ('buy_fee_rate','sell_fee_rate','buy_fee_currency',
                    'sell_fee_currency','quantity_step','price_tick','min_quantity','max_quantity',
                    'min_notional','max_notional')}
            plan.update(as_of=iso(stamp),entry=str(o),stop=signal['stop'],target=signal['target'],slippage_rate=drag)
            try:
                sizing = size_plan({'mode':'paper','account':account.for_sizing(stamp),'plan':plan},
                                   datetime.fromtimestamp(stamp/1000,timezone.utc))
            except (ValueError,ArithmeticError) as exc:
                decisions.append({**decision,'decision':'skip','reason':'risk_or_order_constraint','detail':str(exc)})
                continue
            position = {'signal_close_ms':stamp,'entry_time_ms':stamp,'entry_price':sizing['entry_fill_assumption'],
                        'gross_quantity':sizing['gross_buy_quantity'],'quantity':sizing['protected_sell_quantity'],
                        'initial_quantity':sizing['protected_sell_quantity'],
                        'pending_exit':None,'retry_at_ms':None,'residual_rejections':0,
                        'partial_proceeds_usdt':dec(0),'exit_fills':[],
                        'dust_valued_at_zero':sizing['dust_valued_at_zero'],'cash_spent':sizing['cash_spent_usdt'],
                        'initial_risk_usdt':sizing['planned_loss_usdt'],'planned_net_rr':sizing['net_reward_risk'],
                        'stop':dec(signal['stop']),'target':dec(signal['target']),
                        'time_exit_ms':stamp+12*3600000}
            account.cash -= position['cash_spent']
            decisions.append({**decision,'decision':'simulated_entry','reason':'bar_open_proxy',
                              'quantity':position['quantity'],'risk_usdt':position['initial_risk_usdt']})
            account.mark(marked(o),stamp)
        if position:
            if position['pending_exit'] is not None:
                account.mark(marked(h),stamp)
                account.mark(marked(low),stamp)
                account.mark(marked(c),stamp)
            elif o <= position['stop']:
                close_position(o,'gap_stop',stamp,stamp)
            elif low <= position['stop']:
                # No assumed favorable peak before an unresolved stop event.
                close_position(position['stop'],'stop_before_target' if h >= position['target'] else 'stop',stamp,stamp+duration)
            elif h >= position['target']:
                account.mark(marked(low),stamp)
                close_position(position['target'],'target',stamp,stamp+duration)
            else:
                account.mark(marked(h),stamp)
                account.mark(marked(low),stamp)
                account.mark(marked(c),stamp)
            if position and position['pending_exit'] is not None:
                # Residual exposure persists after the first hypothetical fill.
                account.mark(marked(low),stamp)
                account.mark(marked(c),stamp)
        if stamp+duration == end and position and position['pending_exit'] is None:
            close_position(c,'data_end_liquidation',stamp,end)
        equity_curve.append({'timestamp_ms':stamp+duration,'equity_usdt':marked(c),
                             'day_halted':account.day_halted,'week_halted':account.week_halted})
        previous_close = c
    for stamp,remaining in groups.items():
        decisions.extend({'signal_close_ms':stamp,'decision':'missed','reason':'no_execution_bar_at_signal_time'} for _ in remaining)
    completed = [t for t in trades if t['exit_reason']!='data_end_liquidation']
    wins = [t for t in completed if t['net_pnl_usdt']>0]
    losses = [t for t in completed if t['net_pnl_usdt']<0]
    open_cash_flow = position['partial_proceeds_usdt']-position['cash_spent'] if position else dec(0)
    if abs(account.cash-initial-sum((t['net_pnl_usdt'] for t in trades),dec(0))-open_cash_flow) > dec('1e-18'):
        raise ValueError('Cash-flow conservation failed')
    ending_equity = marked(previous_close)
    return {'strategy':VERSION,'mode':'historical_approximation','live_eligible':False,
            'execution_model':model,'ending_cash_usdt':account.cash,
            'unresolved_position':position,
            'unresolved_inventory_mark_usdt':position['quantity']*previous_close if position else dec(0),
            'initial_equity_usdt':initial,'ending_equity_usdt':ending_equity,
            'total_net_pnl_usdt':ending_equity-initial,'return_fraction':ending_equity/initial-1,
            'completed_strategy_trades':len(completed),'boundary_liquidations':len(trades)-len(completed),
            'mean_net_r_completed':sum(t['net_r'] for t in completed)/len(completed) if completed else None,
            'mean_net_pnl_completed':sum(t['net_pnl_usdt'] for t in completed)/len(completed) if completed else None,
            'win_rate_completed':dec(len(wins))/len(completed) if completed else None,
            'profit_factor_completed':sum(t['net_pnl_usdt'] for t in wins)/-sum(t['net_pnl_usdt'] for t in losses) if losses else None,
            'modeled_intrabar_drawdown_usdt':account.drawdown,'modeled_intrabar_drawdown_fraction':account.drawdown_pct,
            'decision_counts':dict(Counter(d['decision'] for d in decisions)),
            'halt_events':account.halts,'decisions':decisions,'trades':trades,'equity_curve':equity_curve}


def benchmark(execution, config):
    drag = settings(config)
    initial, tick, step = map(positive,(config['initial_equity_usdt'],config['price_tick'],config['quantity_step']))
    buy_fee, sell_fee = dec(config['buy_fee_rate']),dec(config['sell_fee_rate'])
    entry = ceil_step(dec(execution[0][1])*(1+drag),tick)
    gross = floor_step(initial/(entry*(1+buy_fee if config['buy_fee_currency']=='quote' else 1)),step)
    qty = floor_step(gross*(1-buy_fee) if config['buy_fee_currency']=='base' else gross,step)
    spent = gross*entry*(1+buy_fee if config['buy_fee_currency']=='quote' else 1)
    fill = floor_step(dec(execution[-1][4])*(1-drag),tick)
    if (min(gross,qty)<dec(config['min_quantity']) or min(gross*entry,qty*fill)<dec(config['min_notional'])
            or max(gross,qty)>dec(config['max_quantity']) or max(gross*entry,qty*fill)>dec(config['max_notional'])):
        return {'cash_net_pnl_usdt':'0','buy_hold_available':False,'reason':'instrument_constraints'}
    equity = initial-spent+qty*fill*(1-sell_fee)
    peak,dd = initial,dec(0)
    for row in execution:
        peak=max(peak,initial-spent+qty*dec(row[2]))
        dd=max(dd,peak-(initial-spent+qty*dec(row[3])))
    dd=max(dd,peak-equity)
    return {'cash_net_pnl_usdt':dec(0),'buy_hold_available':True,'buy_hold_net_pnl_usdt':equity-initial,
            'buy_hold_return_fraction':equity/initial-1,'buy_hold_modeled_drawdown_usdt':dd,
            'note':'100% buy-and-hold exposure; not risk-matched to the strategy. USDT valuation basis.'}


def run(dataset, config, execution_model=None):
    settings(config)
    h1,h4,execution,start,end = validate_dataset(dataset)
    signals=evaluate(h1,h4,config['price_tick'])
    result=simulate(signals,execution,config,start,end,execution_model)
    result.update(evaluation_start=iso(start),evaluation_end_exclusive=iso(end),
                  execution_interval_minutes=dataset['execution_interval_minutes'],
                  assumptions=config,benchmarks=benchmark(execution,config),
                  limitations=['Exploratory OHLC approximation, not a validation pass or a forecast.',
                  'Bar opens plus assumed spread are not observed executable quotes within the 60-second entry window.',
                  'Baseline assumes full fills; optional partial/failed-exit scenarios are hypothetical, not measured liquidity.',
                  'Residual retries use later bar opens and may fail order minima; unresolved inventory remains marked, not fabricated as sold.',
                  'Marked unresolved inventory excludes future exit costs; completed-trade statistics omit open positions.',
                  'A 60-second entry delay expires the entry window; subminute latency requires finer quotes.',
                  'Stop-first ambiguity and adverse high/low ordering model intrabar drawdown, not observed tick paths.',
                  'Fees and instrument rules are constant supplied assumptions, not verified historical schedules.',
                  'Daily/weekly halts latch on modeled marks; no external deposits or withdrawals are modeled.',
                  'Data-end liquidations affect total equity but are excluded from completed-strategy-trade averages.',
                  'No confidence intervals, multiple-testing adjustment, or live promotion decision.'])
    return result


def load_json(path):
    if path.stat().st_size>256_000_000:
        raise ValueError('Input exceeds 256 MB limit')
    raw=path.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--execution-model',type=Path,help='Optional deterministic execution-stress JSON')
    args=parser.parse_args()
    try:
        if args.out.exists(): raise ValueError('Output exists; choose a new filename')
        dataset,digest=load_json(args.dataset); config,config_digest=load_json(args.config)
        model,model_digest=load_json(args.execution_model) if args.execution_model else (None,None)
        result=run(dataset,config,model)
        result['execution_model_sha256']=model_digest
        result['dataset_sha256']=digest; result['config_sha256']=config_digest
        result['code_sha256']={name:hashlib.sha256(Path('tools',name).read_bytes()).hexdigest()
                               for name in ('backtest.py','strategy.py','risk.py','history.py','market.py')}
        with args.out.open('x') as f: json.dump(result,f,default=str,indent=2)
        print(json.dumps({k:result[k] for k in ('mode','live_eligible','completed_strategy_trades','total_net_pnl_usdt')},default=str))
    except (ValueError,KeyError,TypeError,ArithmeticError,OSError) as exc:
        parser.exit(2,f'SIMULATION REJECTED: {exc}\n')
