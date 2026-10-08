import json
import unittest
from copy import deepcopy
from backend.app.services.menu import MenuService
from backend.app.services.errors import DomainError
from backend.app.services.meal_engine import create_meal, apply_action, apply_response, completeness, validate_state
from backend.app.services.price_engine import quote, price_cart
from backend.app.schemas.actions import validate_response, action_schema


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.menu = MenuService()

    def act(self, state, kind, **fields):
        return apply_action(state, {'type': kind, **fields}, self.menu)

    def draft(self, category, size=None, complete=False):
        state = self.act(create_meal(), 'SET_CATEGORY', category=category)
        if size:
            state = self.act(state, 'SET_SIZE', size=size)
        if complete:
            for slot, rule in self.menu.rules(category, size).items():
                for item in self.menu.items(category, slot)[:rule['min']]:
                    state = self.act(state, 'ADD_ITEM', item_id=item['id'])
        return state

    def rejects(self, code, state, kind, **fields):
        before = deepcopy(state)
        with self.assertRaises(DomainError) as cm:
            self.act(state, kind, **fields)
        self.assertEqual(cm.exception.code, code)
        self.assertEqual(state, before)

    def test_all_menu_items_can_be_added_and_removed(self):
        for item in self.menu.items():
            with self.subTest(item=item['id']):
                state = self.draft(item['category'], 'large' if item['category'] == 'salad' else None)
                added = self.act(state, 'ADD_ITEM', item_id=item['id'])
                self.assertEqual(self.act(added, 'REMOVE_ITEM', item_id=item['id']), state)
                self.assertNotEqual(state, added)

    def test_exact_salad_rules(self):
        expected = {'small': [1, 2, 1, 1], 'large': [2, 5, 3, 2]}
        for size, counts in expected.items():
            full = self.draft('salad', size, True)
            self.assertEqual(list(map(len, full['categories']['salad']['slots'].values())), counts)
            self.assertTrue(completeness(full, self.menu)['complete'])
            self.assertEqual(self.act(full, 'CONFIRM_ORDER'), full)
            for slot, ids in full['categories']['salad']['slots'].items():
                partial = self.act(full, 'REMOVE_ITEM', item_id=ids[0])
                self.assertFalse(completeness(partial, self.menu)['complete'])
                self.rejects('INCOMPLETE_MEAL', partial, 'CONFIRM_ORDER')
                extra = next(i for i in self.menu.items('salad', slot) if i['id'] not in ids)
                self.rejects('SLOT_FULL', full, 'ADD_ITEM', item_id=extra['id'])

    def test_size_conflict_and_safe_upsize(self):
        large = self.draft('salad', 'large', True)
        self.rejects('SIZE_CONFLICT', large, 'SET_SIZE', size='small')
        small = self.draft('salad', 'small', True)
        up = self.act(small, 'SET_SIZE', size='large')
        self.assertFalse(completeness(up, self.menu)['complete'])
        self.assertEqual(up['categories']['salad']['slots'], small['categories']['salad']['slots'])
        self.assertEqual(self.act(up, 'SET_SIZE', size='small'), small)

    def test_all_slot_limits(self):
        for category in self.menu.snapshot()['categories']:
            state = self.draft(category, 'large' if category == 'salad' else None)
            for slot, rule in self.menu.rules(category, state['categories'][category]['size']).items():
                items = self.menu.items(category, slot)
                for item in items[:rule['max']]:
                    state = self.act(state, 'ADD_ITEM', item_id=item['id'])
                    self.rejects('DUPLICATE_ITEM', state, 'ADD_ITEM', item_id=item['id'])
                if len(items) > rule['max']:
                    self.rejects('SLOT_FULL', state, 'ADD_ITEM', item_id=items[rule['max']]['id'])
            self.assertTrue(completeness(state, self.menu)['complete'])

    def test_required_and_optional_slots(self):
        for category in ('sandwich', 'plat', 'drink'):
            full = self.draft(category, complete=True)
            self.assertTrue(completeness(full, self.menu)['complete'])
            for ids in full['categories'][category]['slots'].values():
                if ids:
                    partial = self.act(full, 'REMOVE_ITEM', item_id=ids[0])
                    self.assertFalse(completeness(partial, self.menu)['complete'])
                    self.rejects('INCOMPLETE_MEAL', partial, 'CONFIRM_ORDER')

    def test_switch_preserves_and_clear_is_explicit(self):
        salad = self.draft('salad', 'small', True)
        mixed = self.act(salad, 'SET_CATEGORY', category='drink')
        self.assertEqual(mixed['categories']['salad'], salad['categories']['salad'])
        mixed = self.act(mixed, 'ADD_ITEM', item_id='drink.drink.orange')
        self.assertTrue(completeness(mixed, self.menu)['complete'])
        cleared = self.act(mixed, 'CLEAR_CATEGORY', category='salad')
        self.assertEqual(cleared['active_category'], 'drink')
        cleared = self.act(cleared, 'CLEAR_CATEGORY', category='drink')
        self.assertEqual(cleared, create_meal())
        self.assertEqual(self.act(mixed, 'CLEAR_MEAL'), create_meal())

    def test_invalid_transitions(self):
        empty = create_meal()
        self.rejects('NO_ACTIVE_MEAL', empty, 'ADD_ITEM', item_id='drink.drink.orange')
        self.rejects('CART_EMPTY', empty, 'CONFIRM_ORDER')
        salad = self.draft('salad')
        self.rejects('SIZE_REQUIRED', salad, 'ADD_ITEM', item_id='salad.base.lettuce')
        self.rejects('INVALID_SIZE', salad, 'SET_SIZE', size='huge')
        sandwich = self.draft('sandwich')
        self.rejects('SIZE_NOT_ALLOWED', sandwich, 'SET_SIZE', size='small')
        self.rejects('WRONG_CATEGORY', sandwich, 'ADD_ITEM', item_id='drink.drink.orange')
        self.rejects('UNKNOWN_ITEM', sandwich, 'ADD_ITEM', item_id='invented')
        self.rejects('NOT_IN_MEAL', sandwich, 'REMOVE_ITEM', item_id='sandwich.extra.egg')
        self.rejects('UNKNOWN_CATEGORY', empty, 'SET_CATEGORY', category='pizza')
        self.assertEqual(self.act(empty, 'RECOMMEND_ITEM', item_id='drink.drink.orange'), empty)

    def test_batch_atomicity(self):
        state = create_meal()
        for bad in ({'type': 'ADD_ITEM', 'item_id': 'unknown'},
                    {'type': 'ADD_ITEM', 'item_id': 'drink.drink.lemon'}):
            response = {'message': 'Proposition', 'actions': [
                {'type': 'SET_CATEGORY', 'category': 'drink'},
                {'type': 'ADD_ITEM', 'item_id': 'drink.drink.orange'}, bad]}
            with self.assertRaises(DomainError):
                apply_response(state, response, self.menu)
            self.assertEqual(state, create_meal())

    def test_strict_response_schema(self):
        invalid = [None, [], {}, {'message': '', 'actions': []},
            {'message': 'x', 'actions': [], 'price': 0},
            {'message': 'x', 'actions': {}}, {'message': 'x', 'actions': [None]},
            {'message': 'x', 'actions': [{'type': []}]},
            {'message': 'x', 'actions': [{'type': 'HACK'}]},
            {'message': 'x', 'actions': [{'type': 'SET_CATEGORY', 'category': []}]},
            {'message': 'x', 'actions': [{'type': 'ADD_ITEM'}]},
            {'message': 'x', 'actions': [{'type': 'ADD_ITEM', 'item_id': 'drink.drink.orange', 'price': 0}]},
            {'message': 'x', 'actions': [{'type': 'SET_SIZE', 'size': 'small', 'category': 'drink'}]},
            {'message': 'x', 'actions': [{'type': 'CLEAR_MEAL'}] * 65},
            '```json\n{}\n```', '{"message":"x","message":"y","actions":[]}']
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(DomainError):
                validate_response(raw, self.menu)
        schema = action_schema(self.menu)
        self.assertEqual(len(schema['properties']['actions']['items']['oneOf']), 8)
        self.assertFalse(schema['additionalProperties'])
        good = {'message': 'Bonjour', 'actions': [{'type': 'CLEAR_MEAL'}]}
        self.assertEqual(validate_response(json.dumps(good), self.menu), good)

    def test_forged_states_rejected_by_engine_and_pricing(self):
        valid = self.draft('drink', complete=True)
        mutations = []
        for edit in ('extra', 'duplicate', 'unknown', 'wrong_slot', 'size', 'active', 'type'):
            state = deepcopy(valid)
            draft = state['categories']['drink']
            if edit == 'extra': draft['price'] = 0
            if edit == 'duplicate': draft['slots']['drink'] *= 2
            if edit == 'unknown': draft['slots']['drink'] = ['unknown']
            if edit == 'wrong_slot': draft['slots'] = {'protein': ['drink.drink.orange']}
            if edit == 'size': draft['size'] = 'small'
            if edit == 'active': state['active_category'] = []
            if edit == 'type': draft['type'] = 'salad'
            mutations.append(state)
        for state in mutations:
            with self.subTest(state=state):
                for fn in (validate_state, quote):
                    with self.assertRaises(DomainError): fn(state, self.menu)

    def test_prices(self):
        for size, price in [('small', 35), ('large', 55)]:
            for complete in (False, True):
                q = quote(self.draft('salad', size, complete), self.menu)
                self.assertEqual(q['total'], price)
                self.assertEqual(q['orderable'], complete)
        self.assertIsNone(quote(self.draft('salad'), self.menu)['total'])
        self.assertEqual(quote(create_meal(), self.menu)['total'], 0)
        self.assertFalse(quote(create_meal(), self.menu)['orderable'])
        for category in ('sandwich', 'plat', 'drink'):
            for item in self.menu.items(category, 'drink' if category == 'drink' else 'protein'):
                state = self.draft(category, complete=True)
                slot = item['slot']
                old = state['categories'][category]['slots'][slot][0]
                state = self.act(state, 'REMOVE_ITEM', item_id=old)
                state = self.act(state, 'ADD_ITEM', item_id=item['id'])
                self.assertEqual(quote(state, self.menu)['total'], item['price'])
        sandwich = self.draft('sandwich', complete=True)
        initial = quote(sandwich, self.menu)['total']
        for item_id in ('sandwich.extra.egg', 'sandwich.extra.avocado'):
            sandwich = self.act(sandwich, 'ADD_ITEM', item_id=item_id)
        self.assertEqual(quote(sandwich, self.menu)['total'], initial + 12)
        self.assertFalse(quote(self.draft('plat'), self.menu)['orderable'])

    def test_cart_drinks_are_separate_lines(self):
        drink = self.draft('drink', complete=True)
        total = quote(drink, self.menu)['total']
        cart = price_cart([drink, drink], self.menu)
        self.assertEqual(len(cart['lines']), 2)
        self.assertEqual(cart['total'], total * 2)
        self.assertTrue(all(len(l['meal']['slots']['drink']) == 1 for l in cart['lines']))
        for states, code in [([], 'CART_EMPTY'), ([self.draft('salad', 'small')], 'INCOMPLETE_MEAL')]:
            with self.assertRaises(DomainError) as cm: price_cart(states, self.menu)
            self.assertEqual(cm.exception.code, code)

    def test_menu_defensive_access(self):
        self.assertEqual(len(self.menu.items()), 75)
        item = self.menu.item('drink.drink.orange')
        self.assertEqual(item['price'], 15)
        item['price'] = -100
        self.menu.snapshot()['categories'].clear()
        self.menu.category('salad')['sizes'].clear()
        self.assertEqual(self.menu.item('drink.drink.orange')['price'], 15)
        self.assertEqual(self.menu.rules('salad', 'small')['ingredient'], {'min': 2, 'max': 2})
        with self.assertRaises(DomainError): self.menu.items('salad', 'bread')
