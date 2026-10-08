"""Lossless context encoding for the HTTP application, independent of evaluation.

No retrieval, truncation, rule deletion or authorization inference. The original
schema and menu remain authoritative; only their injected representation changes.
"""
import json
from copy import deepcopy


def compact_context(context):
    result = deepcopy(context)
    schema = result['ACTION_SCHEMA']
    definitions = {}
    for variant in schema['properties']['actions']['items']['oneOf']:
        for field, value in list(variant['properties'].items()):
            if field == 'type':
                continue
            # Factor identical definitions only; future schema differences stay inline.
            if field in definitions and definitions[field] != value:
                continue
            definitions[field] = deepcopy(value)
            variant['properties'][field] = {'$ref': '#/$defs/' + field}
    schema['$defs'] = definitions
    items = result['MENU_CONTEXT']['items']
    columns = list(dict.fromkeys(key for item in items for key in item))
    # A short row omits only trailing optional fields. Non-prefix shapes use the
    # original objects, rather than silently changing missing fields into null.
    if items and all(set(item) == set(columns[:len(item)]) for item in items):
        names_are_bilingual = all(isinstance(item.get('name'), dict) and set(item['name']) == {'fr', 'en'} for item in items)
        rows = [[item[key] for key in columns[:len(item)]] for item in items]
        if names_are_bilingual:
            for row in rows:
                name = row[columns.index('name')]
                row[columns.index('name')] = [name['fr'], name['en']]
        result['MENU_CONTEXT']['items'] = {
            'columns': columns,
            'rows': rows,
            'nested_columns': {'name': ['fr', 'en']} if names_are_bilingual else {},
            'encoding': 'Each row maps to columns in order; nested_columns maps nested arrays to object keys. Short rows omit trailing optional fields. All products are included.',
        }
    return result


def compact_messages(messages):
    """Keep the exact prompt prefix, every history turn and the user message."""
    result = deepcopy(messages)
    prefix, raw = result[0]['content'].rsplit('\n', 1)
    context = compact_context(json.loads(raw))
    result[0]['content'] = prefix + '\n' + json.dumps(context, ensure_ascii=False, separators=(',', ':'))
    return result
