"""Analyze independent PC-side packet captures without rewriting application evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def summarize_packets(tsv):
    packets = []
    for line in tsv.splitlines():
        if not line.strip():
            continue
        columns = line.split('\t')
        if len(columns) != 7:
            raise ValueError('unexpected tshark field count')
        flag = lambda v: v not in ('', '0', 'False')
        packets.append((float(columns[0]), int(columns[1]), int(columns[2] or '0'),
                        flag(columns[3]) or flag(columns[4]), flag(columns[5]), flag(columns[6])))
    return {'captured_packets': len(packets), 'captured_frame_bytes': sum(p[1] for p in packets),
            'tcp_payload_bytes_including_retransmissions': sum(p[2] for p in packets),
            'tcp_retransmission_packets': sum(p[3] for p in packets),
            'suspected_lost_segments': sum(p[4] for p in packets),
            'tcp_reset_packets': sum(p[5] for p in packets),
            'packet_loss_rate': None,
            'limits': ['Retransmissions are Wireshark sequence-analysis classifications.',
                       'A missing segment can reflect capture loss; it is not a proven network packet-loss rate.',
                       'Captured frame bytes exclude uncaptured preamble/interframe gaps.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--tshark', default='tshark')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if report.get('source') != 'E07_PHYSICAL':
        raise ValueError('capture analysis requires an E07 physical report')
    fields = ['frame.time_epoch', 'frame.len', 'tcp.len', 'tcp.analysis.retransmission',
              'tcp.analysis.fast_retransmission', 'tcp.analysis.lost_segment', 'tcp.flags.reset']
    base_filter = 'ip.src == 192.168.10.2 && ip.dst == 192.168.10.1 && tcp.port == 5001'
    commands = []
    def analyze(filter_text):
        command = [args.tshark, '-r', str(args.capture), '-Y', filter_text, '-T', 'fields']
        for field in fields:
            command += ['-e', field]
        completed = subprocess.run(command, text=True, capture_output=True, check=True)
        commands.append(command)
        return summarize_packets(completed.stdout)
    result = {'source': 'INDEPENDENT_PACKET_CAPTURE', 'direction': 'EDGE_TO_CLOUD',
              'capture_sha256': hashlib.sha256(args.capture.read_bytes()).hexdigest(),
              'application_report_sha256': hashlib.sha256(args.report.read_bytes()).hexdigest(),
              'overall': analyze(base_filter), 'stages': []}
    for experiment in report.get('experiments', []):
        for mode, values in experiment['modes'].items():
            start, end = values['host_start_wall_ns'] / 1e9, values['host_end_wall_ns'] / 1e9
            result['stages'].append({'camera_streams': experiment['camera_streams'], 'mode': mode,
                **analyze(f'({base_filter}) && frame.time_epoch >= {start:.9f} && frame.time_epoch <= {end:.9f}')})
    result['commands'] = commands
    output = args.report.parent / 'network_quality.json'
    with output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write('\n')
    print('NETWORK_QUALITY=' + str(output))


if __name__ == '__main__':
    main()
