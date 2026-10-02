"""Offline TPB journal exposure and append-only correction regressions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.journal import append, report


def signal(stamp, decision='paper'):
    return {'type': 'signal', 'mode': 'paper', 'strategy': 'TPB-v1',
            'symbol': 'BTCUSDT', 'timestamp': stamp, 'decision': decision,
            'reason': 'synthetic chronology fixture', 'initial_risk_usdt': '.5',
            'entry': '100', 'stop': '98', 'target': '107', 'quantity': '.2',
            'estimated_cost_usdt': '.04'}


def outcome(ident, stamp, pnl='1'):
    return {'type': 'outcome', 'mode': 'paper', 'strategy': 'TPB-v1',
            'symbol': 'BTCUSDT', 'timestamp': stamp, 'signal_id': ident,
            'reason': 'synthetic chronology fixture', 'net_pnl_usdt': pnl,
            'observed_cost_usdt': '.04', 'exit_price': '107'}


def void(ident):
    return {'type': 'void', 'mode': 'paper', 'strategy': 'TPB-v1',
            'symbol': 'BTCUSDT', 'timestamp': '2026-09-25T00:00:00Z',
            'voids_id': ident, 'reason': 'correct synthetic chronology'}


def stamp(hour, minute=0):
    return f'2026-09-24T{hour:02d}:{minute:02d}:00Z'


class JournalChronologyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'paper.jsonl'

    def events(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def trade(self, entry_hour, exit_hour):
        entry = append(self.path, signal(stamp(entry_hour)))
        close = append(self.path, outcome(entry, stamp(exit_hour)))
        return entry, close

    def reject_unchanged(self, event, pattern='overlapping exposure'):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, pattern):
            append(self.path, event)
        self.assertEqual(self.path.read_bytes(), before)

    def test_closed_position_still_blocks_overlapping_historical_entry(self):
        self.trade(12, 14)
        self.reject_unchanged(signal(stamp(13)))
        self.assertEqual(report(self.events())['closed_trades'], 1)

    def test_historical_adjacent_intervals_allow_equivalent_timezone_boundary(self):
        self.trade(12, 14)
        entry = append(self.path, signal('2026-09-24T15:00:00+01:00'))
        append(self.path, outcome(entry, stamp(15)))
        result = report(self.events())
        self.assertEqual(result['closed_trades'], 2)
        self.assertEqual(result['net_pnl_usdt'], 2)
        self.assertFalse(result['live_eligible'])

    def test_timezone_equivalent_overlap_is_rejected(self):
        self.trade(12, 14)
        self.reject_unchanged(signal('2026-09-24T14:59:00+01:00'))

    def test_open_entry_cannot_be_inserted_before_existing_closed_trade(self):
        self.trade(14, 15)
        self.reject_unchanged(signal(stamp(12)))

    def test_second_open_entry_is_rejected(self):
        append(self.path, signal(stamp(12)))
        self.reject_unchanged(signal(stamp(13)))

    def test_report_rejects_legacy_overlap_instead_of_counting_profit(self):
        self.trade(12, 14)
        self.trade(14, 15)
        legacy = copy.deepcopy(self.events())
        legacy[2]['timestamp'] = stamp(13)
        with self.assertRaisesRegex(ValueError, 'overlapping exposure'):
            report(legacy)

    def test_earlier_outcome_void_is_pending_until_valid_replacement(self):
        first, close = self.trade(12, 14)
        self.trade(14, 15)
        append(self.path, void(close))
        with self.assertRaisesRegex(ValueError, 'pending outcome correction'):
            report(self.events())
        self.reject_unchanged(signal(stamp(16)), 'pending outcome correction')
        append(self.path, signal(stamp(16), decision='skip'))
        append(self.path, signal(stamp(17), decision='missed'))
        append(self.path, outcome(first, stamp(13), pnl='-.5'))
        result = report(self.events())
        self.assertEqual(result['closed_trades'], 2)
        self.assertEqual(result['net_pnl_usdt'], .5)
        self.assertEqual(result['skipped_or_missed'], 2)
        self.assertEqual(len(self.events()), 8)
        append(self.path, signal(stamp(18)))

    def test_replacement_exit_cannot_cross_later_entry(self):
        first, close = self.trade(12, 14)
        self.trade(14, 15)
        append(self.path, void(close))
        self.reject_unchanged(outcome(first, stamp(14, 30)))
        with self.assertRaisesRegex(ValueError, 'pending outcome correction'):
            report(self.events())
        append(self.path, outcome(first, '2026-09-24T15:00:00+01:00'))
        self.assertEqual(report(self.events())['closed_trades'], 2)

    def test_voiding_corrected_signal_clears_pending_without_erasing_history(self):
        first, close = self.trade(12, 14)
        self.trade(14, 15)
        append(self.path, void(close))
        append(self.path, void(first))
        self.assertEqual(len(self.events()), 6)
        self.assertEqual(report(self.events())['closed_trades'], 1)
        append(self.path, signal(stamp(16)))

    def test_zero_duration_closed_trade_and_correction_remain_supported(self):
        first, close = self.trade(12, 12)
        append(self.path, void(close))
        with self.assertRaisesRegex(ValueError, 'pending outcome correction'):
            report(self.events())
        append(self.path, outcome(first, stamp(12), pnl='-.5'))
        self.assertEqual(report(self.events())['mean_net_r'], -1)

    def test_legacy_overlapping_outcome_can_be_corrected_append_only(self):
        first, close = self.trade(12, 14)
        self.trade(14, 15)
        legacy = self.events()
        legacy[2]['timestamp'] = stamp(13)
        self.path.write_text(''.join(json.dumps(e) + '\n' for e in legacy))
        original = self.path.read_bytes()
        append(self.path, void(close))
        append(self.path, outcome(first, stamp(13)))
        self.assertTrue(self.path.read_bytes().startswith(original))
        self.assertEqual(report(self.events())['closed_trades'], 2)

    def void_trade(self, entry, close):
        append(self.path, void(close))
        append(self.path, void(entry))

    def replacement(self, original, when, **changes):
        return dict(signal(when), replaces_signal_id=original, **changes)

    def test_earlier_closed_signal_risk_can_be_corrected_after_later_trade(self):
        first, close = self.trade(12, 14)
        self.trade(14, 15)
        original_bytes = self.path.read_bytes()
        self.void_trade(first, close)
        replacement = append(self.path, self.replacement(first, stamp(12), initial_risk_usdt='1'))
        with self.assertRaisesRegex(ValueError, 'pending outcome correction'):
            report(self.events())
        self.reject_unchanged(signal(stamp(16)), 'pending outcome correction')
        append(self.path, signal(stamp(16), decision='skip'))
        append(self.path, signal(stamp(17), decision='missed'))
        append(self.path, outcome(replacement, stamp(14)))
        result = report(self.events())
        self.assertEqual(result['closed_trades'], 2)
        self.assertEqual(result['mean_net_r'], 1.5)
        self.assertEqual(result['skipped_or_missed'], 2)
        self.assertTrue(self.path.read_bytes().startswith(original_bytes))

    def test_linked_entry_timestamp_correction_accepts_adjacent_boundaries(self):
        self.trade(10, 12)
        middle, close = self.trade(13, 14)
        self.trade(14, 15)
        self.void_trade(middle, close)
        replacement = append(self.path, self.replacement(middle, '2026-09-24T13:00:00+01:00'))
        append(self.path, outcome(replacement, '2026-09-24T15:00:00+01:00'))
        self.assertEqual(report(self.events())['closed_trades'], 3)

    def test_linked_correction_exit_cannot_overlap_following_trade(self):
        first, close = self.trade(12, 14)
        self.trade(14, 15)
        self.void_trade(first, close)
        replacement = append(self.path, self.replacement(first, stamp(12)))
        self.reject_unchanged(outcome(replacement, stamp(14, 30)))
        with self.assertRaisesRegex(ValueError, 'pending outcome correction'):
            report(self.events())
        append(self.path, outcome(replacement, stamp(14)))
        self.assertEqual(report(self.events())['closed_trades'], 2)

    def test_linked_correction_entry_cannot_overlap_preceding_trade(self):
        self.trade(10, 12)
        middle, close = self.trade(13, 14)
        self.trade(14, 15)
        self.void_trade(middle, close)
        replacement = append(self.path, self.replacement(middle, stamp(11)))
        self.reject_unchanged(outcome(replacement, stamp(14)))
        append(self.path, void(replacement))
        corrected = append(self.path, self.replacement(middle, stamp(12)))
        append(self.path, outcome(corrected, stamp(14)))
        self.assertEqual(report(self.events())['closed_trades'], 3)

    def test_replacement_rejects_unknown_unvoided_nonpaper_and_unclosed_sources(self):
        closed, _ = self.trade(12, 14)
        skipped = append(self.path, signal(stamp(15), decision='skip'))
        append(self.path, void(skipped))
        unclosed = append(self.path, signal(stamp(16)))
        append(self.path, void(unclosed))
        for reference in ('unknown', closed, skipped):
            with self.subTest(reference=reference):
                self.reject_unchanged(self.replacement(reference, stamp(17)), 'voided paper signal')
        self.reject_unchanged(self.replacement(unclosed, stamp(17)), 'previously recorded outcome')

    def test_replacement_link_requires_paper_signal_and_valid_string(self):
        first, close = self.trade(12, 14)
        self.void_trade(first, close)
        for reference in ('', None, []):
            with self.subTest(reference=reference):
                self.reject_unchanged(self.replacement(reference, stamp(12)), 'voided paper signal ID')
        self.reject_unchanged(dict(signal(stamp(12), decision='skip'), replaces_signal_id=first),
                              'only valid on a paper signal correction')

    def test_same_voided_signal_cannot_have_two_active_replacements(self):
        first, close = self.trade(12, 14)
        self.void_trade(first, close)
        replacement = append(self.path, self.replacement(first, stamp(12)))
        append(self.path, outcome(replacement, stamp(14)))
        self.reject_unchanged(self.replacement(first, stamp(16)), 'already has an active replacement')

    def test_report_rejects_forged_replacement_link_even_when_exposure_fits(self):
        self.trade(12, 14)
        forged = self.events()
        forged[0]['replaces_signal_id'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'voided paper signal'):
            report(forged)

    def replacement_chain(self):
        original, close = self.trade(12, 14)
        self.void_trade(original, close)
        middle = append(self.path, self.replacement(original, stamp(12)))
        middle_close = append(self.path, outcome(middle, stamp(14)))
        self.void_trade(middle, middle_close)
        current = append(self.path, self.replacement(middle, stamp(12)))
        current_close = append(self.path, outcome(current, stamp(14)))
        return original, middle, current, current_close

    def test_replacement_lineage_rejects_forks_from_any_ancestor(self):
        original, middle, _, _ = self.replacement_chain()
        for ancestor in (original, middle):
            with self.subTest(ancestor=ancestor):
                self.reject_unchanged(self.replacement(ancestor, stamp(16)),
                                      'already has an active replacement in its lineage')
        result = report(self.events())
        self.assertEqual(result['closed_trades'], 1)
        self.assertEqual(result['net_pnl_usdt'], 1)

    def test_repeated_linked_correction_remains_supported_after_voiding_current(self):
        _, _, current, current_close = self.replacement_chain()
        original_bytes = self.path.read_bytes()
        self.void_trade(current, current_close)
        corrected = append(self.path, self.replacement(current, stamp(12), initial_risk_usdt='1'))
        with self.assertRaisesRegex(ValueError, 'pending outcome correction'):
            report(self.events())
        self.reject_unchanged(signal(stamp(16)), 'pending outcome correction')
        append(self.path, outcome(corrected, stamp(14)))
        result = report(self.events())
        self.assertEqual(result['closed_trades'], 1)
        self.assertEqual(result['mean_net_r'], 1)
        self.assertTrue(self.path.read_bytes().startswith(original_bytes))

    def test_report_rejects_legacy_replacement_lineage_fork(self):
        original, _, _, _ = self.replacement_chain()
        invalid = self.events()
        invalid.append(dict(self.replacement(original, stamp(16)), id='fork'))
        invalid.append(dict(outcome('fork', stamp(17)), id='fork-outcome'))
        with self.assertRaisesRegex(ValueError, 'already has an active replacement in its lineage'):
            report(invalid)


if __name__ == '__main__':
    unittest.main()
