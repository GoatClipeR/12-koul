import json
import io
from contextlib import redirect_stdout
import unittest
from pathlib import Path
from backend.app.services.evaluation import evaluate, METRICS
from backend.app.services.llm.providers import MockProvider


class EvaluationTests(unittest.TestCase):
    def test_all_mock_scenarios_and_metrics(self):
        report = evaluate()
        self.assertEqual(len(report['rows']), 42)
        self.assertTrue(all(r['contract_pass'] for r in report['rows']))
        for version, comparison in report['comparison'].items():
            self.assertEqual(comparison['contract_passes'], 14)
            for metric in METRICS:
                if metric in ('action_validity', 'correct_menu_usage', 'meal_state_correctness'):
                    self.assertGreater(comparison['metrics'][metric]['measured'], 0)
                else:
                    self.assertEqual(comparison['metrics'][metric]['measured'], 0)
        self.assertEqual(report['comparison']['v1'], report['comparison']['v3'])

    def test_mock_cannot_be_labeled_real(self):
        with self.assertRaises(ValueError): evaluate('real', MockProvider())

    def test_notebook_code_executes_offline(self):
        path = Path(__file__).resolve().parents[2] / 'notebook/phase1.ipynb'
        notebook = json.loads(path.read_text())
        namespace = {'__name__': '__notebook__'}
        for cell in notebook['cells']:
            if cell['cell_type'] == 'code':
                with redirect_stdout(io.StringIO()):
                    exec(compile(''.join(cell['source']), str(path), 'exec'), namespace)
        self.assertEqual(namespace['report']['mode'], 'mock')
        self.assertEqual(len(namespace['report']['rows']), 42)
