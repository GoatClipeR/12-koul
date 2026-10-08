"""Single validator for startup and the menu validation CLI.

Approved composition constants are contract assertions, not a second item catalogue.
"""
from collections import Counter

SALAD = {'small': {'base': 1, 'ingredient': 2, 'topping': 1, 'sauce': 1},
         'large': {'base': 2, 'ingredient': 5, 'topping': 3, 'sauce': 2}}
OTHER = {'sandwich': {'bread': (1, 1), 'protein': (1, 1), 'cheese': (0, 1),
                     'vegetable': (0, 3), 'sauce': (1, 1), 'extra': (0, 2)},
         'plat': {'protein': (1, 1), 'side': (1, 1), 'sauce': (1, 1)},
         'drink': {'drink': (1, 1)}}


class MenuValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise MenuValidationError(message)


def integer(value):
    return type(value) is int and value >= 0


def names(value):
    return isinstance(value, dict) and all(isinstance(value.get(k), str) and value[k].strip()
                                          for k in ('fr', 'en'))


def validate_menu(data):
    try:
        _validate(data)
    except MenuValidationError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise MenuValidationError('Malformed menu structure') from exc
    return data


def _validate(data):
    require(isinstance(data, dict), 'Menu must be an object')
    meta, categories, items = data['meta'], data['categories'], data['items']
    require(isinstance(meta, dict) and isinstance(categories, dict), 'Invalid menu metadata/categories')
    require(all(isinstance(meta.get(k), str) and meta[k].strip() for k in ('restaurant','slogan','schema_version')), 'Missing menu identity')
    require(meta['languages'] == ['fr','en'] and meta['default_language'] == 'fr'
            and type(meta['fictional']) is bool, 'Invalid menu language/fiction metadata')
    scope = meta['allergen_scope']
    require(meta['currency'] == 'MAD', 'Currency must be MAD')
    require(isinstance(scope, list) and len(scope) == 5 and
            set(scope) == {'dairy', 'nuts', 'gluten', 'eggs', 'sesame'}, 'Invalid allergen scope')
    require(meta['nutrition_available'] is False and meta['availability_tracked'] is False,
            'Unsupported nutrition or availability metadata')
    require(names(meta['allergen_note']), 'Missing allergen limitations')
    require(all(meta['rules'][k] is True for k in ('no_duplicates_within_slot',
        'exact_when_min_equals_max', 'incomplete_meal_cannot_be_ordered')), 'Invalid menu rules')
    require(set(categories) == {'salad', 'sandwich', 'plat', 'drink'}, 'Invalid categories')
    require(isinstance(items, list) and 0 < len(items) <= 1000, 'Invalid item collection')
    counts, ids = Counter(), set()
    for category, spec in categories.items():
        require(names(spec['name']), 'Missing category names')
        require(spec['requires_size'] is (category == 'salad'), 'Invalid size requirement')
        require(spec['pricing']['model'] == ('size_price' if category == 'salad' else 'item_sum'),
                'Invalid pricing model')
        expected_slots = list(SALAD['small'] if category == 'salad' else OTHER[category])
        require(spec['slot_order'] == expected_slots, 'Invalid slot order')
        require(set(spec['slot_labels']) == set(expected_slots) and
                all(names(v) for v in spec['slot_labels'].values()), 'Invalid slot labels')
        if category == 'salad':
            require(set(spec['sizes']) == set(SALAD), 'Invalid salad sizes')
            for size, counts_expected in SALAD.items():
                size_spec = spec['sizes'][size]
                require(integer(size_spec['price']) and size_spec['price'] == {'small':35,'large':55}[size],
                        'Invalid salad price')
                require(names(size_spec['name']), 'Invalid size name')
                _slots(size_spec['slots'], {s:(n,n) for s,n in counts_expected.items()})
        else:
            _slots(spec['slots'], OTHER[category])
    for item in items:
        item_id, category, slot = item['id'], item['category'], item['slot']
        require(isinstance(item_id, str) and item_id and item_id not in ids, 'Invalid or duplicate item ID')
        ids.add(item_id)
        require(category in categories and slot in categories[category]['slot_order'], 'Invalid item category/slot')
        require(item_id.startswith(category + '.' + slot + '.'), 'Item ID/category mismatch')
        require(names(item['name']), 'Invalid item names')
        require(integer(item['price']), 'Invalid item price')
        price = item['price']
        if category == 'salad' or (category == 'sandwich' and slot not in ('protein','extra')) or (category == 'plat' and slot != 'protein'):
            require(price == 0, 'Included selection must have zero component price')
        if category == 'sandwich' and slot == 'protein': require(35 <= price <= 50, 'Sandwich price outside approved range')
        if category == 'plat' and slot == 'protein': require(50 <= price <= 65, 'Plat price outside approved range')
        if category == 'drink': require(8 <= price <= 18, 'Drink price outside approved range')
        allergens = item['allergens']
        require(isinstance(allergens, list) and all(isinstance(a,str) for a in allergens)
                and len(allergens) == len(set(allergens)) and set(allergens) <= set(scope), 'Invalid allergens')
        require(type(item['spice']) is int and 0 <= item['spice'] <= 3, 'Invalid spice')
        require(type(item['vegan']) is bool and type(item['vegetarian']) is bool, 'Invalid diet flags')
        require(not item['vegan'] or (item['vegetarian'] and not set(allergens) & {'dairy','eggs'}), 'Contradictory vegan data')
        require(isinstance(item['tags'], list) and all(isinstance(t,str) for t in item['tags']), 'Invalid tags')
        require(item['asset'] is None or isinstance(item['asset'], str), 'Invalid asset key')
        counts[category, slot] += 1
    for category, spec in categories.items():
        rulesets = [v['slots'] for v in spec['sizes'].values()] if category == 'salad' else [spec['slots']]
        for rules in rulesets:
            for slot, rule in rules.items():
                require(counts[category, slot] >= rule['max'], 'Insufficient items to fill slot')


def _slots(actual, expected):
    require(set(actual) == set(expected), 'Invalid slots')
    for slot, (minimum, maximum) in expected.items():
        rule = actual[slot]
        require(set(rule) == {'min','max'} and integer(rule['min']) and integer(rule['max'])
                and rule == {'min':minimum,'max':maximum}, 'Invalid composition rule: ' + slot)
