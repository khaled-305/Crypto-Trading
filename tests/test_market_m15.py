"""Opt-in M15 collection: no network access or account permissions in these tests."""
import contextlib
import copy
import io
import json
import runpy
import subprocess
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from tools.market import bounded_request, collect, failure_detail


NOW = datetime(2026, 10, 2, 12, 7, 30, tzinfo=timezone.utc)
ASOF = int(NOW.timestamp() * 1000)
HOUR = 3600000
START = ASOF // HOUR * HOUR - 2 * HOUR


def bar(stamp, close='100'):
    value = int(close)
    return [stamp, close, str(value + 1), str(value - 1), close, '1', close]


def fixtures():
    series = {
        '60': [bar(START - 2 * HOUR), bar(START - HOUR), bar(START),
               bar(START + HOUR), bar(START + 2 * HOUR, '200')],
        '240': [bar((ASOF // (4 * HOUR) - 1) * 4 * HOUR),
                bar(ASOF // (4 * HOUR) * 4 * HOUR, '200')],
        '15': [bar(START + i * 900000) for i in range(8)]
              + [bar(START + 2 * HOUR, '200')],
    }
    result = {}
    for interval, rows in series.items():
        result[interval] = {'retCode': 0, 'time': ASOF,
                            'result': {'category': 'spot', 'symbol': 'BTCUSDT',
                                       'list': list(reversed(rows))}}
    result['book'] = {'retCode': 0, 'time': ASOF,
                      'result': {'s': 'BTCUSDT', 'ts': ASOF,
                                 'b': [['99.99', '1']], 'a': [['100', '1']]}}
    result['instrument'] = {'retCode': 0, 'time': ASOF,
                            'result': {'category': 'spot', 'list': [
                                {'symbol': 'BTCUSDT', 'status': 'Trading'}]}}
    return result


class M15CollectionTests(unittest.TestCase):
    def collect_fixture(self, payload, use_bounded_request=False, **kwargs):
        def fake_request(path, params):
            if path.endswith('kline'):
                key = params['interval']
            elif path.endswith('orderbook'):
                key = 'book'
            elif path.endswith('instruments-info'):
                key = 'instrument'
            else:
                raise AssertionError('Unexpected endpoint')
            if isinstance(payload[key], Exception):
                raise payload[key]
            return {'url': 'fixture', 'received_at': NOW.isoformat(), 'sha256': 'a' * 64,
                    'response': copy.deepcopy(payload[key])}

        with patch('tools.market.request', side_effect=fake_request) as requests, \
                patch('tools.market.time.time', return_value=NOW.timestamp()):
            if use_bounded_request:
                result = collect('BTCUSDT', **kwargs)
            else:
                with patch('tools.market.bounded_request', side_effect=requests) as bounded:
                    result = collect('BTCUSDT', **kwargs)
                self.assertEqual(bounded.call_count, int(kwargs.get('include_m15', False)))
                if kwargs.get('include_m15'):
                    self.assertEqual(bounded.call_args.args[1]['interval'], '15')
        return result, requests

    def test_default_keeps_four_requests_and_original_sources(self):
        result, requests = self.collect_fixture(fixtures())
        self.assertEqual(requests.call_count, 4)
        self.assertEqual(set(result['sources']), {'h1', 'h4', 'book', 'instrument'})
        self.assertEqual(result['schema_version'], 1)
        self.assertFalse(result['live_eligible'])
        self.assertNotIn('source_errors', result)
        self.assertEqual(len(result['sources']['h1']['closed_candles']), 4)

    def test_opt_in_requests_m15_and_excludes_forming_candle(self):
        result, requests = self.collect_fixture(fixtures(), include_m15=True)
        self.assertEqual(requests.call_count, 5)
        request = [call for call in requests.call_args_list
                   if call.args[1].get('interval') == '15']
        self.assertEqual(len(request), 1)
        self.assertEqual(request[0].args, ('/v5/market/kline', {
            'category': 'spot', 'symbol': 'BTCUSDT', 'interval': '15', 'limit': 1000}))
        closed = result['sources']['m15']['closed_candles']
        self.assertEqual([row[0] for row in closed], [START + i * 900000 for i in range(8)])
        self.assertTrue(all(row[4] == '100' for row in closed))
        self.assertFalse(result['live_eligible'])
        self.assertEqual(result['source_errors'], {})

    def assert_m15_unavailable(self, payload, kind='invalid_data', stage='validation'):
        result, requests = self.collect_fixture(payload, include_m15=True)
        self.assertEqual(requests.call_count, 5)
        self.assertEqual(set(result['sources']), {'h1', 'h4', 'book', 'instrument'})
        self.assertEqual(len(result['sources']['h1']['closed_candles']), 4)
        self.assertEqual(len(result['sources']['h4']['closed_candles']), 1)
        self.assertEqual(result['sources']['book']['response'], payload['book'])
        self.assertEqual(result['sources']['instrument']['response'], payload['instrument'])
        self.assertFalse(result['live_eligible'])
        error = result['source_errors']['m15']
        self.assertEqual(error['kind'], kind)
        self.assertEqual(error['stage'], stage)
        self.assertEqual(error['provenance']['url'],
                         'https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=15&limit=1000')
        if stage != 'fetch':
            self.assertEqual(error['provenance']['received_at'], NOW.isoformat())
            self.assertEqual(error['provenance']['sha256'], 'a' * 64)
        return result

    def test_gap_or_missing_latest_completed_m15_preserves_required_sources(self):
        for stamp in [START + 3 * 900000, START + 7 * 900000]:
            with self.subTest(missing=stamp):
                payload = fixtures()
                payload['15']['result']['list'] = [
                    row for row in payload['15']['result']['list'] if row[0] != stamp]
                self.assert_m15_unavailable(payload)

    def test_wrong_symbol_m15_preserves_required_sources(self):
        payload = fixtures()
        payload['15']['result']['symbol'] = 'ETHUSDT'
        self.assert_m15_unavailable(payload)

    def test_completed_m15_hourly_ohlc_disagreement_preserves_required_sources(self):
        payload = fixtures()
        payload['15']['result']['list'][-1][2] = '102'
        self.assert_m15_unavailable(payload, stage='overlap')

    def test_partial_first_hour_is_not_compared_to_full_hour(self):
        payload = fixtures()
        # Remove only the earliest window edge; subsequent M15 candles stay contiguous.
        payload['15']['result']['list'].pop()
        # The altered H1 bar lacks complete M15 coverage and must not be compared.
        first_partial_hour = next(row for row in payload['60']['result']['list'] if row[0] == START)
        first_partial_hour[2] = '102'
        # Required H1/H4 data must still agree; only optional M15 lacks the edge.
        payload['240']['result']['list'][-1][2] = '102'
        result, _ = self.collect_fixture(payload, include_m15=True)
        self.assertEqual(len(result['sources']['m15']['closed_candles']), 7)

    def test_no_fully_overlapping_hour_preserves_required_sources(self):
        payload = fixtures()
        payload['15']['result']['list'] = payload['15']['result']['list'][:4]
        self.assert_m15_unavailable(payload, stage='overlap')

    def test_inconsistent_h1_h4_rejects_required_data_with_or_without_m15(self):
        for include_m15 in (False, True):
            for field, value in ((1, '100.5'), (2, '150'), (3, '90'), (4, '100.5')):
                with self.subTest(include_m15=include_m15, field=field):
                    payload = fixtures()
                    payload['240']['result']['list'][-1][field] = value
                    with self.assertRaisesRegex(ValueError, 'Hourly OHLC disagrees'):
                        self.collect_fixture(payload, include_m15=include_m15)

    def test_h1_h4_mismatch_is_not_hidden_by_optional_m15_failure(self):
        payload = fixtures()
        payload['240']['result']['list'][-1][2] = '150'
        payload['15'] = TimeoutError('optional fixture failure')
        with self.assertRaisesRegex(ValueError, 'Hourly OHLC disagrees'):
            self.collect_fixture(payload, include_m15=True)

    def test_h1_h4_requires_at_least_one_complete_overlap(self):
        payload = fixtures()
        payload['60']['result']['list'].pop()
        with self.assertRaisesRegex(ValueError, 'No fully overlapping completed hourly/four-hour'):
            self.collect_fixture(payload)

    def test_h1_h4_partial_history_edge_does_not_invalidate_complete_overlap(self):
        payload = fixtures()
        # H4 04:00 lacks H1 04:00; its high cannot be checked against only 05–07.
        partial_start = START - 6 * HOUR
        payload['60']['result']['list'].extend(
            bar(partial_start + i * HOUR) for i in (3, 2, 1))
        partial = bar(partial_start)
        partial[2] = '150'
        payload['240']['result']['list'].append(partial)
        result, _ = self.collect_fixture(payload)
        self.assertEqual(len(result['sources']['h4']['closed_candles']), 2)
        self.assertEqual(len(result['sources']['h1']['closed_candles']), 7)

    def test_m15_timeout_preserves_required_sources_without_retry(self):
        payload = fixtures()
        payload['15'] = TimeoutError('private proxy URL or response body')
        result = self.assert_m15_unavailable(payload, kind='timeout', stage='fetch')
        self.assertNotIn('private proxy', json.dumps(result))
        self.assertEqual(set(result['source_errors']['m15']['provenance']), {'url'})

    def test_optional_dns_child_deadline_preserves_required_sources(self):
        error = subprocess.TimeoutExpired(['private command text'], 15)
        with patch('tools.market.subprocess.run', side_effect=error) as run:
            result, requests = self.collect_fixture(fixtures(), include_m15=True, use_bounded_request=True)
        self.assertEqual(requests.call_count, 4)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs['timeout'], 15)
        self.assertLess(run.call_args.kwargs['timeout'], 25)
        self.assertEqual(run.call_args.args[0][1:4], ['-m', 'tools.market', '--request-worker'])
        spec = json.loads(run.call_args.args[0][4])
        self.assertEqual(spec['params']['interval'], '15')
        self.assertEqual(set(result['sources']), {'h1', 'h4', 'book', 'instrument'})
        self.assertEqual(result['source_errors']['m15']['kind'], 'timeout')
        self.assertNotIn('private command text', json.dumps(result))

    def test_optional_child_restrictions_abort_without_retry(self):
        for kind, code in (('access_denied', 403), ('rate_limited', 429)):
            with self.subTest(code=code):
                child = subprocess.CompletedProcess([], 2, '', f'DATA UNAVAILABLE [{kind}]: private response\n')
                with patch('tools.market.subprocess.run', return_value=child) as run, \
                        self.assertRaises(urllib.error.HTTPError) as caught:
                    self.collect_fixture(fixtures(), include_m15=True, use_bounded_request=True)
                run.assert_called_once()
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn('private response', str(caught.exception))
                caught.exception.close()

    def test_malformed_optional_response_and_error_text_are_sanitized(self):
        malformed = [None, {'time': ASOF, 'result': None},
                     {'time': ASOF, 'result': {'symbol': 'BTCUSDT', 'list': None}},
                     {'time': 'private response body', 'result': {'symbol': 'BTCUSDT', 'list': []}}]
        for response in malformed:
            with self.subTest(response=response):
                payload = fixtures()
                payload['15'] = response
                result = self.assert_m15_unavailable(payload)
                self.assertNotIn('private response', json.dumps(result))
        payload = fixtures()
        payload['15'] = ValueError('secret=private response body')
        result = self.assert_m15_unavailable(payload, stage='fetch')
        self.assertNotIn('secret=', json.dumps(result))

    def test_required_source_fetch_failure_still_fails_whole_collection(self):
        for key in ('60', '240', 'book', 'instrument'):
            with self.subTest(source=key):
                payload = fixtures()
                payload[key] = TimeoutError('required source failed')
                with self.assertRaises(TimeoutError):
                    self.collect_fixture(payload, include_m15=True)

    def test_required_validation_failure_still_fails_whole_collection(self):
        for key in ('60', '240', 'book', 'instrument'):
            with self.subTest(source=key):
                payload = fixtures()
                if key in ('60', '240'):
                    payload[key]['result']['symbol'] = 'ETHUSDT'
                elif key == 'book':
                    payload[key]['result']['s'] = 'ETHUSDT'
                else:
                    payload[key]['result']['list'][0]['status'] = 'Settling'
                with self.assertRaises(ValueError):
                    self.collect_fixture(payload, include_m15=True)

    def test_restricted_optional_request_aborts_even_if_required_request_also_failed(self):
        for code in (403, 429):
            for other_failure in (False, True):
                with self.subTest(code=code, other_failure=other_failure):
                    payload = fixtures()
                    error = urllib.error.HTTPError('https://api.bybit.com', code, 'untrusted body', {}, None)
                    payload['15'] = error
                    if other_failure:
                        payload['60'] = TimeoutError('required source failed')
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        self.collect_fixture(payload, include_m15=True)
                    self.assertIs(caught.exception, error)
                    error.close()

    def test_restricted_required_request_aborts(self):
        for code in (403, 429):
            for key in ('60', '240', 'book', 'instrument'):
                with self.subTest(code=code, source=key):
                    payload = fixtures()
                    error = urllib.error.HTTPError('https://api.bybit.com', code, 'untrusted body', {}, None)
                    payload[key] = error
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        self.collect_fixture(payload, include_m15=True)
                    self.assertIs(caught.exception, error)
                    error.close()

    def test_m15_response_time_controls_completed_candles(self):
        payload = fixtures()
        payload['15']['time'] = START + 2 * HOUR - 1
        payload['15']['result']['list'] = payload['15']['result']['list'][1:]
        result, _ = self.collect_fixture(payload, include_m15=True)
        closed = result['sources']['m15']['closed_candles']
        self.assertEqual(len(closed), 7)
        self.assertEqual(closed[-1][0], START + 6 * 900000)

    def test_future_m15_candle_degrades_to_required_sources(self):
        payload = fixtures()
        payload['15']['result']['list'][0][0] += 900000
        self.assert_m15_unavailable(payload)

    def test_book_cannot_postdate_its_own_response(self):
        payload = fixtures()
        payload['book']['result']['ts'] += 1
        for include in (False, True):
            with self.subTest(include_m15=include), \
                    self.assertRaisesRegex(ValueError, 'timestamp follows its API response'):
                self.collect_fixture(payload, include_m15=include)


class M15CommandTests(unittest.TestCase):
    def test_bounded_worker_timeout_prefix_stays_timeout(self):
        child = subprocess.CompletedProcess([], 2, '', 'DATA UNAVAILABLE [timeout]: private response\n')
        with patch('tools.market.subprocess.run', return_value=child), \
                self.assertRaises(TimeoutError) as caught:
            bounded_request('/v5/market/kline', {'category': 'spot', 'symbol': 'BTCUSDT', 'interval': '15'})
        self.assertEqual(failure_detail(caught.exception)[0], 'timeout')
        self.assertNotIn('private response', str(caught.exception))

    def test_bounded_worker_does_not_parse_embedded_or_copy_error_text(self):
        for stderr in ('private=secret',
                       'DATA UNAVAILABLE [invalid_data]: DATA UNAVAILABLE [access_denied]: private=secret'):
            with self.subTest(stderr=stderr):
                child = subprocess.CompletedProcess([], 2, '', stderr)
                with patch('tools.market.subprocess.run', return_value=child), \
                        self.assertRaises(ValueError) as caught:
                    bounded_request('/v5/market/kline', {'category': 'spot', 'symbol': 'BTCUSDT', 'interval': '15'})
                self.assertEqual(str(caught.exception), 'Bounded public-data request failed; no data accepted')

    def test_cli_forwards_opt_in_and_preserves_bounded_default(self):
        for include in (False, True):
            with self.subTest(include_m15=include), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'snapshot.json'
                argv = ['tools.market', '--symbol', 'BTCUSDT', '--out', str(output)]
                if include:
                    argv.append('--include-m15')
                child = subprocess.CompletedProcess([], 0, json.dumps({'fixture': True}), '')
                with patch('sys.argv', argv), patch('subprocess.run', return_value=child) as run, \
                        contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path('tools/market.py', run_name='__main__')
                run.assert_called_once()
                command = run.call_args.args[0]
                self.assertEqual('--include-m15' in command, include)
                self.assertEqual(command[1:6], ['-m', 'tools.market', '--worker', '--symbol', 'BTCUSDT'])
                self.assertEqual(run.call_args.kwargs['timeout'], 25)
                self.assertEqual(json.loads(output.read_text()), {'fixture': True})


if __name__ == '__main__':
    unittest.main()
