"""Train the audio signal on YouTube's own "Most replayed" data (transfer learning on YAMNet).

For each video that HAS official data, this downloads the audio once, runs YAMNet (laughter,
applause, cheering, crowd, shouting, music, speech, silence...) plus loudness and speech rate,
and lines the features up with the official curve. Then it fits a small ridge regression on top
of the frozen YAMNet features and checks it with leave-one-video-out cross-validation, so the
numbers it prints are for videos the model did NOT see.

The trained head is saved to models/audio_head.json and switched on only if it beats the
built-in zero-shot audio score. Otherwise the zero-shot score stays in use.

    python -m scripts.train_audio --file calibration/videos.txt
    python -m scripts.train_audio VIDEO [VIDEO ...]
    python -m scripts.train_audio --file calibration/videos.txt --no-embeddings

Runs on the computer that hosts the server (cloud IPs get blocked by YouTube). Features are
cached in calibration/audio/, so re-runs only process new videos. 5+ videos needed, 15+ is better.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.calibrate import CACHE, resample, spearman, top_hits, video_id  # noqa: E402

AUDIO_CACHE = CACHE / "audio"
ALPHAS = [0.3, 1, 3, 10, 30, 100, 300, 1000, 3000]
MIN_VIDEOS = 5
MARGIN = 0.02  # the head must beat zero-shot by this much rank correlation to be switched on


def hand_feature_names() -> list[str]:
    from app.sources.audio import BASIC
    from app.sources.audio_events import GROUPS

    return BASIC + [f"{g}_{s}" for g in GROUPS for s in ("max", "mean")] + ["reaction"]


# ------------------------------------------------------------------- data --
def official_for(vid: str, window: int):
    """(official segments, duration, title) from the calibrate cache or a fresh official fetch."""
    f = CACHE / f"{vid}-{window}.json"
    if f.exists():
        rec = json.loads(f.read_text(encoding="utf-8"))
        segs = rec["official"]
        return segs, max(s["end"] for s in segs), rec.get("title")
    from app.pipeline import build_heatmap
    from app.sources.official import fetch_metadata

    info = fetch_metadata(vid)
    off = build_heatmap(vid, window, info=info)
    if off.source != "official":
        return None, None, info.get("title")
    return off.segments, float(info.get("duration") or max(s["end"] for s in off.segments)), info.get("title")


def collect(vid: str, window: int) -> dict | None:
    import numpy as np

    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    f = AUDIO_CACHE / f"{vid}-{window}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=False)
        return {k: z[k] for k in z.files} | {"video_id": vid}

    from app.scoring import make_windows
    from app.sources import audio

    print(f"  {vid}: official data...", flush=True)
    segs, duration, title = official_for(vid, window)
    if not segs:
        print(f"  {vid}: no official 'Most replayed' data, skipped")
        return None
    windows = make_windows(duration, window)
    work = tempfile.mkdtemp(prefix="train-audio-")
    try:
        print(f"  {vid}: downloading audio + running YAMNet...", flush=True)
        path = audio.download_audio(vid, work)
        fo: dict = {}
        audio.analyse_audio(path, windows, events=True, features_out=fo)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if "events" not in fo:
        raise RuntimeError("YAMNet did not run (is onnxruntime installed?)")
    names = hand_feature_names()
    from app.sources.audio_events import feature_matrix

    rec = {
        "windows": np.array(windows, dtype=float),
        "official": np.array(resample(segs, windows), dtype=float),
        "X": feature_matrix(fo["events"], fo["basic"], names),
        "E": np.asarray(fo["embeddings"], dtype=np.float32),
        "names": np.array(names),
        "title": np.array(title or ""),
    }
    np.savez_compressed(f, **rec)
    return rec | {"video_id": vid}


# ------------------------------------------------------------------ model --
def design(d: dict, use_emb: bool):
    import numpy as np

    from app.sources.audio_events import zscore_cols

    X = zscore_cols(d["X"])
    if use_emb:
        X = np.hstack([X, zscore_cols(d["E"])])
    return X


def target(d: dict):
    from app.sources.audio_events import zscore_cols

    return zscore_cols(d["official"].reshape(-1, 1)).ravel()


def ridge(X, y, alpha):
    import numpy as np

    A = X.T @ X + alpha * np.eye(X.shape[1])
    return np.linalg.solve(A, X.T @ y)


def lovo(data, use_emb, alpha):
    """Leave-one-video-out: train on the others, score the held-out video."""
    import numpy as np

    Xs = [design(d, use_emb) for d in data]
    ys = [target(d) for d in data]
    sp, hits = [], []
    for i in range(len(data)):
        X = np.vstack([x for j, x in enumerate(Xs) if j != i])
        y = np.concatenate([v for j, v in enumerate(ys) if j != i])
        w = ridge(X, y, alpha)
        pred = (Xs[i] @ w).tolist()
        off = data[i]["official"].tolist()
        sp.append(spearman(pred, off))
        hits.append(top_hits(pred, off))
    return sum(sp) / len(sp), sum(hits) / len(hits), sp


def baseline(data, kind):
    from app.sources.audio import basic_curve, zero_shot_curve

    names = list(data[0]["names"])
    sp, hits = [], []
    for d in data:
        cols = {n: d["X"][:, k].tolist() for k, n in enumerate(names)}
        rows = [{"reaction": v} for v in cols["reaction"]]
        curve = zero_shot_curve(rows, cols) if kind == "zero" else basic_curve(cols)
        off = d["official"].tolist()
        sp.append(spearman(curve, off))
        hits.append(top_hits(curve, off))
    return sum(sp) / len(sp), sum(hits) / len(hits), sp


# ------------------------------------------------------------------- main --
def main() -> None:
    import numpy as np

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--no-embeddings", action="store_true", help="only use the named event features")
    a = ap.parse_args()

    items = list(a.videos)
    if a.file:
        items += [l for l in Path(a.file).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if not items:
        ap.error("give some videos that have YouTube's 'Most replayed' graph")

    data = []
    for it in items:
        try:
            rec = collect(video_id(it), a.window)
        except Exception as exc:  # noqa: BLE001  one bad video shouldn't stop the run
            print(f"  {it}: failed ({type(exc).__name__}: {str(exc)[:120]})")
            continue
        if rec is not None and len(rec["official"]) >= 6:
            data.append(rec)
    names = hand_feature_names()
    data = [d for d in data if list(d["names"]) == names]  # drop caches from an older feature set
    print(f"\n{len(data)} usable videos.")
    if len(data) < MIN_VIDEOS:
        sys.exit(f"Need at least {MIN_VIDEOS} videos with official data to train. Add more links and re-run.")

    b_sp, b_hit, _ = baseline(data, "basic")
    z_sp, z_hit, z_each = baseline(data, "zero")
    print(f"  loudness only (old audio):  rank match {b_sp:+.2f}, top-5 found {b_hit:.0%}")
    print(f"  YAMNet zero-shot (default): rank match {z_sp:+.2f}, top-5 found {z_hit:.0%}")

    best = None
    for use_emb in ([False] if a.no_embeddings else [False, True]):
        for alpha in ALPHAS:
            sp, hit, each = lovo(data, use_emb, alpha)
            obj = 0.6 * hit + 0.4 * sp
            if best is None or obj > best[0]:
                best = (obj, use_emb, alpha, sp, hit, each)
    _, use_emb, alpha, h_sp, h_hit, h_each = best
    kind = "events + embeddings" if use_emb else "events"
    print(f"  trained head ({kind}, alpha {alpha}): rank match {h_sp:+.2f}, top-5 found {h_hit:.0%}"
          "  (cross-validated: each video scored by a model that never saw it)")
    for d, zs, hs in zip(data, z_each, h_each):
        print(f"    {d['video_id']}  zero-shot {zs:+.2f}  trained {hs:+.2f}")

    X = np.vstack([design(d, use_emb) for d in data])
    y = np.concatenate([target(d) for d in data])
    w = ridge(X, y, alpha)
    active = h_sp >= z_sp + MARGIN and (0.6 * h_hit + 0.4 * h_sp) >= (0.6 * z_hit + 0.4 * z_sp)
    head = {
        "active": bool(active),
        "features": names,
        "use_embeddings": bool(use_emb),
        "alpha": alpha,
        "coef": [round(float(c), 6) for c in w],
        "intercept": 0.0,
        "trained_on": [str(d["video_id"]) for d in data],
        "window_seconds": a.window,
        "cv": {"trained": {"spearman": round(h_sp, 3), "top5": round(h_hit, 3)},
               "zero_shot": {"spearman": round(z_sp, 3), "top5": round(z_hit, 3)},
               "basic": {"spearman": round(b_sp, 3), "top5": round(b_hit, 3)}},
        "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    from app.sources.audio_events import MODEL_DIR, head_path

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    head_path().write_text(json.dumps(head), encoding="utf-8")
    if not use_emb:
        top = sorted(zip(names, w), key=lambda t: -abs(t[1]))[:6]
        print("  strongest cues: " + ", ".join(f"{n} {c:+.2f}" for n, c in top))
    if active:
        print("\nTrained head saved and switched ON. Restart the server to use it.")
    else:
        print("\nThe trained head didn't beat zero-shot on unseen videos, so it's saved but OFF."
              " Add more videos (similar to the ones you analyse) and re-run.")
    if len(data) < 15:
        print("Tip: 15+ videos gives a much more reliable model.")


if __name__ == "__main__":
    main()
