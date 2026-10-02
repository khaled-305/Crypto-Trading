"""Deterministic FBR-v1 observer checks; no network, account access or orders."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from tools import manual_observer as observer

START = int(datetime(2026, 10, 2, tzinfo=timezone.utc).timestamp() * 1000)
HOUR, M15 = observer.HOUR, observer.M15


def bar(start, opening=100, high=105, low=99, close=103):
    return [start, str(opening), str(high), str(low), str(close), '10', '1000']


def watch_input():
    return {'watch_id': 'FBR-v1-BTCUSDT-20261002T000000Z', 'symbol': 'BTCUSDT',
            'registered_at': observer.iso(START), 'expires_at': observer.iso(START + 6 * HOUR),
            'zone': {'lower': '99', 'upper': '101'}, 'support': '80', 'overhead_resistance': '120'}


def watch():
    return observer.validate_watch(watch_input(), START)


def series():
    return {'h1': [bar(START, 98, 104, 97, 103), bar(START + HOUR, 103, 105, 100, 104)],
            'h4': [bar(START - 4 * HOUR, 98, 108, 90, 100)],
            'm15': [bar(START + HOUR + 3 * M15, 103, 105, 100, 104),
                    bar(START + 2 * HOUR, 104, 107, 102, 106)], 'tick': '1'}


def context():
    return {'tick': '1'}


def quote(stamp=START + 2 * HOUR + M15 + 2000):
    return {'response': {'retCode': 0, 'time': stamp,
                        'result': {'s': 'BTCUSDT', 'ts': stamp,
                                   'b': [['105.99', '10']], 'a': [['106', '10']]}}}


def consistent_snapshot():
    """A coherent H4/H1/M15 fixture with a currently forming bar in each source."""
    observed = START + 12 * HOUR + 5000
    hours = [bar(START + i * HOUR, 100, 102, 98, 101) for i in range(-32, 13)]
    quarters = []
    for hour in hours:
        for i in range(4):
            if hour[0] + i * M15 <= observed:
                quarters.append(bar(hour[0] + i * M15, 100 if i == 0 else 101, 102, 98, 101))
    fours = [bar(START + i * HOUR, 100, 102, 98, 101) for i in range(-32, 13, 4)]
    sources = {}
    for key, rows in (('h1', hours), ('h4', fours), ('m15', quarters)):
        sources[key] = {'response': {'retCode': 0, 'time': observed,
                        'result': {'category': 'spot', 'symbol': 'BTCUSDT', 'list': list(reversed(rows))}}}
    sources['instrument'] = {'response': {'result': {'list': [{'symbol': 'BTCUSDT', 'status': 'Trading',
                                            'priceFilter': {'tickSize': '1'}}]}}}
    sources['book'] = quote(observed)
    return {'symbol': 'BTCUSDT', 'category': 'spot', 'sources': sources, 'source_errors': {}}, observed


class WatchRegistrationTests(unittest.TestCase):
    def test_acceptance_not_supplied_timestamp_controls_first_breakout(self):
        value = watch_input()
        accepted = START + 30_000
        result = observer.validate_watch(value, accepted)
        self.assertEqual(result['registered_ms'], accepted)
        self.assertEqual(result['expires_ms'], START + 6 * HOUR)
        result = observer.evaluate(result, context(), series(), START + HOUR + 1000)
        self.assertEqual(result['state'], 'WAIT_BREAKOUT')

    def test_old_future_non_utc_and_extended_registration_rejected(self):
        for changed in ({'registered_at': observer.iso(START - 60_001)},
                        {'registered_at': observer.iso(START + 1)},
                        {'registered_at': '2026-10-02T01:00:00+01:00'},
                        {'expires_at': observer.iso(START + 6 * HOUR + 1)},
                        {'event_cutoff': observer.iso(START)}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                observer.validate_watch({**watch_input(), **changed}, START)

    def test_unknown_sensitive_fields_and_unapproved_pair_rejected(self):
        for changed in ({'api_key': 'not-a-real-secret'}, {'symbol': 'DOGEUSDT'}, {'watch_id': '../replace'}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                observer.validate_watch({**watch_input(), **changed}, START)

    def test_placeholder_example_cannot_register(self):
        value = json.loads((observer.ROOT / 'examples/manual-watch-input.json').read_text())
        with self.assertRaises(ValueError):
            observer.validate_watch(value, START)

    def test_swing_is_unavailable_until_second_following_close(self):
        rows = [bar(START + i * HOUR, high=high) for i, high in enumerate([106, 107, 110, 109, 108])]
        self.assertEqual(observer.swings(rows[:-1], HOUR, 2), [])
        result = observer.swings(rows, HOUR, 2)
        self.assertEqual(result[0]['start_ms'], START + 2 * HOUR)
        self.assertEqual(result[0]['confirmed_ms'], START + 5 * HOUR)

    def test_registration_levels_are_verified_using_only_prior_candles(self):
        h4 = []
        # Two separated high and low pivots, with latest support 80.
        values = [(105, 91), (107, 92), (120, 93), (108, 92), (106, 90),
                  (105, 85), (107, 90), (110, 92), (115, 93), (108, 90),
                  (107, 85), (106, 80), (107, 87), (108, 88)]
        for index, (high, low) in enumerate(values):
            h4.append(bar(START - (len(values) - index) * 4 * HOUR, 100, high, low, 100))
        h1 = [bar(START - (8 - index) * HOUR, 96, high, 94, 96)
              for index, high in enumerate([97, 98, 100, 99, 98, 97, 98, 99])]
        data = {'h1': h1, 'h4': h4, 'tick': '1'}
        value = watch()
        value['overhead_resistance'] = '115'
        result = observer.registration_context(value, data)
        self.assertEqual(result['structure'], 'falling')
        self.assertEqual(result['h4_lows'][-1]['price'], '80')
        self.assertEqual(result['hourly_level']['price'], '100')
        # A forming/new hourly high cannot redraw the registered level.
        data['h1'].append(bar(START, 96, 150, 95, 140))
        self.assertEqual(observer.registration_context(value, data), result)
        value['zone']['upper'] = '102'
        with self.assertRaisesRegex(ValueError, 'Premarked zone'):
            observer.registration_context(value, data)


class CandleSequenceTests(unittest.TestCase):
    def assess(self, data=None, when=None, registered=None):
        return observer.evaluate(registered or watch(), context(), data or series(),
                                 when if when is not None else START + 2 * HOUR + M15 + 2000)

    def test_distinct_breakout_retest_and_confirmation(self):
        for when, state in ((START + HOUR, 'WAIT_RETEST'),
                            (START + 2 * HOUR, 'WAIT_CONFIRMATION'),
                            (START + 2 * HOUR + M15, 'TRIGGER_RISK_UNVERIFIED')):
            with self.subTest(when=when):
                result = self.assess(when=when)
                self.assertEqual(result['state'], state)
                self.assertFalse(result['live_eligible'])
                self.assertFalse(result['orders_placed'])
        result = self.assess()
        self.assertEqual(result['stop'], '99')
        self.assertEqual(result['target'], '119')
        self.assertEqual(result['entry_deadline_ms'], START + 2 * HOUR + 2 * M15)

    def test_forming_breakout_retest_confirmation_never_qualify(self):
        for when, state in ((START + HOUR - 1, 'WAIT_BREAKOUT'),
                            (START + 2 * HOUR - 1, 'WAIT_RETEST'),
                            (START + 2 * HOUR + M15 - 1, 'WAIT_CONFIRMATION')):
            with self.subTest(when=when):
                self.assertEqual(self.assess(when=when)['state'], state)

    def test_preregistration_and_already_forming_breakouts_cannot_count(self):
        registered = watch()
        registered['registered_ms'] = START + 1
        data = series()
        data['h1'] = data['h1'][:1]
        self.assertEqual(self.assess(data, registered=registered)['state'], 'WAIT_BREAKOUT')

    def test_first_failed_retest_cannot_be_replaced_by_later_success(self):
        data = series()
        data['h1'][1] = bar(START + HOUR, 103, 105, 100, 101)
        data['h1'].append(bar(START + 2 * HOUR, 103, 105, 100, 104))
        result = self.assess(data, START + 3 * HOUR)
        self.assertEqual(result['state'], 'INVALIDATED')
        self.assertEqual(result['reason'], 'FIRST_RETEST_FAILED')

    def test_retest_must_overlap_and_finish_within_two_hours(self):
        data = series()
        data['h1'][1] = bar(START + HOUR, 104, 106, 102, 105)
        data['h1'].append(bar(START + 2 * HOUR, 105, 107, 102, 106))
        data['h1'].append(bar(START + 3 * HOUR, 103, 105, 100, 104))
        result = self.assess(data, START + 4 * HOUR)
        self.assertEqual(result['reason'], 'RETEST_DEADLINE')

    def test_second_hour_retest_and_fourth_quarter_confirmation_are_inclusive(self):
        data = series()
        data['h1'][1] = bar(START + HOUR, 104, 106, 102, 105)
        data['h1'].append(bar(START + 2 * HOUR, 103, 105, 100, 104))
        data['m15'] = [bar(START + 3 * HOUR - M15, 103, 105, 100, 104)]
        data['m15'] += [bar(START + 3 * HOUR + i * M15, 104, 107, 101, 105) for i in range(3)]
        data['m15'].append(bar(START + 3 * HOUR + 3 * M15, 105, 109, 102, 108))
        result = self.assess(data, START + 4 * HOUR + 1000)
        self.assertEqual(result['state'], 'TRIGGER_RISK_UNVERIFIED')
        self.assertEqual(result['retest_close_ms'], START + 3 * HOUR)
        self.assertEqual(result['confirmation_close_ms'], START + 4 * HOUR)

    def test_confirmation_requires_strict_close_above_preceding_high(self):
        data = series()
        data['m15'][-1] = bar(START + 2 * HOUR, 104, 107, 102, 105)
        self.assertEqual(self.assess(data)['state'], 'WAIT_CONFIRMATION')
        self.assertEqual(self.assess(data, START + 3 * HOUR)['reason'], 'CONFIRMATION_DEADLINE')

    def test_retest_hour_m15_cannot_double_as_confirmation(self):
        data = series()
        data['m15'][-2] = bar(START + HOUR + 3 * M15, 104, 120, 100, 119)
        data['m15'] = data['m15'][:-1]
        self.assertEqual(self.assess(data)['state'], 'WAIT_CONFIRMATION')

    def test_hourly_and_m15_invalidation_and_frozen_support(self):
        data = series()
        data['h1'][1] = bar(START + HOUR, 103, 105, 97, 98)
        self.assertEqual(self.assess(data)['reason'], 'HOURLY_ZONE_BROKEN')
        data = series()
        data['m15'][-1] = bar(START + 2 * HOUR, 104, 107, 97, 98)
        self.assertEqual(self.assess(data)['reason'], 'M15_ZONE_BROKEN')
        data = series()
        data['h1'] = []  # Isolate the context break before any breakout attempt.
        data['h4'].append(bar(START, 98, 108, 78, 80))
        self.assertEqual(self.assess(data, START + 4 * HOUR)['reason'], 'FOUR_HOUR_SUPPORT_BROKEN')

    def test_later_invalidation_cannot_relabel_a_missed_confirmation(self):
        data = series()
        data['h4'].append(bar(START, 98, 108, 78, 80))
        result = self.assess(data, START + 4 * HOUR)
        self.assertEqual(result['state'], 'MISSED_WINDOW')
        self.assertEqual(result['reason'], 'CONFIRMATION_ENTRY_WINDOW_ELAPSED')

    def test_stop_uses_all_postretest_lows_through_confirmation(self):
        data = series()
        data['m15'][-1] = bar(START + 2 * HOUR, 104, 107, 98, 105)
        data['m15'].append(bar(START + 2 * HOUR + M15, 105, 110, 101, 109))
        result = self.assess(data, START + 2 * HOUR + 2 * M15 + 1000)
        self.assertEqual(result['stop'], '97')

    def test_missed_window_and_postconfirmation_stop_breach_are_not_entries(self):
        self.assertEqual(self.assess(when=START + 2 * HOUR + 2 * M15)['state'], 'MISSED_WINDOW')
        data = series()
        data['m15'].append(bar(START + 2 * HOUR + M15, 106, 108, 98, 106))
        self.assertEqual(self.assess(data, START + 2 * HOUR + 2 * M15)['reason'], 'STOP_BREACHED_BEFORE_ENTRY')

    def test_watch_and_event_deadlines(self):
        registered = watch()
        registered['deadline_ms'] = START + HOUR + M15
        self.assertEqual(self.assess(registered=registered)['reason'], 'WATCH_DEADLINE')
        registered = watch()
        registered['event_cutoff'] = observer.iso(START + 2 * HOUR + 2 * M15)
        self.assertEqual(self.assess(registered=registered)['reason'], 'EVENT_CUTOFF_LESS_THAN_30_MINUTES')


class SourceAndQuoteTests(unittest.TestCase):
    def test_hourly_sources_may_precede_quarter_boundary_when_their_closed_bars_are_current(self):
        snap, _ = consistent_snapshot()
        decision = START + 12 * HOUR + M15 + 100
        for key in ('h1', 'h4'):
            snap['sources'][key]['response']['time'] = decision - 200
        snap['sources']['m15']['response']['time'] = decision
        result = observer.closed_sources(snap, 'BTCUSDT', decision)
        self.assertEqual(result['h1'][-1][0] + HOUR, START + 12 * HOUR)
        self.assertEqual(result['h4'][-1][0] + 4 * HOUR, START + 12 * HOUR)
        self.assertEqual(result['m15'][-1][0] + M15, START + 12 * HOUR + M15)

    def test_source_must_cross_its_own_boundary_before_its_new_bar_is_usable(self):
        for key in ('h1', 'h4', 'm15'):
            with self.subTest(key=key):
                snap, decision = consistent_snapshot()
                # All three timeframes close at 12:00. A response stamped just
                # before it cannot establish the newly closed source candle.
                snap['sources'][key]['response']['time'] = START + 12 * HOUR - 1
                with self.assertRaisesRegex(ValueError, key + ' candle boundary'):
                    observer.closed_sources(snap, 'BTCUSDT', decision)

    def test_quarter_alignment_does_not_relax_source_freshness(self):
        for offset in (-60_001, 1):
            snap, _ = consistent_snapshot()
            decision = START + 12 * HOUR + M15 + 100
            for key in ('h1', 'h4', 'm15'):
                snap['sources'][key]['response']['time'] = decision
            snap['sources']['h1']['response']['time'] = decision + offset
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'Stale or future'):
                observer.closed_sources(snap, 'BTCUSDT', decision)

    def test_closed_source_validation_excludes_forming_bars(self):
        snap, stamp = consistent_snapshot()
        result = observer.closed_sources(snap, 'BTCUSDT', stamp)
        for key, duration in (('h1', HOUR), ('h4', 4 * HOUR), ('m15', M15)):
            self.assertTrue(all(r[0] + duration <= stamp for r in result[key]))

    def test_wrong_market_stale_boundary_and_cross_timeframe_mismatch_rejected(self):
        for change in ('symbol', 'stale', 'boundary', 'h4', 'm15'):
            with self.subTest(change=change):
                snap, stamp = consistent_snapshot()
                if change == 'symbol':
                    snap['sources']['h1']['response']['result']['symbol'] = 'ETHUSDT'
                elif change == 'stale':
                    snap['sources']['h1']['response']['time'] -= 60_001
                elif change == 'boundary':
                    snap['sources']['h1']['response']['time'] -= 6000
                else:
                    snap['sources'][change]['response']['result']['list'][1][2] = '103'
                with self.assertRaises(ValueError):
                    observer.closed_sources(snap, 'BTCUSDT', stamp)

    def test_quote_checks_real_exchange_book_time_not_retrieval_label(self):
        confirmation = START + 2 * HOUR + M15
        received = confirmation + 70_000
        for stamp in (confirmation - 1, received - 60_001, received + 1):
            source = quote(stamp)
            source['received_at'] = observer.iso(received)
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                observer.quote_values(source, 'BTCUSDT', confirmation, received)
        result = observer.quote_values(quote(received - 60_000), 'BTCUSDT', confirmation, received)
        self.assertEqual(result['age_ms'], 60_000)
        self.assertFalse(result['quote_eligible'])

    def test_quote_response_cannot_predate_book_or_be_in_future(self):
        confirmation = START + 2 * HOUR + M15
        received = confirmation + 5000
        for response_ms in (confirmation + 1999, received + 1):
            source = quote(confirmation + 2000)
            source['response']['time'] = response_ms
            with self.subTest(response_ms=response_ms), self.assertRaises(ValueError):
                observer.quote_values(source, 'BTCUSDT', confirmation, received)

    def test_snapshot_subprocess_keeps_25second_deadline(self):
        child = subprocess.CompletedProcess([], 0, '{}', '')
        with patch.object(observer.subprocess, 'run', return_value=child) as call:
            observer.snapshot('BTCUSDT', True)
        self.assertEqual(call.call_args.kwargs['timeout'], 25)
        self.assertIn('--include-m15', call.call_args.args[0])
        self.assertNotIn('shell', call.call_args.kwargs)

    def observe_fixture(self, source=None, stamp=None, remaining=None):
        stamp = stamp or START + 2 * HOUR + M15 + 2000
        snapshot = {'sources': {}, 'source_errors': {}}
        with patch.object(observer, 'closed_sources', return_value=series()), \
                patch.object(observer, 'registration_context', return_value=context()):
            return observer.observe(watch(), get_snapshot=lambda *_: snapshot,
                                    get_quote=lambda: source or quote(), clock=lambda: stamp,
                                    remaining_seconds=remaining)

    def test_trigger_fresh_book_still_has_no_sizing_or_entry(self):
        result = self.observe_fixture()
        self.assertEqual(result['state'], 'TRIGGER_RISK_UNVERIFIED')
        self.assertTrue(result['quote_freshness_pass'])
        self.assertFalse(result['quote_eligible'])
        self.assertEqual(result['paper_positions_opened'], 0)
        self.assertNotIn('quantity', result)

    def test_stale_book_keeps_quote_unverified(self):
        stamp = START + 2 * HOUR + M15 + 61_000
        result = self.observe_fixture(source=quote(stamp - 60_001), stamp=stamp)
        self.assertFalse(result['quote_freshness_pass'])
        self.assertFalse(result['quote_eligible'])

    def test_insufficient_run_time_prevents_optional_book_call(self):
        result = self.observe_fixture(remaining=lambda: 14.99)
        self.assertEqual(result['quote_error'], 'RUN_DEADLINE_NO_TIME_FOR_BOOK')
        self.assertNotIn('quote_source', result)

    def test_collection_crossing_confirmation_window_never_requests_book(self):
        times = iter([START + 2 * HOUR + M15 + 2000, START + 2 * HOUR + 2 * M15])
        with patch.object(observer, 'closed_sources', return_value=series()):
            result = observer.observe(watch(), context(), get_snapshot=lambda *_: {},
                        get_quote=lambda: self.fail('Late collection must not request a quote'), clock=lambda: next(times))
        self.assertEqual(result['state'], 'MISSED_WINDOW')
        self.assertNotIn('trigger_observed_ms', result)

    def test_trigger_detection_survives_quote_receipt_at_or_after_entry_deadline(self):
        deadline = START + 2 * HOUR + 2 * M15
        detected = deadline - 10_000
        for received in (deadline, deadline + 2000):
            times = iter([detected, detected, detected, received])
            with self.subTest(received=received), patch.object(observer, 'closed_sources', return_value=series()):
                result = observer.observe(watch(), context(), get_snapshot=lambda *_: {},
                    get_quote=lambda: quote(received), clock=lambda: next(times))
            self.assertEqual(result['state'], 'MISSED_WINDOW')
            self.assertEqual(result['reason'], 'QUOTE_RECEIVED_AFTER_ENTRY_WINDOW')
            self.assertEqual(result['trigger_observed_ms'], detected)
            self.assertEqual(result['candle_checked_ms'], detected)
            self.assertEqual(result['quote_received_ms'], received)
            self.assertEqual(result['checked_ms'], received)
            self.assertFalse(result['quote_eligible'])

    def test_quote_failure_preserves_the_preceding_trigger_observation(self):
        detected = START + 2 * HOUR + M15 + 1000
        def unavailable():
            raise subprocess.TimeoutExpired('public-quote-fixture', 15)
        with patch.object(observer, 'closed_sources', return_value=series()):
            result = observer.observe(watch(), context(), get_snapshot=lambda *_: {},
                                      get_quote=unavailable, clock=lambda: detected)
        self.assertEqual(result['trigger_observed_ms'], detected)
        self.assertEqual(result['error']['kind'], 'timeout')
        self.assertFalse(result['quote_eligible'])

    def test_missing_optional_m15_preserves_hourly_baseline_and_marks_gap(self):
        data = series()
        del data['m15']
        snap = {'source_errors': {'m15': {'kind': 'timeout', 'stage': 'fetch'}}}
        with patch.object(observer, 'closed_sources', return_value=data):
            result = observer.observe(watch(), context(), get_snapshot=lambda *_: snap,
                                      clock=lambda: START + 2 * HOUR)
        self.assertEqual(result['reason'], 'M15_DATA_MISSING')
        self.assertEqual(result['coverage'], 'DATA_MISSING')
        self.assertIn('hourly_baseline', result)

    def test_optional_source_access_restriction_is_also_a_halt(self):
        data = series()
        del data['m15']
        for kind in ('access_denied', 'rate_limited'):
            with self.subTest(kind=kind), patch.object(observer, 'closed_sources', return_value=data):
                result = observer.observe(watch(), context(),
                    get_snapshot=lambda *_: {'source_errors': {'m15': {'kind': kind}}},
                    clock=lambda: START + 2 * HOUR)
                self.assertTrue(result['halt'])

    def test_access_denied_and_rate_limit_are_halts_without_retry(self):
        for code in (403, 429):
            calls = []
            def unavailable(*_):
                calls.append(1)
                raise ValueError(f'DATA UNAVAILABLE: HTTP {code}')
            result = observer.observe(None, get_snapshot=unavailable, clock=lambda: START)
            self.assertTrue(result['halt'])
            self.assertEqual(len(calls), 1)


class RunEvidenceTests(unittest.TestCase):
    def baseline_event(self):
        return {'started_ms': START, 'checked_ms': START + 2000, 'state': None,
                'coverage': 'OBSERVED', 'reason': 'BASELINE_ONLY_NO_REGISTERED_WATCH',
                **observer.FALSE_CAPABILITIES}

    def test_atomic_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            observer.save_new(path, {'original': True})
            with self.assertRaises(FileExistsError):
                observer.save_new(path, {'original': False})
            self.assertEqual(json.loads(path.read_text()), {'original': True})
            self.assertFalse(list(path.parent.glob('.pending-*')))

    def test_default_is_six_hours_once_and_offline_report_make_no_network_calls(self):
        self.assertEqual(observer.DEFAULT_HOURS, 6)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(observer, 'now_ms', return_value=START), \
                patch.object(observer, 'observe', return_value=self.baseline_event()) as check, \
                patch.object(observer, 'snapshot', side_effect=AssertionError('No network in fixture')), \
                contextlib.redirect_stdout(io.StringIO()):
            run = observer.run_observer(Path(folder), once=True)
            manifest = json.loads((run / 'run.json').read_text())
            self.assertEqual(manifest['hours'], 6)
            self.assertEqual(check.call_count, 1)
            report = observer.report(Path(folder))
            self.assertEqual(report['checks'], 1)
            self.assertEqual(report['registered_watches'], 0)
            self.assertEqual(report['distinct_triggers_observed_in_window'], 0)
            self.assertEqual(report['paper_positions_opened'], 0)

    def once_crossing_boundary(self, *, registered, interrupted):
        cadence = M15 if registered else HOUR
        start = START + cadence - 10_000
        finish = start + 15_000
        wall = [start]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = None
            if registered:
                source = root / 'watch.json'
                value = watch_input()
                value.update(registered_at=observer.iso(start), expires_at=observer.iso(start + 6 * HOUR))
                source.write_text(json.dumps(value))
            def check(*_, **__):
                wall[0] = finish
                if interrupted:
                    raise KeyboardInterrupt
                return {**self.baseline_event(), 'started_ms': start, 'checked_ms': finish,
                        'state': 'WAIT_BREAKOUT' if registered else None}
            with patch.object(observer, 'now_ms', side_effect=lambda: wall[0]), \
                    patch.object(observer.time, 'monotonic', return_value=0), \
                    patch.object(observer, 'observe', side_effect=check), \
                    contextlib.redirect_stdout(io.StringIO()):
                run = observer.run_observer(root / 'observations', once=True, watch_path=source)
            result = observer.report(root / 'observations')
            stopped = json.loads((run / 'stopped.json').read_text())
            self.assertEqual(result['checks'], 0 if interrupted else 1)
            self.assertEqual(result['missed_scheduled_checks'], 0)
            self.assertFalse(list((run / 'gaps').glob('*.json')))
            self.assertEqual(stopped['reason'], 'USER_INTERRUPTED' if interrupted else 'ONCE_COMPLETE')

    def test_once_finishing_across_boundary_has_no_later_scheduled_check(self):
        for registered in (False, True):
            with self.subTest(registered=registered):
                self.once_crossing_boundary(registered=registered, interrupted=False)

    def test_once_interrupted_across_boundary_has_no_later_scheduled_check(self):
        for registered in (False, True):
            with self.subTest(registered=registered):
                self.once_crossing_boundary(registered=registered, interrupted=True)

    def test_duration_cap_invalid_values_and_subrequest_budget_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for hours in (0, -1, 6.001, float('nan'), float('inf'), 0.001):
                with self.subTest(hours=hours), self.assertRaises(ValueError):
                    observer.run_observer(Path(folder), hours=hours, once=True)

    def test_watch_copy_hash_and_duplicate_id_prevent_retroactive_reregistration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input.json'
            source.write_text(json.dumps(watch_input()))
            event = {**self.baseline_event(), 'state': 'WAIT_BREAKOUT', 'reason': 'WAIT_BREAKOUT'}
            with patch.object(observer, 'now_ms', return_value=START), \
                    patch.object(observer, 'observe', return_value=event), contextlib.redirect_stdout(io.StringIO()):
                run = observer.run_observer(root / 'observations', once=True, watch_path=source)
                copy_value = json.loads((run / 'watch-input.json').read_text())
                self.assertEqual(copy_value, watch_input())
                manifest = json.loads((run / 'run.json').read_text())
                self.assertTrue(manifest['watch_sha256'])
                with self.assertRaises(FileExistsError):
                    observer.run_observer(root / 'observations', once=True, watch_path=source)
                source.write_text('{}')
                self.assertEqual(json.loads((run / 'watch-input.json').read_text()), watch_input())

    def test_exclusive_lock_prevents_second_observer(self):
        import fcntl
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (root / 'observer.lock').open('a+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, 'Another manual observer'):
                    observer.run_observer(root, once=True)

    def test_observation_gaps_are_counted_not_backfilled_as_no_signal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input.json'
            source.write_text(json.dumps(watch_input()))
            clock = [START]
            calls = []
            def check(*_, **__):
                calls.append(1)
                if len(calls) == 1:
                    value = {**self.baseline_event(), 'state': 'WAIT_BREAKOUT', 'reason': 'WAIT_BREAKOUT'}
                    clock[0] += 3 * M15
                    return value
                return {**self.baseline_event(), 'started_ms': clock[0], 'checked_ms': clock[0],
                        'state': 'INVALIDATED', 'reason': 'FIXTURE_STOP'}
            with patch.object(observer, 'now_ms', side_effect=lambda: clock[0]), \
                    patch.object(observer, 'observe', side_effect=check), contextlib.redirect_stdout(io.StringIO()):
                observer.run_observer(root / 'observations', watch_path=source)
            report = observer.report(root / 'observations')
            self.assertEqual(report['checks'], 2)
            self.assertEqual(report['missed_scheduled_checks'], 2)
            self.assertEqual(len(report['actual_check_times']), 2)

    def run_timed_fixture(self, advances, *, expires=None, hours=6, state='WAIT_BREAKOUT',
                          interrupt_last=False, event_extra=None, once=False):
        """Advance wall time after each mocked check; no real waits or requests."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'watch.json'
            value = watch_input()
            if expires is not None:
                value['expires_at'] = observer.iso(expires)
            source.write_text(json.dumps(value))
            wall = [START]
            calls = []
            def check(*_, **__):
                detected = wall[0] + 1000
                index = len(calls)
                calls.append(1)
                if index >= len(advances):
                    self.fail('Unexpected additional check')
                wall[0] = advances[index]
                if interrupt_last and index == len(advances) - 1:
                    raise KeyboardInterrupt
                return {**self.baseline_event(), 'started_ms': detected - 1000,
                        'checked_ms': detected, 'state': state, 'reason': state,
                        **(event_extra or {})}
            with patch.object(observer, 'now_ms', side_effect=lambda: wall[0]), \
                    patch.object(observer.time, 'monotonic', return_value=0), \
                    patch.object(observer.time, 'sleep', side_effect=AssertionError('No waits in fixture')), \
                    patch.object(observer, 'observe', side_effect=check), \
                    contextlib.redirect_stdout(io.StringIO()):
                run = observer.run_observer(root / 'observations', hours=hours, once=once, watch_path=source)
            return (observer.report(root / 'observations'),
                    json.loads((run / 'stopped.json').read_text()),
                    [json.loads(p.read_text()) for p in sorted((run / 'checks').glob('*.json'))],
                    [json.loads(p.read_text()) for p in sorted((run / 'gaps').glob('*.json'))])

    def test_suspension_to_or_beyond_deadline_records_trailing_gaps_and_expires_watch(self):
        for wake in (START + 6 * HOUR, START + 9 * HOUR):
            with self.subTest(wake=wake):
                report, stopped, checks, gaps = self.run_timed_fixture([wake])
            self.assertEqual(report['checks'], 1)
            self.assertEqual(report['missed_scheduled_checks'], 23)
            self.assertEqual(gaps[0]['until_ms'], START + 6 * HOUR)
            self.assertEqual(stopped['reason'], 'WATCH_TERMINAL')
            self.assertEqual(stopped['watch_state'], 'EXPIRED')
            # Preserve the preceding assessment, but the returned status must
            # acknowledge a deadline crossed before the check was recorded.
            self.assertEqual(checks[0]['pre_expiry_state'], 'WAIT_BREAKOUT')
            self.assertEqual(checks[0]['state'], 'EXPIRED')

    def test_trailing_gaps_end_at_earlier_watch_expiry(self):
        for expiry, expected in ((START + HOUR, 3), (START + HOUR + 12 * 60_000, 4)):
            with self.subTest(expiry=expiry):
                report, stopped, _, gaps = self.run_timed_fixture([START + 9 * HOUR], expires=expiry)
            self.assertEqual(report['missed_scheduled_checks'], expected)
            self.assertEqual(gaps[0]['until_ms'], expiry)
            self.assertEqual(stopped['watch_state'], 'EXPIRED')

    def test_shorter_run_does_not_expire_a_still_valid_watch(self):
        report, stopped, _, gaps = self.run_timed_fixture([START + HOUR], hours=1)
        self.assertEqual(report['missed_scheduled_checks'], 3)
        self.assertEqual(gaps[0]['until_ms'], START + HOUR)
        self.assertEqual(stopped['watch_state'], 'WAIT_BREAKOUT')

    def test_middle_and_trailing_gaps_do_not_double_count_an_observed_slot(self):
        report, _, _, gaps = self.run_timed_fixture([START + 3 * M15, START + 6 * HOUR])
        self.assertEqual(report['checks'], 2)
        self.assertEqual(report['missed_scheduled_checks'], 22)
        self.assertEqual([gap['missing_checks'] for gap in gaps], [2, 20])

    def test_interrupt_after_a_recorded_gap_counts_only_elapsed_unobserved_slots_once(self):
        report, stopped, _, gaps = self.run_timed_fixture(
            [START + 3 * M15, START + 3 * M15 + 10_000], interrupt_last=True)
        self.assertEqual(stopped['reason'], 'USER_INTERRUPTED')
        self.assertEqual(report['checks'], 1)
        self.assertEqual(report['missed_scheduled_checks'], 3)
        self.assertEqual([gap['missing_checks'] for gap in gaps], [2, 1])

    def test_terminal_and_once_checks_do_not_require_later_scheduled_observations(self):
        for state, once in (('INVALIDATED', False), ('WAIT_BREAKOUT', True)):
            with self.subTest(state=state):
                report, stopped, _, gaps = self.run_timed_fixture(
                    [START + 6 * HOUR], state=state, once=once)
            self.assertEqual(report['missed_scheduled_checks'], 0)
            self.assertEqual(gaps, [])
            if state == 'INVALIDATED':
                self.assertEqual(stopped['watch_state'], 'INVALIDATED')

    def test_report_counts_detected_trigger_even_when_quote_missed_entry_window(self):
        confirmation = START + 2 * HOUR + M15
        deadline = confirmation + M15
        # Use the actual observation function for the trigger/late-quote evidence.
        times = iter([deadline - 10_000] * 3 + [deadline + 2000])
        with patch.object(observer, 'closed_sources', return_value=series()):
            event = observer.observe(watch(), context(), get_snapshot=lambda *_: {},
                                     get_quote=lambda: quote(deadline + 2000), clock=lambda: next(times))
        report, stopped, checks, _ = self.run_timed_fixture([deadline + 2000], event_extra=event)
        self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
        self.assertEqual(report['distinct_triggers_observed_in_window'], 1)
        self.assertTrue(checks[0]['trigger_first_observed_in_window'])

    def test_quote_timeout_after_entry_expiry_preserves_candles_but_expires_status(self):
        confirmation = START + 2 * HOUR + M15
        deadline = confirmation + M15
        wall = [confirmation + 1000]

        def unavailable_quote():
            wall[0] = deadline + 2000
            raise subprocess.TimeoutExpired('quote-fixture', 15)

        with patch.object(observer, 'closed_sources', return_value=series()):
            event = observer.observe(watch(), context(), get_snapshot=lambda *_: {},
                                     get_quote=unavailable_quote, clock=lambda: wall[0])
        # A quote failure does not erase the successfully assessed candles.
        self.assertEqual(event['coverage'], 'OBSERVED')
        self.assertEqual(event['reason'], 'DATA_MISSING')
        for once in (False, True):
            with self.subTest(once=once):
                report, stopped, checks, _ = self.run_timed_fixture(
                    [deadline + 2000], event_extra=event, once=once)
            self.assertEqual(len(checks), 1)
            check = checks[0]
            self.assertEqual(check['state'], 'MISSED_WINDOW')
            self.assertEqual(check['pre_expiry_state'], 'TRIGGER_RISK_UNVERIFIED')
            self.assertEqual(check['data_missing_reason'], 'DATA_MISSING')
            self.assertEqual(check['error']['kind'], 'timeout')
            self.assertEqual(check['coverage'], 'OBSERVED')
            self.assertEqual(check['candle_checked_ms'], confirmation + 1000)
            self.assertEqual(check['trigger_observed_ms'], confirmation + 1000)
            self.assertEqual(check['checked_ms'], deadline + 2000)
            self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
            self.assertEqual(stopped['reason'], 'ONCE_COMPLETE' if once else 'WATCH_TERMINAL')
            self.assertEqual(report['distinct_triggers_observed_in_window'], 1)
            self.assertEqual(report['data_missing_checks'], 0)

    def test_repeated_trigger_evidence_is_counted_once_without_relaxing_deadline(self):
        confirmation = START + 2 * HOUR + M15
        deadline = confirmation + M15
        event = {'confirmation_close_ms': confirmation, 'entry_deadline_ms': deadline,
                 'trigger_observed_ms': confirmation + 1000}
        report, stopped, checks, _ = self.run_timed_fixture(
            [START + 3 * M15, START + 6 * HOUR], state='TRIGGER_RISK_UNVERIFIED', event_extra=event)
        self.assertEqual(report['distinct_triggers_observed_in_window'], 1)
        self.assertEqual([e['trigger_first_observed_in_window'] for e in checks], [True, False])
        self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
        # An observation at the entry deadline is already too late to count.
        event['trigger_observed_ms'] = deadline
        report, _, checks, _ = self.run_timed_fixture(
            [START + 6 * HOUR], state='MISSED_WINDOW', event_extra=event)
        self.assertEqual(report['distinct_triggers_observed_in_window'], 0)
        self.assertFalse(checks[0]['trigger_first_observed_in_window'])

    def test_seen_confirmation_caps_trailing_coverage_at_its_entry_expiry(self):
        confirmation = START + 2 * HOUR + M15
        deadline = confirmation + M15
        event = {'confirmation_close_ms': confirmation, 'entry_deadline_ms': deadline,
                 'trigger_observed_ms': confirmation + 1000}
        report, stopped, _, gaps = self.run_timed_fixture(
            [START + 6 * HOUR], state='TRIGGER_RISK_UNVERIFIED', event_extra=event)
        self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
        self.assertEqual(gaps[0]['until_ms'], deadline)
        self.assertEqual(report['missed_scheduled_checks'], 9)

    def run_entry_expiry_fixture(self, resume_ms, *, failure='m15', cutoff=None,
                                 trigger_start=None, terminal=None):
        """Use real observe(), with a clock pause between the recorded checks."""
        confirmation = START + 2 * HOUR + M15
        deadline = min(confirmation + M15, cutoff or START + 6 * HOUR)
        wall = [START]
        requests = []
        real_observe = observer.observe
        real_save = observer.save_new
        resume_after_check = [False]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'watch.json'
            value = watch_input()
            if cutoff is not None:
                value['expires_at'] = observer.iso(cutoff)
            source.write_text(json.dumps(value))

            def check(registered, *_args, **_kwargs):
                started = wall[0]
                requests.append(started)
                if len(requests) == 1:
                    wall[0] = trigger_start if trigger_start is not None else confirmation - 1000
                    return {**self.baseline_event(), 'checked_ms': START,
                            'state': 'WAIT_BREAKOUT', 'reason': 'WAIT_BREAKOUT'}
                if len(requests) == 2:
                    def trigger_snapshot(*_):
                        wall[0] = confirmation + 1000
                        return {}
                    with patch.object(observer, 'closed_sources', return_value=series()):
                        event = real_observe(registered, context(), get_snapshot=trigger_snapshot,
                                             get_quote=lambda: quote(wall[0]), clock=lambda: wall[0])
                    resume_after_check[0] = True
                    return event
                if len(requests) != 3 or started >= deadline:
                    self.fail('Requested market data after known expiry')
                if terminal is not None:
                    wall[0] = deadline + 2000
                    return {'started_ms': started, 'checked_ms': wall[0], 'coverage': 'OBSERVED',
                            'state': terminal, 'reason': 'FIXTURE_EARLIER_CANCELLATION',
                            **observer.FALSE_CAPABILITIES}

                def missing_snapshot(*_):
                    wall[0] = deadline + 2000
                    if failure == 'timeout':
                        raise subprocess.TimeoutExpired('snapshot-fixture', 25)
                    return {'source_errors': {'m15': {'kind': 'timeout', 'stage': 'fetch'}}}
                missing_series = series()
                del missing_series['m15']
                with patch.object(observer, 'closed_sources', return_value=missing_series):
                    return real_observe(registered, context(), get_snapshot=missing_snapshot,
                                        clock=lambda: wall[0])

            def save(path, event):
                real_save(path, event)
                if path.parent.name == 'checks' and resume_after_check[0]:
                    # Suspension happens after the trigger evidence is saved,
                    # allowing the next iteration's pre-request guard to run.
                    wall[0] = resume_ms
                    resume_after_check[0] = False

            with patch.object(observer, 'now_ms', side_effect=lambda: wall[0]), \
                    patch.object(observer.time, 'monotonic', return_value=0), \
                    patch.object(observer.time, 'sleep', side_effect=AssertionError('No waits in fixture')), \
                    patch.object(observer, 'observe', side_effect=check), \
                    patch.object(observer, 'save_new', side_effect=save), \
                    patch.object(observer, 'snapshot', side_effect=AssertionError('No network in fixture')), \
                    contextlib.redirect_stdout(io.StringIO()):
                run = observer.run_observer(root / 'observations', watch_path=source)
            return (requests, observer.report(root / 'observations'),
                    json.loads((run / 'stopped.json').read_text()),
                    sorted((json.loads(p.read_text()) for p in (run / 'checks').glob('*.json')),
                           key=lambda event: event['checked_ms']))

    def test_known_entry_deadline_ends_run_without_another_market_request(self):
        deadline = START + 2 * HOUR + 2 * M15
        for resume in (deadline, deadline + M15):
            with self.subTest(resume=resume):
                requests, report, stopped, checks = self.run_entry_expiry_fixture(resume)
            self.assertEqual(len(requests), 2)
            self.assertEqual(checks[-1]['coverage'], 'NOT_CHECKED')
            self.assertEqual(checks[-1]['state'], 'MISSED_WINDOW')
            self.assertEqual(checks[-1]['entry_deadline_ms'], deadline)
            self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
            self.assertEqual(stopped['reason'], 'WATCH_TERMINAL')
            self.assertEqual(report['distinct_triggers_observed_in_window'], 1)
            self.assertEqual(report['missed_scheduled_checks'], 8)

    def test_missing_data_request_crossing_entry_expiry_does_not_restore_trigger(self):
        deadline = START + 2 * HOUR + 2 * M15
        for failure, diagnostic in (('m15', 'M15_DATA_MISSING'), ('timeout', 'DATA_MISSING')):
            with self.subTest(failure=failure):
                requests, report, stopped, checks = self.run_entry_expiry_fixture(
                    deadline - 1000, failure=failure)
            self.assertEqual(len(requests), 3)
            self.assertEqual(checks[-1]['coverage'], 'DATA_MISSING')
            self.assertTrue(checks[-1]['observation_gap'])
            self.assertEqual(checks[-1]['data_missing_reason'], diagnostic)
            self.assertEqual(checks[-1]['state'], 'MISSED_WINDOW')
            self.assertEqual(checks[-1]['checked_ms'], deadline + 2000)
            self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
            self.assertEqual(stopped['reason'], 'WATCH_TERMINAL')
            self.assertEqual(report['distinct_triggers_observed_in_window'], 1)
            self.assertEqual(report['data_missing_checks'], 1)
            self.assertEqual(report['missed_scheduled_checks'], 7)

    def test_expiry_does_not_replace_an_observed_terminal_reason(self):
        deadline = START + 2 * HOUR + 2 * M15
        for terminal in ('INVALIDATED', 'EXPIRED'):
            with self.subTest(terminal=terminal):
                _, _, stopped, checks = self.run_entry_expiry_fixture(deadline - 1000, terminal=terminal)
            self.assertEqual(checks[-1]['state'], terminal)
            self.assertEqual(checks[-1]['reason'], 'FIXTURE_EARLIER_CANCELLATION')
            self.assertEqual(stopped['watch_state'], terminal)

    def test_watch_cutoff_inside_checked_slot_appends_expiry_without_overwriting(self):
        confirmation = START + 2 * HOUR + M15
        cutoff = confirmation + 5000
        requests, report, stopped, checks = self.run_entry_expiry_fixture(
            cutoff, cutoff=cutoff, trigger_start=confirmation)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(checks), 3)
        self.assertEqual(checks[-2]['state'], 'TRIGGER_RISK_UNVERIFIED')
        self.assertEqual(checks[-1]['state'], 'MISSED_WINDOW')
        self.assertEqual(checks[-2]['slot_ms'], checks[-1]['slot_ms'])
        self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
        self.assertEqual(report['distinct_triggers_observed_in_window'], 1)

    def test_known_expiry_preserves_a_strictly_earlier_watch_deadline(self):
        registered = watch()
        registered['deadline_ms'] = START + HOUR
        result = observer.known_expiry(registered, START + 2 * HOUR, START + 3 * HOUR)
        self.assertEqual(result, {'state': 'EXPIRED', 'reason': 'WATCH_DEADLINE'})

    def run_stage_expiry_fixture(self, stage, actions, *, cutoff=None):
        """Observe one real stage, then script gaps or recovery with no network."""
        wall = [START]
        stage_close = START + (HOUR if stage == 'breakout' else 2 * HOUR)
        requests = []
        real_save, real_observe = observer.save_new, observer.observe
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'watch.json'
            value = watch_input()
            if cutoff is not None:
                value['expires_at'] = observer.iso(cutoff)
            source.write_text(json.dumps(value))

            def check(registered, *_args, **_kwargs):
                started = wall[0]
                requests.append(started)
                if len(requests) == 1:
                    return {**self.baseline_event(), 'state': 'WAIT_BREAKOUT', 'reason': 'WAIT_BREAKOUT'}
                if len(requests) == 2:
                    with patch.object(observer, 'closed_sources', return_value=series()):
                        return real_observe(registered, context(), get_snapshot=lambda *_: {},
                                            clock=lambda: wall[0])
                action = actions[len(requests) - 3]
                if action['kind'] == 'must_expire':
                    self.fail('Requested market data after latest possible entry')
                wall[0] = action.get('finish', wall[0])
                if action['kind'] == 'interrupt':
                    raise KeyboardInterrupt
                if action['kind'] == 'recovery':
                    data = series()
                    retest = START + (3 * HOUR if stage == 'breakout' else 2 * HOUR)
                    if stage == 'breakout':
                        data['h1'][1] = bar(START + HOUR, 104, 106, 102, 105)
                        data['h1'].append(bar(retest - HOUR, 103, 105, 100, 104))
                    data['m15'] = [bar(retest - M15, 103, 105, 100, 104)]
                    data['m15'] += [bar(retest + i * M15, 104, 107, 101, 105) for i in range(3)]
                    data['m15'].append(bar(retest + 3 * M15, 105, 109, 102, 108))
                    with patch.object(observer, 'closed_sources', return_value=data):
                        return real_observe(registered, context(), get_snapshot=lambda *_: {},
                                            get_quote=lambda: quote(wall[0]), clock=lambda: wall[0])

                def missing(*_):
                    if action['kind'] == 'timeout':
                        raise subprocess.TimeoutExpired('snapshot-fixture', 25)
                    return {'source_errors': {'m15': {'kind': 'timeout', 'stage': 'fetch'}}}
                missing_data = series()
                del missing_data['m15']
                with patch.object(observer, 'closed_sources', return_value=missing_data):
                    return real_observe(registered, context(), get_snapshot=missing, clock=lambda: wall[0])

            def save(path, event):
                real_save(path, event)
                if path.parent.name != 'checks':
                    return
                if len(requests) == 1:
                    wall[0] = stage_close + 1000
                elif len(requests) - 2 < len(actions):
                    wall[0] = actions[len(requests) - 2]['at']

            with patch.object(observer, 'now_ms', side_effect=lambda: wall[0]), \
                    patch.object(observer.time, 'monotonic', return_value=0), \
                    patch.object(observer.time, 'sleep', side_effect=AssertionError('No waits in fixture')), \
                    patch.object(observer, 'observe', side_effect=check), \
                    patch.object(observer, 'save_new', side_effect=save), \
                    patch.object(observer, 'snapshot', side_effect=AssertionError('No network in fixture')), \
                    contextlib.redirect_stdout(io.StringIO()):
                run = observer.run_observer(root / 'observations', watch_path=source)
            return (requests, observer.report(root / 'observations'),
                    json.loads((run / 'stopped.json').read_text()),
                    sorted((json.loads(p.read_text()) for p in (run / 'checks').glob('*.json')),
                           key=lambda event: event.get('checked_ms', event['started_ms'])),
                    [json.loads(p.read_text()) for p in (run / 'gaps').glob('*.json')])

    def test_stage_outages_preserve_evidence_but_expire_without_inventing_triggers(self):
        for stage, final_hour in (('breakout', 4), ('retest', 3)):
            deadline = START + final_hour * HOUR + M15
            with self.subTest(stage=stage):
                requests, report, stopped, checks, gaps = self.run_stage_expiry_fixture(stage, [
                    {'at': START + 2 * HOUR + M15, 'kind': 'm15'},
                    {'at': START + final_hour * HOUR, 'kind': 'timeout'},
                    {'at': deadline, 'kind': 'must_expire'}])
            self.assertEqual(len(requests), 4)
            self.assertEqual(checks[-1]['coverage'], 'NOT_CHECKED')
            self.assertEqual(checks[-1]['reason'], 'POSSIBLE_ENTRY_WINDOW_ELAPSED')
            self.assertEqual(checks[-1]['latest_possible_entry_ms'], deadline)
            self.assertEqual(checks[-1]['confirmation_status'], 'NOT_OBSERVED')
            self.assertEqual(stopped['watch_state'], 'EXPIRED')
            self.assertEqual(report['distinct_triggers_observed_in_window'], 0)
            self.assertEqual(report['data_missing_checks'], 2)
            for check in checks[1:]:
                self.assertEqual(check['breakout_close_ms'], START + HOUR)
                self.assertNotIn('confirmation_close_ms', check)
                if stage == 'retest':
                    self.assertEqual(check['retest_close_ms'], START + 2 * HOUR)
            self.assertTrue(all(gap['until_ms'] <= deadline for gap in gaps))

    def test_missing_request_crossing_stage_expiry_cannot_restore_waiting_state(self):
        for stage, final_hour in (('breakout', 4), ('retest', 3)):
            deadline = START + final_hour * HOUR + M15
            for failure in ('m15', 'timeout'):
                with self.subTest(stage=stage, failure=failure):
                    requests, report, stopped, checks, _ = self.run_stage_expiry_fixture(stage, [
                        {'at': deadline - 1000, 'finish': deadline + 2000, 'kind': failure}])
                self.assertEqual(len(requests), 3)
                self.assertEqual(checks[-1]['coverage'], 'DATA_MISSING')
                self.assertEqual(checks[-1]['reason'], 'POSSIBLE_ENTRY_WINDOW_ELAPSED')
                self.assertEqual(checks[-1]['checked_ms'], deadline + 2000)
                self.assertIn('data_missing_reason', checks[-1])
                self.assertEqual(stopped['watch_state'], 'EXPIRED')
                self.assertEqual(report['distinct_triggers_observed_in_window'], 0)

    def test_stage_suspend_or_interrupt_caps_trailing_coverage(self):
        for stage, final_hour, missing in (('breakout', 4, 15), ('retest', 3, 11)):
            deadline = START + final_hour * HOUR + M15
            for action in ({'at': START + 9 * HOUR, 'kind': 'must_expire'},
                           {'at': deadline - 1000, 'finish': START + 9 * HOUR, 'kind': 'interrupt'}):
                with self.subTest(stage=stage, action=action):
                    _, report, stopped, _, gaps = self.run_stage_expiry_fixture(stage, [action])
                self.assertEqual(report['missed_scheduled_checks'], missing)
                self.assertEqual(stopped['watch_state'], 'EXPIRED')
                self.assertEqual(max(gap['until_ms'] for gap in gaps), deadline)
                self.assertEqual(report['distinct_triggers_observed_in_window'], 0)

    def test_latest_eligible_retest_and_confirmation_can_recover_during_outage_window(self):
        for stage, final_hour in (('breakout', 4), ('retest', 3)):
            confirmation = START + final_hour * HOUR
            deadline = confirmation + M15
            with self.subTest(stage=stage):
                requests, report, stopped, checks, _ = self.run_stage_expiry_fixture(stage, [
                    {'at': confirmation - M15, 'kind': 'm15'},
                    {'at': confirmation + 1000, 'kind': 'recovery'},
                    {'at': deadline, 'kind': 'must_expire'}])
            self.assertEqual(len(requests), 4)
            self.assertEqual(checks[-2]['state'], 'TRIGGER_RISK_UNVERIFIED')
            self.assertEqual(checks[-2]['confirmation_close_ms'], confirmation)
            self.assertEqual(report['distinct_triggers_observed_in_window'], 1)
            self.assertEqual(stopped['watch_state'], 'MISSED_WINDOW')
            self.assertEqual(checks[-1]['reason'], 'CONFIRMATION_ENTRY_WINDOW_ELAPSED')

    def test_earlier_watch_cutoff_still_caps_stage_coverage_and_expiry(self):
        cutoff = START + 2 * HOUR + 2 * M15
        for stage in ('breakout', 'retest'):
            with self.subTest(stage=stage):
                requests, report, stopped, checks, gaps = self.run_stage_expiry_fixture(stage, [
                    {'at': cutoff, 'kind': 'must_expire'}], cutoff=cutoff)
            self.assertEqual(len(requests), 2)
            self.assertEqual(checks[-1]['reason'], 'WATCH_DEADLINE')
            self.assertEqual(stopped['watch_state'], 'EXPIRED')
            self.assertTrue(all(gap['until_ms'] <= cutoff for gap in gaps))
            self.assertEqual(report['distinct_triggers_observed_in_window'], 0)


if __name__ == '__main__':
    unittest.main()
