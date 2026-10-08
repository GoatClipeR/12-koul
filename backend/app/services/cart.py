"""Application cart: independent validated meals; prices always come from menu."""
from copy import deepcopy
from .meal_engine import apply_action
from .price_engine import quote, price_cart
from .errors import DomainError
from .action_policy import check_policy
from ..schemas.actions import validate_response

MAX_LINES = 40


def add_line(lines, state, menu):
    if len(lines) >= MAX_LINES:
        raise DomainError('CART_FULL')
    pricing = quote(state, menu)
    if not pricing['orderable']:
        raise DomainError('INCOMPLETE_MEAL')
    # Line IDs belong to the application, never to the model.
    from uuid import uuid4
    lines.append({'id': uuid4().hex, 'state': deepcopy(state)})


def cart_view(lines, menu, confirmed=False):
    result = []
    for line in lines:
        pricing = quote(line['state'], menu)
        ids = [i for d in line['state']['categories'].values() for slot in d['slots'].values() for i in slot]
        result.append({'id': line['id'], 'meal_state': deepcopy(line['state']),
                       'quote': pricing, 'items': [menu.item(i) for i in ids]})
    total = price_cart([line['state'] for line in lines], menu)['total'] if lines else 0
    return {'lines': result, 'total': total, 'currency': 'MAD', 'confirmed': confirmed,
            'external_order_submitted': False}


def execute(state, lines, raw, menu, authorization=None, mode='composition'):
    response = validate_response(raw, menu)
    actions = response['actions']
    if any(a['type']=='CONFIRM_ORDER' for a in actions[:-1]):
        raise DomainError('CONFIRM_MUST_BE_FINAL')
    check_policy(state, actions, authorization, mode)
    candidate, cart = deepcopy(state), deepcopy(lines)
    confirmed = False
    for action in actions:
        kind = action['type']
        if kind == 'CONFIRM_ORDER':
            if 'drink' in candidate['categories'] and not candidate['categories']['drink']['slots']['drink']:
                del candidate['categories']['drink']
                if candidate['active_category']=='drink':
                    candidate['active_category']=next(iter(candidate['categories']),None)
            if candidate['categories']:
                quote_result = quote(candidate, menu)
                if not quote_result['orderable']:
                    raise DomainError('INCOMPLETE_MEAL')
            elif not cart:
                raise DomainError('CART_EMPTY')
            confirmed = True
            continue
        if kind == 'REMOVE_ITEM' and action['item_id'].startswith('drink.'):
            matches = [line for line in cart if action['item_id'] in line['state']['categories'].get('drink',{}).get('slots',{}).get('drink',[])]
            if len(matches) != 1:
                raise DomainError('AMBIGUOUS_CART_ITEM' if matches else 'NOT_IN_MEAL')
            cart.remove(matches[0]); continue
        if kind == 'CLEAR_MEAL':
            cart = []
        # Authorization was checked atomically against the original state above.
        candidate = apply_action(candidate, action, menu)
        if kind == 'ADD_ITEM' and menu.item(action['item_id'])['category']=='drink':
            draft = candidate['categories'].pop('drink')
            candidate['active_category'] = next(iter(candidate['categories']), None)
            add_line(cart, {'active_category':'drink','categories':{'drink':draft}}, menu)
            # A second ADD_ITEM drink in the same batch gets a fresh independent draft.
            candidate = apply_action(candidate, {'type':'SET_CATEGORY','category':'drink'}, menu)
    if 'drink' in candidate['categories'] and not candidate['categories']['drink']['slots']['drink']:
        del candidate['categories']['drink']
        if candidate['active_category']=='drink':
            candidate['active_category']=next(iter(candidate['categories']),None)
    return candidate, cart, confirmed


def command(state, lines, operation, menu, category=None, line_id=None):
    candidate, cart = deepcopy(state), deepcopy(lines)
    if operation == 'add':
        if category not in candidate['categories']:
            raise DomainError('NO_ACTIVE_MEAL')
        add_line(cart, {'active_category':category,'categories':{category:candidate['categories'][category]}}, menu)
        del candidate['categories'][category]
        if candidate['active_category']==category:
            candidate['active_category']=next(iter(candidate['categories']),None)
    elif operation == 'remove':
        found = next((line for line in cart if line['id']==line_id),None)
        if found is None:
            raise DomainError('NOT_IN_MEAL')
        cart.remove(found)
    elif operation == 'confirm':
        if candidate['categories']:
            raise DomainError('DRAFTS_NOT_IN_CART')
        if not cart:
            raise DomainError('CART_EMPTY')
        price_cart([line['state'] for line in cart],menu)
    else:
        raise DomainError('INVALID_REQUEST')
    return candidate, cart, operation=='confirm'
