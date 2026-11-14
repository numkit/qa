# NumKit QA (`numkit/qa`)

External differential testing, specification-driven parity & benchmark harnesses, real-world corpus validation, and baseline migration audits for [`numkit/bundle`](https://github.com/numkit/bundle).

## Repository Layout

```text
numkit/qa/
├── parity/                 # Specification-driven parity & benchmark harness
│   ├── run_parity.py       # Parity & benchmark runner (--all, --module <domain>, --isolated)
│   ├── signprobe.py        # `help <fn>` call-signature comparison
│   ├── inventory/          # Reference TOC extractor and coverage diff
│   ├── specs/              # 1,606 JSON specs across 8 domains (core, signal, stats, image, comm, control, wavelet, audio)
│   ├── PROGRESS.md         # Parity coverage & correctness map
│   └── BENCHMARK.md        # Two-point performance table (small & large problem sizes)
├── fieldtest/              # Real-world script differential testing (.mat workspace comparison)
│   ├── fetch.py            # External corpus downloader & UTF-8 normalizer
│   ├── harness.py          # Qualification & batch workspace comparison runner
│   ├── compare.py          # Curated regression group runner
│   ├── groups/             # Curated regression groups
│   ├── data/               # runnable.json, candidates.json, answers.json
│   └── reports/            # Committed batch execution reports
└── audits/                 # Baseline-driven code health & migration gates
    ├── argcheck_audit.py   # Verifies argcheck separation & diagnostic conventions (--gate)
    ├── api_shape_audit.py  # Verifies memory_resource parameter placement (--gate)
    └── baselines/          # Committed audit baselines
```

## Connecting to `numkit/bundle`

By default, every tool in `numkit/qa` looks for a sibling checkout at `../bundle` (and its built CLI at `../bundle/build/bin/numkit` or `../bundle/build/bin/Release/numkit.exe`).

You can override paths via environment variables:

| Variable | Default | Description |
|---|---|---|
| `NUMKIT_BUNDLE_DIR` | `../bundle` | Path to the `numkit/bundle` checkout |
| `NUMKIT_EXE` | Auto-detected in `NUMKIT_BUNDLE_DIR/build/bin/` | Explicit path to the `numkit` CLI binary |
| `MATLAB_EXE` | `matlab` (from `PATH`) | Reference MATLAB executable |
| `OCTAVE_EXE` | `octave-cli` (from `PATH`) | Reference GNU Octave CLI executable |
| `NUMKIT_CORPUS_DIR` | `fieldtest/corpus` | Local gitignored cache directory for `fieldtest/fetch.py` |

## Usage

### 1. Specification-Driven Parity & Benchmarks (`parity/`)
```bash
# Single function spec (auto-resolved across parity/specs/*/)
python3 parity/run_parity.py butter

# Run NumKit-only smoke check without external reference engines
python3 parity/run_parity.py --module signal --no-matlab --no-octave

# Isolated namespace mode
python3 parity/run_parity.py --module signal --isolated

# Full 1,606-spec suite
python3 parity/run_parity.py --all
```

### 2. Real-World Corpus Differential Testing (`fieldtest/`)
```bash
python3 fieldtest/fetch.py --list
python3 fieldtest/compare.py --list
python3 fieldtest/compare.py mdadams
```

### 3. Baseline Migration Audits (`audits/`)
```bash
python3 audits/argcheck_audit.py --gate
python3 audits/api_shape_audit.py --gate
```
