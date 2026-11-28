#!/usr/bin/env python3
"""Visual & DOM Graphics Parity Runner (MATLAB vs NumKit).

Runs all graphics test cases in a single batched MATLAB session (cached into
`golden/`) and a single batched NumKit session, then compares:
  1. Runtime status (ok / error)
  2. Live Handle Graphics DOM snapshots (axes, limits, ticks, legend, children)
  3. Multi-layer rendered PNG metrics (SSIM, Ink-IoU, Plot-box IoU, BBox, Color L1)
  4. Optional cross-format check (NumKit PNG vs rasterized NumKit PDF via pdftoppm)
  5. Side-by-side [MATLAB | NumKit | Diff-heatmap] PNGs & ranked Markdown report.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cases import CASES, GraphicsCase
from metrics import DomDiffSummary, VisualMetrics, compare_dom, compare_images

ROOT = Path(__file__).resolve().parent
GOLDEN_DIR = ROOT / "golden"
RUNS_DIR = ROOT / "runs" / "latest"
BASELINE_FILE = ROOT / "baseline.json"
DEFAULT_NUMKIT = Path("/home/user/Projects/numkit/bundle/build/bin/numkit")


def find_numkit_bin(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    if DEFAULT_NUMKIT.exists():
        return DEFAULT_NUMKIT
    found = shutil.which("numkit")
    if found:
        return Path(found)
    raise FileNotFoundError("Could not find numkit binary; pass --numkit PATH")


def find_matlab_bin(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    return shutil.which("matlab")


def write_batch_script(
    cases: List[GraphicsCase],
    out_dir: Path,
    engine_kind: str,
    export_pdf: bool,
) -> Path:
    """Generates a single batched .m script that isolates and runs every case."""
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = out_dir / f"batch_{engine_kind}.m"
    lines: List[str] = [
        f"% Auto-generated graphics parity batch for {engine_kind}",
        f"addpath('{ROOT.as_posix()}');",
        f"meta_fid = fopen('{(out_dir / 'meta.jsonl').as_posix()}', 'w');",
        "",
    ]
    for c in cases:
        case_dir = out_dir / c.name
        case_dir.mkdir(parents=True, exist_ok=True)
        case_m = case_dir / "case_body.m"
        case_m.write_text(c.code.strip() + "\n", encoding="utf-8")

        png_path = (case_dir / "plot.png").as_posix()
        pdf_path = (case_dir / "plot.pdf").as_posix()
        dom_path = (case_dir / "dom.json").as_posix()

        lines.append(f"% === CASE: {c.name} ===")
        lines.append("close all force; rng(42);")
        lines.append("t_case = tic;")
        lines.append("ok_flag = 1; err_msg = '';")
        lines.append("try")
        if engine_kind == "matlab":
            lines.append("    set(0, 'DefaultFigureVisible', 'off');")
        lines.append(f"    run('{case_m.as_posix()}');")
        lines.append("    f_cur = gcf;")
        lines.append(f"    dump_dom(f_cur, '{dom_path}');")
        if engine_kind == "matlab":
            # exportgraphics auto-crops in MATLAB; print -dpng preserves full Figure.Position
            # canvas exactly as shown on screen (matching NumKit Figure.Position scaling).
            lines.append("    set(f_cur, 'PaperPositionMode', 'auto', 'InvertHardcopy', 'off');")
            lines.append(f"    print(f_cur, '{png_path}', '-dpng', '-r{c.dpi}');")
        else:
            lines.append(f"    exportgraphics(f_cur, '{png_path}', 'Resolution', {c.dpi});")
            if export_pdf:
                lines.append(f"    exportgraphics(f_cur, '{pdf_path}');")
        lines.append("catch ME")
        lines.append("    ok_flag = 0;")
        lines.append("    err_msg = regexprep(ME.message, '[\\r\\n\"\\\\]', ' ');")
        lines.append("end")
        lines.append("ms_case = toc(t_case) * 1000.0;")
        lines.append(
            f"fprintf(meta_fid, '{{\"name\":\"{c.name}\",\"ok\":%d,\"ms\":%.2f,\"err\":\"%s\"}}\\n', "
            "ok_flag, ms_case, err_msg);"
        )
        lines.append("close all force;")
        lines.append("")

    lines.append("fclose(meta_fid);")
    script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return script_path


def parse_meta(meta_path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not meta_path.exists():
        return out
    for raw in meta_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
            out[obj["name"]] = obj
        except json.JSONDecodeError:
            continue
    return out


def run_matlab_batch(cases: List[GraphicsCase], matlab_bin: str) -> Dict[str, Dict[str, Any]]:
    script = write_batch_script(cases, GOLDEN_DIR, "matlab", export_pdf=False)
    print(f"[matlab] running {len(cases)} cases in one session...", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [matlab_bin, "-batch", f"run('{script.as_posix()}')"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    dt = time.perf_counter() - t0
    print(f"[matlab] finished in {dt:.1f}s (exit={proc.returncode})", flush=True)
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr[:1000], file=sys.stderr)
    return parse_meta(GOLDEN_DIR / "meta.jsonl")


def run_numkit_batch(
    cases: List[GraphicsCase], numkit_bin: Path, export_pdf: bool
) -> Dict[str, Dict[str, Any]]:
    script = write_batch_script(cases, RUNS_DIR, "numkit", export_pdf=export_pdf)
    print(f"[numkit] running {len(cases)} cases...", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [str(numkit_bin), str(script)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    dt = time.perf_counter() - t0
    print(f"[numkit] finished in {dt:.1f}s (exit={proc.returncode})", flush=True)
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr[:1000], file=sys.stderr)
    return parse_meta(RUNS_DIR / "meta.jsonl")


def check_pdf_consistency(case_dir: Path, dpi: int) -> Optional[float]:
    pdf = case_dir / "plot.pdf"
    png = case_dir / "plot.png"
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm or not pdf.exists() or not png.exists():
        return None
    prefix = case_dir / "pdf_raster"
    proc = subprocess.run(
        [pdftoppm, "-png", "-r", str(dpi), "-singlefile", str(pdf), str(prefix)],
        capture_output=True,
        timeout=30,
    )
    raster = case_dir / "pdf_raster.png"
    if proc.returncode != 0 or not raster.exists():
        return None
    vm = compare_images(png, raster)
    return vm.ink_iou


def classify_verdict(
    c: GraphicsCase,
    ml_ok: bool,
    nk_ok: bool,
    dom: DomDiffSummary,
    vis: Optional[VisualMetrics],
) -> str:
    if not ml_ok and not nk_ok:
        return "BOTH_ERR"
    if ml_ok and not nk_ok:
        return "NK_CRASH"
    if not ml_ok and nk_ok:
        return "ML_ERR"
    if vis is None:
        return "NO_PNG"
    if vis.score >= 88.0 and not dom.axes_count_mismatch and not dom.position_mismatch:
        return "PASS"
    if dom.issues and vis.score < 88.0:
        return "DOM+RENDER"
    if vis.score < 88.0:
        return "RENDER_DIFF"
    return "DOM_ONLY"


def write_report(rows: List[Dict[str, Any]], report_path: Path) -> None:
    rows_sorted = sorted(rows, key=lambda r: (r["verdict"] == "PASS", r["score"]))
    lines: List[str] = [
        "# Graphics Parity Report (MATLAB vs NumKit)",
        "",
        f"Total cases: **{len(rows)}** | "
        f"PASS (score ≥ 88 & DOM layout ok): **{sum(1 for r in rows if r['verdict'] == 'PASS')}** | "
        f"NK_CRASH: **{sum(1 for r in rows if r['verdict'] == 'NK_CRASH')}** | "
        f"DOM+RENDER: **{sum(1 for r in rows if r['verdict'] == 'DOM+RENDER')}** | "
        f"RENDER_DIFF: **{sum(1 for r in rows if r['verdict'] == 'RENDER_DIFF')}** | "
        f"DOM_ONLY: **{sum(1 for r in rows if r['verdict'] == 'DOM_ONLY')}**",
        "",
        "| Case | Cat | Verdict | Score | SSIM | InkIoU | PlotIoU | ColorL1 | PDF | NK ms | ML ms | Key Issues |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows_sorted:
        issues_str = "; ".join(r["issues"][:3]).replace("|", "/")
        if len(r["issues"]) > 3:
            issues_str += f" (+{len(r['issues']) - 3} more)"
        if r.get("nk_err"):
            issues_str = f"NK ERR: {r['nk_err'][:100]}"
        elif r.get("ml_err"):
            issues_str = f"ML ERR: {r['ml_err'][:100]}"
        pdf_str = f"{r['pdf_iou']:.2f}" if r.get("pdf_iou") is not None else "—"
        lines.append(
            f"| `{r['name']}` | {r['category']} | **{r['verdict']}** | "
            f"{r['score']:.1f} | {r['ssim']:.3f} | {r['ink_iou']:.3f} | "
            f"{r['plot_iou']:.3f} | {r['color_l1']:.2f} | {pdf_str} | "
            f"{r['nk_ms']:.0f} | {r['ml_ms']:.0f} | {issues_str} |"
        )

    lines.append("")
    lines.append("## Diff Images (Worst Cases)")
    for r in rows_sorted[:15]:
        if r.get("diff_png"):
            lines.append(f"- **{r['name']}** ({r['verdict']}, score {r['score']:.1f}): `{r['diff_png']}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Visual & DOM Graphics Parity Runner")
    ap.add_argument("--numkit", help="Path to numkit executable")
    ap.add_argument("--matlab", help="Path to matlab executable")
    ap.add_argument("--cases", default="*", help="fnmatch filter on case names")
    ap.add_argument("--refresh-matlab", action="store_true", help="Re-run MATLAB to regenerate golden/")
    ap.add_argument("--check-pdf", action="store_true", help="Also compare NumKit PNG vs rasterized PDF")
    ap.add_argument("--save-baseline", action="store_true", help="Write baseline.json ratchet scores")
    ap.add_argument("--check-ratchet", action="store_true", help="Fail if any case drops >3 pts below baseline.json")
    args = ap.parse_args()

    selected = [c for c in CASES if fnmatch.fnmatch(c.name, args.cases)]
    if not selected:
        print(f"No cases matched '{args.cases}'", file=sys.stderr)
        return 2

    numkit_bin = find_numkit_bin(args.numkit)
    need_matlab = args.refresh_matlab or any(
        not (GOLDEN_DIR / c.name / "plot.png").exists() for c in selected
    )
    ml_meta = parse_meta(GOLDEN_DIR / "meta.jsonl")
    if need_matlab:
        matlab_bin = find_matlab_bin(args.matlab)
        if not matlab_bin:
            print("MATLAB binary not found and golden/ missing; install MATLAB or copy golden/", file=sys.stderr)
            return 2
        to_run_ml = selected if args.refresh_matlab else [
            c for c in selected if not (GOLDEN_DIR / c.name / "plot.png").exists()
        ]
        new_ml = run_matlab_batch(to_run_ml, matlab_bin)
        ml_meta.update(new_ml)
        # Persist merged meta.jsonl so partial refreshes keep prior entries.
        with (GOLDEN_DIR / "meta.jsonl").open("w", encoding="utf-8") as mf:
            for item in ml_meta.values():
                mf.write(json.dumps(item) + "\n")

    nk_meta = run_numkit_batch(selected, numkit_bin, export_pdf=args.check_pdf)

    diffs_dir = RUNS_DIR / "diffs"
    diffs_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    for c in selected:
        ml_m = ml_meta.get(c.name, {"ok": 0, "ms": 0.0, "err": "missing golden"})
        nk_m = nk_meta.get(c.name, {"ok": 0, "ms": 0.0, "err": "missing run"})
        ml_ok = bool(ml_m.get("ok"))
        nk_ok = bool(nk_m.get("ok"))

        ml_dom_p = GOLDEN_DIR / c.name / "dom.json"
        nk_dom_p = RUNS_DIR / c.name / "dom.json"
        ml_png = GOLDEN_DIR / c.name / "plot.png"
        nk_png = RUNS_DIR / c.name / "plot.png"

        dom = compare_dom(ml_dom_p, nk_dom_p) if (ml_ok and nk_ok) else DomDiffSummary()
        vis: Optional[VisualMetrics] = None
        diff_png_str = ""
        if ml_ok and nk_ok and ml_png.exists() and nk_png.exists():
            ml_dom_obj = json.loads(ml_dom_p.read_text(encoding="utf-8")) if ml_dom_p.exists() else None
            diff_out = diffs_dir / f"{c.name}.png"
            vis = compare_images(ml_png, nk_png, ml_dom=ml_dom_obj, diff_out=diff_out)
            diff_png_str = str(diff_out)

        pdf_iou = check_pdf_consistency(RUNS_DIR / c.name, c.dpi) if (args.check_pdf and nk_ok) else None
        if pdf_iou is not None and pdf_iou < 0.85:
            dom.issues.append(f"PDF_vs_PNG_IoU={pdf_iou:.2f}")

        verdict = classify_verdict(c, ml_ok, nk_ok, dom, vis)
        rows.append({
            "name": c.name,
            "category": c.category,
            "verdict": verdict,
            "score": vis.score if vis else 0.0,
            "ssim": vis.ssim if vis else 0.0,
            "ink_iou": vis.ink_iou if vis else 0.0,
            "plot_iou": vis.plot_iou if vis else 0.0,
            "color_l1": vis.color_l1 if vis else 2.0,
            "bbox_diff": vis.bbox_diff if vis else 1.0,
            "pdf_iou": pdf_iou,
            "nk_ms": float(nk_m.get("ms", 0.0)),
            "ml_ms": float(ml_m.get("ms", 0.0)),
            "nk_err": nk_m.get("err", ""),
            "ml_err": ml_m.get("err", ""),
            "issues": dom.issues,
            "diff_png": diff_png_str,
        })

    report_path = RUNS_DIR / "report.md"
    write_report(rows, report_path)
    (RUNS_DIR / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # Compact console summary
    print(f"\nReport written to: {report_path}")
    print(f"{'CASE':30s} {'VERDICT':11s} {'SCORE':6s} {'INK':5s} {'PLOT':5s} {'COL':5s} {'NKms':6s} ISSUE")
    for r in sorted(rows, key=lambda x: (x["verdict"] == "PASS", x["score"])):
        first_issue = r["nk_err"] or r["ml_err"] or (r["issues"][0] if r["issues"] else "")
        print(
            f"{r['name']:30s} {r['verdict']:11s} {r['score']:6.1f} "
            f"{r['ink_iou']:5.2f} {r['plot_iou']:5.2f} {r['color_l1']:5.2f} "
            f"{r['nk_ms']:6.0f} {first_issue[:70]}"
        )

    if args.save_baseline:
        base = {r["name"]: {"score": round(r["score"], 2), "verdict": r["verdict"]} for r in rows}
        BASELINE_FILE.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
        print(f"\nSaved baseline to {BASELINE_FILE}")

    if args.check_ratchet and BASELINE_FILE.exists():
        base = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        regressions = []
        for r in rows:
            b = base.get(r["name"])
            if b and r["score"] + 3.0 < float(b["score"]):
                regressions.append(f"{r['name']}: {r['score']:.1f} < baseline {b['score']:.1f}")
        if regressions:
            print("\nRATCHET REGRESSIONS:", file=sys.stderr)
            for msg in regressions:
                print("  -", msg, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
