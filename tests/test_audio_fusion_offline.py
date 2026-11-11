"""Run with python -m unittest tests.test_audio_fusion_offline. Synthetic checks only."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scripts import compare_audio_fusion as c


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.head = json.loads((c.ROOT / 'app/sources/default_audio_head.json').read_text())
        self.rng = np.random.default_rng(42)

    def datum(self, vid):
        n = 30
        return dict(video_id=vid, windows=np.column_stack([np.arange(n)*10, (np.arange(n)+1)*10]),
                    X=self.rng.normal(size=(n, len(self.head['features']))),
                    names=np.array(self.head['features']), official=self.rng.random(n))

    def record(self, d):
        return dict(video_id=d['video_id'], official=[dict(start=float(a), end=float(b), score=float(y))
                    for (a, b), y in zip(d['windows'], d['official'])],
                    estimate=[dict(start=float(a), end=float(b), signals=dict(comments=i/29, transcript=(29-i)/29,
                                                               audio=.3, visual=(i%3)/2))
                              for i, (a, b) in enumerate(d['windows'])])

    def test_historical_scores(self):
        expected = [('video-1/v1.3-digitised', .4051189467, .6), ('video-2/v1.4', .2190663655, .4)]
        for folder, rho, recall in expected:
            root = c.ROOT / 'benchmarks/videos' / folder
            e, o = [json.loads((root / name).read_text())['full_heatmap']
                    for name in ('estimated.json', 'official.json')]
            m = c.metrics([s['score'] for s in e], c.grid(e), o)
            self.assertAlmostEqual(m['spearman'], rho)
            self.assertEqual(m['peak_recall'], recall)

    def test_overlap_resampling_and_coverage(self):
        src = np.array([[0, 10], [10, 20]])
        np.testing.assert_allclose(c.aligned([0, 1], src, np.array([[5, 15]])), [.5])
        with self.assertRaises(ValueError):
            c.aligned([0, 1], src, np.array([[5, 25]]))

    def test_fusion_keeps_other_signals(self):
        d = self.datum('synthetic01')
        r = self.record(d)
        before = json.dumps(r)
        audio = np.linspace(0, 1, 30)
        values, _ = c.fused(r, audio, c.WEIGHTS, .12)
        raw = [sum(c.WEIGHTS[k] * (audio[i] if k == 'audio' else row['signals'][k])
                   for k in c.WEIGHTS) for i, row in enumerate(r['estimate'])]
        np.testing.assert_allclose(values, c.calibrate_shape(c.normalize(raw), .12))
        self.assertEqual(json.dumps(r), before)

    def test_outer_labels_do_not_affect_predictions(self):
        data = [self.datum(str(i)) for i in range(5)]
        alpha, emb = c.select(data[1:], [.3, 3000], False)
        before = c.fit_predict(data[1:], data[0], alpha, emb)
        data[0]['official'][:] = 999
        after = c.fit_predict(data[1:], data[0], alpha, emb)
        np.testing.assert_array_equal(before, after)
        with self.assertRaises(ValueError):
            c.fit_predict(data, data[0], alpha, emb)

    def test_inner_folds_are_disjoint(self):
        data = [self.datum(str(i)) for i in range(4)]
        calls = []
        original = c.fit_predict
        def checked(train, val, alpha, emb):
            calls.append((set(d['video_id'] for d in train), val['video_id']))
            return original(train, val, alpha, emb)
        with patch.object(c, 'fit_predict', side_effect=checked):
            c.select(data, [1, 3000], False)
        self.assertEqual(len(calls), 8)
        self.assertTrue(all(vid not in train for train, vid in calls))

    def test_constant_correlation_is_undefined(self):
        d = self.datum('synthetic01')
        m = c.metrics(np.zeros(30), d['windows'], self.record(d)['official'])
        self.assertIsNone(m['spearman'])

    def test_end_to_end_modes_and_leakage_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / 'audio'
            audio.mkdir()
            for i in range(5):
                vid = self.head['trained_on'][0] if i == 0 else f'synthetic{i:02d}'
                d = self.datum(vid)
                np.savez(audio / f'{vid}-10.npz', **{k:v for k,v in d.items() if k != 'video_id'})
                (root / f'{vid}-10.json').write_text(json.dumps(self.record(d)))
            args = argparse.Namespace(head=c.ROOT / 'app/sources/default_audio_head.json',
                cache=root, audio_cache=audio, benchmarks=root/'absent', mode='bundled',
                embeddings=False, median=.12, seed=0, output=root/'result.json')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(c.run(args), 0)
            r = json.loads(args.output.read_text())
            self.assertEqual(r['eligible_count'], 4)
            self.assertTrue(any('bundled head trained on this video' in x['reasons'] for x in r['audit']))
            args.mode = 'nested'
            with contextlib.redirect_stdout(io.StringIO()), patch.object(c, 'ALPHAS', [1, 3000, 10000]):
                self.assertEqual(c.run(args), 0)
            r = json.loads(args.output.read_text())
            self.assertEqual(r['eligible_count'], 5)
            self.assertEqual(r['expanded_minus_old']['spearman']['n'], 5)
            # A mismatch must block that video, not silently resample its audio features.
            p = root / 'synthetic01-10.json'
            d = json.loads(p.read_text()); d['official'][0]['score'] += .1
            p.write_text(json.dumps(d))
            with contextlib.redirect_stdout(io.StringIO()), patch.object(c, 'ALPHAS', [1]):
                c.run(args)
            r = json.loads(args.output.read_text())
            self.assertEqual(r['eligible_count'], 4)


if __name__ == '__main__':
    unittest.main()
