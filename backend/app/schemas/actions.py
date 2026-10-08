"""Strict action contract. Unknown fields (including prices) are rejected."""
from copy import deepcopy
from ..services.errors import DomainError
from ..services.json_guard import safe_loads

FIELDS = {
    'ADD_ITEM': ('item_id',), 'REMOVE_ITEM': ('item_id',),
    'SET_CATEGORY': ('category',), 'SET_SIZE': ('size',),
    'CLEAR_CATEGORY': ('category',), 'CLEAR_MEAL': (),
    'RECOMMEND_ITEM': ('item_id',), 'CONFIRM_ORDER': (),
}


def action_schema(menu):
    data = menu.snapshot()
    values = {'item_id': list(i['id'] for i in data['items']),
              'category': list(data['categories']),
              'size': list(data['categories']['salad']['sizes'])}
    return {'type': 'object', 'additionalProperties': False,
            'required': ['message', 'actions'], 'properties': {
                'message': {'type': 'string', 'minLength': 1, 'maxLength': 4000},
                'actions': {'type': 'array', 'maxItems': 64, 'items': {'oneOf': [
                    {'type': 'object', 'additionalProperties': False,
                     'required': ['type', *fields],
                     'properties': {'type': {'const': kind}, **{
                         f: {'type': 'string', 'enum': values[f]} for f in fields}}}
                    for kind, fields in FIELDS.items()]}}}}


def validate_action(action, menu):
    if not isinstance(action, dict) or not isinstance(action.get('type'), str):
        raise DomainError('INVALID_ACTION')
    kind = action['type']
    if kind not in FIELDS:
        raise DomainError('UNKNOWN_ACTION')
    if set(action) != {'type', *FIELDS[kind]}:
        raise DomainError('INVALID_ACTION_FIELDS')
    if any(not isinstance(action[f], str) for f in FIELDS[kind]):
        raise DomainError('INVALID_ACTION_FIELDS')
    if 'item_id' in action:
        menu.item(action['item_id'])
    if 'category' in action:
        menu.category(action['category'])
    if 'size' in action:
        menu.rules('salad', action['size'])
    return deepcopy(action)


def validate_response(raw, menu):
    if isinstance(raw, str):
        if len(raw) > 100000:
            raise DomainError('INVALID_RESPONSE')
        try:
            raw = safe_loads(raw)
        except (ValueError, RecursionError) as exc:
            raise DomainError('INVALID_JSON') from exc
    if not isinstance(raw, dict) or set(raw) != {'message', 'actions'}:
        raise DomainError('INVALID_RESPONSE')
    if not isinstance(raw['message'], str) or not 1 <= len(raw['message']) <= 4000:
        raise DomainError('INVALID_RESPONSE')
    if not isinstance(raw['actions'], list) or len(raw['actions']) > 64:
        raise DomainError('INVALID_RESPONSE')
    return {'message': raw['message'],
            'actions': [validate_action(a, menu) for a in raw['actions']]}
