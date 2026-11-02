"""Accuracy vs engagement: how the estimate's accuracy changes with a video's comment count.

Reads every benchmarks/videos/video-N/<version>/ folder that holds official.json and estimated.json,
with the video's facts in benchmarks/videos/video-N/meta.json ({"comments": 6598, "views": 2900000, "genre": "gaming"}) and plots two accuracy scores
against comment count (log scale):

  Peak accuracy %     share of the official top-5 peaks the estimate finds within +/-15 s
  Ranking accuracy %  share of segment pairs the estimate orders the same way as YouTube
                      ((Kendall tau + 1) / 2; 50% is chance, 100% is perfect)

Usage:  python benchmarks/tools/band_plot.py [version] [genre] [out.png]
        defaults: v1.4, gaming, benchmarks/accuracy_vs_engagement.png
Also writes a CSV of the numbers next to the PNG.
"""
import csv, glob, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from scipy import stats

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # benchmarks/
version = sys.argv[1] if len(sys.argv) > 1 else "v1.4"
genre = sys.argv[2] if len(sys.argv) > 2 else "gaming"
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "accuracy_vs_engagement.png")
K, TOL = 5, 15.0


def series(d):
    return np.array([[s["start"], s["end"], s["score"]] for s in d["full_heatmap"]], float)


def resample(src, grid):
    res = []
    for g0, g1, _ in grid:
        w = np.clip(np.minimum(src[:, 1], g1) - np.maximum(src[:, 0], g0), 0, None)
        res.append((w * src[:, 2]).sum() / w.sum() if w.sum() > 0 else np.nan)
    return np.array(res)


def peaks(y, mid, k):
    idx = []
    for i in np.argsort(-y):
        if all(abs(mid[i] - mid[j]) > 30 for j in idx):
            idx.append(i)
        if len(idx) == k:
            break
    return idx


def score(folder):
    O = series(json.load(open(os.path.join(folder, "official.json"))))
    E = series(json.load(open(os.path.join(folder, "estimated.json"))))
    y_est = resample(E, O)
    m = ~np.isnan(y_est)
    y_off, y_est, grid = O[m, 2], y_est[m], O[m]
    mid = (grid[:, 0] + grid[:, 1]) / 2
    po, pe = peaks(y_off, mid, K), peaks(y_est, mid, K)
    hits = sum(any(abs(mid[i] - mid[j]) <= TOL for j in pe) for i in po)
    tau = stats.kendalltau(y_off, y_est)[0]
    rho = stats.spearmanr(y_off, y_est)[0]
    return {"peak_acc": 100 * hits / len(po), "rank_acc": 100 * (tau + 1) / 2, "spearman": rho,
            "mae": float(np.mean(np.abs(y_off - y_est)))}


rows = []
for meta_p in sorted(glob.glob(os.path.join(HERE, "videos", "video-*", "meta.json"))):
    folder = os.path.join(os.path.dirname(meta_p), version)
    meta = json.load(open(meta_p))
    if "comments" not in meta:
        continue
    if genre != "all" and meta.get("genre") != genre:
        continue
    if not all(os.path.exists(os.path.join(folder, f)) for f in ("official.json", "estimated.json")):
        continue
    vid = meta.get("video_id") or os.path.basename(os.path.dirname(folder))
    rows.append({"video": vid, "comments": int(meta["comments"]), "views": int(meta.get("views", 0)), **score(folder)})

if len(rows) < 2:
    sys.exit(f"Need at least 2 scored videos for {version}/{genre}; found {len(rows)}.")
rows.sort(key=lambda r: r["comments"])

with open(os.path.splitext(out)[0] + ".csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

x = np.array([r["comments"] for r in rows], float)
pa = np.array([r["peak_acc"] for r in rows])
ra = np.array([r["rank_acc"] for r in rows])
views = np.array([max(r["views"], 1) for r in rows], float)

plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 10})
fig, ax = plt.subplots(figsize=(8, 4.8), dpi=200)
size = 30 + 120 * (np.log10(views) - np.log10(views).min()) / max(np.ptp(np.log10(views)), 1e-9)
ax.axhline(50, color="#999", lw=0.8, ls=":")
ax.text(x.min(), 51, "chance (ranking)", color="#777", fontsize=8)
for y, c, lab in ((ra, "#E8590C", "Ranking accuracy (pairs ordered correctly)"),
                  (pa, "#7048E8", f"Peak accuracy (top-{K} found within ±{TOL:.0f} s)")):
    ax.plot(x, y, color=c, lw=1.2, alpha=0.6)
    ax.scatter(x, y, s=size, color=c, edgecolor="white", lw=0.8, zorder=3, label=lab)
    if len(x) >= 3:  # log-linear trend
        b, a = np.polyfit(np.log10(x), y, 1)
        xx = np.logspace(np.log10(x.min()), np.log10(x.max()), 50)
        ax.plot(xx, a + b * np.log10(xx), color=c, lw=0.8, ls="--")
for r in rows:
    ax.annotate(f"youtu.be/{r['video']}", (r["comments"], r["rank_acc"]), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=6.5, color="#555")
ax.set_xscale("log")
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1000:g}k" if v >= 1000 else f"{v:g}"))
ax.set_ylim(0, 105)
ax.set_xlabel("Comments on the video (log scale; dot size = views)")
ax.set_ylabel("Accuracy vs YouTube's official curve (%)")
rho_e = stats.spearmanr(x, ra)[0] if len(x) >= 3 else float("nan")
ax.set_title(f"Heatmapify {version}: estimate accuracy vs engagement ({genre}, n = {len(rows)})", fontsize=11)
ax.legend(loc="lower right", fontsize=8, frameon=False)
ax.grid(alpha=0.25)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.text(0.01, 0.01, f"Dashed: log-linear fit. Spearman(comments, ranking accuracy) = {rho_e:.2f}. "
         "Bins are autocorrelated, so treat per-video scores as indicative.", fontsize=6.5, color="#666")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(out)
print(f"wrote {out} and CSV with {len(rows)} videos")
