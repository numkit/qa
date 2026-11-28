"""Multi-layer visual & DOM comparison metrics for MATLAB vs NumKit graphics parity."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, gaussian_filter, uniform_filter


@dataclass
class VisualMetrics:
    ml_size: Tuple[int, int]
    nk_size: Tuple[int, int]
    aspect_diff: float
    ssim: float
    ink_iou: float          # Dilated IoU (r=2px) of non-background pixels
    plot_iou: float         # Dilated IoU inside axes inner plot boxes only
    bbox_diff: float        # Max normalized ink bounding-box mismatch [0..1]
    color_l1: float         # L1 distance of ink color histograms [0..2] (0=identical)
    ink_ratio_ml: float     # Fraction of non-background pixels in MATLAB
    ink_ratio_nk: float     # Fraction of non-background pixels in NumKit
    score: float            # Combined quality score [0..100]


@dataclass
class DomDiffSummary:
    issues: List[str] = field(default_factory=list)
    axes_count_mismatch: bool = False
    position_mismatch: bool = False
    limits_mismatch: bool = False
    ticks_mismatch: bool = False
    legend_mismatch: bool = False
    children_mismatch: bool = False


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.float32)


def _resize_to(arr: np.ndarray, target_hw: Tuple[int, int]) -> np.ndarray:
    th, tw = target_hw
    if arr.shape[0] == th and arr.shape[1] == tw:
        return arr
    im = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    im = im.resize((tw, th), Image.Resampling.BILINEAR)
    return np.asarray(im, dtype=np.float32)


def _compute_ssim(a: np.ndarray, b: np.ndarray) -> float:
    # Luminance SSIM on Gaussian-smoothed image (sigma=0.8) so 1px font hinting doesn't dominate.
    ya = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    yb = 0.299 * b[:, :, 0] + 0.587 * b[:, :, 1] + 0.114 * b[:, :, 2]
    ya = gaussian_filter(ya, sigma=0.8)
    yb = gaussian_filter(yb, sigma=0.8)

    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mu_a = uniform_filter(ya, size=11)
    mu_b = uniform_filter(yb, size=11)
    mu_a2 = mu_a * mu_a
    mu_b2 = mu_b * mu_b
    mu_ab = mu_a * mu_b

    sig_a2 = np.maximum(0.0, uniform_filter(ya * ya, size=11) - mu_a2)
    sig_b2 = np.maximum(0.0, uniform_filter(yb * yb, size=11) - mu_b2)
    sig_ab = uniform_filter(ya * yb, size=11) - mu_ab

    num = (2.0 * mu_ab + c1) * (2.0 * sig_ab + c2)
    den = (mu_a2 + mu_b2 + c1) * (sig_a2 + sig_b2 + c2)
    return float(np.mean(num / np.maximum(den, 1e-6)))


def _detect_bg_color(arr: np.ndarray) -> np.ndarray:
    # Corner median detects figure background cleanly (white or custom gray/dark).
    corners = np.concatenate([
        arr[:8, :8].reshape(-1, 3),
        arr[:8, -8:].reshape(-1, 3),
        arr[-8:, :8].reshape(-1, 3),
        arr[-8:, -8:].reshape(-1, 3),
    ], axis=0)
    return np.median(corners, axis=0)


def _ink_mask(arr: np.ndarray, bg: np.ndarray, thresh: float = 18.0) -> np.ndarray:
    dist = np.max(np.abs(arr - bg[None, None, :]), axis=2)
    return dist > thresh


def _dilated_iou(m1: np.ndarray, m2: np.ndarray, radius: int = 3) -> float:
    s1 = int(m1.sum())
    s2 = int(m2.sum())
    if s1 == 0 and s2 == 0:
        return 1.0
    if s1 == 0 or s2 == 0:
        return 0.0
    struct = np.ones((2 * radius + 1, 2 * radius + 1), dtype=bool)
    d1 = binary_dilation(m1, structure=struct)
    d2 = binary_dilation(m2, structure=struct)
    # Symmetric recall: fraction of m1 covered by dilated m2 AND fraction of m2 covered by dilated m1.
    r1 = float((m1 & d2).sum()) / float(s1)
    r2 = float((m2 & d1).sum()) / float(s2)
    if r1 + r2 == 0.0:
        return 0.0
    return (2.0 * r1 * r2) / (r1 + r2)


def _ink_bbox(mask: np.ndarray) -> Tuple[float, float, float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return (0.0, 0.0, 0.0, 0.0)
    h, w = mask.shape
    return (
        float(xs.min()) / w,
        float(ys.min()) / h,
        float(xs.max()) / w,
        float(ys.max()) / h,
    )


def _color_hist_l1(a: np.ndarray, ma: np.ndarray, b: np.ndarray, mb: np.ndarray) -> float:
    # Quantize ink pixels into 6x6x6 RGB cube (216 bins) and compute L1 distance [0..2].
    def hist_of(arr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        pts = arr[mask]
        if len(pts) == 0:
            return np.zeros(216, dtype=np.float64)
        q = np.clip((pts / 256.0 * 6.0).astype(np.int32), 0, 5)
        bins = q[:, 0] * 36 + q[:, 1] * 6 + q[:, 2]
        h = np.bincount(bins, minlength=216).astype(np.float64)
        return h / max(1.0, float(h.sum()))

    ha = hist_of(a, ma)
    hb = hist_of(b, mb)
    return float(np.sum(np.abs(ha - hb)))


def _plot_region_mask(shape_hw: Tuple[int, int], dom: Optional[Dict[str, Any]]) -> np.ndarray:
    h, w = shape_hw
    mask = np.zeros((h, w), dtype=bool)
    if not dom or not dom.get("axes"):
        mask[int(0.1 * h):int(0.9 * h), int(0.1 * w):int(0.9 * w)] = True
        return mask
    any_pos = False
    for ax in dom["axes"]:
        pos = ax.get("position")
        if isinstance(pos, list) and len(pos) >= 4:
            l, b, pw, ph = [float(x) for x in pos[:4]]
            x0 = max(0, min(w, int(round(l * w))))
            x1 = max(0, min(w, int(round((l + pw) * w))))
            y0 = max(0, min(h, int(round((1.0 - b - ph) * h))))
            y1 = max(0, min(h, int(round((1.0 - b) * h))))
            if x1 > x0 and y1 > y0:
                mask[y0:y1, x0:x1] = True
                any_pos = True
    if not any_pos:
        mask[int(0.1 * h):int(0.9 * h), int(0.1 * w):int(0.9 * w)] = True
    return mask


def compare_images(
    ml_png: Path,
    nk_png: Path,
    ml_dom: Optional[Dict[str, Any]] = None,
    diff_out: Optional[Path] = None,
) -> VisualMetrics:
    ml = _load_rgb(ml_png)
    nk_raw = _load_rgb(nk_png)
    ml_size = (ml.shape[1], ml.shape[0])
    nk_size = (nk_raw.shape[1], nk_raw.shape[0])

    ar_ml = ml_size[0] / max(1.0, float(ml_size[1]))
    ar_nk = nk_size[0] / max(1.0, float(nk_size[1]))
    aspect_diff = abs(ar_ml - ar_nk) / max(1e-6, ar_ml)

    nk = _resize_to(nk_raw, (ml.shape[0], ml.shape[1]))

    bg_ml = _detect_bg_color(ml)
    bg_nk = _detect_bg_color(nk)
    m_ml = _ink_mask(ml, bg_ml)
    m_nk = _ink_mask(nk, bg_nk)

    ssim = _compute_ssim(ml, nk)
    ink_iou = _dilated_iou(m_ml, m_nk, radius=3)

    preg = _plot_region_mask((ml.shape[0], ml.shape[1]), ml_dom)
    plot_iou = _dilated_iou(m_ml & preg, m_nk & preg, radius=3)

    bb_ml = _ink_bbox(m_ml)
    bb_nk = _ink_bbox(m_nk)
    bbox_diff = max(abs(a - b) for a, b in zip(bb_ml, bb_nk))
    color_l1 = _color_hist_l1(ml, m_ml, nk, m_nk)

    ink_ratio_ml = float(m_ml.mean())
    ink_ratio_nk = float(m_nk.mean())

    # Composite [0..100] score: penalizes missing/wrong data, bad colors, bad bbox, bad aspect.
    color_sim = max(0.0, 1.0 - color_l1 * 0.5)
    bbox_sim = max(0.0, 1.0 - bbox_diff * 2.5)
    aspect_sim = max(0.0, 1.0 - aspect_diff * 3.0)
    score = 100.0 * (
        0.22 * max(0.0, ssim)
        + 0.28 * ink_iou
        + 0.28 * plot_iou
        + 0.12 * color_sim
        + 0.06 * bbox_sim
        + 0.04 * aspect_sim
    )

    if diff_out is not None:
        save_triple_diff(ml, nk, m_ml, m_nk, diff_out)

    return VisualMetrics(
        ml_size=ml_size,
        nk_size=nk_size,
        aspect_diff=aspect_diff,
        ssim=ssim,
        ink_iou=ink_iou,
        plot_iou=plot_iou,
        bbox_diff=bbox_diff,
        color_l1=color_l1,
        ink_ratio_ml=ink_ratio_ml,
        ink_ratio_nk=ink_ratio_nk,
        score=score,
    )


def save_triple_diff(
    ml: np.ndarray,
    nk: np.ndarray,
    m_ml: np.ndarray,
    m_nk: np.ndarray,
    out_path: Path,
) -> None:
    """Writes a side-by-side [MATLAB | NumKit | Color Diff Heatmap] PNG."""
    h, w, _ = ml.shape
    # Heatmap: white=agree bg, gray=agree ink, red=MATLAB-only (missing in NK),
    # blue=NK-only (extra/shifted in NK), orange=both ink but color mismatch.
    heat = np.full((h, w, 3), 248, dtype=np.uint8)
    both = m_ml & m_nk
    only_ml = m_ml & (~m_nk)
    only_nk = m_nk & (~m_ml)
    col_err = np.max(np.abs(ml - nk), axis=2) > 45.0

    heat[both & (~col_err)] = [195, 195, 195]
    heat[both & col_err] = [245, 150, 20]
    heat[only_ml] = [230, 40, 40]
    heat[only_nk] = [30, 110, 240]

    # Scale down slightly if huge so contact sheets stay fast to inspect.
    scale = min(1.0, 720.0 / max(1.0, float(w)))
    tw = max(1, int(round(w * scale)))
    th = max(1, int(round(h * scale)))
    pad = 8
    header = 24
    canvas = Image.new("RGB", (tw * 3 + pad * 4, th + header + pad * 2), (235, 235, 238))
    draw = ImageDraw.Draw(canvas)

    panels = [
        ("MATLAB (ref)", Image.fromarray(ml.astype(np.uint8))),
        ("NumKit", Image.fromarray(nk.astype(np.uint8))),
        ("Diff (Red=missing, Blue=extra, Orange=color)", Image.fromarray(heat)),
    ]
    for idx, (label, im) in enumerate(panels):
        if im.size != (tw, th):
            im = im.resize((tw, th), Image.Resampling.BILINEAR)
        x = pad + idx * (tw + pad)
        draw.text((x + 4, 5), label, fill=(25, 25, 30))
        canvas.paste(im, (x, header))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def _vec_close(a: Any, b: Any, rtol: float = 0.05, atol: float = 0.03) -> bool:
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x is None or y is None:
            if x != y:
                return False
            continue
        fx, fy = float(x), float(y)
        if abs(fx - fy) > max(atol, rtol * max(abs(fx), abs(fy))):
            return False
    return True


def _norm_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "|".join(_norm_str(x) for x in v)
    return str(v).strip().lower()


def compare_dom(ml_path: Path, nk_path: Path) -> DomDiffSummary:
    res = DomDiffSummary()
    if not ml_path.exists() or not nk_path.exists():
        res.issues.append("missing DOM json")
        return res

    ml = json.loads(ml_path.read_text(encoding="utf-8"))
    nk = json.loads(nk_path.read_text(encoding="utf-8"))

    ml_axes = ml.get("axes", [])
    nk_axes = nk.get("axes", [])
    if len(ml_axes) != len(nk_axes):
        res.axes_count_mismatch = True
        res.issues.append(f"axes count: ML={len(ml_axes)} NK={len(nk_axes)}")
        return res

    # Match axes by Position (MATLAB and NumKit may order Children newest-first vs oldest-first).
    def sort_key(ax: Dict[str, Any]) -> Tuple[float, float]:
        p = ax.get("position") or [0, 0, 0, 0]
        return (round(float(p[1]) if len(p) > 1 else 0.0, 2),
                round(float(p[0]) if len(p) > 0 else 0.0, 2))

    ml_sorted = sorted(ml_axes, key=sort_key)
    nk_sorted = sorted(nk_axes, key=sort_key)

    for idx, (ma, na) in enumerate(zip(ml_sorted, nk_sorted)):
        tag = f"ax[{idx}]"
        if bool(ma.get("isPolar")) != bool(na.get("isPolar")):
            res.issues.append(f"{tag}.isPolar: ML={ma.get('isPolar')} NK={na.get('isPolar')}")

        if not _vec_close(ma.get("position"), na.get("position"), rtol=0.05, atol=0.04):
            res.position_mismatch = True
            res.issues.append(f"{tag}.Position: ML={ma.get('position')} NK={na.get('position')}")

        for prop in ("visible", "box", "xGrid", "yGrid", "xScale", "yScale", "xDir", "yDir"):
            if _norm_str(ma.get(prop)) != _norm_str(na.get(prop)):
                res.issues.append(f"{tag}.{prop}: ML={ma.get(prop)!r} NK={na.get(prop)!r}")

        if not ma.get("isPolar"):
            for lim in ("xLim", "yLim"):
                if not _vec_close(ma.get(lim), na.get(lim), rtol=0.05, atol=0.05):
                    res.limits_mismatch = True
                    res.issues.append(f"{tag}.{lim}: ML={ma.get(lim)} NK={na.get(lim)}")
            for tk in ("xTick", "yTick"):
                mt, nt = ma.get(tk) or [], na.get(tk) or []
                if abs(len(mt) - len(nt)) > 2 or (len(mt) == len(nt) and not _vec_close(mt, nt, rtol=0.02, atol=0.02)):
                    res.ticks_mismatch = True
                    res.issues.append(f"{tag}.{tk}: ML={mt} NK={nt}")

        if bool(ma.get("hasLegend")) != bool(na.get("hasLegend")):
            res.legend_mismatch = True
            res.issues.append(f"{tag}.hasLegend: ML={ma.get('hasLegend')} NK={na.get('hasLegend')}")
        elif ma.get("hasLegend"):
            if _norm_str(ma.get("legendLocation")) != _norm_str(na.get("legendLocation")):
                res.legend_mismatch = True
                res.issues.append(f"{tag}.legendLocation: ML={ma.get('legendLocation')!r} NK={na.get('legendLocation')!r}")
            if _norm_str(ma.get("legendString")) != _norm_str(na.get("legendString")):
                res.legend_mismatch = True
                res.issues.append(f"{tag}.legendString: ML={ma.get('legendString')!r} NK={na.get('legendString')!r}")

        mc = ma.get("children") or []
        nc = na.get("children") or []
        if len(mc) != len(nc):
            res.children_mismatch = True
            res.issues.append(f"{tag}.numChildren: ML={len(mc)} NK={len(nc)}")
        else:
            m_types = sorted(_norm_str(c.get("type")) for c in mc)
            n_types = sorted(_norm_str(c.get("type")) for c in nc)
            if m_types != n_types:
                res.children_mismatch = True
                res.issues.append(f"{tag}.childTypes: ML={m_types} NK={n_types}")

    return res
