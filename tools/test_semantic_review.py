"""Offline checks of review provenance and presentation, not semantic grading."""
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.phase1_notebook import read_semantic_review, tp_rows

ROOT = Path(__file__).resolve().parents[1]


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / 'notebook/real-results.local.json'
        self.review_path = ROOT / 'docs/semantic-evaluation.json'
        self.report = json.loads(self.source.read_text())
        self.review = json.loads(self.review_path.read_text())

    def test_exact_evidence_and_all_42_unique_judgments(self):
        loaded, _ = read_semantic_review(self.review_path, self.source, self.report)
        self.assertIsNotNone(loaded)
        for version, counts in [('v1', (8, 3, 3)), ('v2', (11, 2, 1)), ('v3', (11, 3, 0))]:
            counter = Counter(r['verdict'] for r in loaded['rows'] if r['prompt'] == version)
            self.assertEqual(tuple(counter[k] for k in ('PASS', 'PARTIAL', 'FAIL')), counts)
        doc = (ROOT / 'docs/semantic-evaluation.md').read_text()
        for row in self.report['rows']:
            self.assertIn(json.loads(row['model_response'])['message'], doc)
        self.assertEqual(len(loaded['rows']), 42)

    def test_stale_missing_and_incomplete_reviews_stay_pending(self):
        with TemporaryDirectory() as directory:
            source, review = Path(directory) / 'source.json', Path(directory) / 'review.json'
            source.write_bytes(self.source.read_bytes())
            review.write_bytes(self.review_path.read_bytes())
            self.assertIsNotNone(read_semantic_review(review, source, self.report)[0])
            source.write_bytes(source.read_bytes() + b'\n')
            self.assertIsNone(read_semantic_review(review, source, self.report)[0])
            source.write_bytes(self.source.read_bytes())
            bad = dict(self.review, rows=self.review['rows'][:-1])
            review.write_text(json.dumps(bad))
            self.assertIsNone(read_semantic_review(review, source, self.report)[0])
            bad['rows'] = self.review['rows'][:-1] + [self.review['rows'][0]]
            review.write_text(json.dumps(bad))
            self.assertIsNone(read_semantic_review(review, source, self.report)[0])
            self.assertIsNone(read_semantic_review(Path(directory) / 'absent', source, self.report)[0])

    def test_mock_and_missing_model_response_cannot_receive_review(self):
        with TemporaryDirectory() as directory:
            source, review = Path(directory) / 'source.json', Path(directory) / 'review.json'
            for variant in ('mock', 'missing_response'):
                report = json.loads(self.source.read_text())
                if variant == 'mock':
                    report['mode'] = 'mock'
                else:
                    report['rows'][0]['model_response'] = None
                source.write_text(json.dumps(report))
                authored = dict(self.review, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
                review.write_text(json.dumps(authored))
                self.assertIsNone(read_semantic_review(review, source, report)[0])

    def test_accepted_batch_can_display_semantic_failure(self):
        row = next(r for r in self.report['rows'] if r['prompt'] == 'v2' and r['scenario'] == 'large_missing_base')
        self.assertTrue(row['validation_result']['accepted'])
        case = {'id': row['scenario'], 'input': row['input'], 'expected_behavior': row['expected_behavior']}
        rendered = tp_rows([case], self.report, 'v2', self.review)[0]
        self.assertIn('Actions acceptées ; FAIL', rendered[3])
        self.assertIn('roquette', rendered[3])


if __name__ == '__main__':
    unittest.main()
