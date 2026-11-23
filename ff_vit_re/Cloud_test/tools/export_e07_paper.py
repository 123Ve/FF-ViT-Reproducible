"""Export hash-checked physical E07 replay evidence; never invent missing measurements."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from Cloud_test.iot_eval.cloud_measurements import percentile, summarize_frames


def export(report_path, output, plots=True):
    report_path, output = Path(report_path), Path(output)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report.get('source') != 'E07_PHYSICAL' or report.get('status') != 'COMPLETE':
        raise ValueError('Only COMPLETE E07_PHYSICAL evidence is accepted')
    raw_path = report_path.parent / 'frames.jsonl'
    raw = raw_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != report.get('evidence_sha256', {}).get('frames.jsonl'):
        raise ValueError('frames.jsonl evidence hash mismatch')
    events = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    if any(e.get('kind') == 'transaction_failure' for e in events):
        raise ValueError('transaction failure exists in allegedly complete evidence')
    board = report.get('board_benchmark')
    if board is not None:
        batches = [e['metadata'] for e in events if e.get('kind') == 'board_repeat']
        sync_hz = [e['metadata'].get('timer_frequency_hz') for e in events
                   if e.get('kind') == 'time_sync']
        if (not batches or board.get('status') != 'COMPLETE'
                or len(batches) != board.get('batches')
                or any(m.get('status') != 'ok' or m.get('count') != board.get('batch_size')
                       or any(type(m.get(k)) is not int or m[k] <= 0
                              for k in ('count', 'total_ticks', 'mm2s_ticks', 'pl_ticks', 's2mm_ticks'))
                       for m in batches)
                or sum(m['count'] for m in batches) != board.get('frames')
                or sum(m['total_ticks'] for m in batches) != board.get('total_ticks')
                or type(board.get('timer_frequency_hz')) is not int
                or board['timer_frequency_hz'] <= 0
                or not sync_hz or any(hz != board['timer_frequency_hz'] for hz in sync_hz)):
            raise ValueError('board repeat raw evidence does not match report')
        expected_ms = board['total_ticks'] / board['frames'] / board['timer_frequency_hz'] * 1000
        if not math.isclose(board.get('mean_board_latency_ms', -1), expected_ms, rel_tol=1e-9):
            raise ValueError('board repeat latency does not match raw timer evidence')
        board = dict(board)
        board['reciprocal_board_latency_fps'] = board['frames'] * board['timer_frequency_hz'] / board['total_ticks']
        board['mean_stage_ticks'] = {k: sum(m[k] for m in batches) / board['frames']
                                    for k in ('mm2s_ticks', 'pl_ticks', 's2mm_ticks')}
        host_elapsed = board.get('host_elapsed_s')
        if type(host_elapsed) not in (int, float) or not math.isfinite(host_elapsed) or host_elapsed <= 0:
            raise ValueError('board repeat host duration is invalid')
        board['host_batch_throughput_fps'] = board['frames'] / host_elapsed
        board['host_duration_basis'] = 'report-derived; per-inference timer sums verified against raw batches'
    rows, comparisons = [], []
    for experiment in report['experiments']:
        trial, streams = experiment.get('trial', 1), experiment['camera_streams']
        load = experiment.get('load_mode', 'fixed')
        rate = experiment.get('offered_fps_per_stream', report.get('configuration', {}).get('fps'))
        verified_modes = {}
        for mode, summary in experiment['modes'].items():
            stage_events = [e for e in events if e.get('mode') == mode and e.get('camera_streams') == streams
                and e.get('trial', 1) == trial and e.get('load_mode', 'fixed') == load
                and e.get('offered_fps_per_stream', rate) == rate]
            frames = [e for e in stage_events if e.get('kind') in ('cloud_frame', 'edge_result')]
            if (summary.get('status') != 'COMPLETE' or not frames
                    or len(frames) != summary['frames_received'] or len(frames) != summary['frames_sent']
                    or sum(e['socket_received_bytes'] for e in frames) != summary['socket_received_bytes']
                    or any(e['metadata'].get('mismatch_count') != 0 for e in frames)):
                raise ValueError('raw frame counts/bytes/validation do not match report')
            if (any(e['stream_id'] not in range(1, streams + 1) for e in frames)
                    or [e['request_id'] for e in frames] != list(range(1, len(frames) + 1))):
                raise ValueError('raw frame IDs are not continuous or stream IDs are invalid')
            for sid in range(1, streams + 1):
                sequence = [e['stream_sequence'] for e in frames if e['stream_id'] == sid]
                if sequence != list(range(1, len(sequence) + 1)):
                    raise ValueError('raw stream sequence is not continuous')
            elapsed = summary['elapsed_s']
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed <= 0:
                raise ValueError('stage duration is invalid')
            starts = [e for e in stage_events if e.get('kind') == 'stage_start']
            ends = [e for e in stage_events if e.get('kind') == 'stage_end']
            timing_basis = 'legacy report-derived duration; raw frame counts and arithmetic verified'
            if starts or ends or report.get('collector_revision') == 'V2.3':
                if (len(starts) != 1 or len(ends) != 1
                        or ends[0]['frames_sent'] != summary['frames_sent']
                        or not math.isclose(elapsed, (ends[0]['monotonic_ns'] - starts[0]['monotonic_ns']) / 1e9,
                                            rel_tol=1e-9, abs_tol=1e-9)):
                    raise ValueError('raw stage timing does not match report')
                timing_basis = 'raw monotonic stage boundaries, including control and evidence overhead'
            sensors = [{'monotonic_ns': e['receive_monotonic_ns'], 'power_uW': e['metadata'].get('power_uW')}
                       for e in stage_events if e.get('kind') == 'telemetry']
            derived = summarize_frames(frames, elapsed, len(frames), sensors)
            for key in ('fps', 'bytes_received_per_frame', 'bandwidth_bytes_s', 'bandwidth_mbit_s',
                        'monitored_system_energy_J', 'energy_coverage_s', 'energy_coverage_fraction'):
                if key in summary:
                    a, b = summary[key], derived[key]
                    if a != b and (type(a) not in (int, float) or type(b) not in (int, float)
                                   or not math.isfinite(a) or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)):
                        raise ValueError(f'{key} does not match raw evidence arithmetic')
            verified_modes[mode] = dict(summary, **derived)
            row = {k: v for k, v in verified_modes[mode].items() if not isinstance(v, (dict, list))}
            row.update(trial=trial, camera_streams=streams, load_mode=load, mode=mode,
                       offered_fps_per_stream=rate, evidence_status='VERIFIED_PHYSICAL_REPLAY',
                       duration_verification_basis=timing_basis)
            for key in ('e2e_ms', 'edge_receive_ms', 'inference_ms', 'edge_processing_ms', 'network_and_receive_ms'):
                values = [e.get('latency', {}).get(key) for e in frames]
                values = [v for v in values if type(v) in (int, float) and math.isfinite(v)]
                row[key + '_mean'] = statistics.mean(values) if values else None
                for suffix, q in [('p50', .5), ('p95', .95), ('p99', .99)]:
                    row[key + '_' + suffix] = percentile(values, q)
            # Preserve unreliable estimates in raw evidence, but exclude them from publication tables.
            for key in list(row):
                if key.startswith(('uplink_estimated_ms', 'result_upload_estimated_ms')):
                    del row[key]
            row['source_payload_bytes'] = sum(e.get('source_sent_payload_bytes', 0) for e in frames)
            row['source_payload_mbit_s'] = row['source_payload_bytes'] * 8 / summary['elapsed_s'] / 1e6
            energy, covered = row.get('monitored_system_energy_J'), row.get('energy_coverage_s')
            row['monitored_mean_power_W'] = energy / covered if energy is not None and covered else None
            rows.append(row)
        comparison = None
        if set(verified_modes) == {'full', 'compact'}:
            from Cloud_test.run_e07_measurements import compare_replay_modes
            comparison = compare_replay_modes(verified_modes['full'], verified_modes['compact'])
        comparisons.append(dict(trial=trial, camera_streams=streams, load_mode=load,
                                offered_fps_per_stream=rate, comparison=comparison))
    groups = {}
    for row in rows:
        groups.setdefault((row['camera_streams'], row['load_mode'], row['offered_fps_per_stream'], row['mode']), []).append(row)
    aggregate = []
    for (streams, load, rate, mode), trials in groups.items():
        entry = dict(camera_streams=streams, load_mode=load, offered_fps_per_stream=rate,
                     mode=mode, trials=len(trials))
        for key in ('fps', 'bandwidth_mbit_s', 'e2e_ms_mean', 'e2e_ms_p95', 'monitored_mean_power_W'):
            values = [r[key] for r in trials if type(r.get(key)) in (int, float) and math.isfinite(r[key])]
            entry[key + '_trial_mean'] = statistics.mean(values) if values else None
            entry[key + '_trial_sd'] = statistics.stdev(values) if len(values) > 1 else None
        aggregate.append(entry)
    result = dict(source='E07_PHYSICAL', status='VERIFIED', identity=report.get('identity'),
        report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(), frames_sha256=digest,
        configuration=report.get('configuration'), host_runtime=report.get('host_runtime'),
        rows=rows, trial_aggregates=aggregate,
        board_benchmark=board,
        comparisons=comparisons,
        unmeasured={key: 'NOT_MEASURED' for key in ('dataset_accuracy', 'cloud_model_latency',
            'internet_wan_latency', 'nic_only_energy', 'wall_power', 'tcp_retransmissions',
            'network_packet_loss', 'calibrated_one_way_latency')},
        limits=report.get('limits', []) + ['No causal energy saving claim from sequential runs.',
            'Saturation means this measured serial application workflow, not hardware peak.',
            'Trial SD is unavailable for a single trial; no fabricated error bars.'])
    output.mkdir(parents=True, exist_ok=False)
    (output/'paper_evidence.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    for name, records in [('measurements.csv', rows), ('trial_aggregates.csv', aggregate)]:
        if records:
            with (output/name).open('w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(set().union(*(r.keys() for r in records))))
                writer.writeheader()
                writer.writerows(records)
    def number(value):
        return '--' if value is None else f'{value:.4f}'
    latex = [r'\begin{tabular}{rrllrrrrrr}', r'\hline',
             r'Trial & Streams & Load & Mode & Target FPS/stream & Actual FPS & Response B/frame & Response Mbps & Mean ms & P95 ms \\', r'\hline']
    for row in rows:
        latex.append(' & '.join([str(row['trial']), str(row['camera_streams']), row['load_mode'],
            row['mode'], number(row['offered_fps_per_stream'])] +
            [number(row.get(k)) for k in ('fps', 'bytes_received_per_frame', 'bandwidth_mbit_s', 'e2e_ms_mean', 'e2e_ms_p95')]) + r' \\')
    latex += [r'\hline', r'\end{tabular}',
              '% Fixed tensor replay; Full forwards input without cloud inference. Saturation is serial stop-and-wait.']
    (output/'measurements.tex').write_text('\n'.join(latex)+'\n', encoding='utf-8')
    if plots and rows:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout='constrained')
        x = list(range(len(rows)))
        labels = [f"{r['mode']}\n{r['camera_streams']}s/{r['load_mode']}\nT{r['trial']} {r['offered_fps_per_stream']}fps" for r in rows]
        for ax, metric, title in zip(axes, ['fps', 'bandwidth_mbit_s', 'e2e_ms_p95'],
                ['Verified responses/s', 'Response application Mbit/s', 'P95 response latency (ms)']):
            ax.bar(x, [r.get(metric) if r.get(metric) is not None else float('nan') for r in rows])
            ax.set_xticks(x, labels, rotation=60, ha='right', fontsize=6)
            ax.set_ylabel(title)
        fig.suptitle('Physical E07 fixed-input replay; Full has no cloud model inference', fontsize=9)
        for suffix in ('png', 'pdf'):
            fig.savefig(output/f'measurements.{suffix}', dpi=200)
        plt.close(fig)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args(argv)
    destination = args.output or args.report.parent / 'paper'
    export(args.report, destination, plots=not args.no_plots)
    print('E07_PAPER=' + str(destination.resolve()))


if __name__ == '__main__':
    main()
