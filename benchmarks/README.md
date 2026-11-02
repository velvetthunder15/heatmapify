# Benchmarks: official vs estimated

These compare Heatmapify's estimate with YouTube's official "Most replayed" curve, one video per folder.

```
benchmarks/
  README.md                  this page: method and results for every video
  videos/
    video-1/
      README.md              the video's link and its results by version
      meta.json              video id, link, and (optional) genre, comments, views
      v1.3-digitised/
        official.json        dashboard Export → JSON, normal mode (official data)
        estimated.json       dashboard Export → JSON, forced-estimate mode
        figure.png           output of tools/compare_fig.py
        RESULTS.md           plain-language write-up (newer entries)
    video-2/ ...
  tools/
    compare_fig.py           one video: official vs estimate figure + metrics
    band_plot.py             many videos: accuracy vs comment count
  datasets/
    ytmr500/                 video id lists from the YTMR500 dataset, for bulk runs
```

New videos take the next number (`video-3`, `video-4`, ...). The link lives in each video's `meta.json` and README.

## Reproduce

```bash
pip install numpy scipy matplotlib
python benchmarks/tools/compare_fig.py official.json estimated.json figure.png
```

Before comparing, estimated windows are resampled onto the official bin grid with overlap-weighted means. The script reports Pearson, Spearman and Kendall correlations, MAE/RMSE, curve match (1 − MAE) beside a flat-median baseline, mean, median and hot-bin share (score ≥ 0.6), top-5 peak recall within ±15 s, whether the official #1 peak is in the estimate's native top 5, hot-segment precision (top 20%) against the 20% chance rate, a 10,000-shuffle timing control, and per-signal Spearman when the export includes signal scores. Without signal scores it shows score ECDFs with a KS test instead.

Optional environment variables: `FIG_LABEL` replaces the title label, and `FIG_NOTE` adds text to the footnote.

## Results

| Video | Link | Version | Spearman ρ | Pearson r | Top-5 peak recall | Mean (official / est.) | Data |
|---|---|---|---|---|---|---|---|
| [Video 1](videos/video-1/) | [youtu.be/IKPJq5Z_1ZM](https://youtu.be/IKPJq5Z_1ZM) | v1.3 | 0.41 (p < 0.001) | 0.41 | 3/5 | 0.12 / 0.50 | digitised* |
| [Video 2](videos/video-2/) | [youtu.be/RKQGRPoDV_I](https://youtu.be/RKQGRPoDV_I) | v1.4 | 0.22 (p = 0.029) | 0.42 | 2/5 | 0.17 / 0.16 | raw JSON ([details](videos/video-2/v1.4/RESULTS.md)) |

Video 2 (30,203 comments): comments alone reach ρ 0.53, but captions run negative (ρ −0.25), which pulls the fused curve down. A raw comments-only blend scores ρ 0.53 with 4/5 peaks. That comes from one video in-sample, so it's a lead, not a new set of weights.

\* The v1.3 data was digitised from exported PNGs, not raw JSON. The listed top-5 and drop-off scores are exact; the other bins are read from the plotted curve to within about ±0.02. The mean and hot-segment share match the export summary. Later entries use raw JSON exports.

Note that p-values treat bins as independent. Neighbouring bins are autocorrelated, so the p-values are optimistic.

## Accuracy vs engagement

`tools/band_plot.py` plots how accuracy changes with a video's comment count. Add `comments`, `views` and `genre` to each video's `meta.json` (`{"video_id": "...", "comments": 6598, "views": 2900000, "genre": "gaming"}`), then run:

```bash
python benchmarks/tools/band_plot.py v1.4 gaming
```

It writes `accuracy_vs_engagement.png` and a CSV with two scores per video:

- **Peak accuracy %**: the share of YouTube's top-5 peaks the estimate finds within ±15 s.
- **Ranking accuracy %**: the share of segment pairs the estimate orders the same way as YouTube, which is (Kendall τ + 1) / 2. 50% is chance and 100% is perfect.

A video folder is added only once its `official.json` and `estimated.json` exist.
