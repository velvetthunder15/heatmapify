# YTMR500 benchmark

Videos from YTMR500 (Duico, Strafforello, van Gemert, TU Delft 2023, arXiv 2309.06102; dataset licensed for academic, non-commercial use). Only video IDs are stored here.

- `ids_live.txt`: 460 of 500 IDs still public on 2026-10-29 (oEmbed check). Fold-0 test videos come first.
- `batch1.txt`: first 100 of those.

Run on the laptop that hosts the server (cloud IPs are blocked):

    python -m scripts.calibrate --file benchmarks/datasets/ytmr500/batch1.txt

Each video takes a minute or two and is cached in `calibration/`, so it can be stopped and resumed. Then zip `calibration/` and share it for weight fitting (position-controlled partial r, 5 folds, TRIBE-style controls).
