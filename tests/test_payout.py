import tempfile
import unittest
from pathlib import Path
from payout_diff import cents, reconcile


class ReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / 'ledger.csv'
        self.bank = Path(self.tmp.name) / 'bank.csv'

    def run_case(self, ledger, bank):
        self.ledger.write_text('entry_id,payout_id,currency,date,amount\n' + ledger)
        self.bank.write_text('deposit_id,reference,currency,date,amount\n' + bank)
        return reconcile(self.ledger, self.bank)

    def test_demo(self):
        base = Path(__file__).resolve().parents[1] / 'examples'
        report = reconcile(base / 'ledger.csv', base / 'bank.csv')
        self.assertEqual([p['status'] for p in report['payouts']],
                         ['matched_reference', 'matched_amount_date', 'ambiguous', 'ambiguous', 'reference_mismatch'])
        self.assertEqual(report['unallocated_deposits'], ['dep_c', 'dep_d'])
        self.assertEqual(report['payouts'][0]['expected_cents'], 8680)

    def test_fallback_respects_reference_currency_and_date(self):
        report = self.run_case('i,p,USD,2025-01-03,20', 'd,,EUR,2025-01-03,20\ne,x,USD,2025-01-03,20\nf,,USD,2025-01-07,20')
        self.assertEqual(report['payouts'][0]['status'], 'missing_deposit')

    def test_duplicate_reference(self):
        report = self.run_case('i,p,USD,2025-01-03,20', 'd,p,USD,2025-01-03,20\ne,p,USD,2025-01-04,20')
        self.assertEqual(report['payouts'][0]['status'], 'duplicate_reference')

    def test_duplicate_entry_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.run_case('i,p,USD,2025-01-03,20\ni,p,USD,2025-01-03,20', '')

    def test_exact_cents(self):
        self.assertEqual(cents('-0.01'), -1)
        self.assertEqual(cents('123456789012345678.90'), 12345678901234567890)
        for bad in ['0.001', '1e3', 'NaN', '']:
            with self.assertRaises(ValueError):
                cents(bad)
