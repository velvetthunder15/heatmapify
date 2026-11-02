# Audio model, Heatmapify v1.5

How well does the **audio signal on its own** follow YouTube's official "Most replayed" curve?
Trained and tested on 20 videos from YTMR500 (the first 20 IDs in
[`datasets/ytmr500/batch1.txt`](../../datasets/ytmr500/batch1.txt)), 10-second windows.

Every number is **leave-one-video-out**: each video is scored by a model trained on the other 19,
so none of them were seen during training.

| Audio signal | Rank match (Spearman ρ) | Top-5 moments found |
|---|---|---|
| Old: loudness, speech rate, noisy bursts | −0.01 | 21% |
| YAMNet zero-shot (laughter, applause, crowd, shouting) | 0.04 | 26% |
| **YAMNet + trained head** (now the default) | **0.16** | **26%** |

## What it means

- The old loudness-based audio score was no better than chance at ranking moments (ρ ≈ 0).
- Detecting reactions with YAMNet helps a little, and training on official replay data helps more:
  ρ goes from about 0 to 0.16 on unseen videos. It now finds the same share of top moments as zero-shot.
- Audio is one of four signals, so this is a building block, not a finished estimate. Comments are
  still the strongest signal ([Video 2](../../videos/video-2/v1.4/RESULTS.md): ρ 0.53 on their own).

## What the head learned

A ridge regression on 21 sound features per window, each standardised within its own video.
The strongest positive cues are shouting and gasps (`excited`), crowd noise, laughter, overall
reaction and music. The strongest negative cue is a window that is speech all the way through
(`speech_mean`), i.e. plain talking. Raw loudness gets almost no weight once these cues are known.
It chose heavy regularisation (alpha 3000, the top of the grid), so it's a conservative model.
v1.5.1 widens the grid for the next run.

## Caveats

- 20 videos is a small set, and YTMR500's mix of genres may not match yours. Train your own with
  `train-audio.bat` / `train-audio.command`; a personal head in `models/` overrides this default.
- Bins next to each other are correlated, so treat per-video numbers as indicative.

Files: [`audio_head.json`](audio_head.json) (identical to `app/sources/default_audio_head.json`).
