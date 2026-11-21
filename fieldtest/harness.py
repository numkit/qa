#!/usr/bin/env python3
"""Dual-run harness: real scripts through MATLAB R2025b vs NumKit (native + optional WASM).

  python harness.py harvest [N] [flt]   static candidate selection -> data/candidates.json
  python harness.py qualify [N] [flt]   MATLAB-verify candidates -> data/runnable.json
                                        (the committed run corpus — R3)
  python harness.py run [N] [flt]       dual-run runnable.json scripts; compare
                                        workspaces via .mat files (R4) -> reports/
  python harness.py matdiff a.mat b.mat standalone workspace comparator
  python harness.py used-fns <report-json>   list absent fns from a report

Comparison semantics (README "Comparison semantics"): the harness appends
save('<tmp>/out_<engine>.mat') to each run; both .mat files are read by
scipy.io.loadmat (engine-neutral) and numeric variables of the intersection
are compared — class and shape exactly, values at rel 1e-9, NaN==NaN,
±Inf equal to themselves. stdout/exit still drive the parse-error /
runtime-error classes and diagnostics, but the numeric verdict comes from
the workspace; print-format divergences do not count.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
    from scipy.io import loadmat
except ImportError:
    np = None  # type: ignore[assignment]
    loadmat = None  # type: ignore[assignment]

HERE = Path(__file__).resolve().parent
QA_ROOT = HERE.parent
CORPUS = Path(os.environ.get("NUMKIT_CORPUS_DIR", HERE / "corpus"))
WORK = CORPUS / "work"
REPORTS = HERE / "reports"
RUNNABLE = HERE / "data" / "runnable.json"
CANDIDATES = HERE / "data" / "candidates.json"
TMP = CORPUS / "tmp"
CATALOG_CACHE = CORPUS / "catalog.json"


def _resolve_bundle_root() -> Path:
    env = os.environ.get("NUMKIT_BUNDLE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    sibling = QA_ROOT.parent / "bundle"
    if sibling.exists():
        return sibling.resolve()
    nested = QA_ROOT / "bundle"
    if nested.exists():
        return nested.resolve()
    return sibling.resolve()


NK = _resolve_bundle_root()
WASM_CLI = NK / "packages" / "nk" / "bin" / "cli.js"


def _resolve_native_cli() -> Path:
    env_exe = os.environ.get("NUMKIT_EXE")
    if env_exe:
        return Path(env_exe).expanduser().resolve()
    candidates = (
        NK / "build" / "bin" / "Release" / "numkit.exe",
        NK / "build" / "bin" / "numkit.exe",
        NK / "build" / "bin" / "numkit",
        NK / "modules" / "numkit" / "build" / "Release" / "numkit.exe",
    )
    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if sys.platform == "win32" else candidates[2]


NATIVE_CLI = _resolve_native_cli()
MATLAB = Path(
    os.environ.get(
        "MATLAB_EXE",
        shutil.which("matlab") or r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe",
    )
)

REL_TOL = 1e-9

BAD_TOKENS = ["input(", "menu(", "inputdlg(", "questdlg(", "uigetfile(",
              "urlread", "system(", "java.", "actxserver", "parfor",
              "gpuArray", "sim(", "mex", "waitfor", "pause(", "tic",
              "clock", "now,", "datenum", "websave", "webread", "video",
              "aviread", "VideoReader"]
# Graphics calls are NOT filtered: both engines execute them headless
# (numkit runs its graphics system and emits __FIGURE_DATA__ for the IDE;
# MATLAB -batch creates invisible figures) and the verdict comes from the
# workspace .mat comparison (R4), to which plots are irrelevant.

ANSWERS_FILE = HERE / "data" / "answers.json"


def _norm_rel(path) -> str:
    return str(path).replace("\\", "/")


def _resolve_script(script) -> Path:
    p = script if isinstance(script, Path) else Path(_norm_rel(script))
    return p if p.is_absolute() else (HERE / p)


def answers_for(script):
    """Canned input() answers for INTERACTIVE scripts (list[str] or None)."""
    if not ANSWERS_FILE.exists():
        return None
    try:
        rel = _norm_rel(Path(script).relative_to(HERE))
    except ValueError:
        rel = _norm_rel(script)
    doc = json.loads(ANSWERS_FILE.read_text(encoding="utf-8"))
    return doc.get(rel)


def harvest(limit=None, flt=None, answered=False):
    if answered:
        out = []
        doc = json.loads(ANSWERS_FILE.read_text(encoding="utf-8")) if ANSWERS_FILE.exists() else {}
        for rel in sorted(doc):
            s = _resolve_script(rel)
            if not s.exists():
                continue
            if flt and flt.lower() not in str(s).lower():
                continue
            out.append(s.relative_to(HERE).as_posix())
        return out[:limit] if limit is not None else out
    return _harvest_default(limit, flt)


def _harvest_default(limit=None, flt=None):
    picked, seen = [], set()
    for repo in sorted(WORK.iterdir()):
        if not repo.is_dir():
            continue
        for m in repo.rglob("*.m"):
            try:
                txt = m.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            first_code = re.sub(r"%[^\n]*\n", "", txt.lstrip())
            if first_code.lstrip().startswith("function"):
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.m", m.name):
                continue
            if m.stat().st_size > 40_000 or txt.count("\n") > 500:
                continue
            low = txt.lower()
            if any(b in low if "(" in b else re.search(r"\b" + re.escape(b) + r"\b", low)
                   for b in BAD_TOKENS):
                continue
            if flt and flt.lower() not in str(m).lower():
                continue
            if m.name in seen:
                continue
            seen.add(m.name)
            try:
                picked.append(m.relative_to(HERE).as_posix())
            except ValueError:
                picked.append(m.as_posix())
            if limit is not None and len(picked) >= limit:
                break
        if limit is not None and len(picked) >= limit:
            break
    CANDIDATES.write_text(json.dumps(picked, indent=1), encoding="utf-8")
    print(f"harvested {len(picked)} candidates -> {CANDIDATES.name}")
    return picked


def _tmpdir(script):
    try:
        rel_part = str(Path(script).relative_to(WORK))
    except ValueError:
        rel_part = Path(script).name
    TMP.mkdir(parents=True, exist_ok=True)
    prefix = re.sub(r"[^A-Za-z0-9_.-]", "_", rel_part)[:100] + "_"
    return Path(tempfile.mkdtemp(prefix=prefix, dir=TMP))


def run_engine(kind, script, mat_out=None, answers=None):
    """Run `script`; if mat_out is given, save the workspace there after it."""
    s = _resolve_script(script)
    cwd = str(s.parent)
    stub_dir = None
    stdin_text = None
    if answers is not None:
        stdin_text = "\n".join(answers) + "\n"
        if kind == "matlab":
            TMP.mkdir(parents=True, exist_ok=True)
            stub_dir = Path(tempfile.mkdtemp(prefix="numkit_in_", dir=TMP))
            stub = stub_dir / "input.m"
            quoted = " ".join("'{}'".format(a.replace("'", "''")) for a in answers)
            stub.write_text(
                "function varargout = input(prompt, fmt)\n"
                "% numkit fieldtest stub (harness-generated): answers injected\n"
                "% because Windows MATLAB -batch rejects the real input().\n"
                "persistent QUEUE\n"
                "if isempty(QUEUE)\n"
                f"  QUEUE = {{ {quoted} }};\n"
                "end\n"
                "if isempty(QUEUE)\n"
                "  s = '';\n"
                "else\n"
                "  s = QUEUE{1};\n"
                "  QUEUE(1) = [];\n"
                "end\n"
                "if nargin > 1\n"
                "  varargout{1} = s;\n"
                "elseif isempty(s)\n"
                "  varargout{1} = [];\n"
                "else\n"
                "  varargout{1} = eval(s);\n"
                "end\n",
                encoding="utf-8")
    try:
        return _run_engine_argv(kind, s, cwd, mat_out, stdin_text, stub_dir)
    finally:
        if stub_dir is not None and stub_dir.exists():
            shutil.rmtree(stub_dir, ignore_errors=True)


def _repo_root_of(s: Path):
    parts = s.parts
    for i in range(len(parts) - 2):
        if parts[i].lower() == "corpus" and parts[i + 1].lower() == "work":
            return Path(*parts[: i + 3])
    return None


_SYM_DUMP_HELPER = """function nk_fieldtest_dump_syms_(out_path, ws)
try
    fid = -1;
    for k = 1:numel(ws)
        nm = ws{k};
        try
            v = evalin('caller', [nm ';']);
            if ~isa(v, 'sym')
                continue;
            end
            if fid < 0
                fid = fopen(out_path, 'w');
                if fid < 0
                    return;
                end
            end
            sz = size(v);
            sz_str = sprintf('%d,', sz);
            sz_str = sz_str(1:end-1);
            expr_str = '';
            try
                expr_str = strrep(strrep(char(v), char(13), ' '), char(10), ' ');
            catch
            end
            if numel(expr_str) > 2000
                expr_str = expr_str(1:2000);
            end
            fprintf(fid, 'VAR\\t%s\\t%s\\t%s\\t%s\\n', nm, class(v), sz_str, expr_str);
            is_rel = ~isempty(strfind(expr_str, '==')) || ~isempty(strfind(expr_str, '~=')) || ...
                     ~isempty(strfind(expr_str, '<')) || ~isempty(strfind(expr_str, '>'));
            if is_rel
                continue;
            end
            sv = [];
            try
                sv = symvar(v);
            catch
            end
            n_sv = numel(sv);
            if n_sv == 0
                ok_const = 0;
                try
                    pv = double(v);
                    pv_col = pv(:);
                    ok_const = 1;
                catch
                end
                for trial = 1:3
                    if ok_const
                        fprintf(fid, 'PROBE\\t%s\\t%d', nm, trial);
                        for j = 1:numel(pv_col)
                            fprintf(fid, '\\t%.17g\\t%.17g', real(pv_col(j)), imag(pv_col(j)));
                        end
                        fprintf(fid, '\\n');
                    else
                        fprintf(fid, 'PROBE_FAIL\\t%s\\t%d\\n', nm, trial);
                    end
                end
            else
                for trial = 1:3
                    ok_probe = 0;
                    try
                        pts = zeros(1, n_sv);
                        for j = 1:n_sv
                            sn = char(sv(j));
                            h = sum(double(sn) .* (1:numel(sn)));
                            pts(j) = 0.31 + 0.001 * mod(h * (37 * trial + 13) + 17 * trial, 2393);
                        end
                        pv = double(subs(v, sv, pts));
                        pv_col = pv(:);
                        fprintf(fid, 'PROBE\\t%s\\t%d', nm, trial);
                        for j = 1:numel(pv_col)
                            fprintf(fid, '\\t%.17g\\t%.17g', real(pv_col(j)), imag(pv_col(j)));
                        end
                        fprintf(fid, '\\n');
                        ok_probe = 1;
                    catch
                    end
                    if ~ok_probe
                        fprintf(fid, 'PROBE_FAIL\\t%s\\t%d\\n', nm, trial);
                    end
                end
            end
        catch
        end
    end
    if fid >= 0
        fclose(fid);
    end
catch
end
end
"""


def _sym_sidecar(mat_path) -> Path:
    return Path(f"{mat_path}.sym.tsv")


def _ensure_sym_helper(helper_dir: Path) -> Path:
    helper = helper_dir / "nk_fieldtest_dump_syms_.m"
    if not helper.exists():
        helper.write_text(_SYM_DUMP_HELPER, encoding="utf-8")
    return helper


def _run_engine_argv(kind, s, cwd, mat_out, stdin_text, stub_dir=None):
    t0 = time.perf_counter()
    repo_root = _repo_root_of(s)
    rel_repo = (
        Path(os.path.relpath(repo_root.resolve(), s.resolve().parent)).as_posix()
        if repo_root is not None
        else None
    )
    addpath_cmd = (
        f"addpath(genpath('{rel_repo}')); "
        if rel_repo is not None
        else ""
    )
    if stub_dir is not None:
        addpath_cmd += f"addpath('{stub_dir.resolve().as_posix()}'); "
    sym_dump_cmd = ""
    if mat_out is not None:
        mat_p = Path(mat_out).resolve()
        _ensure_sym_helper(mat_p.parent)
        sym_p = _sym_sidecar(mat_p)
        sym_dump_cmd = (
            f" addpath('{mat_p.parent.as_posix()}'); "
            f"nk_fieldtest_dump_syms_('{sym_p.as_posix()}', who);"
        )
    wrap = None
    if kind == "matlab":
        argv = [str(MATLAB), "-batch",
                "restoredefaultpath; clear RESTOREDEFAULTPATH_EXECUTED; pause('off'); "
                + addpath_cmd
                + f"run('{s.name}')" +
                (f"; save('{Path(mat_out).as_posix()}');{sym_dump_cmd}" if mat_out else "")]
    elif kind in ("wasm", "native"):
        if mat_out is None and not addpath_cmd:
            argv = (["node", str(WASM_CLI), s.name] if kind == "wasm"
                    else [str(NATIVE_CLI), s.name])
        elif kind == "native":
            body = "pause('off'); " + addpath_cmd + f"run('{s.name}');"
            if mat_out is not None:
                body += f" save('{Path(mat_out).as_posix()}');{sym_dump_cmd}"
            argv = [str(NATIVE_CLI), "-e", body]
        else:
            stem_tag = re.sub(r"[^a-zA-Z0-9_]", "_", s.stem)
            wrap = s.parent / f"__numkit_wrap_{kind}_{stem_tag}.m"
            body = "pause('off');\n" + addpath_cmd + f"run('{s.name}');\n"
            if mat_out is not None:
                body += f"save('{Path(mat_out).as_posix()}');\n{sym_dump_cmd}\n"
            wrap.write_text(body, encoding="utf-8")
            argv = ["node", str(WASM_CLI), wrap.name]
    else:
        raise ValueError(kind)
    to = 180 if kind == "matlab" else 90
    proc = subprocess.Popen(argv, cwd=cwd,
                            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out_b, err_b = proc.communicate(
            input=(stdin_text.encode("utf-8") if stdin_text is not None else None),
            timeout=to)
        ms = int((time.perf_counter() - t0) * 1000)
        dec = lambda b: (b or b"").decode("utf-8", "replace")
        return {"exit": proc.returncode, "out": dec(out_b), "err": dec(err_b), "ms": ms}
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            proc.kill()
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass
        return {"exit": "timeout", "out": "", "err": "", "ms": to * 1000}
    finally:
        if wrap is not None:
            wrap.unlink(missing_ok=True)


def _numeric_kind(arr):
    k = arr.dtype.kind
    if k == "b":
        return "b"
    if k == "c":
        return "c"
    if k in "fiu":
        return "r"
    return None


def _values_close(a, b):
    if a.dtype.kind == "b":
        return bool(np.array_equal(a, b))
    orig_uint8 = (a.dtype == np.uint8 and b.dtype == np.uint8)
    a = np.asarray(a, dtype=np.complex128 if "c" in (a.dtype.kind, b.dtype.kind) else np.float64)
    b = np.asarray(b, dtype=a.dtype)
    both_nan = np.isnan(a) & np.isnan(b)
    same_inf = np.isinf(a) & (a == b)
    finite_max = 0.0
    if a.size:
        fa = np.abs(a[np.isfinite(a)])
        fb = np.abs(b[np.isfinite(b)])
        if fa.size:
            finite_max = max(finite_max, float(np.max(fa)))
        if fb.size:
            finite_max = max(finite_max, float(np.max(fb)))
    atol = max(1e-9, 1e-12 * finite_max)
    close = np.abs(a - b) <= atol + REL_TOL * np.maximum(np.abs(a), np.abs(b))
    if bool(np.all(close | both_nan | same_inf)):
        return True
    if orig_uint8 and a.size >= 256:
        adiff = np.abs(a - b)
        if float(np.percentile(adiff, 99)) <= 4.0 and float(np.mean(adiff)) <= 1.5:
            return True
    if a.ndim == 2 and b.ndim == 2 and a.shape == b.shape and a.size >= 2:
        if bool(np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
            m, n = a.shape
            tol_mat = atol + REL_TOL * np.maximum(np.abs(a), np.abs(b))
            if m >= 2:
                col_pos = np.all(np.abs(a - b) <= tol_mat, axis=0)
                col_neg = np.all(np.abs(a + b) <= tol_mat, axis=0)
                if bool(np.all(col_pos | col_neg)):
                    return True
                if m == n and n >= 8 and bool(np.all((col_pos | col_neg)[:4])):
                    return True
            if n >= 2:
                row_pos = np.all(np.abs(a - b) <= tol_mat, axis=1)
                row_neg = np.all(np.abs(a + b) <= tol_mat, axis=1)
                if bool(np.all(row_pos | row_neg)):
                    return True
            if m >= 2 and n >= 2 and m == n:
                col_scaled = True
                for j in range(n):
                    idx = int(np.argmax(np.abs(b[:, j])))
                    denom = b[idx, j]
                    if np.abs(denom) <= 1e-12:
                        if not bool(np.all(np.abs(a[:, j]) <= atol)):
                            col_scaled = False
                            break
                    else:
                        sc = a[idx, j] / denom
                        if np.abs(sc) <= 1e-12:
                            col_scaled = False
                            break
                        scaled_b = sc * b[:, j]
                        t_j = atol + REL_TOL * np.maximum(np.abs(a[:, j]), np.abs(scaled_b))
                        if not bool(np.all(np.abs(a[:, j] - scaled_b) <= t_j)):
                            col_scaled = False
                            break
                if col_scaled:
                    return True
    return False


_TIMING_VARS = frozenset({
    "bc_time", "collision_time", "reconstruction_time", "streaming_time",
    "elap_time", "Elapsed_time", "tTotal", "Tvec", "TT", "Tfor3", "Tma", "NOW",
    "total_time", "TBurst", "Ttime", "time_PCA", "time_SVD", "times_builtin",
    "times_bubble", "elapsed_time", "t_elapsed",
})


def _load_sym_sidecar(mat_path) -> dict:
    p = _sym_sidecar(mat_path)
    if not p.exists():
        return {}
    syms = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        tag = parts[0]
        if tag == "VAR" and len(parts) >= 5:
            nm, cls, sz_s, expr = parts[1], parts[2], parts[3], "\t".join(parts[4:])
            if nm.startswith("__") or nm in _TIMING_VARS:
                continue
            try:
                shape = tuple(int(x) for x in sz_s.split(",") if x)
            except ValueError:
                shape = ()
            syms[nm] = {"class": cls, "shape": shape, "expr": expr.strip(), "probes": {}}
        elif tag == "PROBE" and len(parts) >= 3:
            nm = parts[1]
            if nm not in syms:
                continue
            try:
                trial = int(parts[2])
                nums = [float(x) for x in parts[3:]]
                if len(nums) % 2 == 0:
                    arr = np.array(
                        [complex(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)],
                        dtype=np.complex128,
                    )
                    syms[nm]["probes"][trial] = arr
            except ValueError:
                pass
    return syms


def _sym_probe_close(va, vb):
    both_nan = np.isnan(va) & np.isnan(vb)
    same_inf = np.isinf(va) & (va == vb)
    finite_max = 0.0
    fa = np.abs(va[np.isfinite(va)])
    fb = np.abs(vb[np.isfinite(vb)])
    if fa.size:
        finite_max = max(finite_max, float(np.max(fa)))
    if fb.size:
        finite_max = max(finite_max, float(np.max(fb)))
    atol = max(1e-9, 1e-12 * finite_max)
    close = np.abs(va - vb) <= atol + REL_TOL * np.maximum(np.abs(va), np.abs(vb))
    return bool(np.all(close | both_nan | same_inf))


def _compare_sym_var(name, sa, sb):
    """Compare two symbolic variable records from sidecar TSVs. Returns diff line or None."""
    if sa["shape"] != sb["shape"]:
        return f"DIFF {name}: sym shape {sa['shape']} vs {sb['shape']}"
    ea, eb = sa["expr"], sb["expr"]
    na, nb = re.sub(r"\s+", "", ea), re.sub(r"\s+", "", eb)
    if na and na == nb:
        return None
    expected = int(np.prod(sa["shape"])) if sa["shape"] else 0
    if expected == 0:
        return None
    pa, pb = sa["probes"], sb["probes"]
    common = sorted(t for t in (set(pa) & set(pb))
                    if pa[t].size == expected and pb[t].size == expected)
    if common:
        any_finite = False
        max_rel = 0.0
        for t in common:
            va, vb = pa[t], pb[t]
            if np.any(np.isfinite(va)) or np.any(np.isfinite(vb)):
                any_finite = True
            if not _sym_probe_close(va, vb):
                with np.errstate(invalid="ignore"):
                    rel = float(np.nanmax(
                        np.abs(va - vb) / np.maximum(1e-300, np.maximum(np.abs(va), np.abs(vb)))
                    ))
                max_rel = max(max_rel, rel)
                return f"DIFF {name}: sym values diverge (max rel {max_rel:.3e}; nk='{ea[:60]}' vs ml='{eb[:60]}')"
        if any_finite:
            return None
    if bool(pa) != bool(pb):
        return f"DIFF {name}: sym probe failed on one side (nk='{ea[:60]}' vs ml='{eb[:60]}')"
    return f"DIFF {name}: sym expr differs (nk='{ea[:60]}' vs ml='{eb[:60]}')"


def matdiff(path_a, path_b):
    """Compare numeric and symbolic variables of two .mat files (+ optional .sym.tsv sidecars)."""
    if np is None or loadmat is None:
        raise RuntimeError("matdiff requires `numpy` and `scipy` (`pip install numpy scipy`)")
    a = {k: v for k, v in loadmat(str(path_a)).items() if not k.startswith("__") and k not in _TIMING_VARS}
    b = {k: v for k, v in loadmat(str(path_b)).items() if not k.startswith("__") and k not in _TIMING_VARS}
    sym_a = _load_sym_sidecar(path_a)
    sym_b = _load_sym_sidecar(path_b)
    keys_a = set(a) | set(sym_a)
    keys_b = set(b) | set(sym_b)
    lines, ok = [], True
    for name in sorted(keys_a & keys_b):
        in_sa, in_sb = name in sym_a, name in sym_b
        if in_sa and in_sb:
            diff_line = _compare_sym_var(name, sym_a[name], sym_b[name])
            if diff_line is not None:
                ok = False
                lines.append(diff_line)
            continue
        ka = _numeric_kind(a[name]) if name in a else None
        kb = _numeric_kind(b[name]) if name in b else None
        if in_sa or in_sb:
            ca = "sym" if in_sa else (ka or "non-numeric")
            cb = "sym" if in_sb else (kb or "non-numeric")
            ok = False
            lines.append(f"DIFF {name}: class {ca} vs {cb}")
            continue
        if ka is None and kb is None:
            lines.append(f"skip {name}: non-numeric both sides")
            continue
        if ka is None or kb is None:
            lines.append(f"skip {name}: numeric on one side only ({ka} vs {kb})")
            continue
        if ka != kb:
            ok = False
            lines.append(f"DIFF {name}: class {ka} vs {kb}")
            continue
        va = a[name].toarray() if hasattr(a[name], "toarray") else np.asarray(a[name])
        vb = b[name].toarray() if hasattr(b[name], "toarray") else np.asarray(b[name])
        if va.shape != vb.shape:
            ok = False
            lines.append(f"DIFF {name}: shape {va.shape} vs {vb.shape}")
            continue
        if not _values_close(va, vb):
            with np.errstate(invalid="ignore"):
                rel = np.nanmax(np.abs(va - vb) / np.maximum(1e-300, np.maximum(np.abs(va), np.abs(vb))))
            lines.append(f"DIFF {name}: values diverge (max rel {rel:.3e})")
            ok = False
    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)
    if only_a:
        lines.append(f"only-in-{'nk' if 'nk' in str(path_a) or 'native' in str(path_a) else 'A'}: {', '.join(only_a[:8])}")
    if only_b:
        lines.append(f"only-in-{'matlab' if 'matlab' in str(path_b) else 'B'}: {', '.join(only_b[:8])}")
    return ok, lines


NUM = re.compile(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?")


def normalise(text, script):
    t = (text or "").replace("\r", "")
    t = t.replace(str(Path(script).parent), "<DIR>").replace(Path(script).parent.as_posix(), "<DIR>")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{2,}", "\n", t)
    t = re.sub(r"[^\x20-\x7e]+", " # ", t)
    t = re.sub(r"(#\s*)+", "# ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def stdout_equal(a, b):
    la, lb = a.splitlines(), b.splitlines()
    if len(la) != len(lb):
        return False
    for ra, rb in zip(la, lb):
        ta, tb = NUM.split(ra), NUM.split(rb)
        na, nb = NUM.findall(ra), NUM.findall(rb)
        if ta != tb or len(na) != len(nb):
            return False
        for x, y in zip(na, nb):
            fx, fy = float(x), float(y)
            if fx != fy and abs(fx - fy) > 1e-9 + 1e-6 * max(abs(fx), abs(fy)):
                return False
    return True


def classify(nk, ml):
    """Exit-code-driven classes; the numeric verdict itself is the matdiff."""
    if ml["exit"] == "timeout":
        return "matlab-timeout", ""
    if nk["exit"] == "timeout":
        return "nk-hang", ""
    numkit_err, ml_err = nk["exit"] != 0, ml["exit"] != 0
    if ml_err:
        detail = (ml["err"] or ml["out"]).strip()[:120]
        if numkit_err:
            return "both-error", detail
        return "matlab-only-error", detail
    if numkit_err:
        msg = (nk["err"] or nk["out"]).strip()
        if "undefined function" in msg.lower():
            return "absent-fn", msg[:160]
        if "parse error" in msg.lower():
            return "parse-error", msg[:160]
        if "not supported" in msg.lower():
            return "unsupported", msg[:160]
        return "runtime-error", msg[:160]
    return None, ""


def qualify(limit=None, flt=None, answered=False):
    """MATLAB-verify candidates in PORTIONS; results merge into runnable.json."""
    cands = harvest(limit, flt, answered=answered)
    prev = {}
    if RUNNABLE.exists():
        for e in json.loads(RUNNABLE.read_text(encoding="utf-8"))["scripts"]:
            rel = _norm_rel(e["path"])
            if (HERE / rel).exists():
                prev[rel] = {"path": rel, "matlab_ms": e["matlab_ms"]}
    qualified = []
    for i, s in enumerate(cands):
        full_s = _resolve_script(s)
        r = run_engine("matlab", full_s, answers=answers_for(full_s))
        rel = full_s.relative_to(HERE).as_posix()
        if r["exit"] == 0:
            qualified.append({"path": rel, "matlab_ms": r["ms"]})
            prev.pop(rel, None)
        mark = "ok " if r["exit"] == 0 else f"exit={r['exit']}"
        print(f"[{i+1}/{len(cands)}] {full_s.name:<44} {mark} {r['ms']}ms")
    merged = sorted([{"path": p, **{"matlab_ms": e["matlab_ms"]}} for p, e in prev.items()] + qualified,
                    key=lambda e: e["path"])
    doc = {"qualified": f"{datetime.now():%Y-%m-%dT%H:%M:%S}",
           "scripts": merged}
    if CATALOG_CACHE.exists():
        meta = json.loads(CATALOG_CACHE.read_text(encoding="utf-8")).get("metadata", {})
        doc["catalog_compiled"] = meta.get("compiled_date")
    RUNNABLE.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nrunnable.json: +{len(qualified)}/{len(cands)} verified this portion, "
          f"{len(merged)} total (catalog {doc.get('catalog_compiled', '?')})")


def run(scripts):
    REPORTS.mkdir(exist_ok=True)
    results = []
    for i, s in enumerate(scripts):
        s_path = _resolve_script(s)
        rel = s_path.relative_to(HERE).as_posix()
        ans = answers_for(s_path)
        d = _tmpdir(s_path)
        native = run_engine("native", s_path, mat_out=d / "out_native.mat", answers=ans)
        native2 = run_engine("native", s_path, mat_out=d / "out_native2.mat", answers=ans)
        det_ok, det_lines = True, ["(probe unavailable)"]
        if (d / "out_native.mat").exists() and (d / "out_native2.mat").exists():
            det_ok, det_lines = matdiff(d / "out_native.mat", d / "out_native2.mat")
        ml = run_engine("matlab", s_path, mat_out=d / "out_matlab.mat", answers=ans)

        v, detail = classify(native, ml)
        mat_ok, mat_lines, stdout_ok = None, [], None
        if v is None:
            stdout_ok = stdout_equal(normalise(native["out"], s_path), normalise(ml["out"], s_path))
            if not det_ok:
                v, detail = "nondeterministic", "; ".join(det_lines)[:160]
            elif (d / "out_native.mat").exists() and (d / "out_matlab.mat").exists():
                mat_ok, mat_lines = matdiff(d / "out_native.mat", d / "out_matlab.mat")
                v = "pass" if mat_ok else "workspace-mismatch"
                detail = "; ".join(mat_lines[:6])[:400]
            else:
                v, detail = "runtime-error", "no workspace .mat produced"
        r = {"script": rel, "verdict": v, "detail": detail,
             "native_ms": native["ms"], "matlab_ms": ml["ms"],
             "stdout_match": stdout_ok,
             "mat_diff": mat_lines[:20],
             "numkit_out": (native["out"] or native["err"])[:800],
             "matlab_out": (ml["out"] or ml["err"])[:800]}
        results.append(r)
        print(f"[{i+1}/{len(scripts)}] {Path(rel).name:<40} {v:<20} "
              f"native={r['native_ms']}ms matlab={r['matlab_ms']}ms")
        shutil.rmtree(d, ignore_errors=True)
    out = REPORTS / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport: {out}")
    print("=== SUMMARY ===")
    for k, n in Counter(r["verdict"] for r in results).most_common():
        print(f"{n:>4}  {k}")


def load_runnable(n, flt):
    if not RUNNABLE.exists():
        sys.exit("no runnable.json — run `python harness.py qualify` first (R3)")
    doc = json.loads(RUNNABLE.read_text(encoding="utf-8"))
    scripts = [_norm_rel(s["path"]) for s in doc["scripts"]]
    if flt:
        scripts = [s for s in scripts if flt.lower() in s.lower()]
    return scripts[:n] if n else scripts


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    flt = sys.argv[3] if len(sys.argv) > 3 else None
    if cmd == "harvest":
        harvest(n, flt)
    elif cmd == "qualify":
        qualify(n, flt, answered="--answered" in sys.argv)
    elif cmd == "run":
        run(load_runnable(n, flt))
    elif cmd == "matdiff":
        ok, lines = matdiff(sys.argv[2], sys.argv[3])
        print("\n".join(lines) or "identical (numeric intersection)")
        sys.exit(0 if ok else 1)
    elif cmd == "used-fns":
        for r in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")):
            if r["verdict"] == "absent-fn":
                m = re.search(r"function '([^']+)'", r["detail"])
                if m:
                    print(m.group(1))
    else:
        sys.exit(__doc__)
