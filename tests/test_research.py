import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from tools.risk import dec, size_plan
from tools.market import candles, request, NoRedirect
from tools.strategy import evaluate, ema
from tools.journal import append, report

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def plan():
    return {'mode': 'paper', 'account': {
        'as_of': NOW.isoformat(), 'reconciled': True, 'equity_usdt': '100',
        'available_usdt': '100', 'open_and_pending_risk_usdt': '0',
        'day_start_equity_usdt': '100', 'week_start_equity_usdt': '100',
        'day_net_external_flows_usdt': '0', 'week_net_external_flows_usdt': '0',
        'day_halted': False, 'week_halted': False},
        'plan': {'as_of': NOW.isoformat(), 'entry': '100', 'stop': '98', 'target': '107',
                 'quantity_step': '.000001', 'price_tick': '.01', 'buy_fee_rate': '.001',
                 'sell_fee_rate': '.001', 'slippage_rate': '.0005',
                 'buy_fee_currency': 'base', 'sell_fee_currency': 'quote',
                 'min_quantity': '.001', 'max_quantity': '100',
                 'min_notional': '5', 'max_notional': '100000'}}


class RiskTests(unittest.TestCase):
    def test_costs_inventory_and_budget(self):
        result = size_plan(plan(), NOW)
        q = result['gross_buy_quantity']
        sell = result['protected_sell_quantity']
        self.assertLess(sell, q)
        self.assertEqual(sell % dec('.000001'), 0)
        spent = q * result['entry_fill_assumption']
        stop_net = sell * result['stop_fill_assumption'] * dec('.999')
        self.assertEqual(result['cash_spent_usdt'], spent)
        self.assertEqual(result['planned_loss_usdt'], spent - stop_net)
        self.assertLessEqual(result['planned_loss_usdt'], dec('.5'))
        self.assertGreaterEqual(result['net_reward_risk'], 2)
        self.assertFalse(result['live_eligible'])

    def test_quote_buy_fee(self):
        p = plan(); p['plan']['buy_fee_currency'] = 'quote'
        r = size_plan(p, NOW)
        self.assertEqual(r['gross_buy_quantity'], r['protected_sell_quantity'])
        self.assertEqual(r['cash_spent_usdt'], r['gross_buy_quantity'] * r['entry_fill_assumption'] * dec('1.001'))

    def test_known_no_fee_answer(self):
        p = plan()
        p['plan'].update(buy_fee_rate='0', sell_fee_rate='0', slippage_rate='0')
        r = size_plan(p, NOW)
        self.assertEqual(r['gross_buy_quantity'], dec('.25'))
        self.assertEqual(r['planned_loss_usdt'], dec('.5'))
        self.assertEqual(r['planned_reward_usdt'], dec('1.75'))

    def test_remaining_portfolio_risk_is_binding(self):
        p = plan(); p['account']['open_and_pending_risk_usdt'] = '.8'
        r = size_plan(p, NOW)
        self.assertIn('portfolio_remaining', r['binding_limits'])
        self.assertLessEqual(r['planned_loss_usdt'], dec('.2'))

    def test_daily_remaining_and_external_flow(self):
        p = plan(); p['account'].update(equity_usdt='98.3', available_usdt='98.3')
        r = size_plan(p, NOW)
        self.assertIn('day_remaining', r['binding_limits'])
        self.assertLessEqual(r['planned_loss_usdt'], dec('.3'))
        p['account'].update(equity_usdt='108.3', available_usdt='108.3',
                            day_net_external_flows_usdt='10', week_net_external_flows_usdt='10')
        r = size_plan(p, NOW)
        self.assertEqual(r['budgets_usdt']['day_remaining'], dec('.3'))

    def test_halt_unknown_and_stale_rejections(self):
        for field, value in [('day_halted', True), ('week_halted', None),
                             ('reconciled', None), ('as_of', None),
                             ('as_of', '2026-09-24T11:00:00+00:00')]:
            with self.subTest(field=field, value=value):
                p = plan(); p['account'][field] = value
                with self.assertRaises(ValueError): size_plan(p, NOW)

    def test_cash_minimum_and_reward_rejections(self):
        changes = [('target', '101'), ('min_notional', '50'), ('stop', '98.005'),
                   ('entry', 'NaN'), ('buy_fee_rate', '-0.1'), ('sell_fee_currency', 'base')]
        for key, value in changes:
            with self.subTest(key=key):
                p = plan(); p['plan'][key] = value
                with self.assertRaises((ValueError, ArithmeticError)): size_plan(p, NOW)
        p = plan(); p['account']['available_usdt'] = '1'
        with self.assertRaises(ValueError): size_plan(p, NOW)

    def test_weekly_cap_and_halt(self):
        p = plan(); p['account'].update(equity_usdt='95', available_usdt='95', day_start_equity_usdt='95')
        with self.assertRaises(ValueError): size_plan(p, NOW)

    def test_template_rejects_unknowns(self):
        data = json.loads(Path('examples/risk-input.json').read_text())
        with self.assertRaises(ValueError): size_plan(data, NOW)


def bar(stamp, close='100'):
    c = dec(close)
    return [stamp, str(c), str(c + 1), str(c - 1), str(c), '1', '100']


class MarketTests(unittest.TestCase):
    def test_closed_only_and_sorted(self):
        rows = [bar(7200000), bar(3600000), bar(0)]
        self.assertEqual([r[0] for r in candles(rows, 60, 9000000)], [0, 3600000])

    def test_missing_duplicate_and_bad_prices(self):
        for rows, stamp in [([bar(0), bar(7200000)], 10800000),
                            ([bar(0), bar(0)], 3600000),
                            ([bar(0)], 7200000), ([bar(0, '-1')], 3600000)]:
            with self.assertRaises(ValueError): candles(rows, 60, stamp)

    def test_endpoint_restrictions_before_network(self):
        with patch('urllib.request.build_opener') as opener:
            for path, params in [('/v5/order/create', {'category':'spot','symbol':'BTCUSDT'}),
                                 ('/v5/market/kline', {'category':'linear','symbol':'BTCUSDT'})]:
                with self.assertRaises(ValueError): request(path, params)
            opener.assert_not_called()
        with self.assertRaises(ValueError): NoRedirect().redirect_request(None)


class StrategyTests(unittest.TestCase):
    def test_ema_known_values(self):
        self.assertEqual(ema(list(map(dec, [1, 2, 3, 4])), 3), [None, None, dec(2), dec(3)])

    def test_future_h4_cannot_change_past_signal(self):
        hour = 3600000
        h4 = [bar(i * 4 * hour, str(100 + i)) for i in range(205)]
        h1 = [bar((740+i)*hour, '300') for i in range(62)]
        h1[-2] = bar(800*hour, '290')
        h1[-1] = bar(801*hour, '310')
        original = evaluate(h1, h4, '.01')
        self.assertEqual(len(original), 1)
        changed = copy.deepcopy(h4)
        changed[201:] = [bar(i * 4 * hour, '1') for i in range(201, 205)]
        self.assertEqual(evaluate(h1, changed, '.01'), original)


class JournalTests(unittest.TestCase):
    def test_empty_report_does_not_claim_edge(self):
        r = report([])
        self.assertIsNone(r['mean_net_r'])
        self.assertFalse(r['live_eligible'])

    def test_linked_outcomes_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'paper.jsonl'
            signal = {'type':'signal','mode':'paper','strategy':'TPB-v1','symbol':'BTCUSDT',
                      'timestamp':NOW.isoformat(),'decision':'paper','reason':'synthetic fixture',
                      'initial_risk_usdt':'.5','entry':'100','stop':'98','target':'107',
                      'quantity':'.2','estimated_cost_usdt':'.04'}
            ident = append(path, signal)
            with self.assertRaises(ValueError): append(path, signal)
            overlap = dict(signal, timestamp='2026-09-24T12:01:00+00:00')
            with self.assertRaises(ValueError): append(path, overlap)
            equivalent_time = dict(signal, timestamp='2026-09-24T13:00:00+01:00')
            with self.assertRaises(ValueError): append(path, equivalent_time)
            outcome = {'type':'outcome','mode':'paper','strategy':'TPB-v1','symbol':'BTCUSDT',
                       'timestamp':NOW.isoformat(),'reason':'synthetic fixture','signal_id':ident,
                       'net_pnl_usdt':'1','observed_cost_usdt':'.04','exit_price':'107'}
            append(path, outcome)
            with self.assertRaises(ValueError): append(path, outcome)
            events = [json.loads(line) for line in path.read_text().splitlines()]
            r = report(events)
            self.assertEqual(r['closed_trades'], 1)
            self.assertEqual(r['mean_net_r'], 2)
            correction = {'type':'void','mode':'paper','strategy':'TPB-v1','symbol':'BTCUSDT',
                          'timestamp':NOW.isoformat(),'reason':'correct synthetic result',
                          'voids_id':events[1]['id']}
            append(path, correction)
            with self.assertRaises(ValueError): append(path, correction)
            outcome['net_pnl_usdt'] = '-.5'
            append(path, outcome)
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(events), 4)
            self.assertEqual(report(events)['mean_net_r'], -1)

    def test_invalid_paper_event_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'paper.jsonl'
            with self.assertRaises(ValueError):
                append(path, {'type':'signal','mode':'live','strategy':'TPB-v1','symbol':'BTCUSDT',
                              'timestamp':NOW.isoformat(),'decision':'skip','reason':'fixture'})


if __name__ == '__main__':
    unittest.main()
