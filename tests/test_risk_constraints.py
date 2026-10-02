"""Synthetic feasible-size regressions; no market calls or journal writes."""
import unittest
from decimal import Decimal, ROUND_FLOOR
from fractions import Fraction

from test_research import NOW, plan
from tools.risk import _largest_reward_feasible_units, size_plan


class FeasibleSizeTests(unittest.TestCase):
    def test_base_fee_rounding_selects_smaller_reward_feasible_size(self):
        p = plan()
        p['plan'].update(quantity_step='.0001', target='104.95')
        result = size_plan(p, NOW, risk_cap_usdt='.24')
        self.assertEqual(result['gross_buy_quantity'], Decimal('.1000'))
        self.assertEqual(result['protected_sell_quantity'], Decimal('.0999'))
        self.assertEqual(result['planned_loss_usdt'], Decimal('.229580205'))
        self.assertGreaterEqual(result['net_reward_risk'], 2)
        self.assertLessEqual(result['planned_loss_usdt'], Decimal('.24'))
        # Lower sizes cannot rescue a minimum exceeded by the largest RR pass.
        for minimum in ({'min_quantity': '.1001'}, {'min_notional': '10'}):
            with self.subTest(minimum=minimum):
                p['plan'].update({'min_quantity': '.001', 'min_notional': '5', **minimum})
                with self.assertRaisesRegex(ValueError, 'minimum'):
                    size_plan(p, NOW, risk_cap_usdt='.24')

    def test_reward_rounding_matches_exhaustive_orders_under_joint_limits(self):
        # The independent oracle evaluates every allowed order; it does not
        # assume reward/risk is monotonic or use the production search helpers.
        step, sell_fee = Decimal('.1'), Decimal('.001')
        for fee_currency in ('base', 'quote'):
            for buy_fee in map(Decimal, ('0', '.025', '.05')):
                for target in map(Decimal, ('1.24', '1.31', '1.5')):
                    for cash in map(Decimal, ('2', '1000')):
                        for maximum in map(Decimal, ('2.5', '8')):
                            for cap in map(Decimal, ('.341', '.5', '1')):
                                with self.subTest(fee=fee_currency, buy_fee=buy_fee, target=target,
                                                  cash=cash, maximum=maximum, cap=cap):
                                    p = plan()
                                    p['account'].update(equity_usdt='1000', available_usdt=str(cash),
                                                        day_start_equity_usdt='1000', week_start_equity_usdt='1000')
                                    p['plan'].update(entry='1', stop='.9', target=str(target), slippage_rate='0',
                                                     quantity_step=str(step), min_quantity='.2', max_quantity='6',
                                                     min_notional='1', max_notional=str(maximum),
                                                     buy_fee_currency=fee_currency, buy_fee_rate=str(buy_fee))
                                    feasible = []
                                    for units in range(1, 61):
                                        qty = units * step
                                        inventory = qty * (1 - buy_fee) if fee_currency == 'base' else qty
                                        sell = (inventory / step).to_integral_value(rounding=ROUND_FLOOR) * step
                                        spent = qty * (1 + buy_fee if fee_currency == 'quote' else 1)
                                        loss = spent - sell * Decimal('.9') * (1 - sell_fee)
                                        reward = sell * target * (1 - sell_fee) - spent
                                        if (min(qty, sell) >= Decimal('.2') and spent <= cash
                                                and 0 < loss <= cap and qty <= maximum
                                                and sell * target <= maximum
                                                and min(qty, sell * Decimal('.9')) >= 1
                                                and reward >= 2 * loss):
                                            feasible.append(qty)
                                    if feasible:
                                        result = size_plan(p, NOW, risk_cap_usdt=cap)
                                        self.assertEqual(result['gross_buy_quantity'], max(feasible))
                                    else:
                                        with self.assertRaises(ValueError):
                                            size_plan(p, NOW, risk_cap_usdt=cap)

    def test_reward_search_handles_sparse_exact_boundary_without_linear_scan(self):
        # At equal slopes, only denominator multiples have no fee-rounding dust.
        denominator = 10 ** 12
        fraction = Fraction(denominator - 1, denominator)
        self.assertEqual(_largest_reward_feasible_units(denominator - 1, fraction, fraction), 0)
        self.assertEqual(_largest_reward_feasible_units(2 * denominator - 1, fraction, fraction), denominator)
        self.assertEqual(_largest_reward_feasible_units(denominator, fraction, Fraction(1)), 0)

    def test_target_notional_limit_reduces_size_instead_of_rejecting(self):
        p = plan()
        p['plan']['max_notional'] = '22'
        r = size_plan(p, NOW)
        self.assertGreaterEqual(r['gross_buy_quantity'], Decimal('.2'))
        self.assertLessEqual(r['protected_sell_quantity'] * r['target_fill_assumption'], 22)
        self.assertLessEqual(r['planned_loss_usdt'], Decimal('.5'))
        self.assertGreaterEqual(r['net_reward_risk'], 2)
        # The very next gross increment would exceed the exit maximum.
        step = Decimal(p['plan']['quantity_step'])
        next_q = r['gross_buy_quantity'] + step
        next_sell = (next_q * Decimal('.999') / step).to_integral_value(rounding=ROUND_FLOOR) * step
        self.assertGreater(next_sell * r['target_fill_assumption'], 22)

    def test_additional_risk_cap_sizes_down_and_never_enlarges_policy(self):
        baseline = size_plan(plan(), NOW)
        small = size_plan(plan(), NOW, risk_cap_usdt='.341')
        self.assertLess(small['gross_buy_quantity'], baseline['gross_buy_quantity'])
        self.assertLessEqual(small['planned_loss_usdt'], Decimal('.341'))
        self.assertIn('additional_risk_cap', small['binding_limits'])
        loose = size_plan(plan(), NOW, risk_cap_usdt='100')
        self.assertEqual(loose['gross_buy_quantity'], baseline['gross_buy_quantity'])
        self.assertEqual(loose['planned_loss_usdt'], baseline['planned_loss_usdt'])
        for bad in ('0', '-1', 'NaN', 'Infinity', True):
            with self.subTest(bad=bad), self.assertRaises((ValueError, ArithmeticError)):
                size_plan(plan(), NOW, risk_cap_usdt=bad)

    def test_additional_cap_preserves_halts_minimums_and_reward_rejections(self):
        p = plan()
        p['account']['day_halted'] = True
        with self.assertRaisesRegex(ValueError, 'halt'):
            size_plan(p, NOW, risk_cap_usdt='100')
        with self.assertRaisesRegex(ValueError, 'minimum'):
            size_plan(plan(), NOW, risk_cap_usdt='.001')
        p = plan()
        p['plan']['target'] = '101'
        with self.assertRaisesRegex(ValueError, 'reward/risk'):
            size_plan(p, NOW, risk_cap_usdt='.341')

    def test_joint_caps_match_exhaustive_feasible_quantities(self):
        # Independent enumeration on a small grid, including base-fee rounding.
        # This checks the largest allowable size, not the binary-search mechanics.
        step, buy_fee, sell_fee = Decimal('.01'), Decimal('.001'), Decimal('.001')
        for fee_currency in ('base', 'quote'):
            for cash in ('100', '15'):
                for maximum in ('18', '22', '100000'):
                    for cap in (Decimal('.341'), Decimal('.5')):
                        with self.subTest(fee=fee_currency, cash=cash, maximum=maximum, cap=cap):
                            p = plan()
                            p['account']['available_usdt'] = cash
                            p['plan'].update(quantity_step=str(step), buy_fee_currency=fee_currency,
                                             max_notional=maximum)
                            feasible = []
                            for units in range(1, 31):
                                qty = units * step
                                inventory = qty * (1 - buy_fee) if fee_currency == 'base' else qty
                                sell = (inventory / step).to_integral_value(rounding=ROUND_FLOOR) * step
                                spent = qty * Decimal('100.05') * (1 + buy_fee if fee_currency == 'quote' else 1)
                                loss = spent - sell * Decimal('97.95') * (1 - sell_fee)
                                reward = sell * Decimal('106.94') * (1 - sell_fee) - spent
                                if (sell > 0 and spent <= Decimal(cash) and 0 < loss <= cap
                                        and qty * Decimal('100.05') <= Decimal(maximum)
                                        and sell * Decimal('106.94') <= Decimal(maximum)
                                        and sell * Decimal('97.95') >= 5 and reward / loss >= 2):
                                    feasible.append(qty)
                            if not feasible:
                                with self.assertRaises(ValueError):
                                    size_plan(p, NOW, risk_cap_usdt=cap)
                            else:
                                result = size_plan(p, NOW, risk_cap_usdt=cap)
                                self.assertEqual(result['gross_buy_quantity'], max(feasible))


if __name__ == '__main__':
    unittest.main()
