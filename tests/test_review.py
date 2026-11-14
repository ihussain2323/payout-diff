from pathlib import Path
import unittest
from payout_diff import reconcile
from review import render

class WorkpaperTest(unittest.TestCase):
    def test_controls_and_escape(self):
        examples = Path(__file__).resolve().parents[1] / 'examples'
        report = reconcile(examples/'ledger.csv', examples/'bank.csv')
        for control in report['controls_by_currency'].values():
            self.assertEqual(control['ledger_cents'], control['matched_cents'] + control['open_ledger_cents'])
            self.assertEqual(control['bank_cents'], control['matched_cents'] + control['unallocated_bank_cents'])
        self.assertEqual(report['controls_by_currency']['EUR']['unallocated_bank_cents'], 3999)
        report['payouts'][0]['payout_id'] = '<script>oops</script>'
        html = render(report)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
