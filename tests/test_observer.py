import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.observer import observe, assess, quote_values, save_new, previous_boundary, report, run_observer, HOUR
from test_backtest import fixture, START


def snap():
    d=fixture()
    return {'category':'spot','symbol':'BTCUSDT','sources':{
        'h1':{'response':{'time':START+2000,'result':{'category':'spot','symbol':'BTCUSDT',
            'list':[r for r in d['h1'] if r[0]<START]}}},
        'h4':{'response':{'time':START+2000,'result':{'category':'spot','symbol':'BTCUSDT',
            'list':[r for r in d['h4'] if r[0]<START]}}},
        'instrument':{'response':{'result':{'list':[{'symbol':'BTCUSDT','priceFilter':{'tickSize':'.1'}}]}}}}}


def book():
    return {'response':{'retCode':0,'result':{'s':'BTCUSDT','ts':START+4000,
             'b':[['109','1']],'a':[['109.1','1']]}}}


class ObserverTests(unittest.TestCase):
    def test_current_signal_quote_pass_is_not_a_trade(self):
        r=observe(START,snap,book,lambda:START+4500)
        self.assertEqual(r['decision'],'quote_pass_risk_unverified')
        self.assertEqual(r['signal']['signal_close_ms'],START)
        self.assertFalse(r['orders_placed'])
        self.assertFalse(r['live_eligible'])
        self.assertIn('quote_source',r)

    def test_expensive_first_quote_is_missed_without_retry(self):
        calls=[]
        def expensive():
            calls.append(1);b=book();b['response']['result']['a']=[['111','1']];return b
        r=observe(START,snap,expensive,lambda:START+4500)
        self.assertEqual(r['reason'],'first_observed_ask_above_maximum')
        self.assertEqual(len(calls),1)

    def test_late_start_does_not_backfill_signal_or_call_network(self):
        def forbidden():raise AssertionError('Network must not be called')
        r=observe(START,forbidden,forbidden,lambda:START+60000)
        self.assertEqual(r['decision'],'missed_check')
        self.assertNotIn('signal',r)

    def test_collection_crossing_deadline_never_attempts_entry(self):
        times=iter([START+2000,START+61000])
        r=observe(START,snap,book,lambda:next(times))
        self.assertEqual(r['reason'],'collection_finished_after_entry_window')

    def test_wrong_boundary_snapshot_rejected(self):
        def wrong():
            s=snap();s['sources']['h1']['response']['time']+=HOUR;return s
        r=observe(START,wrong,book,lambda:START+4500)
        self.assertEqual(r['decision'],'data_unavailable')

    def test_stale_future_and_preclose_quotes_rejected(self):
        for stamp in (START-1,START+1000,START+5000):
            b=book();b['response']['result']['ts']=stamp
            with self.assertRaises(ValueError):quote_values(b,START,START+4500)

    def test_deadline_applies_to_quote_received_not_just_exchange_time(self):
        signal={'entry_deadline_ms':START+60000,'max_entry_quote':'110'}
        r=assess(signal,{'received_ms':START+60000,'ask':'109'})
        self.assertEqual(r['reason'],'entry_window_expired')

    def test_no_signal_is_recorded(self):
        with patch('tools.observer.scan',return_value={'signals':[]}):
            r=observe(START,snap,lambda:self.fail('No signal needs no second quote'),lambda:START+4500)
        self.assertEqual(r['decision'],'no_signal')

    def test_atomic_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'checks'/f'{START}.json'
            save_new(p,{'boundary_ms':START,'decision':'no_signal'})
            with self.assertRaises(FileExistsError):save_new(p,{'boundary_ms':START,'decision':'changed'})
            self.assertEqual(json.loads(p.read_text())['decision'],'no_signal')
            self.assertEqual(previous_boundary(Path(folder)),START)
            self.assertEqual(list(p.parent.glob('.pending-*')),[])

    def test_restart_marks_downtime_and_does_not_overwrite_current_hour(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            save_new(directory/'checks'/f'{START-3*HOUR}.json',
                     {'boundary_ms':START-3*HOUR,'boundary_utc':'prior','decision':'no_signal'})
            with patch('tools.observer.now_ms',return_value=START+120000):
                run_observer(directory,1,once=True)
            r=report(directory)
            self.assertEqual(r['recorded_hours'],4)
            self.assertEqual(r['decisions']['missed_check'],3)
            self.assertEqual(r['paper_positions_opened'],0)
            # A second run in the same hour leaves its original observation intact.
            with patch('tools.observer.now_ms',return_value=START+120001):
                run_observer(directory,1,once=True)
            self.assertEqual(report(directory)['recorded_hours'],4)

    def test_lock_prevents_duplicate_observer(self):
        import fcntl
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            with (directory/'observer.lock').open('a+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError,'Another observer'):
                    run_observer(directory,1,once=True)


if __name__=='__main__':unittest.main()
