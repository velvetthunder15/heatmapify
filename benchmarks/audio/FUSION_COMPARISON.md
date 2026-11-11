# Full heatmap audio comparison

Review date: 2026-11-07. Source revision: `8d1a7d9addc973a1e1f3f09c1d760889d97e344a`.

## Finding

There are **zero eligible paired videos** in the available checkout. The trained head's effect on the complete heatmap cannot be measured from these files. Neither a ranking gain nor a peak-recall gain has been established for the complete heatmap.

Keep the current default provisionally pending this comparison, but describe it as unvalidated for full-heatmap improvement. The audio-only ranking result is a reason to test it, not proof that it improves the product. There is also no paired evidence here that rolling back would improve the product. No production code, model, settings, or weights were changed.

## Measurements reproduced from existing exports

These are historical estimates, NOT trained-versus-zero-shot comparisons:

| Video | Export | Spearman | Top-five peak recall |
| --- | --- | ---: | ---: |
| IKPJq5Z_1ZM | v1.3, digitised | 0.405119 | 3/5 (60%) |
| RKQGRPoDV_I | v1.4, raw JSON | 0.219066 | 2/5 (40%) |

The evaluator resamples estimated scores onto official bins by overlap-weighted means. It selects up to five highest bins with centers more than 30 seconds apart, and counts matches within 15 seconds, following `benchmarks/tools/compare_fig.py`. Ties use chronological order for reproducibility. These two rows cannot measure differences between audio models or establish general performance across videos.

The shipped audio head records audio-only means of 0.161 versus 0.037 Spearman (difference +0.124), and 0.26 versus 0.26 top-five recall. Those stored figures were inspected, not independently rerun. The audio trainer's top-five metric allows adjacent high bins and uses one-window slack; it is NOT the separated-peak metric above.

## Specific missing inputs

- `calibration/audio/RKQGRPoDV_I-10.npz`: raw named audio features for the same 200 ten-second windows as the existing export (the final window includes the short tail). Its other three signal curves and official curve are already present.
- `calibration/audio/IKPJq5Z_1ZM-10.npz`, plus a real per-window four-signal export for this video. Its digitised export has no signal breakdown, so a fused score cannot be decomposed into audio and the other three signals. Prefer a fresh matched pair rather than mixing newly collected signals with digitised data.
- All 20 original training audio caches named in the bundled head's `trained_on` list. `fusion-audit.json` lists each missing ID. There are no NPZ caches anywhere under the inspected `/workspace` tree.
- To measure nested full-heatmap performance on those 20 videos: matched `calibration/<VIDEO_ID>-10.json` records containing the official segments and per-window comments, transcript, audio, and visual scores. None are tracked in the repository. The ID lists alone are not features or replay labels.

NumPy, SciPy, Pydantic and pydantic-settings are available, so offline evaluation can run once caches are supplied. Fresh collection also needs the application's media dependencies: yt-dlp, librosa, soundfile, ONNX Runtime, the YAMNet model and ffmpeg. The first four Python packages are absent here. No new YouTube collection was attempted. The repository notes that collection may need the local host because YouTube can block cloud hosts. Existing user caches outside this workspace were not available to inspect.

## Regularization and separation

The shipped head uses alpha 3000, the upper bound of the old grid. The current grid adds 10000, 30000 and 100000. That boundary result warrants another validation run; it does not show that any larger alpha wins.

The existing trainer computes leave-one-video-out scores for every candidate, picks the best candidate using those scores, then reports that same candidate's scores. Individual regressions exclude each test video's rows, but model selection still uses all test-video outcomes. Its selected-model estimate can therefore be optimistic.

The new evaluator has two distinct modes:

1. `bundled`: evaluate the exact frozen bundled coefficients only on videos absent from `trained_on`. Both existing benchmark IDs are outside that list. No fitting occurs.
2. `nested`: hold out each evaluation video entirely. Inside the remaining audio-cache videos, select alpha using inner leave-one-video-out validation, then refit on those remaining videos and score the outer held-out video. Run the old and expanded grids against the same zero-shot baseline. Default: the same 21 event/basic features as the bundled head. `--embeddings` also searches event-plus-embedding candidates inside the inner folds and requires valid E arrays in every cache. This tests a training procedure, not the exact shipped coefficient file.

Inner selection preserves the trainer's existing audio objective, `0.6 * top_hits + 0.4 * Spearman`; it does not tune fusion weights or select settings using outer results. Testing event-only first isolates the grid change. The additional embedding run is a separate sensitivity analysis, not an extra opportunity to pick the best reported outer score.

Nested validation corrects the explicit within-run selection issue. Reusing a dataset that already informed model development still does not turn it into a new independent test set. Reserve additional videos that were not used in earlier development for the final default decision, with varied genres and engagement levels. Do not choose settings after examining those final outcomes.

## What remains fixed

Both arms use exactly the same normalized comments, transcript and visual arrays. Weights are fixed to repository defaults: comments 0.35, transcript 0.25, audio 0.25, visual 0.15. The script ignores local environment overrides deliberately. It uses production `normalize`, `combine_signals`, `calibrate_shape` (median target 0.12) and `select_ranges` (tolerance 0.05). Audio changes from the production zero-shot function to either frozen-head predictions or outer-held-out predictions.

The script requires all four signals in every window; it never compensates for missing signals by changing weights. It rejects mismatched window grids and mismatched cached official labels. Both arms receive identical normalization and shape processing before official-grid resampling. Shape calibration is monotonic on native windows, but can affect ranking after resampling and range merging, so it is retained.

Outputs include per-video Spearman and peak recall, paired differences, equal-video mean and median differences, win/loss/tie counts, selected alpha/feature mode, and old-versus-expanded differences. Native production peak ranges are included separately for inspection. The scored peak metric is the benchmark definition, not a score for merged UI range boundaries. Undefined constant-curve correlations are null and excluded from paired correlation means; the valid-video count is reported.

Paired 95% bootstrap intervals resample whole videos, not correlated time bins. For nested runs, models share training videos, so these intervals describe variation in the observed outer predictions and do not include all model-training uncertainty. With only two external videos, even a completed run would be weak evidence. Rounded historical signal exports and the digitised Video 1 curve add measurement error. Input hashes, source revision, Python/NumPy/SciPy versions and random seed are recorded.

## Offline reproduction

From the repository root, in an environment with NumPy, SciPy, Pydantic and pydantic-settings:

```bash
python -m unittest tests.test_audio_fusion_offline -v
python -m scripts.compare_audio_fusion --output calibration/fusion-bundled.json
python -m scripts.compare_audio_fusion --mode nested --output calibration/fusion-nested.json
# Optional, separate feature-family sensitivity analysis:
python -m scripts.compare_audio_fusion --mode nested --embeddings --output calibration/fusion-nested-embeddings.json
```

The script never downloads data or writes a model. An empty comparison exits with status 2 after saving an audit, rather than reporting a gain. Seven tests passed, including historical-score reproduction, timeline coverage, unchanged non-audio fusion, disjoint inner folds, outer-label independence, training-video exclusion, and both evaluation modes on synthetic data. Synthetic test metrics are not accuracy evidence.

Use `--cache`, `--audio-cache` and `--benchmarks` to point at existing local exports. Calibration JSON follows `scripts.calibrate.collect`'s schema. NPZ follows `scripts.train_audio.collect`: `windows`, `X`, `names`, `official`, and optionally `E` for embeddings. The default expects the shipped head's ten-second window size. Duplicate audio cache IDs invalidate nested validation; do not mix multiple versions/window sizes in one input directory. Calibration records take precedence over benchmark exports for the same video.

If collecting missing inputs on your local host, use the collection functions only, not the training CLI (which writes and may activate a model):

```python
from scripts.calibrate import collect as collect_heatmap
from scripts.train_audio import collect as collect_audio

# Repeat for the desired video IDs; these calls can download media and run inference.
vid = 'RKQGRPoDV_I'
collect_heatmap(vid, 10)  # caches official segments and the four signal arrays
collect_audio(vid, 10)    # reuses cached official data and writes the NPZ features
```

Existing caches are reused by these functions. Keep an old cache snapshot before recollection, and ensure paired files refer to the same timeline/official data. To test the original training sample, read its exact IDs from `app/sources/default_audio_head.json` rather than assuming every ID in batch1 belongs to the 20-video subset.

## Proposed changes for review

- `scripts/compare_audio_fusion.py`: offline paired comparison and input audit.
- `tests/test_audio_fusion_offline.py`: seven checks of metrics, pairing and data separation.
- `benchmarks/audio/fusion-audit.json`: real available-data audit and reproduced historical metrics, zero paired results.
- `benchmarks/audio/FUSION_COMPARISON.md`: this report and reproduction instructions.

These are uncommitted additions. No commit, push or deployment has been made. The next useful input is the cached feature and calibration files from the training host; the next repository action requires user approval.
