"""Fail closed before exporting a deployable E07 hardware platform."""
import re
import sys
from pathlib import Path


def evaluate(root):
    timing = (root/'timing.rpt').read_text()
    route = (root/'route.rpt').read_text()
    drc = (root/'drc.rpt').read_text()
    clock = (root/'clock.txt').read_text()
    csim = (root/'csim.log').read_text()
    for check in ('no_clock', 'unconstrained_internal_endpoints'):
        match = re.search(r'checking '+check+r' \((\d+)\)', timing)
        if not match or int(match.group(1)) != 0:
            raise ValueError('Missing or failing timing coverage: '+check)
    summary = timing.split('WNS(ns)', 1)[1]
    rows = [line.split() for line in summary.splitlines()
            if re.match(r'^\s*-?\d+\.\d+\s', line)]
    if not rows or len(rows[0]) < 12:
        raise ValueError('Missing complete timing summary')
    values = list(map(float, rows[0][:12]))
    for slack, total, failures in ((0,1,2), (4,5,6), (8,9,10)):
        if values[slack] < 0 or values[total] != 0 or values[failures] != 0:
            raise ValueError('Setup/hold/pulse-width timing failed')
    counts = {}
    for label in ('routable nets', 'fully routed nets', 'nets with routing errors'):
        match = re.search(r'# of '+label+r'\.+\s*:\s*(\d+)', route)
        if not match:
            raise ValueError('Incomplete route report: '+label)
        counts[label] = int(match.group(1))
    if (counts['routable nets'] <= 0 or counts['routable nets'] != counts['fully routed nets']
            or counts['nets with routing errors'] != 0):
        raise ValueError('Routing incomplete')
    if 'Report DRC' not in drc or re.search(r'\|\s*(Error|Critical Warning)\s*\|', drc):
        raise ValueError('DRC errors or missing report')
    frequency = re.search(r'^PL_ACTUAL_MHZ=([\d.]+)$', clock, re.M)
    period = re.search(r'^PL_PERIOD_NS=([\d.]+)$', clock, re.M)
    if not frequency or float(frequency.group(1)) < 300.0:
        raise ValueError('Actual core clock is below 300 MHz')
    if not period or float(period.group(1)) > 3.334:
        raise ValueError('Implementation clock does not constrain 300 MHz')
    if float(period.group(1)) > 1000.0 / float(frequency.group(1)) + 0.00051:
        raise ValueError('Timing constraint slower than configured hardware clock')
    source = re.search(r'^CLOCK_SOURCE=(\w+)$', clock, re.M)
    if source and source.group(1) not in ('PS', 'MMCM'):
        raise ValueError('Unknown clock source')
    if source and source.group(1) == 'MMCM':
        def number(name):
            match = re.search(r'^'+name+r'=([\d.]+)$', clock, re.M)
            if not match or float(match.group(1)) <= 0:
                raise ValueError('Missing or invalid MMCM evidence: '+name)
            return float(match.group(1))
        computed = (number('PS_PL_ACTUAL_MHZ') * number('MMCM_MULT') /
                    number('MMCM_DIVCLK') / number('MMCM_OUT_DIV'))
        if abs(computed - float(frequency.group(1))) > 0.0005:
            raise ValueError('Actual output clock disagrees with implemented MMCM divisors')
        for configured, implemented in (
                ('MMCM_MULT', 'IMPLEMENTED_CLKFBOUT_MULT_F'),
                ('MMCM_DIVCLK', 'IMPLEMENTED_DIVCLK_DIVIDE'),
                ('MMCM_OUT_DIV', 'IMPLEMENTED_CLKOUT0_DIVIDE_F')):
            if abs(number(configured) - number(implemented)) > 0.00001:
                raise ValueError('Configured and implemented MMCM mismatch: '+implemented)
        for check in ('RESET_LOCK_VERIFIED', 'CORE_CLOCK_CONSUMERS_VERIFIED'):
            if number(check) != 1:
                raise ValueError('Unverified MMCM topology: '+check)
    frames = re.findall(r'E04 frame=(\d+) layers=12 logits=1000 cumulative_mismatch=(\d+)', csim)
    if frames != [('0','0'), ('1','0'), ('2','0')]:
        raise ValueError('Three-call bit-exact C regression incomplete or failed')


if __name__ == '__main__':
    try:
        evaluate(Path(sys.argv[1]))
    except (OSError, ValueError, IndexError) as error:
        print('RELEASE_REJECTED: '+str(error), file=sys.stderr)
        sys.exit(1)
    print('RELEASE_APPROVED: timing/route/DRC/clock/C regression; board validation pending')
