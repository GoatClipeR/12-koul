import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.phase1_notebook import read_real_snapshot, tp_rows, markdown_table

class NotebookSnapshotTests(unittest.TestCase):
    def test_missing_partial_and_failed_rows_never_become_mock_success(self):
        cases=[{'id':'a','input':'Question','expected_behavior':'Attendu'},
               {'id':'b','input':'Question 2','expected_behavior':'Attendu'}]
        with TemporaryDirectory() as directory:
            path=Path(directory)/'results.json'
            self.assertIsNone(read_real_snapshot(path)[0])
            data={'mode':'real','metadata':{'completed':False},'rows':[{
                'prompt':'v1','scenario':'a','model_response':None,
                'validation_result':{'accepted':False,'error':{'code':'HTTP_ERROR'}}}]}
            path.write_text(json.dumps(data))
            original=path.read_bytes()
            report,status=read_real_snapshot(path)
            self.assertIn('partiel',status)
            rows=tp_rows(cases,report,'v1')
            self.assertIn('HTTP_ERROR',rows[0][3]);self.assertIn('non exécuté',rows[1][3])
            self.assertEqual(path.read_bytes(),original)
            data['mode']='mock';path.write_text(json.dumps(data))
            self.assertIsNone(read_real_snapshot(path)[0])

    def test_table_escapes_model_html(self):
        table=markdown_table(['Réponse'],[['<script>alert(1)</script>|x\ny']])
        self.assertNotIn('<script>',table)
        self.assertIn('&lt;script&gt;',table)
        self.assertIn('&#124;',table)

    def test_notebook_syntax_and_no_live_execution_switch(self):
        path=Path(__file__).resolve().parents[2]/'notebook/phase1.ipynb'
        notebook=json.loads(path.read_text())
        for cell in notebook['cells']:
            if cell['cell_type']=='code':
                source=''.join(cell['source']);compile(source,str(path),'exec')
                self.assertNotIn('evaluate("real")',source)
                self.assertNotIn('RUN_REAL',source)
