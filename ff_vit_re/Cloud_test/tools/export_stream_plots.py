"""Export measured stream reports as publication-sized PNG/PDF figures."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if report['status'] != 'COMPLETE':
        raise ValueError('Only complete runs can be plotted; inspect failed raw evidence first')
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.5), layout='constrained')
    if report['source'] == 'HOST_LOOPBACK_SYNTHETIC':
        experiments = report['experiments']
        x = [e['camera_streams'] for e in experiments]
        for mode, style in [('full', 'o-'), ('compact', 's-')]:
            modes = [e['modes'][mode] for e in experiments]
            axes[0].plot(x, [m['aggregate_bandwidth_mbit_s'] for m in modes], style, label=mode)
            axes[1].plot(x, [sum(s['fps'] for s in m['streams']) / len(m['streams']) for m in modes], style, label=mode)
            axes[2].plot(x, [max(s['command_response_latency_p95_ms'] for s in m['streams']) for m in modes], style, label=mode)
        labels = ['Received application bandwidth (Mbit/s)', 'Mean FPS per simulated stream', 'Max per-stream P95 receive latency (ms)']
        for ax in axes:
            ax.set_xlabel('Simulated streams')
            ax.set_xticks(x)
        fig.suptitle('Host loopback synthetic traffic — no physical camera / FPGA concurrency claim', fontsize=10)
    elif report['source'] == 'E07_PHYSICAL' and 'experiments' in report:
        experiments = report['experiments']
        x = [e['camera_streams'] for e in experiments]
        for mode, style in [('full', 'o-'), ('compact', 's-')]:
            modes = [e['modes'][mode] for e in experiments]
            axes[0].plot(x, [m['bandwidth_mbit_s'] for m in modes], style, label=mode)
            axes[1].plot(x, [m['fps'] / e['camera_streams'] for e, m in zip(experiments, modes)], style, label=mode)
            axes[2].plot(x, [m['e2e_ms_p95'] for m in modes], style, label=mode)
        labels = ['Cloud application ingress (Mbit/s)', 'Mean FPS per replay stream', 'PC-edge-PC replay P95 E2E (ms)']
        for ax in axes:
            ax.set_xlabel('Multiplexed fixed-tensor source streams')
            ax.set_xticks(x)
        fig.suptitle('E07 physical FPGA — fixed-tensor replay, one serial accelerator', fontsize=10)
    else:
        modes = report['modes']
        for ax, metric in zip(axes, ['bandwidth_mbit_s', 'command_response_latency_p95_ms', 'monitored_system_energy_J']):
            values = [modes[m][metric] for m in ('full', 'compact')]
            if any(v is None for v in values):
                ax.text(.5, .5, 'Unavailable', ha='center', va='center', transform=ax.transAxes)
            else:
                ax.bar(['full', 'compact'], values, color=['#2878b5', '#e07b39'])
        labels = ['Received application bandwidth (Mbit/s)', 'Command response P95 latency (ms)', 'Monitored rail energy over valid samples (J)']
        fig.suptitle('E06 physical paired upload experiment', fontsize=10)
    for ax, label in zip(axes, labels):
        ax.set_ylabel(label, fontsize=9)
        ax.grid(axis='y', alpha=.25)
    if report['source'] in ('HOST_LOOPBACK_SYNTHETIC', 'E07_PHYSICAL'):
        axes[0].legend()
    for suffix in ('png', 'pdf'):
        output = args.report.parent / f'stream_measurements.{suffix}'
        fig.savefig(output, dpi=220)
        print(output.resolve())
    plt.close(fig)


if __name__ == '__main__':
    main()
