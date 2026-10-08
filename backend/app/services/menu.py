"""Read-only menu access; all returned structures are defensive copies."""
from copy import deepcopy
from pathlib import Path
from .errors import DomainError
from .json_guard import safe_loads
from .menu_validation import validate_menu, MenuValidationError

MENU_PATH = Path(__file__).resolve().parents[1] / 'data/menu.json'


class MenuService:
    def __init__(self, path=MENU_PATH):
        try:
            with Path(path).open('rb') as source:
                self._data = validate_menu(safe_loads(source.read(1_000_001), max_bytes=1_000_000))
        except (OSError, ValueError) as exc:
            raise MenuValidationError('Invalid menu: ' + str(exc)) from exc
        self._items = {item['id']: item for item in self._data['items']}
        if len(self._items) != len(self._data['items']):
            raise ValueError('Duplicate menu IDs')

    def snapshot(self):
        return deepcopy(self._data)

    def category(self, category):
        if not isinstance(category, str) or category not in self._data['categories']:
            raise DomainError('UNKNOWN_CATEGORY')
        return deepcopy(self._data['categories'][category])

    def item(self, item_id):
        if not isinstance(item_id, str) or item_id not in self._items:
            raise DomainError('UNKNOWN_ITEM')
        return deepcopy(self._items[item_id])

    def items(self, category=None, slot=None):
        if category is not None:
            spec = self.category(category)
            if slot is not None and slot not in spec['slot_order']:
                raise DomainError('UNKNOWN_SLOT')
        return [deepcopy(i) for i in self._items.values()
                if (category is None or i['category'] == category)
                and (slot is None or i['slot'] == slot)]

    def rules(self, category, size=None):
        spec = self.category(category)
        if spec['requires_size']:
            if size is None:
                raise DomainError('SIZE_REQUIRED')
            if not isinstance(size, str) or size not in spec['sizes']:
                raise DomainError('INVALID_SIZE')
            return spec['sizes'][size]['slots']
        if size is not None:
            raise DomainError('SIZE_NOT_ALLOWED')
        return spec['slots']
