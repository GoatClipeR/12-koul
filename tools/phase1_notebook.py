"""Read-only pedagogical projection of existing evaluation artifacts. No API calls."""
import json
from pathlib import Path


def read_real_snapshot(path):
    path = Path(path)
    if not path.exists():
        return None, 'Résultats réels en attente : fichier absent.'
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('mode') != 'real' or not isinstance(report.get('rows'), list):
            return None, 'Fichier non reconnu comme évaluation réelle ; aucune substitution par du mock.'
        rows = report['rows']
        responses = sum(isinstance(r.get('model_response'), str) and bool(r['model_response'].strip()) for r in rows)
        complete = report.get('metadata', {}).get('completed', False)
        status = 'Exécution déclarée terminée' if complete else 'Checkpoint partiel ; exécution non déclarée terminée'
        return report, f'{status} : {len(rows)}/42 lignes, {responses} réponses du modèle. Voir la revue sémantique séparée si disponible.'
    except (OSError, ValueError, TypeError, AttributeError):
        return None, 'Snapshot indisponible ou illisible ; réexécuter cette cellule plus tard.'


def read_semantic_review(path, source_path, report):
    """Read authored judgments only when bound to this exact complete real snapshot."""
    import hashlib
    try:
        raw = Path(source_path).read_bytes()
        review = json.loads(Path(path).read_text(encoding='utf-8'))
        if (report is None or report.get('mode') != 'real' or json.loads(raw) != report
                or review.get('source_sha256') != hashlib.sha256(raw).hexdigest()
                or review.get('review_type') != 'ASSISTED_SEMANTIC_REVIEW'):
            return None, 'Revue absente, incompatible ou périmée ; appréciations en attente.'
        actual = [(r['prompt'], r['scenario']) for r in report['rows']]
        judged = [(r['prompt'], r['scenario']) for r in review['rows']]
        if (len(actual) != 42 or len(set(actual)) != 42 or len(judged) != 42
                or set(actual) != set(judged)
                or any(not r.get('model_response') for r in report['rows'])
                or any(r.get('verdict') not in ('PASS', 'PARTIAL', 'FAIL')
                       or not r.get('reason') or not r.get('improvement') for r in review['rows'])):
            return None, 'Revue incomplète ou invalide ; appréciations en attente.'
        return review, '42 appréciations assistées reliées au fichier réel ; validation humaine indépendante à faire.'
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return None, 'Revue indisponible ; appréciations en attente.'


def tp_rows(cases, report, version, review=None):
    """Always list all 14 questions; never fill missing real rows with mock output."""
    indexed = {(r.get('prompt'), r.get('scenario')): r for r in (report or {}).get('rows', [])}
    judgments = {(r['prompt'], r['scenario']): r for r in (review or {}).get('rows', [])}
    rows = []
    for case in cases:
        row = indexed.get((version, case['id']))
        response = row.get('model_response') if row else None
        if row is None:
            appreciation, improvement = 'EN ATTENTE — non exécuté dans ce snapshot', 'Attendre la réponse réelle.'
        elif not response:
            error = (row.get('validation_result', {}).get('error') or {}).get('code', 'indisponible')
            appreciation, improvement = f'Sans réponse modèle ({error})', 'Résoudre l’échec technique avant de juger le prompt.'
        else:
            accepted = row.get('validation_result', {}).get('accepted', False)
            appreciation = ('Actions acceptées' if accepted else 'Actions rejetées') + ' ; sens et qualité À RELIRE'
            improvement = 'Comparer intention, réponse et état ; proposer une modification seulement après revue.'
            judgment = judgments.get((version, case['id']))
            if judgment:
                appreciation = ('Actions acceptées' if accepted else 'Actions rejetées') + ' ; ' + judgment['verdict'] + ' — ' + judgment['reason']
                improvement = judgment['improvement']
        rows.append([case['input'], case['expected_behavior'], response or 'EN ATTENTE / aucune réponse réelle', appreciation, improvement])
    return rows


def markdown_table(headers, rows):
    def safe(value):
        # Escape model HTML before displaying a table in Jupyter.
        import html
        return html.escape(str(value)).replace('|', '&#124;').replace('\n', '<br>')
    return '\n'.join(['| ' + ' | '.join(map(safe, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(safe, row)) + ' |' for row in rows])
