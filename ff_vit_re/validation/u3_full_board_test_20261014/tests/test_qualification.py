import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class ReportTests(unittest.TestCase):
    def test_timing_requires_all_three_slacks_and_zero_failures(self):
        from qualify import timing_values
        rpt='checking no_clock (0)\nchecking unconstrained_internal_endpoints (0)\nWNS(ns) TNS(ns) Fail Total WHS(ns) THS Fail Total WPWS TPWS Fail Total\n 0.023 0.000 0 123 0.012 0.000 0 456 0.100 0.000 0 789\n'
        self.assertEqual(timing_values(rpt)['wns'],0.023)
        for old,new in [('0.023','-0.023'),('0.012','-0.012'),('0.100','-0.100'),
                        ('0 123','1 123'),('no_clock (0)','no_clock (1)'),
                        ('unconstrained_internal_endpoints (0)','unconstrained_internal_endpoints (1)')]:
            with self.assertRaises(ValueError): timing_values(rpt.replace(old,new))
        with self.assertRaises(ValueError): timing_values('')

    def test_route_requires_routable_and_routed_counts_to_match(self):
        from qualify import route_values
        rpt='# of routable nets.... : 120\n# of fully routed nets.... : 120\n# of nets with routing errors.... : 0\n'
        self.assertEqual(route_values(rpt)['unrouted'],0)
        with self.assertRaises(ValueError): route_values(rpt.replace('routed nets.... : 120','routed nets.... : 119'))
        with self.assertRaises(ValueError): route_values('')

if __name__=='__main__': unittest.main()
