"""Synthetic manual paper evidence; never written to the project's comparison ledger."""
import copy
import fcntl
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from threading import Event
from unittest.mock import patch

from tools.manual_ledger import apply_event, append_event, initial_state, read_events, replay, report


AT = datetime(2026, 10, 2, 10, 15, 20, tzinfo=timezone.utc)


def event(kind, identifier, at=AT, **fields):
    return {'id': identifier, 'type': kind, 'arm': 'FBR-v1', 'mode': 'paper',
            'at': at.isoformat(), 'evidence': 'synthetic-fixture', **fields}


def entry(identifier='entry1', at=AT):
    return event('entry', identifier, at, symbol='BTCUSDT', bid='99.99', max_entry_ask='100',
                 confirmation_at=(at - timedelta(seconds=20)).isoformat(),
                 entry_expires_at=(at.replace(second=0, microsecond=0) + timedelta(minutes=15)).isoformat(),
                 card_reference='synthetic-card', plan={
                     'as_of': at.isoformat(), 'entry': '100', 'stop': '98', 'target': '108',
                     'buy_fee_rate': '.001', 'sell_fee_rate': '.001',
                     'buy_fee_currency': 'base', 'sell_fee_currency': 'quote',
                     'slippage_rate': '.000549975', 'quantity_step': '.001', 'price_tick': '.01',
                     'min_quantity': '0', 'max_quantity': '100',
                     'min_notional': '5', 'max_notional': '100000'})


def assessment(state, identifier='exit1', exposure='flat', pnls=('-0.45', '1.00'), at=None):
    p = state['arms']['FBR-v1']['position']
    return event('exit_assessment', identifier, at or AT + timedelta(minutes=1),
                 entry_id=p['entry_id'], exposure=exposure, bid='100',
                 outcomes=[{'label': f'path{i}', 'net_proceeds_usdt': str(p['spent'] + D(pnl))}
                           for i, pnl in enumerate(pnls)])


def reconciliation(state, identifier='proof1', exposure='open', pnls=('1',), at=None):
    position = state['arms']['FBR-v1']['position']
    result = event('reconcile_exposure', identifier, at or AT + timedelta(minutes=2),
                   entry_id=position['entry_id'],
                   assessment_id=position['assessment_history'][-1]['id'],
                   evidence='finer-synthetic-evidence',
                   resolution_reason='Finer chronological evidence excludes the earlier exit path.',
                   exposure=exposure, bid='101')
    if exposure == 'flat':
        result['outcomes'] = [{'label': f'proven-path{i}',
                               'net_proceeds_usdt': str(position['spent'] + D(pnl))}
                              for i, pnl in enumerate(pnls)]
    return result


class ManualLedgerTests(unittest.TestCase):
    def test_conservative_period_allowance_sizes_down_instead_of_rejecting(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, pnls=('-0.45', '1.20')))
        tomorrow = AT + timedelta(days=1)
        state = apply_event(state, event('mark', 'next-day', tomorrow))
        account = state['arms']['FBR-v1']
        allowance = account['day_start']['lower'] * D('.02') - (
            account['day_start']['upper'] - account['cash']['lower'])
        self.assertEqual(allowance, D('.341'))
        self.assertFalse(account['day_halted'])
        self.assertFalse(account['week_halted'])
        state = apply_event(state, entry('entry2', tomorrow))
        result = state['arms']['FBR-v1']['position']['entry_calculation']
        self.assertGreater(result['planned_loss_usdt'], 0)
        self.assertLessEqual(result['planned_loss_usdt'], allowance)
        self.assertLess(result['gross_buy_quantity'], D('.2'))
        self.assertGreaterEqual(result['net_reward_risk'], 2)

    def test_zero_conservative_allowance_still_rejects_and_tiny_size_must_meet_minimum(self):
        for upper_pnl, expected in (('1.541', 'No conservative'), ('1.54', 'minimum')):
            with self.subTest(upper_pnl=upper_pnl):
                state = apply_event(initial_state(), entry())
                state = apply_event(state, assessment(state, pnls=('-0.45', upper_pnl)))
                tomorrow = AT + timedelta(days=1)
                # Entry itself rolls the flat account; it cannot enter before the final halt check.
                with self.assertRaisesRegex(ValueError, expected):
                    apply_event(state, entry('entry2', tomorrow))

    def test_finer_evidence_can_prove_still_open_without_changing_cash_or_inventory(self):
        first = entry()
        state = apply_event(initial_state(), first)
        cash = copy.deepcopy(state['arms']['FBR-v1']['cash'])
        quantity = state['arms']['FBR-v1']['position']['quantity']
        uncertain = assessment(state, exposure='open_or_flat', pnls=('-0.45',))
        state = apply_event(state, uncertain)
        original = copy.deepcopy(state['arms']['FBR-v1']['position']['assessment_history'][0])
        proof = reconciliation(state)
        state = apply_event(state, proof)
        account = state['arms']['FBR-v1']
        position = account['position']
        self.assertEqual(account['cash'], cash)
        self.assertEqual(position['quantity'], quantity)
        self.assertEqual(position['exposure'], 'open')
        self.assertEqual(position['possible_net_proceeds'], [])
        self.assertEqual(account['equity']['lower'], cash['lower'] + quantity * D('101'))
        self.assertEqual(account['equity']['lower'], account['equity']['upper'])
        self.assertEqual(position['assessment_history'][0], original)
        self.assertEqual(position['assessment_history'][1]['supersedes_assessment_id'], uncertain['id'])
        self.assertEqual(replay([first, uncertain, proof]), state)
        with self.assertRaisesRegex(ValueError, 'One-position'):
            apply_event(state, entry('blocked', AT + timedelta(minutes=15)))

    def test_finer_evidence_can_close_directly_at_proven_proceeds_charging_fees_once(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, exposure='open_or_flat', pnls=('-0.45',)))
        original = copy.deepcopy(state['arms']['FBR-v1']['position']['assessment_history'][0])
        proof = reconciliation(state, exposure='flat', pnls=('1.25',))
        state = apply_event(state, proof)
        account = state['arms']['FBR-v1']
        self.assertIsNone(account['position'])
        self.assertEqual(account['cash'], {'lower': D('101.25'), 'upper': D('101.25')})
        trade = account['trades'][0]
        self.assertEqual(trade['outcome_certainty'], 'resolved')
        self.assertEqual(trade['net_pnl_usdt'], D('1.25'))
        self.assertEqual(trade['assessment_history'][0], original)
        self.assertEqual(trade['assessment_history'][1]['resolution_reason'], proof['resolution_reason'])

    def test_finer_evidence_can_close_with_narrower_bounds_then_resolve_normally(self):
        state = apply_event(initial_state(), entry())
        spent = state['arms']['FBR-v1']['position']['spent']
        state = apply_event(state, assessment(state, exposure='open_or_flat', pnls=('-0.45', '1.25')))
        state = apply_event(state, reconciliation(state, exposure='flat', pnls=('.5', '1.25')))
        account = state['arms']['FBR-v1']
        self.assertIsNone(account['position'])
        self.assertEqual(account['cash'], {'lower': D('100.5'), 'upper': D('101.25')})
        self.assertIsNone(account['trades'][0]['net_pnl_usdt'])
        state = apply_event(state, event('resolve_outcome', 'final', AT + timedelta(minutes=3),
                                        entry_id='entry1', net_proceeds_usdt=str(spent + 1)))
        self.assertEqual(state['arms']['FBR-v1']['cash'], {'lower': D('101'), 'upper': D('101')})
        self.assertEqual(len(state['arms']['FBR-v1']['trades'][0]['assessment_history']), 2)

    def test_reconciliation_preserves_halts_reviews_and_fixed_period_budgets(self):
        for exposure in ('open', 'flat'):
            with self.subTest(exposure=exposure):
                state = apply_event(initial_state(), entry())
                state = apply_event(state, assessment(state, exposure='open_or_flat', pnls=('-5',)))
                before = copy.deepcopy(state['arms']['FBR-v1'])
                self.assertTrue(before['day_halted'])
                self.assertTrue(before['week_halted'])
                self.assertTrue(before['setup_review_required'])
                state = apply_event(state, reconciliation(state, exposure=exposure))
                after = state['arms']['FBR-v1']
                for field in ('day_halted', 'week_halted', 'setup_review_required', 'day_start', 'week_start'):
                    self.assertEqual(after[field], before[field])

    def test_reconciliation_requires_current_link_new_evidence_reason_and_supported_exposure(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, exposure='open_or_flat', pnls=('-0.45',)))
        proof = reconciliation(state)
        changes = [({'entry_id': 'wrong'}, 'outstanding entry'),
                   ({'assessment_id': 'wrong'}, 'latest outstanding'),
                   ({'resolution_reason': ''}, 'resolution reason'),
                   ({'evidence': ''}, 'Evidence reference'),
                   ({'evidence': 'synthetic-fixture'}, 'new evidence'),
                   ({'exposure': 'partial'}, 'partial exits'),
                   ({'exposure': 'open_or_flat'}, 'proven open or flat'),
                   ({'outcomes': []}, 'must not declare'),
                   ({'net_proceeds_usdt': '20'}, 'must not declare'),
                   ({'bid': '0'}, 'positive number')]
        before = copy.deepcopy(state)
        for fields, message in changes:
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, message):
                apply_event(state, dict(proof, **fields))
        self.assertEqual(state, before)
        later = assessment(state, 'new-assessment', exposure='open_or_flat', pnls=('-0.45', '1'),
                           at=AT + timedelta(minutes=2))
        state = apply_event(state, later)
        with self.assertRaisesRegex(ValueError, 'latest outstanding'):
            apply_event(state, dict(proof, at=(AT + timedelta(minutes=3)).isoformat()))

    def test_reconciliation_cannot_be_repeated_or_used_without_uncertain_exposure(self):
        state = apply_event(initial_state(), entry())
        fake = event('reconcile_exposure', 'fake', AT + timedelta(minutes=1), entry_id='entry1')
        with self.assertRaisesRegex(ValueError, 'uncertain exposure'):
            apply_event(state, fake)
        state = apply_event(state, assessment(state, exposure='open_or_flat', pnls=('-0.45',)))
        proof = reconciliation(state)
        state = apply_event(state, proof)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            apply_event(state, proof)
        with self.assertRaisesRegex(ValueError, 'uncertain exposure'):
            apply_event(state, dict(proof, id='repeat'))
        # Ordinary closure works after disproving the earlier possible exit.
        state = apply_event(state, assessment(state, 'closed', pnls=('1',),
                                               at=AT + timedelta(minutes=3)))
        self.assertEqual(state['arms']['FBR-v1']['cash']['lower'], D('101'))
        with self.assertRaisesRegex(ValueError, 'outstanding entry'):
            apply_event(state, dict(proof, id='after-close', at=(AT + timedelta(minutes=4)).isoformat()))

    def test_flat_reconciliation_rejects_invalid_proceeds_and_preserves_original_event_log(self):
        first = entry()
        state = apply_event(initial_state(), first)
        uncertain = assessment(state, exposure='open_or_flat', pnls=('-0.45',))
        state = apply_event(state, uncertain)
        proof = reconciliation(state, exposure='flat')
        for outcomes in ([], [{'label': 'bad', 'net_proceeds_usdt': '-1'}],
                         [{'label': 'bad', 'net_proceeds_usdt': 'NaN'}], ['not-an-object']):
            with self.subTest(outcomes=outcomes), self.assertRaises(ValueError):
                apply_event(state, dict(proof, outcomes=outcomes))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            append_event(path, first, now=AT)
            append_event(path, uncertain, now=AT + timedelta(minutes=1))
            original = path.read_bytes()
            appended = append_event(path, proof, now=AT + timedelta(minutes=2))
            self.assertTrue(path.read_bytes().startswith(original))
            self.assertEqual(replay(read_events(path)), appended)

    def test_all_arms_enforce_frozen_spread_fees_and_slippage(self):
        changes = [({'bid': '99.89'}, None, 'spread'),
                   ({}, {'buy_fee_rate': '0'}, 'fee model'),
                   ({}, {'sell_fee_rate': '0'}, 'fee model'),
                   ({}, {'buy_fee_currency': 'quote'}, 'fee model'),
                   ({}, {'sell_fee_currency': 'base'}, 'fee model'),
                   ({}, {'slippage_rate': '0'}, 'slippage'),
                   ({}, {'slippage_rate': '.00055'}, 'slippage')]
        for arm in ('MPB-v1', 'MBR-v1', 'FBR-v1'):
            for fields, plan, message in changes:
                with self.subTest(arm=arm, fields=fields, plan=plan):
                    e = dict(entry(), arm=arm, **fields)
                    e['plan'].update(plan or {})
                    with self.assertRaisesRegex(ValueError, message):
                        apply_event(initial_state(), e)
        at_limit = entry()
        at_limit['bid'] = '99.90'
        at_limit['plan']['slippage_rate'] = '.00099975'
        self.assertIsNotNone(apply_event(initial_state(), at_limit)['arms']['FBR-v1']['position'])

    def test_risk_overshoot_blocks_until_recorded_review_and_survives_day_change(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, pnls=('-0.75',)))
        self.assertTrue(state['arms']['FBR-v1']['setup_review_required'])
        tomorrow = AT + timedelta(days=1)
        state = apply_event(state, event('mark', 'next-day', tomorrow))
        with self.assertRaisesRegex(ValueError, 'Setup review required'):
            apply_event(state, entry('blocked', tomorrow))
        before = copy.deepcopy(state['arms']['FBR-v1'])
        review = event('review', 'review1', tomorrow,
                       corrective_action='Record the observed gap and confirm model scope.',
                       resumption_reason='Cause and corrective action reviewed; frozen rules retained.')
        for field in ('corrective_action', 'resumption_reason', 'evidence'):
            with self.subTest(missing=field), self.assertRaises(ValueError):
                apply_event(state, dict(review, **{field: ''}))
        state = apply_event(state, review)
        account = state['arms']['FBR-v1']
        self.assertFalse(account['setup_review_required'])
        for field in ('cash', 'equity', 'day_start', 'week_start', 'day_halted', 'week_halted', 'trades'):
            self.assertEqual(account[field], before[field])
        self.assertEqual(account['reviews'][0]['id'], 'review1')
        state = apply_event(state, entry('resumed', tomorrow))
        self.assertIsNotNone(state['arms']['FBR-v1']['position'])

    def test_bounded_loss_overshoot_requires_review_even_after_winning_resolution(self):
        state = apply_event(initial_state(), entry())
        spent = state['arms']['FBR-v1']['position']['spent']
        state = apply_event(state, assessment(state, pnls=('-0.75', '1')))
        self.assertTrue(state['arms']['FBR-v1']['setup_review_required'])
        state = apply_event(state, event('resolve_outcome', 'resolve', AT + timedelta(minutes=2),
                                        entry_id='entry1', net_proceeds_usdt=str(spent + 1)))
        self.assertTrue(state['arms']['FBR-v1']['setup_review_required'])

    def test_loss_exactly_at_planned_risk_does_not_require_overshoot_review(self):
        state = apply_event(initial_state(), entry())
        risk = state['arms']['FBR-v1']['position']['planned_risk']
        state = apply_event(state, assessment(state, pnls=(str(-risk),)))
        self.assertFalse(state['arms']['FBR-v1']['setup_review_required'])

    def test_review_never_clears_daily_or_weekly_halts(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, pnls=('-5',)))
        review = event('review', 'review1', AT + timedelta(minutes=2),
                       corrective_action='Document unexpected execution loss.',
                       resumption_reason='Model reviewed; period halt still applies.')
        state = apply_event(state, review)
        account = state['arms']['FBR-v1']
        self.assertFalse(account['setup_review_required'])
        self.assertTrue(account['day_halted'])
        self.assertTrue(account['week_halted'])
        with self.assertRaisesRegex(ValueError, 'halt'):
            apply_event(state, entry('blocked', AT + timedelta(minutes=15)))

    def test_ambiguous_pnl_known_flat_releases_slot_with_lower_cash(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state))
        a = report(state)['arms']['FBR-v1']
        self.assertEqual(a['exposure'], 'flat')
        self.assertEqual(a['cash'], {'lower': D('99.55'), 'upper': D('101')})
        self.assertEqual(a['bounded_count'], 1)
        self.assertIsNone(a['trades'][0]['net_pnl_usdt'])
        self.assertIsNone(a['mean_resolved_r'])
        second = entry('entry2', AT + timedelta(minutes=15))
        state = apply_event(state, second)
        calc = state['arms']['FBR-v1']['position']['entry_calculation']
        self.assertEqual(calc['budgets_usdt']['default'], D('99.55') * D('.005'))

    def test_unknown_exposure_blocks_and_later_flat_keeps_earlier_loss_possible(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, exposure='open_or_flat', pnls=('-0.45',)))
        self.assertEqual(report(state)['arms']['FBR-v1']['exposure'], 'open_or_flat')
        with self.assertRaisesRegex(ValueError, 'One-position'):
            apply_event(state, entry('entry2', AT + timedelta(minutes=15)))
        optimistic = assessment(state, 'later', pnls=('1.00',), at=AT + timedelta(minutes=2))
        with self.assertRaisesRegex(ValueError, 'earlier possible exit'):
            apply_event(state, optimistic)
        flat = assessment(state, 'later', pnls=('-0.45', '1.00'), at=AT + timedelta(minutes=2))
        result = apply_event(state, flat)
        self.assertIsNone(result['arms']['FBR-v1']['position'])
        self.assertIsNone(result['arms']['FBR-v1']['trades'][0]['net_r'])

    def test_entry_inventory_and_fees_not_counted_twice(self):
        state = apply_event(initial_state(), entry())
        p = state['arms']['FBR-v1']['position']
        self.assertLess(p['quantity'], p['entry_calculation']['gross_buy_quantity'])
        state = apply_event(state, assessment(state, pnls=('1.25',)))
        self.assertEqual(state['arms']['FBR-v1']['cash'], {'lower': D('101.25'), 'upper': D('101.25')})

    def test_daily_halt_persists_after_marked_recovery(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, event('mark', 'crash', AT + timedelta(minutes=1), bid='50'))
        self.assertTrue(state['arms']['FBR-v1']['day_halted'])
        state = apply_event(state, assessment(state, pnls=('1',), at=AT + timedelta(minutes=2)))
        self.assertTrue(state['arms']['FBR-v1']['day_halted'])
        with self.assertRaisesRegex(ValueError, 'halt'):
            apply_event(state, entry('entry2', AT + timedelta(minutes=15)))

    def test_weekly_halt_persists_across_new_day(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, pnls=('-5',)))
        tomorrow = AT + timedelta(days=1)
        state = apply_event(state, event('mark', 'next-day', tomorrow))
        self.assertFalse(state['arms']['FBR-v1']['day_halted'])
        self.assertTrue(state['arms']['FBR-v1']['week_halted'])
        with self.assertRaisesRegex(ValueError, 'halt'):
            apply_event(state, entry('entry2', tomorrow))

    def test_uncertain_loss_bounds_trigger_halt_without_fabricating_loss(self):
        state = apply_event(initial_state(), entry())
        state = apply_event(state, assessment(state, pnls=('-2.1', '1')))
        account = state['arms']['FBR-v1']
        self.assertTrue(account['day_halted'])
        self.assertIsNone(account['trades'][0]['net_pnl_usdt'])

    def test_resolution_preserves_record_and_does_not_clear_latched_halt(self):
        state = apply_event(initial_state(), entry())
        spent = state['arms']['FBR-v1']['position']['spent']
        state = apply_event(state, assessment(state, pnls=('-2.1', '1')))
        resolution = event('resolve_outcome', 'resolve', AT + timedelta(minutes=2),
                           entry_id='entry1', net_proceeds_usdt=str(spent + 1))
        state = apply_event(state, resolution)
        account = state['arms']['FBR-v1']
        self.assertEqual(account['cash'], {'lower': D('101'), 'upper': D('101')})
        self.assertEqual(account['trades'][0]['net_pnl_usdt'], D('1'))
        self.assertIn('original_net_proceeds_bounds', account['trades'][0])
        self.assertTrue(account['day_halted'])
        with self.assertRaisesRegex(ValueError, 'previously bounded'):
            apply_event(state, dict(resolution, id='resolve-again'))

    def test_open_exposure_requires_each_midnight_boundary(self):
        near_midnight = datetime(2026, 10, 2, 22, 45, 20, tzinfo=timezone.utc)
        state = apply_event(initial_state(), entry(at=near_midnight))
        with self.assertRaisesRegex(ValueError, 'midnight boundary'):
            apply_event(state, event('mark', 'late', near_midnight + timedelta(hours=1), bid='100'))
        boundary = event('boundary', 'midnight', datetime(2026, 10, 2, 23, tzinfo=timezone.utc), bid='100')
        state = apply_event(state, boundary)
        self.assertEqual(state['arms']['FBR-v1']['day'], '2026-10-03')
        with self.assertRaisesRegex(ValueError, 'each crossed day'):
            apply_event(state, event('boundary', 'skip', datetime(2026, 10, 4, 23, tzinfo=timezone.utc), bid='100'))

    def test_duplicate_entry_exit_wrong_link_and_backdating_rejected(self):
        first = entry()
        state = apply_event(initial_state(), first)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            apply_event(state, first)
        with self.assertRaisesRegex(ValueError, 'One-position'):
            apply_event(state, entry('entry2'))
        exit_event = assessment(state, pnls=('1',))
        with self.assertRaisesRegex(ValueError, 'outstanding entry'):
            apply_event(state, dict(exit_event, entry_id='missing'))
        state = apply_event(state, exit_event)
        with self.assertRaisesRegex(ValueError, 'outstanding entry'):
            apply_event(state, dict(exit_event, id='exit2'))
        with self.assertRaisesRegex(ValueError, 'Backdated'):
            apply_event(state, event('mark', 'backdated', AT))

    def test_event_ids_require_strings_and_missing_exit_links_are_rejected(self):
        for identifier in (None, 1, True):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, 'event ID'):
                apply_event(initial_state(), entry(identifier))
        state = apply_event(initial_state(), entry())
        exit_event = assessment(state)
        del exit_event['entry_id']
        with self.assertRaisesRegex(ValueError, 'outstanding entry'):
            apply_event(state, exit_event)

    def test_actual_quote_timestamp_must_follow_confirmation_and_be_fresh(self):
        e = entry()
        e['plan']['as_of'] = (AT - timedelta(seconds=30)).isoformat()
        with self.assertRaisesRegex(ValueError, 'Quote must follow'):
            apply_event(initial_state(), e)
        e = entry(at=AT + timedelta(seconds=90))
        e['confirmation_at'] = AT.isoformat()
        e['plan']['as_of'] = AT.isoformat()
        e['entry_expires_at'] = AT.replace(minute=30, second=0, microsecond=0).isoformat()
        with self.assertRaisesRegex(ValueError, 'Stale'):
            apply_event(initial_state(), e)

    def test_arms_are_independent_and_partial_exits_unsupported(self):
        state = apply_event(initial_state(), entry())
        other = dict(entry('other'), arm='MBR-v1')
        state = apply_event(state, other)
        self.assertIsNotNone(state['arms']['FBR-v1']['position'])
        self.assertIsNotNone(state['arms']['MBR-v1']['position'])
        with self.assertRaisesRegex(ValueError, 'partial exits unsupported'):
            apply_event(state, assessment(state, exposure='partial'))
        with self.assertRaisesRegex(ValueError, 'Only explicit paper'):
            apply_event(initial_state(), dict(entry(), mode='live'))

    def test_validation_before_append_and_replay_no_hidden_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            first = entry()
            state = append_event(path, first, now=AT)
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                append_event(path, first, now=AT)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(replay(read_events(path)), state)
            with self.assertRaisesRegex(ValueError, 'prospectively'):
                append_event(path, entry('late'), now=AT + timedelta(minutes=2))
            self.assertEqual(path.read_bytes(), before)

    def test_append_preserves_replay_when_prior_event_has_no_final_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            original = json.dumps(entry())
            path.write_text(original)
            mark = event('mark', 'mark1', AT + timedelta(seconds=1), bid='100')
            state = append_event(path, mark, now=AT + timedelta(seconds=1))
            self.assertTrue(path.read_text().startswith(original + '\n'))
            self.assertEqual(state['event_ids'], ['entry1', 'mark1'])
            self.assertEqual(replay(read_events(path)), state)

    def test_entry_expiring_while_waiting_for_lock_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            path.write_text(json.dumps(event('mark', 'prior', AT - timedelta(seconds=1))))
            before = path.read_bytes()
            current, attempted = [AT], Event()
            real_flock = fcntl.flock

            def acquire(lock, operation):
                attempted.set()
                return real_flock(lock, operation)

            with path.with_suffix('.jsonl.lock').open('a') as held:
                real_flock(held, fcntl.LOCK_EX)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    with patch('tools.manual_ledger.fcntl.flock', side_effect=acquire):
                        pending = executor.submit(append_event, path, entry(), clock=lambda: current[0])
                        try:
                            self.assertTrue(attempted.wait(timeout=3), 'Appender did not reach the lock')
                            current[0] = AT + timedelta(seconds=61)
                        finally:
                            real_flock(held, fcntl.LOCK_UN)
                        with self.assertRaisesRegex(ValueError, 'prospectively'):
                            pending.result(timeout=3)
            self.assertEqual(path.read_bytes(), before)

    def test_entry_expiring_during_replay_or_encoding_does_not_write(self):
        for stage in ('replay', 'encoding'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'events.jsonl'
                # The missing separator must also remain untouched on rejection.
                path.write_text(json.dumps(event('mark', 'prior', AT - timedelta(seconds=1))))
                before = path.read_bytes()
                current = [AT]
                operation = replay if stage == 'replay' else json.dumps

                def delayed(*args, **kwargs):
                    result = operation(*args, **kwargs)
                    current[0] += timedelta(seconds=61)
                    return result

                target = 'tools.manual_ledger.' + ('replay' if stage == 'replay' else 'json.dumps')
                with patch(target, side_effect=delayed):
                    with self.assertRaisesRegex(ValueError, 'prospectively'):
                        append_event(path, entry(), clock=lambda: current[0])
                self.assertEqual(path.read_bytes(), before)

    def test_production_append_refreshes_wall_clock_after_lock_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            with patch('tools.manual_ledger.datetime', wraps=datetime) as wall_clock:
                wall_clock.now.side_effect = [AT, AT, AT + timedelta(seconds=61)]
                with self.assertRaisesRegex(ValueError, 'prospectively'):
                    append_event(path, entry())
            self.assertFalse(path.exists())

    def test_entry_expiring_while_opening_append_stream_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            path.write_text(json.dumps(event('mark', 'prior', AT - timedelta(seconds=1))))
            before, current, real_open = path.read_bytes(), [AT], Path.open

            def delayed_open(candidate, mode='r', *args, **kwargs):
                result = real_open(candidate, mode, *args, **kwargs)
                if candidate == path and mode == 'a':
                    current[0] += timedelta(seconds=61)
                return result

            with patch('tools.manual_ledger.Path.open', autospec=True, side_effect=delayed_open):
                with self.assertRaisesRegex(ValueError, 'prospectively'):
                    append_event(path, entry(), clock=lambda: current[0])
            self.assertEqual(path.read_bytes(), before)

    def test_quote_age_and_entry_deadline_cannot_expire_during_append(self):
        for stage in ('quote', 'deadline'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'events.jsonl'
                paper_entry = entry()
                if stage == 'quote':
                    paper_entry['plan']['as_of'] = (AT - timedelta(seconds=20)).isoformat()
                    later = AT + timedelta(seconds=41)
                    message = 'quote must remain fresh'
                else:
                    paper_entry['entry_expires_at'] = (AT + timedelta(seconds=30)).isoformat()
                    later = AT + timedelta(seconds=30)
                    message = 'entry expiry'
                moments = iter([AT, AT, later])
                with self.assertRaisesRegex(ValueError, message):
                    append_event(path, paper_entry, clock=lambda: next(moments))
                self.assertFalse(path.exists())

    def test_recent_entry_preserves_observed_timestamp_when_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            moments = iter([AT, AT + timedelta(seconds=5), AT + timedelta(seconds=60),
                            AT + timedelta(seconds=60)])
            paper_entry = entry()
            state = append_event(path, paper_entry, clock=lambda: next(moments))
            self.assertEqual(read_events(path), [paper_entry])
            self.assertEqual(replay(read_events(path)), state)

    def test_historical_nonentry_allowed_but_future_guard_is_rechecked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            historical = event('mark', 'historical')
            moments = iter([AT + timedelta(days=1), AT + timedelta(days=2), AT + timedelta(days=3),
                            AT + timedelta(days=3)])
            state = append_event(path, historical, clock=lambda: next(moments))
            before = path.read_bytes()
            future = event('mark', 'future', AT + timedelta(seconds=10))
            moments = iter([AT + timedelta(seconds=10), AT + timedelta(seconds=10), AT])
            with self.assertRaisesRegex(ValueError, 'Future observation'):
                append_event(path, future, clock=lambda: next(moments))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(replay(read_events(path)), state)


if __name__ == '__main__':
    unittest.main()
