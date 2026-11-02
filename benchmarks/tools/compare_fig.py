"""Paper-style comparison of official vs estimated Heatmapify results.
Usage: python compare_fig.py official.json estimated.json out.png
"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

off_p, est_p, out = sys.argv[1:4]
off, est = json.load(open(off_p)), json.load(open(est_p))
dur = float(off.get("duration") or est.get("duration"))

def series(d):
    h = d["full_heatmap"]
    return np.array([[s["start"], s["end"], s["score"]] for s in h], float), h

O, Oh = series(off)
E, Eh = series(est)

# Evaluate the estimate on the official bin grid (mean of overlapping estimate windows, overlap-weighted).
def resample(src, grid):
    out = []
    for g0, g1, _ in grid:
        w = np.clip(np.minimum(src[:, 1], g1) - np.maximum(src[:, 0], g0), 0, None)
        out.append((w * src[:, 2]).sum() / w.sum() if w.sum() > 0 else np.nan)
    return np.array(out)

y_off = O[:, 2]
y_est = resample(E, O)
m = ~np.isnan(y_est)
y_off, y_est, grid = y_off[m], y_est[m], O[m]

r_p, p_p = stats.pearsonr(y_off, y_est)
r_s, p_s = stats.spearmanr(y_off, y_est)
tau, p_t = stats.kendalltau(y_off, y_est)
mae = np.mean(np.abs(y_off - y_est))
rmse = np.sqrt(np.mean((y_off - y_est) ** 2))

# Peak agreement: top-k official bins vs top-k estimate bins (same grid), hit if within +/- tol seconds.
K, TOL = 5, 15.0
mid = (grid[:, 0] + grid[:, 1]) / 2
def peaks(y, k):
    idx = []
    for i in np.argsort(-y):
        if all(abs(mid[i] - mid[j]) > 30 for j in idx):
            idx.append(i)
        if len(idx) == k:
            break
    return idx
po, pe = peaks(y_off, K), peaks(y_est, K)
hits = sum(any(abs(mid[i] - mid[j]) <= TOL for j in pe) for i in po)

# Per-signal Spearman against official.
sig_names = ["comments", "transcript", "audio", "visual"]
sig_r = {}
for s in sig_names:
    vals = [h.get("signals", {}).get(s) for h in Eh]
    if all(v is None for v in vals):
        continue
    S = np.column_stack([E[:, 0], E[:, 1], [v if v is not None else np.nan for v in vals]])
    S = S[~np.isnan(S[:, 2])]
    ys = resample(S, grid)
    k = ~np.isnan(ys)
    if k.sum() > 5 and np.std(ys[k]) > 0:
        sig_r[s] = stats.spearmanr(y_off[k], ys[k])[0]

def fmt_p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"

def mmss(x, _=None):
    x = int(round(x)); return f"{x // 60}:{x % 60:02d}"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 9,
    "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.direction": "out", "ytick.direction": "out", "figure.dpi": 100,
})
fig = plt.figure(figsize=(7.2, 8.6))
gs = fig.add_gridspec(3, 2, height_ratios=[1.15, 1, 1.0], hspace=0.62, wspace=0.32)

# (a) time series
ax = fig.add_subplot(gs[0, :])
ax.step(np.r_[O[:, 0], O[-1, 1]], np.r_[O[:, 2], O[-1, 2]], where="post", color="black", lw=1.1, label=f"Official (YouTube “Most replayed”, n = {len(O)} bins)")
ax.step(np.r_[E[:, 0], E[-1, 1]], np.r_[E[:, 2], E[-1, 2]], where="post", color="0.45", lw=1.0, ls="--", label=f"Estimated (multi-signal, n = {len(E)} × {int(est.get('window_seconds', 10))} s windows)")
for i in po:
    ax.plot(mid[i], y_off[i], marker="v", ms=5, color="black", ls="none")
for i in pe:
    ax.plot(mid[i], resample(E, grid[i:i+1])[0] + 0.0, marker="^", ms=5, mfc="white", mec="0.35", ls="none")
ax.set_xlim(0, dur); ax.set_ylim(0, 1.05)
ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(300 if dur <= 1800 else 600))
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(mmss))
ax.set_xlabel("Time (min:s)"); ax.set_ylabel("Normalised engagement score")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=1, fontsize=8)
ax.text(-0.07, 1.12, "(a)", transform=ax.transAxes, fontweight="bold")
ax.text(1.0, -0.3, "▼ official top-5 peaks   △ estimated top-5 peaks", transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color="0.25")

# (b) scatter
ax = fig.add_subplot(gs[1, 0])
ax.scatter(y_off, y_est, s=10, facecolors="none", edgecolors="black", linewidths=0.6)
sl, ic = np.polyfit(y_off, y_est, 1)
xs = np.linspace(0, 1, 50)
ax.plot(xs, sl * xs + ic, color="black", lw=0.9)
ax.plot([0, 1], [0, 1], color="0.6", lw=0.7, ls=":")
ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02); ax.set_aspect("equal")
ax.set_xlabel("Official score"); ax.set_ylabel("Estimated score (resampled)")
ax.text(0.97, 0.97, f"Pearson r = {r_p:.2f} ({fmt_p(p_p)})\nSpearman ρ = {r_s:.2f} ({fmt_p(p_s)})", transform=ax.transAxes, va="top", ha="right", fontsize=6.5, bbox=dict(fc="white", ec="0.6", lw=0.5, pad=2))
ax.text(-0.3, 1.04, "(b)", transform=ax.transAxes, fontweight="bold")

# (c) per-signal correlation, or score distributions when per-signal data is absent
ax = fig.add_subplot(gs[1, 1])
if sig_r:
    names = list(sig_r)
    vals = [sig_r[n] for n in names]
    w = est.get("weights") or {}
    short = {"comments": "Comm.", "transcript": "Capt.", "audio": "Audio", "visual": "Visual"}
    labels = [f"{short.get(n, n)}\nw={w[n]:.2f}" if n in w else short.get(n, n) for n in names] + ["Comb."]
    vals = vals + [r_s]
    bars = ax.bar(range(len(vals)), vals, color=["0.75"] * len(names) + ["0.2"], edgecolor="black", linewidth=0.6, width=0.65)
    ax.axhline(0, color="black", lw=0.7)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.02 if v >= 0 else -0.06), f"{v:.2f}", ha="center", fontsize=7.5)
    ax.set_xticks(range(len(vals))); ax.set_xticklabels(labels, fontsize=7.2)
    ax.set_ylim(min(0, min(vals)) - 0.1, 1)
    ax.set_ylabel("Spearman ρ vs official")
else:
    for y, ls, c, lab in [(y_off, "-", "black", "Official"), (y_est, "--", "0.45", "Estimated")]:
        xs_ = np.sort(y); ax.step(np.r_[0, xs_], np.r_[0, np.arange(1, len(xs_) + 1) / len(xs_)], where="post", ls=ls, color=c, lw=1.0, label=lab)
        ax.axvline(np.median(y), color=c, lw=0.6, ls=":")
    ax.axvline(0.6, color="0.7", lw=0.6)
    ax.text(0.59, 0.55, "hot ≥ 0.6", fontsize=7, color="0.4", rotation=90, ha="right")
    ks = stats.ks_2samp(y_off, y_est)
    ax.text(0.97, 0.12, f"KS D = {ks.statistic:.2f}\n({fmt_p(ks.pvalue)})", transform=ax.transAxes, ha="right", fontsize=7.5)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    ax.set_xlabel("Score"); ax.set_ylabel("Cumulative fraction of bins")
    ax.legend(frameon=False, fontsize=7.5, loc="center right")
ax.text(-0.36, 1.04, "(c)", transform=ax.transAxes, fontweight="bold")

# Plain-language checks: hot-segment precision vs chance, #1 peak, shuffled-timing control.
n_hot = max(1, int(round(0.2 * len(y_off))))
hot_o = set(np.argsort(-y_off)[:n_hot]); hot_e = set(np.argsort(-y_est)[:n_hot])
hot_prec = len(hot_o & hot_e) / n_hot
e_mid = (E[:, 0] + E[:, 1]) / 2
e_top = []
for i in np.argsort(-E[:, 2]):  # estimate's own top-K windows at native resolution
    if all(abs(e_mid[i] - e_mid[j]) > 30 for j in e_top):
        e_top.append(i)
    if len(e_top) == K:
        break
top1_rank = next((r + 1 for r, j in enumerate(e_top) if abs(mid[po[0]] - e_mid[j]) <= TOL), None)
rng = np.random.default_rng(0)
shuf = np.array([np.mean(np.abs(y_off - rng.permutation(y_est))) for _ in range(10000)])
beat = np.mean(shuf > mae)
flat = np.mean(np.abs(y_off - np.median(y_off)))

# (d) table
ax = fig.add_subplot(gs[2, :]); ax.axis("off")
rows = [
    ["Hot bins, score ≥ 0.6 (official / estimated)", f"{(y_off>=0.6).mean()*100:.0f}% / {(y_est>=0.6).mean()*100:.0f}%"],
    ["Mean score (official / estimated)", f"{y_off.mean():.3f} / {y_est.mean():.3f}"],
    ["Median score (official / estimated)", f"{np.median(y_off):.3f} / {np.median(y_est):.3f}"],
    ["Pearson r  ·  Spearman ρ  ·  Kendall τ", f"{r_p:.3f}  ·  {r_s:.3f}  ·  {tau:.3f}"],
    ["MAE  ·  RMSE", f"{mae:.3f}  ·  {rmse:.3f}"],
    ["Curve match, 1 − MAE (estimate / flat-median baseline)", f"{(1 - mae) * 100:.1f}% / {(1 - np.mean(np.abs(y_off - np.median(y_off)))) * 100:.1f}%"],
    [f"Top-{K} peak recall (± {int(TOL)} s)", f"{hits}/{K} ({100 * hits / K:.0f}%)"],
    [f"Official #1 peak in estimate's native top-{K} (± {int(TOL)} s)", f"yes, estimate's #{top1_rank}" if top1_rank else "no"],
    ["Hot-segment precision, top 20% (estimate / chance)", f"{hot_prec*100:.0f}% / 20%  ({hot_prec/0.2:.2f}×)"],
    ["Shuffled-timing control: estimate beats", f"{beat*100:.2f}% of 10,000 shuffles"],
]
t = ax.table(cellText=rows, colLabels=["Metric", "Value"], loc="center", cellLoc="left", colWidths=[0.62, 0.38], edges="horizontal")
t.auto_set_font_size(False); t.set_fontsize(8); t.scale(1, 1.25)
for (r, c), cell in t.get_celld().items():
    cell.set_linewidth(0.6)
    if r == 0: cell.set_text_props(fontweight="bold")
ax.text(-0.07, 1.0, "(d)", transform=ax.transAxes, fontweight="bold")

import os
label = os.environ.get("FIG_LABEL") or f"“{off.get('title') or est.get('title')}” ({off.get('video_id')})"
fig.suptitle(f"Official vs. estimated engagement: {label}, {mmss(dur)}", fontsize=10, fontweight="bold", y=0.985)
fig.text(0.5, 0.005, "Estimated scores were averaged onto the official bin grid (overlap-weighted) before all comparisons. Official scores reflect replay behaviour; estimates reflect observable signals." + os.environ.get("FIG_NOTE", ""),
         ha="center", fontsize=6.8, color="0.3", wrap=True)
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
print(json.dumps(dict(hot_prec=hot_prec, top1_rank=top1_rank, beat_shuffles=beat, flat_curve_match=1-flat, curve_match=1-mae, pearson=r_p, spearman=r_s, kendall=tau, mae=mae, rmse=rmse, hits=hits, mean_off=y_off.mean(), mean_est=y_est.mean(), sig=sig_r), default=float))
