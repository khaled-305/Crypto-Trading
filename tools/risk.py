"""Deterministic spot-long PAPER sizing. No network, credentials, or orders."""
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING


def dec(value):
    if isinstance(value, bool):
        raise ValueError('Boolean supplied as a number')
    x = Decimal(str(value))
    if not x.is_finite():
        raise ValueError('Numbers must be finite')
    return x


def positive(value):
    x = dec(value)
    if x <= 0:
        raise ValueError('Expected a positive number')
    return x


def nonnegative(value):
    x = dec(value)
    if x < 0:
        raise ValueError('Expected a nonnegative number')
    return x


def fresh(stamp, now, seconds):
    if not isinstance(stamp, str):
        raise ValueError('A confirmed timestamp is required')
    dt = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    age = (now - dt).total_seconds()
    if age < -5 or age > seconds:
        raise ValueError('Stale or future timestamp')


def floor_step(x, step):
    return (x / step).to_integral_value(rounding=ROUND_FLOOR) * step


def ceil_step(x, step):
    return (x / step).to_integral_value(rounding=ROUND_CEILING) * step


def size_plan(data, now=None):
    now = now or datetime.now(timezone.utc)
    if data['mode'] != 'paper':
        raise ValueError('Only paper calculations are supported')
    a, p = data['account'], data['plan']
    fresh(a['as_of'], now, 300)
    fresh(p['as_of'], now, 60)
    if a['reconciled'] is not True:
        raise ValueError('Account including pending orders must be reconciled')
    for flag in ('day_halted', 'week_halted'):
        if type(a[flag]) is not bool or a[flag]:
            raise ValueError('Period halt is active or unknown')
    equity, cash = positive(a['equity_usdt']), nonnegative(a['available_usdt'])
    if cash > equity:
        raise ValueError('Available cash exceeds equity; reconcile account')
    open_risk = nonnegative(a['open_and_pending_risk_usdt'])
    budgets = {'default': equity * dec('.005'), 'per_trade_ceiling': equity * dec('.02'),
               'portfolio_remaining': equity * dec('.01') - open_risk}
    for period, rate in (('day', '.02'), ('week', '.04')):
        start = positive(a[f'{period}_start_equity_usdt'])
        flows = dec(a[f'{period}_net_external_flows_usdt'])
        used = max(dec(0), start + flows - equity)
        budgets[f'{period}_remaining'] = start * dec(rate) - used - open_risk
    budget = min(budgets.values())
    if budget <= 0:
        raise ValueError('No remaining risk allowance')
    entry, stop, target = map(positive, (p['entry'], p['stop'], p['target']))
    step, tick = positive(p['quantity_step']), positive(p['price_tick'])
    if not stop < entry < target:
        raise ValueError('Require stop < entry < target')
    for price in (entry, stop, target):
        if price % tick:
            raise ValueError('Entry/stop/target must align to price tick')
    buy_fee, sell_fee, slip = map(nonnegative, (p['buy_fee_rate'], p['sell_fee_rate'], p['slippage_rate']))
    if max(buy_fee, sell_fee, slip) >= dec('.1'):
        raise ValueError('Rates must be decimals below 0.1; verify units')
    if p['buy_fee_currency'] not in ('base', 'quote') or p['sell_fee_currency'] != 'quote':
        raise ValueError('Unsupported fee currency model')
    entry_fill = ceil_step(entry * (1 + slip), tick)
    stop_fill = floor_step(stop * (1 - slip), tick)
    target_fill = floor_step(target * (1 - slip), tick)
    if stop_fill <= 0:
        raise ValueError('Invalid modeled stop fill')
    min_qty, max_qty = nonnegative(p['min_quantity']), positive(p['max_quantity'])
    min_value, max_value = positive(p['min_notional']), positive(p['max_notional'])

    def amounts(qty):
        base_net = qty * (1 - buy_fee) if p['buy_fee_currency'] == 'base' else qty
        sell_qty = floor_step(base_net, step)
        spent = qty * entry_fill * (1 + buy_fee if p['buy_fee_currency'] == 'quote' else 1)
        stop_net = sell_qty * stop_fill * (1 - sell_fee)
        target_net = sell_qty * target_fill * (1 - sell_fee)
        return spent, spent - stop_net, target_net - spent, sell_qty, base_net - sell_qty

    # Loss is monotonic on gross quantity increments; binary search includes dust loss.
    lo, hi = 0, int(floor_step(min(max_qty, max_value / entry_fill, cash / entry_fill), step) / step)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        spent, loss, _, _, _ = amounts(dec(mid) * step)
        if spent <= cash and loss <= budget:
            lo = mid
        else:
            hi = mid - 1
    qty = dec(lo) * step
    spent, loss, reward, sell_qty, dust = amounts(qty)
    if qty <= 0 or sell_qty <= 0 or min(qty, sell_qty) < min_qty:
        raise ValueError('Size is below exchange quantity minimum')
    if min(qty * entry_fill, sell_qty * stop_fill) < min_value:
        raise ValueError('Entry or stop exit below exchange notional minimum')
    if sell_qty * target_fill > max_value or sell_qty > max_qty:
        raise ValueError('Target exit exceeds exchange maximum')
    if loss <= 0 or reward / loss < 2:
        raise ValueError('Net reward/risk below 2:1')
    return {'status': 'paper_math_pass_only', 'live_eligible': False,
            'budgets_usdt': budgets, 'binding_limits': [k for k, v in budgets.items() if v == budget],
            'gross_buy_quantity': qty, 'protected_sell_quantity': sell_qty,
            'dust_valued_at_zero': dust, 'entry_fill_assumption': entry_fill,
            'stop_fill_assumption': stop_fill, 'target_fill_assumption': target_fill,
            'cash_spent_usdt': spent, 'planned_loss_usdt': loss,
            'planned_reward_usdt': reward, 'net_reward_risk': reward / loss,
            'remaining_risk_budget_usdt': budget - loss,
            'warning': 'Assumptions only; gaps can exceed modeled loss. No orders placed.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Local JSON account and single-exit plan')
    args = parser.parse_args()
    try:
        with open(args.input) as f:
            result = size_plan(json.load(f))
        print(json.dumps(result, default=str, indent=2))
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError) as exc:
        parser.exit(2, f'REJECTED: {exc}\n')
