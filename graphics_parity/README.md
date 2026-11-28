# Graphics Parity Harness (MATLAB vs NumKit)

Automated multi-layer visual & Handle Graphics DOM parity suite comparing NumKit's graphics engine against local MATLAB across 36 structured scenarios.

## What It Checks

1. **Runtime parity**: Every case runs in both MATLAB (`-batch`, single session) and NumKit (single session) with per-case `try/catch` isolation and wall-clock timing.
2. **Handle Graphics DOM oracle (`dump_dom.m`)**: Serializes live figure/axes/legend/children properties (`Position`, `Visible`, `Box`, `XGrid`/`YGrid`, `XLim`/`YLim`, `XTick`/`YTick`, `XScale`/`YScale`, `XDir`/`YDir`, `Legend`, child types & counts) into `dom.json` and compares them structurally.
3. **Multi-layer visual oracle (`metrics.py`)**:
   - Luminance `SSIM` (Gaussian-smoothed, resistant to 1 px font hinting)
   - Dilated `InkIoU` (`r = 3 px`, background-masked)
   - Inner plot-box `PlotIoU` (isolates data/curves from outer labels/margins)
   - Ink 6×6×6 RGB histogram `ColorL1`
   - Ink bounding-box mismatch `BBoxΔ` & aspect ratio check
   - Composite score `[0..100]` and `[MATLAB | NumKit | Color Diff Heatmap]` side-by-side PNGs
4. **Cross-format consistency (`--check-pdf`)**: Exports NumKit PDF, rasterizes via `pdftoppm`, and verifies PNG ↔ PDF ink IoU (catches PDF stream corruption, missing Unicode/Cyrillic glyphs, or renderer drift).
5. **Ratchet baseline (`baseline.json`)**: Tracks per-case scores and fails CI (`--check-ratchet`) if any case regresses by more than 3 points.

## Usage

```bash
# Fast run using cached MATLAB golden/ references (~0.6 s for all 36 cases)
python3 qa/graphics_parity/run_graphics_parity.py

# Run with cross-format PNG vs PDF consistency check
python3 qa/graphics_parity/run_graphics_parity.py --check-pdf

# Regenerate cached MATLAB golden/ references (runs MATLAB once in batch mode)
python3 qa/graphics_parity/run_graphics_parity.py --refresh-matlab --check-pdf

# Filter specific cases
python3 qa/graphics_parity/run_graphics_parity.py --cases "chart_*" --check-pdf

# Verify no regressions against committed baseline.json
python3 qa/graphics_parity/run_graphics_parity.py --check-ratchet

# Update baseline.json after fixing graphics parity gaps
python3 qa/graphics_parity/run_graphics_parity.py --check-pdf --save-baseline
```

## Outputs (gitignored)

- `golden/` — cached MATLAB reference PNGs and DOM JSONs
- `runs/latest/report.md` — ranked Markdown table of all cases
- `runs/latest/results.json` — machine-readable metrics and DOM diffs
- `runs/latest/diffs/<case>.png` — side-by-side `[MATLAB | NumKit | Diff Heatmap]` images
