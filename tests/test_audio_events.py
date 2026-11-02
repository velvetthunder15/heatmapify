import math

import numpy as np
import pytest

from app.sources import audio, audio_events as ae


def _fake_frames(n=100, laugh_at=(40, 45)):
    t = np.arange(n) * ae.FRAME_HOP + ae.FRAME_LEN / 2
    scores = np.zeros((n, 521), dtype=np.float32)
    scores[:, 0] = 0.8  # speech everywhere
    scores[laugh_at[0]:laugh_at[1], 13] = 0.9  # laughter burst
    embs = np.random.default_rng(0).normal(size=(n, 1024)).astype(np.float32)
    return t, scores, embs


def test_window_features_finds_laughter():
    t, s, e = _fake_frames()
    windows = [(i * 5.0, (i + 1) * 5.0) for i in range(10)]
    rows, emb = ae.window_features(t, ae.group_scores(s), e, windows)
    assert len(rows) == 10 and emb.shape == (10, 1024)
    best = max(range(10), key=lambda i: rows[i]["reaction"])
    assert best in (3, 4)  # laughter frames sit around 19.7-21.6 s
    assert rows[best]["laughter_max"] == pytest.approx(0.9, abs=1e-6)
    assert rows[0]["speech_mean"] == pytest.approx(0.8, abs=1e-6)


def test_zero_shot_curve_in_range():
    rows = [{"reaction": r} for r in (0.0, 0.9, 0.1)]
    basic = {"loudness": [-30, -10, -20], "speech_rate": [1, 2, 1], "loudness_change": [0, 1, 1], "noisy_burst": [0, 0, 0]}
    c = audio.zero_shot_curve(rows, basic)
    assert len(c) == 3 and all(0 <= v <= 1 for v in c)
    assert max(range(3), key=c.__getitem__) == 1


def test_apply_head_shape_mismatch():
    head = {"active": True, "features": ["reaction"], "coef": [1.0, 2.0], "use_embeddings": False}
    with pytest.raises(ValueError):
        ae.apply_head(head, [{"reaction": 0.1}, {"reaction": 0.5}], {}, np.zeros((2, 1024)))


def test_apply_head_ranks_by_feature():
    head = {"active": True, "features": ["reaction"], "coef": [1.0], "use_embeddings": False}
    out = ae.apply_head(head, [{"reaction": 0.1}, {"reaction": 0.5}, {"reaction": 0.2}], {}, np.zeros((3, 1024)))
    assert max(range(3), key=out.__getitem__) == 1


def test_ridge_learns_laughter():
    from scripts import train_audio as ta

    names = ta.hand_feature_names()
    rng = np.random.default_rng(1)
    data = []
    for v in range(6):
        X = rng.normal(size=(60, len(names)))
        off = X[:, names.index("laughter_max")] * 2 + rng.normal(scale=0.3, size=60)
        data.append({"X": X, "E": rng.normal(size=(60, 8)), "official": off, "names": np.array(names), "video_id": str(v)})
    sp, hit, _ = ta.lovo(data, False, 10)
    assert sp > 0.8


def test_fallback_when_model_unavailable(tmp_path, monkeypatch):
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    sr = 16000
    y = np.concatenate([0.01 * np.random.default_rng(2).normal(size=sr * 10), 0.5 * np.random.default_rng(3).normal(size=sr * 10)])
    p = tmp_path / "a.wav"
    sf.write(p, y.astype(np.float32), sr)
    windows = [(0, 5), (5, 10), (10, 15), (15, 20)]

    def boom(_):
        raise RuntimeError("no model")

    monkeypatch.setattr(ae, "run_yamnet", boom)
    with_events = audio.analyse_audio(str(p), windows, events=True)
    basic = audio.analyse_audio(str(p), windows, events=False)
    assert with_events == pytest.approx(basic)
    assert basic[3] > basic[0]


@pytest.mark.skipif(not ae.model_path().exists(), reason="YAMNet model not downloaded")
def test_real_model_silence():
    pytest.importorskip("onnxruntime")
    t, s, e = ae.run_yamnet(np.zeros(16000 * 5, dtype=np.float32))
    assert s.shape[1] == 521 and e.shape[1] == 1024 and len(t) == len(s)
    assert int(s.mean(axis=0).argmax()) == ae.GROUPS["silence"][0]


def test_bundled_head_matches_features(monkeypatch, tmp_path):
    from scripts import train_audio as ta

    monkeypatch.setattr(ae, "MODEL_DIR", tmp_path)  # no personal head
    h = ae.load_head()
    assert h is not None and h["features"] == ta.hand_feature_names()
    assert len(h["coef"]) == len(h["features"]) and not h["use_embeddings"]
