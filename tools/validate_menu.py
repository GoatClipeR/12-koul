"""Validate the authoritative menu using the same validator as runtime startup."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.menu import MenuService
from backend.app.services.menu_validation import MenuValidationError

if __name__ == '__main__':
    try:
        menu = MenuService()
    except MenuValidationError as exc:
        print('ERROR', exc)
        sys.exit(1)
    data = menu.snapshot()
    print('INFO ', len(data['items']), 'items; all items validated at load time')
    print('OK    menu.json valid')
