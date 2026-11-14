import unittest
from stress import exercise


class CloseSimulationTest(unittest.TestCase):
    def test_all_fault_classes(self):
        result = exercise(14, 17)
        self.assertEqual(result['payouts'], 16)
        self.assertEqual(result['allocated_deposits'], 4)
        self.assertEqual(result['unallocated_deposits'], 10)
