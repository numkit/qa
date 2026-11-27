#!/usr/bin/env python3
"""GraphicsScene content differential tester: MATLAB R2025b vs NumKit.

Runs real MATLAB scripts from fieldtest/ through both MATLAB R2025b and NumKit,
dumps the live Handle Graphics scene tree (groot -> Figure -> Layout/Axes ->
Charts/Legends/Colorbars + plotted data arrays & limits/scales/labels) via an
identical pure-MATLAB helper function on both engines, and diffs the content.

Usage:
  python gfxdiff.py script <rel_or_abs_path> [-v]
  python gfxdiff.py group <group_name> [-v] [--jobs 4]
  python gfxdiff.py sweep [N] [--all-groups] [--filter <substr>] [--jobs 4] [-v]
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

_GFX_DUMP_HELPER = r"""function nk_fieldtest_dump_gfx_(out_path)
try
    fid = fopen(out_path, 'w');
    if fid < 0
        return;
    end
    r = groot;
    raw_figs = get(r, 'Children');
    figs = [];
    for i = numel(raw_figs):-1:1
        c = raw_figs(i);
        try
            if strcmpi(char(get(c, 'Type')), 'figure')
                if isempty(figs)
                    figs = c;
                else
                    figs(end + 1) = c; %#ok<AGROW>
                end
            end
        catch
        end
    end

    data_props = {'XData','YData','ZData','CData','UData','VData','WData', ...
                  'ThetaData','RData','Data','BinEdges','Values', ...
                  'Vertices','Faces','Value', ...
                  'YNegativeDelta','YPositiveDelta','XNegativeDelta','XPositiveDelta', ...
                  'LevelList','XEndPoints','YEndPoints'};

    for fi = 1:numel(figs)
        f = figs(fi);
        fnum = '';
        fname = '';
        try
            nv = get(f, 'Number');
            if ~isempty(nv)
                fnum = sprintf('%g', double(nv(1)));
            end
        catch
        end
        try
            fname = nk_gfx_flat_(get(f, 'Name'));
        catch
        end
        fprintf(fid, 'FIG\t%d\t%s\t%s\n', fi, fnum, fname);

        f_kids = get(f, 'Children');
        axes_list = {};
        leg_idx = 0;
        cbar_idx = 0;
        lay_idx = 0;
        for ki = numel(f_kids):-1:1
            kc = f_kids(ki);
            kt = '';
            try
                kt = lower(char(get(kc, 'Type')));
            catch
            end
            if strcmp(kt, 'axes') || strcmp(kt, 'polaraxes')
                axes_list{end + 1} = kc; %#ok<AGROW>
            elseif strcmp(kt, 'tiledlayout')
                lay_idx = lay_idx + 1;
                gs = '';
                try
                    gsv = double(get(kc, 'GridSize'));
                    if numel(gsv) >= 2
                        gs = sprintf('%g,%g', gsv(1), gsv(2));
                    end
                catch
                end
                fprintf(fid, 'LAYOUT\t%d\t%d\t%s\n', fi, lay_idx, gs);
                tk = [];
                try
                    tk = get(kc, 'Children');
                catch
                end
                for ti = numel(tk):-1:1
                    tc = tk(ti);
                    tt = '';
                    try
                        tt = lower(char(get(tc, 'Type')));
                    catch
                    end
                    if strcmp(tt, 'axes') || strcmp(tt, 'polaraxes')
                        axes_list{end + 1} = tc; %#ok<AGROW>
                    elseif strcmp(tt, 'legend')
                        leg_idx = leg_idx + 1;
                        lstr = '';
                        try
                            lstr = nk_gfx_flat_(get(tc, 'String'));
                        catch
                        end
                        fprintf(fid, 'LEG\t%d\t%d\t%s\n', fi, leg_idx, lstr);
                    elseif strcmp(tt, 'colorbar')
                        cbar_idx = cbar_idx + 1;
                        cstr = '';
                        try
                            cstr = nk_gfx_flat_(get(get(tc, 'Label'), 'String'));
                        catch
                        end
                        fprintf(fid, 'CBAR\t%d\t%d\t%s\n', fi, cbar_idx, cstr);
                    end
                end
            elseif strcmp(kt, 'legend')
                leg_idx = leg_idx + 1;
                lstr = '';
                try
                    lstr = nk_gfx_flat_(get(kc, 'String'));
                catch
                end
                fprintf(fid, 'LEG\t%d\t%d\t%s\n', fi, leg_idx, lstr);
            elseif strcmp(kt, 'colorbar')
                cbar_idx = cbar_idx + 1;
                cstr = '';
                try
                    cstr = nk_gfx_flat_(get(get(kc, 'Label'), 'String'));
                catch
                end
                fprintf(fid, 'CBAR\t%d\t%d\t%s\n', fi, cbar_idx, cstr);
            end
        end

        for ai = 1:numel(axes_list)
            ax = axes_list{ai};
            atype = lower(char(get(ax, 'Type')));
            ttl = nk_gfx_text_prop_(ax, 'Title');
            xlb = nk_gfx_text_prop_(ax, 'XLabel');
            ylb = nk_gfx_text_prop_(ax, 'YLabel');
            zlb = nk_gfx_text_prop_(ax, 'ZLabel');
            xsc = nk_gfx_char_prop_(ax, 'XScale');
            ysc = nk_gfx_char_prop_(ax, 'YScale');
            zsc = nk_gfx_char_prop_(ax, 'ZScale');
            xgr = nk_gfx_char_prop_(ax, 'XGrid');
            ygr = nk_gfx_char_prop_(ax, 'YGrid');
            boxp = nk_gfx_char_prop_(ax, 'Box');
            npl = nk_gfx_char_prop_(ax, 'NextPlot');
            if strcmp(atype, 'polaraxes')
                xlims = nk_gfx_vec_prop_(ax, 'ThetaLim');
                ylims = nk_gfx_vec_prop_(ax, 'RLim');
                zlims = '';
            else
                xlims = nk_gfx_vec_prop_(ax, 'XLim');
                ylims = nk_gfx_vec_prop_(ax, 'YLim');
                zlims = nk_gfx_vec_prop_(ax, 'ZLim');
            end
            fprintf(fid, 'AX\t%d\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n', ...
                fi, ai, atype, ttl, xlb, ylb, zlb, xsc, ysc, zsc, xgr, ygr, boxp, npl, xlims, ylims, zlims);

            ak = get(ax, 'Children');
            oidx = 0;
            for oi = numel(ak):-1:1
                co = ak(oi);
                otype = '';
                try
                    otype = lower(char(get(co, 'Type')));
                catch
                end
                oidx = oidx + 1;
                dname = nk_gfx_char_prop_(co, 'DisplayName');
                lst = nk_gfx_char_prop_(co, 'LineStyle');
                txt_str = '';
                if strcmp(otype, 'text')
                    txt_str = nk_gfx_char_prop_(co, 'String');
                end
                fprintf(fid, 'OBJ\t%d\t%d\t%d\t%s\t%s\t%s\t%s\n', fi, ai, oidx, otype, dname, lst, txt_str);

                for pi = 1:numel(data_props)
                    pn = data_props{pi};
                    try
                        if ~isprop(co, pn)
                            continue;
                        end
                        val = get(co, pn);
                        if isempty(val)
                            continue;
                        end
                        if isa(val, 'datetime')
                            val = datenum(val);
                        elseif ~isnumeric(val) && ~islogical(val)
                            continue;
                        end
                        dv = double(val);
                        sz = size(dv);
                        sz_str = sprintf('%d,', sz);
                        sz_str = sz_str(1:end-1);
                        flat = dv(:);
                        n = numel(flat);
                        nan_c = sum(isnan(flat));
                        inf_c = sum(isinf(flat));
                        fprintf(fid, 'DATA\t%d\t%d\t%d\t%s\t%s\t%d\t%d\t%d', ...
                            fi, ai, oidx, pn, sz_str, n, nan_c, inf_c);
                        if n <= 64
                            fprintf(fid, '\tALL');
                            for j = 1:n
                                fprintf(fid, '\t%.12g', flat(j));
                            end
                        else
                            fin = flat(isfinite(flat));
                            if isempty(fin)
                                fmin = NaN; fmax = NaN; fmean = NaN;
                            else
                                fmin = min(fin); fmax = max(fin); fmean = mean(fin);
                            end
                            fprintf(fid, '\tSAMP\t%.12g\t%.12g\t%.12g', fmin, fmax, fmean);
                            idxs = round(linspace(1, n, 32));
                            for j = 1:numel(idxs)
                                fprintf(fid, '\t%.12g', flat(idxs(j)));
                            end
                        end
                        fprintf(fid, '\n');
                    catch
                    end
                end
            end
        end
    end
    fclose(fid);
catch
end
end

function s = nk_gfx_flat_(v)
s = '';
try
    if isempty(v)
        return;
    end
    if iscell(v)
        parts = cell(1, numel(v));
        for k = 1:numel(v)
            parts{k} = nk_gfx_flat_(v{k});
        end
        s = strjoin(parts, '|');
    elseif isstring(v)
        if numel(v) == 1
            s = char(v);
        else
            parts = cell(1, numel(v));
            for k = 1:numel(v)
                parts{k} = char(v(k));
            end
            s = strjoin(parts, '|');
        end
    elseif ischar(v)
        if size(v, 1) > 1
            parts = cell(1, size(v, 1));
            for k = 1:size(v, 1)
                parts{k} = strtrim(v(k, :));
            end
            s = strjoin(parts, '|');
        else
            s = v;
        end
    else
        s = char(v);
    end
    s = strrep(s, char(9), ' ');
    s = strrep(s, char(13), ' ');
    s = strrep(s, char(10), '|');
catch
    s = '';
end
end

function s = nk_gfx_char_prop_(h, prop)
s = '';
try
    if isprop(h, prop)
        s = nk_gfx_flat_(get(h, prop));
    end
catch
end
end

function s = nk_gfx_text_prop_(ax, prop)
s = '';
try
    if isprop(ax, prop)
        th = get(ax, prop);
        if ~isempty(th)
            s = nk_gfx_flat_(get(th, 'String'));
        end
    end
catch
end
end

function s = nk_gfx_vec_prop_(h, prop)
s = '';
try
    if isprop(h, prop)
        v = double(get(h, prop));
        v = v(:);
        if ~isempty(v)
            parts = cell(1, numel(v));
            for k = 1:numel(v)
                parts{k} = sprintf('%.12g', v(k));
            end
            s = strjoin(parts, ',');
        end
    end
catch
end
end
"""


def _ensure_gfx_helper(helper_dir: Path) -> Path:
    helper = helper_dir / "nk_fieldtest_dump_gfx_.m"
    helper.write_text(_GFX_DUMP_HELPER, encoding="utf-8")
    return helper


def run_with_gfx(kind: str, script: Path, gfx_out: Path, answers=None):
    """Run script in MATLAB or NumKit and dump GraphicsScene tree to gfx_out."""
    cwd = str(script.parent)
    repo_root = H._repo_root_of(script)
    rel_repo = (
        Path(os.path.relpath(repo_root.resolve(), script.resolve().parent)).as_posix()
        if repo_root is not None
        else None
    )
    addpath_cmd = f"addpath(genpath('{rel_repo}')); " if rel_repo is not None else ""

    stub_dir = None
    stdin_text = None
    if answers is not None:
        stdin_text = "\n".join(answers) + "\n"
        if kind == "matlab":
            H.TMP.mkdir(parents=True, exist_ok=True)
            stub_dir = Path(tempfile.mkdtemp(prefix="numkit_gfx_in_", dir=H.TMP))
            stub = stub_dir / "input.m"
            quoted = " ".join("'{}'".format(a.replace("'", "''")) for a in answers)
            stub.write_text(
                "function varargout = input(prompt, fmt)\n"
                "persistent QUEUE\n"
                f"if isempty(QUEUE), QUEUE = {{ {quoted} }}; end\n"
                "if isempty(QUEUE), s = ''; else, s = QUEUE{1}; QUEUE(1) = []; end\n"
                "if nargin > 1, varargout{1} = s;\n"
                "elseif isempty(s), varargout{1} = [];\n"
                "else, varargout{1} = eval(s); end\n",
                encoding="utf-8",
            )
            addpath_cmd += f"addpath('{stub_dir.resolve().as_posix()}'); "

    _ensure_gfx_helper(gfx_out.parent)
    dump_cmd = (
        f" addpath('{gfx_out.parent.resolve().as_posix()}'); "
        f"nk_fieldtest_dump_gfx_('{gfx_out.resolve().as_posix()}');"
    )

    if kind == "matlab":
        argv = [
            str(H.MATLAB),
            "-batch",
            "restoredefaultpath; clear RESTOREDEFAULTPATH_EXECUTED; pause('off'); "
            "try, s__ = settings; s__.matlab.appearance.figure.GraphicsTheme.TemporaryValue = 'light'; clear s__; catch, end; "
            + addpath_cmd
            + f"run('{script.name}');"
            + dump_cmd,
        ]
    elif kind == "native":
        body = "pause('off'); " + addpath_cmd + f"run('{script.name}');" + dump_cmd
        argv = [str(H.NATIVE_CLI), "-e", body]
    else:
        raise ValueError(kind)

    t0 = time.perf_counter()
    to = 180 if kind == "matlab" else 90
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            out_b, err_b = proc.communicate(
                input=(stdin_text.encode("utf-8") if stdin_text is not None else None),
                timeout=to,
            )
            ms = int((time.perf_counter() - t0) * 1000)
            dec = lambda b: (b or b"").decode("utf-8", "replace")
            return {"exit": proc.returncode, "out": dec(out_b), "err": dec(err_b), "ms": ms}
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                proc.kill()
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
            return {"exit": "timeout", "out": "", "err": "", "ms": to * 1000}
    finally:
        if stub_dir is not None and stub_dir.exists():
            shutil.rmtree(stub_dir, ignore_errors=True)


def _parse_floats(vals):
    out = []
    for s in vals:
        s = s.strip()
        if not s:
            continue
        low = s.lower()
        if low == "nan":
            out.append(float("nan"))
        elif low in ("inf", "+inf"):
            out.append(float("inf"))
        elif low == "-inf":
            out.append(float("-inf"))
        else:
            try:
                out.append(float(s))
            except ValueError:
                out.append(float("nan"))
    return out


def parse_gfx_tsv(path: Path) -> dict:
    """Parse a .gfx.tsv dump into a structured scene dict."""
    scene = {"figures": []}
    if not path.exists():
        return scene
    figs_by_id = {}
    axes_by_key = {}
    objs_by_key = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        tag = parts[0]
        if tag == "FIG" and len(parts) >= 4:
            fi = int(parts[1])
            f = {
                "idx": fi,
                "number": parts[2],
                "name": parts[3],
                "layouts": [],
                "axes": [],
                "legends": [],
                "colorbars": [],
            }
            figs_by_id[fi] = f
            scene["figures"].append(f)
        elif tag == "LAYOUT" and len(parts) >= 4:
            fi = int(parts[1])
            if fi in figs_by_id:
                figs_by_id[fi]["layouts"].append({"idx": int(parts[2]), "gridSize": parts[3]})
        elif tag == "LEG" and len(parts) >= 4:
            fi = int(parts[1])
            if fi in figs_by_id:
                figs_by_id[fi]["legends"].append({"idx": int(parts[2]), "string": parts[3]})
        elif tag == "CBAR" and len(parts) >= 4:
            fi = int(parts[1])
            if fi in figs_by_id:
                figs_by_id[fi]["colorbars"].append({"idx": int(parts[2]), "label": parts[3]})
        elif tag == "AX" and len(parts) >= 18:
            fi, ai = int(parts[1]), int(parts[2])
            ax = {
                "idx": ai,
                "type": parts[3],
                "title": parts[4],
                "xlabel": parts[5],
                "ylabel": parts[6],
                "zlabel": parts[7],
                "xscale": parts[8].lower(),
                "yscale": parts[9].lower(),
                "zscale": parts[10].lower(),
                "xgrid": parts[11].lower(),
                "ygrid": parts[12].lower(),
                "box": parts[13].lower(),
                "nextplot": parts[14].lower(),
                "xlim": _parse_floats(parts[15].split(",")) if parts[15] else [],
                "ylim": _parse_floats(parts[16].split(",")) if parts[16] else [],
                "zlim": _parse_floats(parts[17].split(",")) if parts[17] else [],
                "objects": [],
            }
            if fi in figs_by_id:
                figs_by_id[fi]["axes"].append(ax)
                axes_by_key[(fi, ai)] = ax
        elif tag == "OBJ" and len(parts) >= 8:
            fi, ai, oi = int(parts[1]), int(parts[2]), int(parts[3])
            obj = {
                "idx": oi,
                "type": parts[4].lower(),
                "displayName": parts[5],
                "lineStyle": parts[6],
                "text": parts[7],
                "data": {},
            }
            if (fi, ai) in axes_by_key:
                axes_by_key[(fi, ai)]["objects"].append(obj)
                objs_by_key[(fi, ai, oi)] = obj
        elif tag == "DATA" and len(parts) >= 10:
            fi, ai, oi = int(parts[1]), int(parts[2]), int(parts[3])
            if (fi, ai, oi) in objs_by_key:
                objs_by_key[(fi, ai, oi)]["data"][parts[4]] = {
                    "shape": parts[5],
                    "numel": int(parts[6]),
                    "nan": int(parts[7]),
                    "inf": int(parts[8]),
                    "mode": parts[9],
                    "vals": _parse_floats(parts[10:]),
                }
    return scene


def _float_list_close(a, b, rel=1e-6, atol=1e-7):
    if len(a) != len(b):
        return False, float("inf")
    max_rel = 0.0
    for x, y in zip(a, b):
        if math.isnan(x) and math.isnan(y):
            continue
        if math.isinf(x) and math.isinf(y) and (x > 0) == (y > 0):
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            return False, float("inf")
        diff = abs(x - y)
        scale = max(abs(x), abs(y))
        if diff > atol + rel * scale:
            r = diff / max(scale, 1e-300)
            max_rel = max(max_rel, r)
            return False, max_rel
    return True, max_rel


# Properties that are primary plotted data (must match MATLAB closely).
_PRIMARY_DATA_PROPS = frozenset({
    "XData", "YData", "ZData", "CData", "UData", "VData", "WData",
    "ThetaData", "RData", "Data", "BinEdges", "Values",
    "Vertices", "Faces", "Value",
    "YNegativeDelta", "YPositiveDelta", "XNegativeDelta", "XPositiveDelta",
    "LevelList",
})

# Derived/secondary properties where minor layout/padding conventions may differ.
_SECONDARY_DATA_PROPS = frozenset({"XEndPoints", "YEndPoints"})


def diff_scenes(nk_scene: dict, ml_scene: dict) -> dict:
    """Compare two parsed scenes. Returns categorized diff report."""
    hard = []   # Structural (fig/ax/obj counts, types, scales) + plotted data mismatches
    lim = []    # XLim/YLim/ZLim differences
    meta = []   # Titles, labels, legends, grid, box, displayName, secondary endpoints

    nf_nk, nf_ml = len(nk_scene["figures"]), len(ml_scene["figures"])
    if nf_nk != nf_ml:
        hard.append(f"FIG_COUNT: nk={nf_nk} vs ml={nf_ml}")

    for fi in range(min(nf_nk, nf_ml)):
        fnk, fml = nk_scene["figures"][fi], ml_scene["figures"][fi]
        ftag = f"F{fi+1}"
        if fnk["number"] != fml["number"]:
            meta.append(f"{ftag}.Number: nk={fnk['number']} vs ml={fml['number']}")
        if fnk["name"] != fml["name"]:
            meta.append(f"{ftag}.Name: nk='{fnk['name']}' vs ml='{fml['name']}'")

        if len(fnk["layouts"]) != len(fml["layouts"]):
            hard.append(f"{ftag}.LAYOUT_COUNT: nk={len(fnk['layouts'])} vs ml={len(fml['layouts'])}")
        else:
            for li, (lnk, lml) in enumerate(zip(fnk["layouts"], fml["layouts"])):
                if lnk["gridSize"] != lml["gridSize"]:
                    hard.append(f"{ftag}.L{li+1}.GridSize: nk={lnk['gridSize']} vs ml={lml['gridSize']}")

        if len(fnk["legends"]) != len(fml["legends"]):
            meta.append(f"{ftag}.LEGEND_COUNT: nk={len(fnk['legends'])} vs ml={len(fml['legends'])}")
        else:
            for li, (lnk, lml) in enumerate(zip(fnk["legends"], fml["legends"])):
                if lnk["string"] != lml["string"]:
                    meta.append(f"{ftag}.Leg{li+1}.String: nk='{lnk['string']}' vs ml='{lml['string']}'")

        if len(fnk["colorbars"]) != len(fml["colorbars"]):
            meta.append(f"{ftag}.CBAR_COUNT: nk={len(fnk['colorbars'])} vs ml={len(fml['colorbars'])}")

        na_nk, na_ml = len(fnk["axes"]), len(fml["axes"])
        if na_nk != na_ml:
            hard.append(f"{ftag}.AX_COUNT: nk={na_nk} vs ml={na_ml}")

        for ai in range(min(na_nk, na_ml)):
            ank, aml = fnk["axes"][ai], fml["axes"][ai]
            atag = f"{ftag}.A{ai+1}"
            if ank["type"] != aml["type"]:
                hard.append(f"{atag}.Type: nk={ank['type']} vs ml={aml['type']}")
            for sc in ("xscale", "yscale", "zscale"):
                if ank[sc] != aml[sc]:
                    hard.append(f"{atag}.{sc}: nk={ank[sc]} vs ml={aml[sc]}")
            for tp in ("title", "xlabel", "ylabel", "zlabel"):
                if ank[tp] != aml[tp]:
                    meta.append(f"{atag}.{tp}: nk='{ank[tp]}' vs ml='{aml[tp]}'")
            for gp in ("xgrid", "ygrid", "box"):
                if ank[gp] != aml[gp]:
                    meta.append(f"{atag}.{gp}: nk={ank[gp]} vs ml={aml[gp]}")
            for lp in ("xlim", "ylim", "zlim"):
                if aml[lp] and ank[lp]:
                    ok_l, _ = _float_list_close(ank[lp], aml[lp], rel=1e-4, atol=1e-6)
                    if not ok_l:
                        lim.append(f"{atag}.{lp}: nk={ank[lp]} vs ml={aml[lp]}")

            no_nk, no_ml = len(ank["objects"]), len(aml["objects"])
            if no_nk != no_ml:
                nk_types = [o["type"] for o in ank["objects"]]
                ml_types = [o["type"] for o in aml["objects"]]
                hard.append(f"{atag}.OBJ_COUNT: nk={no_nk} {nk_types} vs ml={no_ml} {ml_types}")

            for oi in range(min(no_nk, no_ml)):
                onk, oml = ank["objects"][oi], aml["objects"][oi]
                otag = f"{atag}.O{oi+1}({oml['type']})"
                if onk["type"] != oml["type"]:
                    hard.append(f"{otag}.Type: nk={onk['type']} vs ml={oml['type']}")
                    continue
                if oml["type"] == "text" and onk["text"] != oml["text"]:
                    meta.append(f"{otag}.String: nk='{onk['text']}' vs ml='{oml['text']}'")
                if onk["displayName"] != oml["displayName"]:
                    meta.append(f"{otag}.DisplayName: nk='{onk['displayName']}' vs ml='{oml['displayName']}'")
                if oml["lineStyle"] and onk["lineStyle"] != oml["lineStyle"]:
                    meta.append(f"{otag}.LineStyle: nk='{onk['lineStyle']}' vs ml='{oml['lineStyle']}'")

                # Compare plotted data arrays
                all_props = sorted(set(oml["data"]) | set(onk["data"]))
                for pn in all_props:
                    target = hard if pn in _PRIMARY_DATA_PROPS else meta
                    in_nk = pn in onk["data"]
                    in_ml = pn in oml["data"]
                    if in_ml and not in_nk:
                        # Skip CData on surface/patch/bar/area when MATLAB auto-populates CData
                        if pn == "CData" and oml["type"] in ("surface", "patch", "bar", "area"):
                            meta.append(f"{otag}.{pn}: missing in nk (ml shape={oml['data'][pn]['shape']})")
                        else:
                            target.append(f"{otag}.{pn}: missing in nk (ml shape={oml['data'][pn]['shape']})")
                        continue
                    if in_nk and not in_ml:
                        # Extra ZData/CData in nk when MATLAB leaves empty is worth noting in meta
                        if pn in ("ZData", "CData", "XEndPoints", "YEndPoints", "Vertices", "Faces"):
                            meta.append(f"{otag}.{pn}: extra in nk (nk shape={onk['data'][pn]['shape']})")
                        else:
                            target.append(f"{otag}.{pn}: extra in nk (nk shape={onk['data'][pn]['shape']})")
                        continue

                    dnk, dml = onk["data"][pn], oml["data"][pn]
                    if dnk["numel"] != dml["numel"]:
                        target.append(
                            f"{otag}.{pn}.numel: nk={dnk['numel']} ({dnk['shape']}) vs ml={dml['numel']} ({dml['shape']})"
                        )
                        continue
                    if dnk["nan"] != dml["nan"] or dnk["inf"] != dml["inf"]:
                        target.append(
                            f"{otag}.{pn}.specials: nk=(nan={dnk['nan']},inf={dnk['inf']}) vs ml=(nan={dml['nan']},inf={dml['inf']})"
                        )
                        continue
                    ok_v, rel = _float_list_close(dnk["vals"], dml["vals"])
                    if not ok_v:
                        # On datetime axes, MATLAB's DatetimeRuler stores Patch.Vertices(:,1)
                        # relative to the first date (e.g. 0..24107) while Patch.XData holds the
                        # absolute serial dates. If XData and YData already match, check Vertices
                        # with the X-origin shift accounted for.
                        if (pn == "Vertices" and oml["type"] == "patch"
                                and "XData" in onk["data"] and "XData" in oml["data"]):
                            xd_nk = onk["data"]["XData"]
                            xd_ml = oml["data"]["XData"]
                            ok_x, _ = _float_list_close(xd_nk["vals"], xd_ml["vals"])
                            if ok_x and xd_ml["vals"] and max(abs(v) for v in xd_ml["vals"] if math.isfinite(v)) > 600000.0:
                                meta.append(f"{otag}.Vertices: datetime ruler origin offset (XData/YData match)")
                                continue
                        target.append(
                            f"{otag}.{pn}.values: diverge (rel={rel:.3e}, shape={dml['shape']}, "
                            f"nk={dnk['vals'][:4]} vs ml={dml['vals'][:4]})"
                        )

    return {
        "nk_figs": nf_nk,
        "ml_figs": nf_ml,
        "hard": hard,
        "lim": lim,
        "meta": meta,
    }


def evaluate_script(rel: str) -> dict:
    s = H._resolve_script(rel)
    if not s.exists():
        return {"script": rel, "verdict": "missing", "detail": "file not found"}
    ans = H.answers_for(s)
    d = H._tmpdir(s)
    try:
        nk_tsv = d / "nk.gfx.tsv"
        ml_tsv = d / "ml.gfx.tsv"
        nk_res = run_with_gfx("native", s, nk_tsv, answers=ans)
        ml_res = run_with_gfx("matlab", s, ml_tsv, answers=ans)
        v, detail = H.classify(nk_res, ml_res)
        if v is not None:
            return {
                "script": rel,
                "verdict": v,
                "detail": detail,
                "nk_ms": nk_res["ms"],
                "ml_ms": ml_res["ms"],
                "hard": [],
                "lim": [],
                "meta": [],
            }
        nk_scene = parse_gfx_tsv(nk_tsv)
        ml_scene = parse_gfx_tsv(ml_tsv)
        diff = diff_scenes(nk_scene, ml_scene)

        # Determinism check if hard data diverges (unseeded rand/randn scripts)
        if diff["hard"]:
            nk_tsv2 = d / "nk2.gfx.tsv"
            run_with_gfx("native", s, nk_tsv2, answers=ans)
            nk_scene2 = parse_gfx_tsv(nk_tsv2)
            det = diff_scenes(nk_scene, nk_scene2)
            if det["hard"]:
                # If every hard diff is also nondeterministic between two nk runs, classify as nondeterministic
                hard_keys = {h.split(":", 1)[0] for h in diff["hard"]}
                det_keys = {h.split(":", 1)[0] for h in det["hard"]}
                if hard_keys <= det_keys:
                    return {
                        "script": rel,
                        "verdict": "nondeterministic",
                        "detail": f"figs={diff['ml_figs']} (random data)",
                        "nk_ms": nk_res["ms"],
                        "ml_ms": ml_res["ms"],
                        "nk_figs": diff["nk_figs"],
                        "ml_figs": diff["ml_figs"],
                        "hard": [],
                        "lim": diff["lim"],
                        "meta": diff["meta"],
                    }

        if diff["ml_figs"] == 0 and diff["nk_figs"] == 0:
            verdict = "no-figs"
        elif not diff["hard"]:
            verdict = "pass" if (not diff["lim"] and not diff["meta"]) else "pass-data"
        else:
            verdict = "gfx-mismatch"

        return {
            "script": rel,
            "verdict": verdict,
            "detail": "; ".join(diff["hard"][:3]) if diff["hard"] else "",
            "nk_ms": nk_res["ms"],
            "ml_ms": ml_res["ms"],
            "nk_figs": diff["nk_figs"],
            "ml_figs": diff["ml_figs"],
            "hard": diff["hard"],
            "lim": diff["lim"],
            "meta": diff["meta"],
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


_GFX_PAT = re.compile(
    r"\b(plot|plot3|scatter|scatter3|bar|barh|surf|mesh|contour|contourf|stem|"
    r"errorbar|histogram|area|stairs|quiver|polarplot|semilogx|semilogy|loglog|"
    r"imagesc|image|patch|fill|animatedline|xline|yline|subplot|tiledlayout|"
    r"figure|axes|legend|colorbar|yyaxis)\s*\("
)


def pick_diverse_scripts(limit: int, all_groups: bool, flt: str | None) -> list[str]:
    """Select a diverse set of graphics scripts covering as many distinct plot functions as possible."""
    pool = []
    seen = set()
    if all_groups:
        for g in sorted((HERE / "groups").glob("*.txt")):
            for line in g.read_text(encoding="utf-8").splitlines():
                if "# known:" in line:
                    continue
                rel = line.split("#", 1)[0].strip()
                if not rel or rel in seen:
                    continue
                seen.add(rel)
                pool.append(rel)
    else:
        doc = json.loads(H.RUNNABLE.read_text(encoding="utf-8"))
        for e in doc["scripts"]:
            rel = H._norm_rel(e["path"])
            if rel not in seen:
                seen.add(rel)
                pool.append(rel)

    cands = []
    for rel in pool:
        if flt and flt.lower() not in rel.lower():
            continue
        p = H._resolve_script(rel)
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        fns = set(_GFX_PAT.findall(txt))
        if fns:
            cands.append((rel, fns))

    # Greedy set-cover / diversity selection so we hit rare functions (surf, bar, histogram,
    # contour, stem, errorbar, scatter, patch, imagesc, tiledlayout, xline, yline, polarplot...) first!
    selected = []
    fn_counts = Counter()
    remaining = list(cands)
    while remaining and len(selected) < limit:
        best_i = 0
        best_score = -1.0
        for i, (rel, fns) in enumerate(remaining):
            score = sum(1.0 / (1 + fn_counts[fn]) for fn in fns)
            if score > best_score:
                best_score = score
                best_i = i
        rel, fns = remaining.pop(best_i)
        selected.append(rel)
        for fn in fns:
            fn_counts[fn] += 1
    return selected


def main():
    ap = argparse.ArgumentParser(description="Diff GraphicsScene content vs MATLAB R2025b")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sc = sub.add_parser("script", help="Test a single script")
    p_sc.add_argument("path")
    p_sc.add_argument("-v", "--verbose", action="store_true")

    p_gr = sub.add_parser("group", help="Test a fieldtest group")
    p_gr.add_argument("name")
    p_gr.add_argument("-j", "--jobs", type=int, default=4)
    p_gr.add_argument("-v", "--verbose", action="store_true")

    p_sw = sub.add_parser("sweep", help="Test a diverse sweep of graphics scripts")
    p_sw.add_argument("limit", type=int, nargs="?", default=40)
    p_sw.add_argument("--all-groups", action="store_true")
    p_sw.add_argument("--filter", dest="flt", default=None)
    p_sw.add_argument("-j", "--jobs", type=int, default=4)
    p_sw.add_argument("-v", "--verbose", action="store_true")

    args = ap.parse_args()

    if args.cmd == "script":
        r = evaluate_script(args.path)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        sys.exit(0 if r["verdict"] in ("pass", "pass-data", "no-figs", "nondeterministic") else 1)

    if args.cmd == "group":
        gfile = HERE / "groups" / f"{args.name}.txt"
        if not gfile.exists():
            sys.exit(f"no such group: {args.name}")
        scripts = []
        for line in gfile.read_text(encoding="utf-8").splitlines():
            rel = line.split("#", 1)[0].strip()
            if rel:
                p = H._resolve_script(rel)
                if p.exists() and _GFX_PAT.search(p.read_text(encoding="utf-8", errors="ignore")):
                    scripts.append(rel)
    else:
        scripts = pick_diverse_scripts(args.limit, args.all_groups, args.flt)

    print(f"=== gfxdiff: {len(scripts)} graphics scripts (jobs={args.jobs}) ===", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, r in enumerate(pool.map(evaluate_script, scripts), 1):
            results.append(r)
            figs_tag = f"figs={r.get('nk_figs', '-')}/{r.get('ml_figs', '-')}"
            extra = ""
            if r["verdict"] == "gfx-mismatch" and r.get("hard"):
                extra = r["hard"][0][:90]
            elif r["verdict"] not in ("pass", "pass-data", "no-figs", "nondeterministic"):
                dlines = (r.get("detail") or "").splitlines()
                extra = dlines[0][:90] if dlines else ""
            elif r["verdict"] == "pass-data":
                extra = f"lim={len(r.get('lim', []))} meta={len(r.get('meta', []))}"
            print(
                f"[{i:2d}/{len(scripts)}] {Path(r['script']).name:<36} {r['verdict']:<16} "
                f"{figs_tag:<10} {extra}",
                flush=True,
            )
            if args.verbose:
                for h in r.get("hard", [])[:8]:
                    print(f"      HARD: {h}", flush=True)
                for l in r.get("lim", [])[:4]:
                    print(f"      LIM : {l}", flush=True)
                for m in r.get("meta", [])[:4]:
                    print(f"      META: {m}", flush=True)

    H.REPORTS.mkdir(exist_ok=True)
    out_path = H.REPORTS / f"gfx-{datetime.now():%Y%m%d-%H%M%S}.json"
    out_path.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    print("\n=== SUMMARY ===", flush=True)
    for k, n in Counter(r["verdict"] for r in results).most_common():
        print(f"  {n:>4}  {k}")
    print(f"report: {out_path}", flush=True)


if __name__ == "__main__":
    main()
