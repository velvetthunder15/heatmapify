"""Signal: audio energy.

Downloads audio only (converted to WAV by ffmpeg, resampled to 16 kHz mono on load), then per window:
  - loudness: mean RMS in dB (librosa)
  - speech rate proxy: onset density
  - bursts: frames that are both loud and noise-like (high spectral flatness)
  - audio events (YAMNet, see audio_events.py): laughter, applause, cheering, crowd noise,
    shouting. Falls back to the basic features above if the model can't load.
"""
from __future__ import annotations

import logging

from ..config import get_settings
from ..logging_setup import log_event
from ..urls import canonical_url
from .. import ytdl

log = logging.getLogger(__name__)
SR = 16000
HOP = 512


def download_audio(video_id: str, out_dir: str) -> str:
    return ytdl.download(
        canonical_url(video_id),
        out_dir,
        fmt="bestaudio[abr<=128]/bestaudio/worst",
        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    )


BASIC = ["loudness", "loudness_change", "speech_rate", "noisy_burst"]


def basic_features(y, sr, windows) -> dict[str, list[float]]:
    """Per-window loudness (dB), change in loudness vs the previous window, onset rate, noisy bursts."""
    import librosa  # lazy, heavy
    import numpy as np

    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    db = librosa.amplitude_to_db(rms, ref=np.max)
    flat = librosa.feature.spectral_flatness(y=y, hop_length=HOP)[0]
    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=HOP, units="time")
    frame_t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP)
    loud_thr = np.percentile(db, 75)
    flat_thr = np.percentile(flat, 80)

    loud, rate, burst = [], [], []
    for a, b in windows:
        m = (frame_t >= a) & (frame_t < b)
        if not m.any():  # past the end of the audio: treat as silence
            loud.append(float("nan")); rate.append(0.0); burst.append(0.0)
            continue
        loud.append(float(db[m].mean()))
        rate.append(float(((onsets >= a) & (onsets < b)).sum()) / max(b - a, 1e-6))
        burst.append(float(((db[m] > loud_thr) & (flat[m] > flat_thr)).mean()))
    floor = min((v for v in loud if v == v), default=0.0)  # dB: lowest real value = quietest
    loud = [floor if v != v else v for v in loud]
    change = [0.0] + [abs(loud[i] - loud[i - 1]) for i in range(1, len(loud))]
    return {"loudness": loud, "loudness_change": change, "speech_rate": rate, "noisy_burst": burst}


def basic_curve(f: dict[str, list[float]]) -> list[float]:
    from ..scoring import normalize

    L, R, B = normalize(f["loudness"]), normalize(f["speech_rate"]), normalize(f["noisy_burst"])
    return [0.5 * l + 0.3 * r + 0.2 * bb for l, r, bb in zip(L, R, B)]


def zero_shot_curve(rows: list[dict], f: dict[str, list[float]]) -> list[float]:
    """Laughter / applause / crowd / excitement first, loudness and speech rate as support."""
    from ..scoring import normalize

    E = normalize([r["reaction"] for r in rows])
    L, R = normalize(f["loudness"]), normalize(f["speech_rate"])
    return [0.5 * e + 0.3 * l + 0.2 * r for e, l, r in zip(E, L, R)]


def analyse_audio(path: str, windows: list[tuple[float, float]], events: bool | None = None,
                  features_out: dict | None = None) -> list[float]:
    """Audio curve for the windows. With `features_out`, also fills it with the raw features
    (used by scripts.train_audio)."""
    import librosa  # lazy, heavy

    from ..scoring import normalize

    y, sr = librosa.load(path, sr=SR, mono=True)
    if y.size == 0:
        return [0.0] * len(windows)
    basic = basic_features(y, sr, windows)
    if features_out is not None:
        features_out["basic"] = basic
    if events is None:
        events = get_settings().audio_events
    if not events:
        return basic_curve(basic)
    try:
        from . import audio_events as ae

        ft, scores, embs = ae.run_yamnet(y)
        rows, emb_rows = ae.window_features(ft, ae.group_scores(scores), embs, windows)
        if features_out is not None:
            features_out["events"] = rows
            features_out["embeddings"] = emb_rows
        head = ae.load_head()
        if head:
            try:
                return normalize(ae.apply_head(head, rows, basic, emb_rows))
            except Exception as exc:  # noqa: BLE001  a stale head must not break estimates
                log_event(log, "audio_head_failed", error=str(exc)[:200])
        return zero_shot_curve(rows, basic)
    except Exception as exc:  # noqa: BLE001  no onnxruntime / model offline: keep the basic signal
        log_event(log, "audio_events_unavailable", error=str(exc)[:200])
        return basic_curve(basic)


def audio_signal(video_id: str, windows: list[tuple[float, float]], work_dir: str) -> list[float] | None:
    try:
        path = download_audio(video_id, work_dir)
        return analyse_audio(path, windows)
    except Exception as exc:
        log_event(log, "audio_failed", video_id=video_id, error=str(exc)[:200])
        if get_settings().log_level.upper() == "DEBUG":
            log.exception("audio")
        raise  # the pipeline records the reason in signals_skipped
