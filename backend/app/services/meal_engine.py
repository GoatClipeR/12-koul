"""Pure transitions over JSON-compatible state. Caller owns persistence.

One draft per category, with an active category. Switching preserves drafts.
A drink draft is always a separate line. Confirmation validates, never places an order.
"""
from copy import deepcopy
from .errors import DomainError
from ..schemas.actions import validate_action, validate_response


def create_meal():
    return {'active_category': None, 'categories': {}}


def validate_state(state, menu):
    if not isinstance(state, dict) or set(state) != {'active_category', 'categories'}:
        raise DomainError('INVALID_STATE')
    drafts = state['categories']
    if not isinstance(drafts, dict):
        raise DomainError('INVALID_STATE')
    active = state['active_category']
    if active is not None and (not isinstance(active, str) or active not in drafts):
        raise DomainError('INVALID_STATE')
    for category, draft in drafts.items():
        spec = menu.category(category)
        if not isinstance(draft, dict) or set(draft) != {'type', 'size', 'slots'}:
            raise DomainError('INVALID_STATE')
        if draft['type'] != category or not isinstance(draft['slots'], dict):
            raise DomainError('INVALID_STATE')
        if set(draft['slots']) != set(spec['slot_order']):
            raise DomainError('INVALID_STATE')
        unsized = spec['requires_size'] and draft['size'] is None
        rules = None if unsized else menu.rules(category, draft['size'])
        for slot, ids in draft['slots'].items():
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                raise DomainError('INVALID_STATE')
            if len(ids) != len(set(ids)):
                raise DomainError('DUPLICATE_ITEM', {'slot': slot})
            if unsized and ids:
                raise DomainError('SIZE_REQUIRED')
            if rules and len(ids) > rules[slot]['max']:
                raise DomainError('SLOT_FULL', {'category': category, 'slot': slot})
            for item_id in ids:
                item = menu.item(item_id)
                if item['category'] != category:
                    raise DomainError('WRONG_CATEGORY')
                if item['slot'] != slot:
                    raise DomainError('WRONG_SLOT')
    return state


def completeness(state, menu):
    validate_state(state, menu)
    missing = []
    for category, draft in state['categories'].items():
        if category == 'salad' and draft['size'] is None:
            missing.append({'category': category, 'size_required': True})
            continue
        for slot, rule in menu.rules(category, draft['size']).items():
            count = rule['min'] - len(draft['slots'][slot])
            if count > 0:
                missing.append({'category': category, 'slot': slot, 'count': count})
    return {'complete': bool(state['categories']) and not missing, 'missing': missing}


def apply_action(state, action, menu):
    """Trusted domain primitive. Untrusted model batches must use apply_response."""
    validate_state(state, menu)
    action = validate_action(action, menu)
    result = deepcopy(state)
    kind = action['type']
    if kind == 'CLEAR_MEAL':
        return create_meal()
    if kind == 'SET_CATEGORY':
        category = action['category']
        result['active_category'] = category
        result['categories'].setdefault(category, {'type': category, 'size': None,
            'slots': {s: [] for s in menu.category(category)['slot_order']}})
        return result
    if kind == 'CLEAR_CATEGORY':
        category = action['category']
        result['categories'].pop(category, None)
        if result['active_category'] == category:
            result['active_category'] = None
        return result
    if kind == 'RECOMMEND_ITEM':
        return result  # informational only; never silently adds the recommendation
    if kind == 'CONFIRM_ORDER':
        if not result['categories']:
            raise DomainError('CART_EMPTY')
        status = completeness(result, menu)
        if not status['complete']:
            raise DomainError('INCOMPLETE_MEAL', status)
        return result
    category = result['active_category']
    if category is None:
        raise DomainError('NO_ACTIVE_MEAL')
    draft = result['categories'][category]
    if kind == 'SET_SIZE':
        rules = menu.rules(category, action['size'])
        if any(len(draft['slots'][s]) > r['max'] for s, r in rules.items()):
            raise DomainError('SIZE_CONFLICT')
        draft['size'] = action['size']
    else:
        item = menu.item(action['item_id'])
        if item['category'] != category:
            raise DomainError('WRONG_CATEGORY')
        rules = menu.rules(category, draft['size'])
        ids = draft['slots'][item['slot']]
        if kind == 'REMOVE_ITEM':
            if item['id'] not in ids:
                raise DomainError('NOT_IN_MEAL')
            ids.remove(item['id'])
        else:
            if item['id'] in ids:
                raise DomainError('DUPLICATE_ITEM')
            if len(ids) >= rules[item['slot']]['max']:
                raise DomainError('SLOT_FULL', {'slot': item['slot']})
            ids.append(item['id'])
    validate_state(result, menu)
    return result


def apply_response(state, raw, menu, *, authorization=None, mode="composition"):
    """Atomic batch: validate every action, then apply to a copy or reject all."""
    response = validate_response(raw, menu)
    validate_state(state, menu)
    from .action_policy import check_policy
    actions = response['actions']
    if any(a['type'] == 'CONFIRM_ORDER' for a in actions[:-1]):
        raise DomainError('CONFIRM_MUST_BE_FINAL')
    check_policy(state, actions, authorization, mode)
    candidate = deepcopy(state)
    for action in actions:
        candidate = apply_action(candidate, action, menu)
    return candidate
