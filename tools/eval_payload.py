"""Evaluation-only context projection. Never reads fixture answers to select context."""
import json
import re
import unicodedata
from copy import deepcopy
from functools import lru_cache
from backend.app.services.llm.prompts import build_messages, PROMPT_DIR
from backend.app.schemas.actions import action_schema

STRATEGY_VERSION = 'scoped-eval-v1'
INPUT_BUDGET = 6000
FRAMING_RESERVE = 512
COMPLETION_BUDGET = 1024


class PayloadBudgetError(ValueError):
    pass


@lru_cache(maxsize=1)
def tokenizer():
    try:
        import tiktoken
        return tiktoken.get_encoding('o200k_harmony')
    except Exception as exc:
        raise PayloadBudgetError('Tokenizer unavailable; install tools/requirements-eval.txt and initialize o200k_harmony before live calls') from exc


def token_count(text):
    return len(tokenizer().encode(text, disallowed_special=()))


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


def scope_categories(state, message, history):
    """Deterministic lexical retrieval, not intent authorization or semantic scoring.

    No scenario ID, expected action or mock response is available to this function.
    Existing drafts are always retained. Unclear category -> category overview only.
    """
    text = normalize(message + '\n' + '\n'.join(t['content'] for t in history))
    aliases = {
        'salad': r'\b(salade?s?|salad\s*bar)\b',
        'sandwich': r'\b(sandwichs?|sandwiches)\b',
        'plat': r'\b(plats?|main dish(?:es)?)\b',
        'drink': r'\b(boissons?|drinks?|jus|juices?|sodas?|eau|water|coca(?:-cola)?|sprite|fanta)\b',
    }
    selected = set(state['categories'])
    selected.update(k for k, pattern in aliases.items() if re.search(pattern, text))
    # Chicken without category is intentionally ambiguous: do not choose a meal.
    return [k for k in aliases if k in selected]


def compact_schema(menu):
    """JSON Schema-equivalent factoring, retaining every original item ID enum."""
    schema = deepcopy(action_schema(menu))
    definitions = {}
    for variant in schema['properties']['actions']['items']['oneOf']:
        for field, value in list(variant['properties'].items()):
            if field == 'type':
                continue
            definitions.setdefault(field, deepcopy(value))
            variant['properties'][field] = {'$ref': '#/$defs/' + field}
    schema['$defs'] = definitions
    return schema


def scoped_menu(menu, categories):
    data = menu.snapshot()
    rules = {}
    for category, spec in data['categories'].items():
        rule = {k: deepcopy(spec[k]) for k in ('name', 'pricing', 'requires_size')}
        if spec['requires_size']:
            rule['sizes'] = {size: {k: deepcopy(value[k]) for k in ('price', 'slots')}
                             for size, value in spec['sizes'].items()}
        else:
            rule['slots'] = deepcopy(spec['slots'])
        rules[category] = rule
    columns = ['id','name_fr','name_en','price','allergens','tags','spice','vegetarian','vegan','group']
    grouped = {}
    for category in categories:
        grouped[category] = {}
        for item in menu.items(category):
            row = [item['id'],item['name']['fr'],item['name']['en'],item['price'],
                   item['allergens'],item['tags'],item['spice'],item['vegetarian'],item['vegan'],item.get('group')]
            grouped[category].setdefault(item['slot'], []).append(row)
    return {'meta': data['meta'], 'categories': rules, 'item_columns': columns,
            'items_by_category_slot': grouped,
            'scope_note': 'Category/slot keys apply to every row. All composition rules remain global. '
            'Item details are scoped by user/history/current drafts. Missing detail does not mean unavailable. '
            'For an unclear category ask which category; never infer price/allergens from an ID in the action schema.'}


def payload_measure(messages):
    content = sum(token_count(m['content']) for m in messages)
    framing = FRAMING_RESERVE + 16 * len(messages)
    return {'content_tokens': content, 'framing_reserve_tokens': framing,
            'budgeted_input_tokens': content + framing,
            'content_characters': sum(len(m['content']) for m in messages),
            'input_budget': INPUT_BUDGET, 'tokenizer': 'o200k_harmony',
            'note': 'Local BPE counts plus conservative framing reserve; Groq usage is authoritative.'}


def build_eval_messages(version, menu, state, message, history=(), *, policy=None):
    # Keep all input validation and exact prompt/history handling in the existing builder.
    original = build_messages(version, menu, state, message, history, policy=policy)
    prompt = (PROMPT_DIR / ('prompt_' + version + '.txt')).read_text(encoding='utf-8')
    original_context = json.loads(original[0]['content'][len(prompt) + 1:])
    categories = scope_categories(state, message, history)
    context = {'MENU_CONTEXT': scoped_menu(menu, categories), 'MEAL_STATE': state,
               'ACTION_SCHEMA': compact_schema(menu), 'ACTION_POLICY': original_context['ACTION_POLICY']}
    messages = [{'role':'system','content':prompt + '\n' + compact_json(context)}, *original[1:]]
    measurement = payload_measure(messages)
    if measurement['budgeted_input_tokens'] > INPUT_BUDGET:
        raise PayloadBudgetError('Evaluation payload exceeds 6000 input tokens; no truncation or request sent')
    return messages


def component_breakdown(messages, version):
    prompt = (PROMPT_DIR / ('prompt_' + version + '.txt')).read_text(encoding='utf-8')
    context = json.loads(messages[0]['content'][len(prompt) + 1:])
    menu = context['MENU_CONTEXT']
    scoped = 'items_by_category_slot' in menu
    dump = compact_json if scoped else lambda x: json.dumps(x, ensure_ascii=False)
    categories = menu['categories']
    # Rules and labels are partitioned so the character accounting is explicit.
    rules = {c: {k:v for k,v in spec.items() if k in ('pricing','requires_size','sizes','slots')}
             for c,spec in categories.items()}
    labels = {c: {k:v for k,v in spec.items() if k not in ('pricing','requires_size','sizes','slots')}
              for c,spec in categories.items()}
    parts = {'system_prompt': prompt,
             'menu_item_data': dump(menu.get('items_by_category_slot', menu.get('items'))),
             'meal_rules_and_pricing': dump(rules), 'category_labels': dump(labels),
             'menu_meta': dump(menu['meta']), 'action_schema': dump(context['ACTION_SCHEMA']),
             'meal_state': dump(context['MEAL_STATE']), 'authorization_policy': dump(context['ACTION_POLICY']),
             'conversation_history': dump(messages[1:-1]), 'scenario_input': messages[-1]['content'],
             'scope_and_table_legend': dump({k: menu[k] for k in ('item_columns','scope_note') if k in menu})}
    return {k:{'characters':len(v),'tokens':token_count(v)} for k,v in parts.items()}
