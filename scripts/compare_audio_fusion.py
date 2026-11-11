"""Offline paired audio ablation. Never downloads, saves models, or changes settings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import scipy

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.scoring import calibrate_shape, combine_signals, normalize, select_ranges
from app.sources.audio import zero_shot_curve
from scripts.train_audio import ALPHAS, design, ridge, target
from scripts.calibrate import resample, spearman, top_hits

WEIGHTS = dict(comments=.35, transcript=.25, audio=.25, visual=.15)


def grid(rows):
    w = np.array([[s['start'], s['end']] for s in rows], dtype=float)
    if (w.ndim != 2 or w.shape[1] != 2 or not np.isfinite(w).all()
            or np.any(w[:, 1] <= w[:, 0]) or np.any(w[1:, 0] < w[:-1, 1])):
        raise ValueError('invalid or overlapping time windows')
    return w


def aligned(values, src, dst):
    overlap = np.maximum(0, np.minimum(dst[:, None, 1], src[None, :, 1])
                         - np.maximum(dst[:, None, 0], src[None, :, 0]))
    if not np.allclose(overlap.sum(axis=1), dst[:, 1] - dst[:, 0], atol=1e-6):
        raise ValueError('incomplete timeline coverage')
    return overlap @ values / overlap.sum(axis=1)


def peaks(values, windows):
    mid = windows.mean(axis=1)
    out = []
    for i in np.argsort(-np.asarray(values), kind='stable'):
        if all(abs(mid[i] - mid[j]) > 30 for j in out):
            out.append(int(i))
        if len(out) == 5:
            break
    return out


def metrics(values, windows, official):
    ow = grid(official)
    truth = np.array([s['score'] for s in official], dtype=float)
    estimate = aligned(np.asarray(values), windows, ow)
    if not np.isfinite(truth).all() or not np.isfinite(estimate).all():
        raise ValueError('nonfinite scores')
    rho = None if np.ptp(truth) == 0 or np.ptp(estimate) == 0 else float(spearmanr(truth, estimate).statistic)
    op, ep = peaks(truth, ow), peaks(estimate, ow)
    mid = ow.mean(axis=1)
    hits = sum(any(abs(mid[i] - mid[j]) <= 15 for j in ep) for i in op)
    return dict(spearman=rho, peak_recall=hits / len(op), peak_hits=hits,
                official_peak_count=len(op))


def fused(record, audio, weights, median):
    rows = record['estimate']
    sig = {name: [s['signals'][name] for s in rows] for name in WEIGHTS if name != 'audio'}
    sig['audio'] = normalize(audio)
    segs = combine_signals([tuple(w) for w in grid(rows)], sig, weights)
    vals = calibrate_shape([s.score for s in segs], median)
    for s, value in zip(segs, vals):
        s.score = value
    ranges, _ = select_ranges(segs, 5, 0, .05)
    return vals, [dict(start=r.start, end=r.end, score=r.score) for r in ranges]


def zero(d):
    cols = {n: d['X'][:, i].tolist() for i, n in enumerate(d['names'])}
    return zero_shot_curve([dict(reaction=v) for v in cols['reaction']], cols)


def fit_predict(train, test, alpha, embeddings):
    if test['video_id'] in {d['video_id'] for d in train}:
        raise ValueError('training/test video overlap')
    coef = ridge(np.vstack([design(d, embeddings) for d in train]),
                 np.concatenate([target(d) for d in train]), alpha)
    return design(test, embeddings) @ coef


def select(train, alphas, embeddings):
    # Inner LOVO uses only outer training videos, matching the existing audio objective.
    best = None
    for emb in ([False, True] if embeddings else [False]):
        for alpha in alphas:
            scores = []
            for i, val in enumerate(train):
                pred = fit_predict(train[:i] + train[i+1:], val, alpha, emb).tolist()
                truth = val['official'].tolist()
                scores.append(.6 * top_hits(pred, truth) + .4 * spearman(pred, truth))
            score = float(np.mean(scores))
            if best is None or score > best[0]:
                best = (score, alpha, emb)
    return best[1:]


def summarize(rows, seed):
    out = {}
    for metric in ('spearman', 'peak_recall'):
        valid = [r for r in rows if r['zero'][metric] is not None and r['trained'][metric] is not None]
        if not valid:
            out[metric] = dict(n=0)
            continue
        a = np.array([r['zero'][metric] for r in valid])
        b = np.array([r['trained'][metric] for r in valid])
        delta = b-a
        ci = None
        if len(delta) >= 2:
            rng = np.random.default_rng(seed)
            boot = delta[rng.integers(0, len(delta), (10000, len(delta)))].mean(axis=1)
            ci = np.quantile(boot, [.025, .975]).tolist()
        out[metric] = dict(n=len(valid), zero_mean=float(a.mean()), trained_mean=float(b.mean()),
                           mean_delta=float(delta.mean()), median_delta=float(np.median(delta)),
                           wins=int((delta > 1e-12).sum()), losses=int((delta < -1e-12).sum()),
                           ties=int((abs(delta) <= 1e-12).sum()), paired_video_bootstrap_95=ci)
    return out


def load_records(cache, benchmarks):
    records = {}
    for p in sorted(benchmarks.glob('videos/*/*/estimated.json')):
        e = json.loads(p.read_text())
        o = json.loads(p.with_name('official.json').read_text())
        if e['video_id'] != o['video_id']:
            raise ValueError(f'video mismatch: {p}')
        vid = e['video_id']
        if vid in records:
            raise ValueError(f'multiple benchmark versions for {vid}; select one input directory')
        records[vid] = dict(video_id=vid, estimate=e['full_heatmap'], official=o['full_heatmap'],
                            path=str(p), historical_weights=e.get('weights'))
    for p in sorted(cache.glob('*.json')):
        d = json.loads(p.read_text())
        if 'estimate' in d and 'official' in d:
            vid = d['video_id']
            if vid in records and 'cache_path' in records[vid]:
                raise ValueError(f'multiple cache records for {vid}')
            records[vid] = d | dict(path=str(p), cache_path=str(p))
    return records


def run(args):
    head = json.loads(args.head.read_text())
    records = load_records(args.cache, args.benchmarks)
    features, rejected = {}, []
    for p in sorted(args.audio_cache.glob('*.npz')):
        try:
            vid, window_size = p.stem.rsplit('-', 1)
            if int(window_size) != head['window_seconds']:
                raise ValueError('cache window size differs from head')
            with np.load(p, allow_pickle=False) as z:
                d = {k: z[k] for k in z.files}
            if vid in features:
                raise ValueError('duplicate video cache')
            if list(d['names']) != head['features']:
                raise ValueError('feature names/order differ from bundled head')
            n = len(d['windows'])
            grid([dict(start=a, end=b) for a, b in d['windows']])
            if d['X'].shape != (n, len(head['features'])) or d['official'].shape != (n,) or n < 6:
                raise ValueError('invalid cache shape or fewer than six windows')
            for key in ('X', 'official', 'windows'):
                if not np.isfinite(d[key]).all():
                    raise ValueError(f'nonfinite {key}')
            if args.embeddings or head['use_embeddings']:
                if d['E'].ndim != 2 or d['E'].shape[0] != n or not np.isfinite(d['E']).all():
                    raise ValueError('invalid embeddings')
            features[vid] = d | dict(video_id=vid, path=str(p))
        except (ValueError, KeyError) as exc:
            rejected.append(dict(path=str(p), reason=str(exc)))
    audit, eligible, historical = [], [], []
    for vid, r in records.items():
        reasons = []
        if all('score' in s for s in r['estimate']):
            historical.append(dict(video_id=vid, metrics=metrics(
                [s['score'] for s in r['estimate']], grid(r['estimate']), r['official'])))
        if not all(all(k in s.get('signals', {}) for k in WEIGHTS) for s in r['estimate']):
            reasons.append('missing per-window four-signal scores')
        else:
            vals = np.array([[s['signals'][k] for k in WEIGHTS] for s in r['estimate']])
            if not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any():
                reasons.append('invalid normalized signal scores')
        if vid not in features:
            reasons.append(f'missing audio cache: {args.audio_cache}/{vid}-10.npz (or matching window size)')
        else:
            d = features[vid]
            w = grid(r['estimate'])
            if d['windows'].shape != w.shape or not np.allclose(d['windows'], w, atol=1e-6):
                reasons.append('audio and estimate windows differ; regenerate matched inputs')
            elif not np.allclose(d['official'], resample(r['official'], w), atol=1e-6):
                reasons.append('audio training labels and official export differ')
        if args.mode == 'bundled' and vid in head['trained_on']:
            reasons.append('bundled head trained on this video')
        audit.append(dict(video_id=vid, reasons=reasons))
        if not reasons:
            eligible.append(vid)
    result = dict(mode=args.mode, weights=WEIGHTS, median_target=args.median,
                  merge_tolerance=.05, seed=args.seed, audit=audit, rejected_caches=rejected,
                  audio_cache_count=len(features), eligible_count=len(eligible),
                  missing_original_training_caches=sorted(set(head['trained_on']) - set(features)),
                  historical_exports_only=historical, comparisons={})
    if args.mode == 'nested' and (len(features) < 5 or rejected):
        result['blocked'] = 'Nested validation needs at least five unique valid audio caches and no rejected caches.'
    else:
        variants = ['bundled'] if args.mode == 'bundled' else ['old_grid', 'expanded_grid']
        for variant in variants:
            rows = []
            for vid in eligible:
                d, r = features[vid], records[vid]
                if args.mode == 'bundled':
                    alpha, emb = head['alpha'], head['use_embeddings']
                    pred = design(d, emb) @ np.array(head['coef']) + head.get('intercept', 0)
                else:
                    train = [v for k, v in features.items() if k != vid]
                    alphas = [a for a in ALPHAS if a <= 3000] if variant == 'old_grid' else ALPHAS
                    alpha, emb = select(train, alphas, args.embeddings)
                    pred = fit_predict(train, d, alpha, emb)
                z, zp = fused(r, zero(d), WEIGHTS, args.median)
                h, hp = fused(r, pred, WEIGHTS, args.median)
                zm, hm = metrics(z, d['windows'], r['official']), metrics(h, d['windows'], r['official'])
                rows.append(dict(video_id=vid, alpha=alpha, embeddings=emb, zero=zm, trained=hm,
                                 delta={k: None if zm[k] is None or hm[k] is None else hm[k]-zm[k]
                                        for k in ('spearman', 'peak_recall')},
                                 production_peak_ranges=dict(zero=zp, trained=hp)))
            result['comparisons'][variant] = dict(videos=rows, summary=summarize(rows, args.seed))
    if args.mode == 'nested' and result['comparisons']:
        old = result['comparisons']['old_grid']['videos']
        new = result['comparisons']['expanded_grid']['videos']
        result['expanded_minus_old'] = summarize([dict(zero=a['trained'], trained=b['trained'])
                                                  for a, b in zip(old, new)], args.seed)
    # Hash every actual input for a reproducible record, including training-only caches.
    paths = {args.head, Path(__file__), ROOT / 'app/scoring.py',
             ROOT / 'app/sources/audio.py', ROOT / 'app/sources/audio_events.py',
             ROOT / 'scripts/train_audio.py', ROOT / 'scripts/calibrate.py'} | {Path(d['path']) for d in features.values()}
    paths |= {Path(r['path']) for r in records.values()}
    paths |= {p.with_name('official.json') for p in paths if p.name == 'estimated.json'}
    result['input_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    result['versions'] = dict(numpy=np.__version__, scipy=scipy.__version__, python=sys.version)
    result['git_revision'] = subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: result[k] for k in ('mode', 'audio_cache_count', 'eligible_count', 'comparisons')}, indent=2))
    return 0 if any(c['videos'] for c in result['comparisons'].values()) else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache', type=Path, default=ROOT / 'calibration')
    ap.add_argument('--audio-cache', type=Path, default=ROOT / 'calibration/audio')
    ap.add_argument('--benchmarks', type=Path, default=ROOT / 'benchmarks')
    ap.add_argument('--head', type=Path, default=ROOT / 'app/sources/default_audio_head.json')
    ap.add_argument('--mode', choices=['bundled', 'nested'], default='bundled')
    ap.add_argument('--embeddings', action='store_true', help='Nested search: test both event-only and embedding models')
    ap.add_argument('--median', type=float, default=.12)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--output', type=Path, default=ROOT / 'calibration/audio-fusion-comparison.json')
    args = ap.parse_args()
    if not 0 <= args.median < 1:
        ap.error('--median must be in [0, 1)')
    raise SystemExit(run(args))


if __name__ == '__main__':
    main()
