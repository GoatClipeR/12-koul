"""Execute this project's plain-Python Phase 1 notebook and save real cell outputs.

No IPython magics are used. This is a stdlib alternative, not a Jupyter kernel run.
Run from repository root: python3 -B tools/run_phase1.py
"""
import contextlib
import io
import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'notebook/phase1.ipynb'
notebook = json.loads(path.read_text(encoding='utf-8'))
namespace = {'__name__': '__notebook__'}
count = 0
for cell in notebook['cells']:
    if cell['cell_type'] != 'code':
        continue
    count += 1
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(''.join(cell['source']), str(path), 'exec'), namespace)
    cell['execution_count'] = count
    cell['outputs'] = ([{'output_type': 'stream', 'name': 'stdout',
                         'text': output.getvalue().splitlines(True)}] if output.getvalue() else [])
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Executed and saved', count, 'Python cells; mode:', namespace['report']['mode'])
