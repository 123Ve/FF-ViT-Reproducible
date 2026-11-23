"""Windows executable entry point for the physical E07 experiment and English GUI."""
from pathlib import Path
import sys
from Cloud_test.run_e07_measurements import main

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--gui' not in args:
        args += ['--gui']
    if '--keep-gui' not in args:
        args += ['--keep-gui']
    if getattr(sys, 'frozen', False) and '--output-root' not in args:
        args += ['--output-root', str(Path(sys.executable).resolve().parent / 'results/stream_measurements')]
    raise SystemExit(main(args))
