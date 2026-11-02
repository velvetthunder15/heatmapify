"""Audio event detection with YAMNet (AudioSet, 521 classes) running on ONNX Runtime.

Laughter, applause, cheering, crowd noise and shouting are strong engagement cues that plain
loudness misses. YAMNet scores every 0.96 s frame (hop 0.48 s); we fold the frames into the
estimate's windows as a small feature table. Two ways to turn that table into a curve:

  1. zero-shot (default): a "reaction" score = the strongest of laughter / applause / crowd /
     excitement in each window, blended with loudness and speech rate.
  2. trained head (models/audio_head.json, made by `python -m scripts.train_audio`): a ridge
     regression fitted on YOUR videos' official "Most replayed" curves, on top of the frozen
     YAMNet features (transfer learning). Used only when it beat zero-shot in cross-validation.

The model (16 MB, Apache-2.0, Google's YAMNet converted to ONNX) downloads once on first use and
is checked against a pinned SHA-256. If onnxruntime or the model is unavailable, callers fall back
to the basic loudness heuristic, so nothing breaks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import urllib.request
from pathlib import Path

from ..logging_setup import log_event

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = Path(os.environ.get("AUDIO_MODEL_DIR", ROOT / "models"))
MODEL_FILE = "yamnet.onnx"
HEAD_FILE = "audio_head.json"
# audiomagic/yamnet-onnx, pinned to a commit: straight tf2onnx conversion of google/yamnet v1.
MODEL_URL = ("https://huggingface.co/audiomagic/yamnet-onnx/resolve/"
             "f25b741c2f0bdc6d7e6db24b5fddda23347dbafd/yamnet.onnx")
MODEL_SHA256 = "d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e"

SR = 16000
FRAME_HOP = 0.48
FRAME_LEN = 0.96
CHUNK_SAMPLES = 7680 * 250  # 2 minutes per call: faster and ~0.3 GB peak RAM (10-min chunks hit 1.3 GB)

# AudioSet class indices (yamnet_class_map.csv) grouped into engagement cues.
GROUPS: dict[str, list[int]] = {
    "laughter": [13, 14, 15, 16, 17, 18],  # laughter, baby laughter, giggle, snicker, belly laugh, chuckle
    "applause": [58, 61, 62],              # clapping, cheering, applause
    "crowd": [63, 64, 65],                 # chatter, crowd, hubbub
    "excited": [6, 8, 9, 11, 39],          # shout, whoop, yell, screaming, gasp
    "impact": [420, 421, 430],             # explosion, gunshot, boom
    "music": [132],
    "speech": [0],
    "silence": [494],
}
REACTION = ["laughter", "applause", "crowd", "excited"]

_session = None
_lock = threading.Lock()


# ---------------------------------------------------------------- model --
def model_path() -> Path:
    return MODEL_DIR / MODEL_FILE


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ensure_model() -> Path:
    """Return the verified model path, downloading it once if needed."""
    p = model_path()
    if p.exists() and _sha256(p) == MODEL_SHA256:
        return p
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part")
    log_event(log, "audio_model_download", url=MODEL_URL)
    with urllib.request.urlopen(MODEL_URL, timeout=60) as r, open(tmp, "wb") as f:  # noqa: S310 pinned https url
        while chunk := r.read(1 << 20):
            f.write(chunk)
    if _sha256(tmp) != MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("audio model checksum mismatch; not using it")
    os.replace(tmp, p)
    return p


def _get_session():
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort  # lazy, optional

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 2) // 2))
            _session = ort.InferenceSession(str(ensure_model()), opts, providers=["CPUExecutionProvider"])
        return _session


def run_yamnet(y):
    """Waveform (16 kHz mono float32) -> (frame_times, scores[F,521], embeddings[F,1024])."""
    import numpy as np

    sess = _get_session()
    times, scores, embs = [], [], []
    for start in range(0, max(len(y), 1), CHUNK_SAMPLES):
        chunk = np.ascontiguousarray(y[start:start + CHUNK_SAMPLES], dtype=np.float32)
        if chunk.size == 0:
            break
        s, e, _ = sess.run(None, {"waveform": chunk})
        t0 = start / SR
        times.append(t0 + np.arange(len(s)) * FRAME_HOP + FRAME_LEN / 2)  # frame centres
        scores.append(s)
        embs.append(e)
    return np.concatenate(times), np.concatenate(scores), np.concatenate(embs)


# ------------------------------------------------------------- features --
def group_scores(scores):
    """[F,521] class scores -> {group: [F]} (max over the group's classes)."""
    return {g: scores[:, idx].max(axis=1) for g, idx in GROUPS.items()}


def window_features(frame_t, groups, embs, windows):
    """Fold frames into windows. Returns (event_rows, emb_rows); a window with no frame gets zeros."""
    import numpy as np

    rows, erows = [], []
    for a, b in windows:
        m = (frame_t >= a) & (frame_t < b)
        if not m.any():  # very short window: use the nearest frame
            if len(frame_t) and a <= frame_t[-1] + FRAME_LEN:
                m = np.zeros(len(frame_t), bool)
                m[int(np.argmin(np.abs(frame_t - (a + b) / 2)))] = True
        row = {}
        for g, v in groups.items():
            row[f"{g}_max"] = float(v[m].max()) if m.any() else 0.0
            row[f"{g}_mean"] = float(v[m].mean()) if m.any() else 0.0
        reaction = np.max([groups[g] for g in REACTION], axis=0) if m.any() else None
        row["reaction"] = float(0.6 * reaction[m].max() + 0.4 * reaction[m].mean()) if m.any() else 0.0
        rows.append(row)
        erows.append(embs[m].mean(axis=0) if m.any() else np.zeros(embs.shape[1] if embs.ndim == 2 else 1024))
    return rows, np.array(erows)


def zscore_cols(X):
    """Standardise each column within one video (scores are relative to the video's own baseline)."""
    import numpy as np

    X = np.asarray(X, dtype=float)
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    return (X - mu) / sd


def feature_matrix(rows, basic, names):
    """rows: event dicts per window; basic: dict of per-window basic features; -> X[W, len(names)]."""
    import numpy as np

    cols = []
    for n in names:
        if n in basic:
            cols.append(basic[n])
        else:
            cols.append([r.get(n, 0.0) for r in rows])
    return np.array(cols, dtype=float).T


# ----------------------------------------------------------------- head --
def head_path() -> Path:
    return MODEL_DIR / HEAD_FILE


def load_head() -> dict | None:
    p = head_path()
    if not p.exists():
        return None
    try:
        h = json.loads(p.read_text(encoding="utf-8"))
        if h.get("active") and h.get("coef") and h.get("features"):
            return h
    except Exception as exc:  # noqa: BLE001
        log_event(log, "audio_head_unreadable", error=str(exc)[:120])
    return None


def apply_head(head: dict, rows, basic, emb_rows):
    import numpy as np

    X = zscore_cols(feature_matrix(rows, basic, head["features"]))
    if head.get("use_embeddings"):
        X = np.hstack([X, zscore_cols(emb_rows)])
    coef = np.asarray(head["coef"], dtype=float)
    if X.shape[1] != coef.size:
        raise ValueError("audio head does not match the features")
    return (X @ coef + float(head.get("intercept", 0.0))).tolist()
