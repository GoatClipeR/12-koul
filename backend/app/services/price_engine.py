"""Integer MAD quotes; invalid states raise, incomplete states are estimates."""
from copy import deepcopy
from .meal_engine import completeness, validate_state
from .errors import DomainError


def quote(state, menu):
    validate_state(state, menu)
    lines = []
    for category, draft in state['categories'].items():
        spec = menu.category(category)
        if spec['pricing']['model'] == 'size_price':
            amount = None if draft['size'] is None else spec['sizes'][draft['size']]['price']
        elif spec['pricing']['model'] == 'item_sum':
            amount = sum(menu.item(i)['price'] for ids in draft['slots'].values() for i in ids)
        else:
            raise DomainError('UNKNOWN_PRICING_MODEL')
        line_state = {'active_category': category, 'categories': {category: draft}}
        lines.append({'category': category, 'meal': deepcopy(draft), 'amount': amount,
                      'complete': completeness(line_state, menu)['complete']})
    status = completeness(state, menu)
    return {'currency': menu.snapshot()['meta']['currency'], 'lines': lines,
            'total': None if any(l['amount'] is None for l in lines)
            else sum(l['amount'] for l in lines), 'orderable': status['complete'],
            'missing': status['missing']}


def price_cart(states, menu):
    """Multiple independent meals, including repeated drinks as separate lines."""
    if not states:
        raise DomainError('CART_EMPTY')
    quotes = [quote(state, menu) for state in states]
    if not all(q['orderable'] for q in quotes):
        raise DomainError('INCOMPLETE_MEAL')
    return {'currency': menu.snapshot()['meta']['currency'],
            'lines': [line for q in quotes for line in q['lines']],
            'total': sum(q['total'] for q in quotes)}
