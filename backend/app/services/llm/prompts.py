import json
from pathlib import Path
from ...schemas.actions import action_schema
from ..errors import DomainError
from ..meal_engine import validate_state

PROMPT_DIR = Path(__file__).resolve().parents[2] / 'prompts'


def build_messages(version, menu, state, message, history=(), *, policy=None):
    if version not in ('v1', 'v2', 'v3'):
        raise DomainError('UNKNOWN_PROMPT')
    if not isinstance(message, str) or not 1 <= len(message) <= 1000:
        raise DomainError('INVALID_MESSAGE')
    if not isinstance(history, (list, tuple)) or len(history) > 40:
        raise DomainError('INVALID_HISTORY')
    clean_history = []
    total_chars = 0
    for turn in history:
        if (not isinstance(turn, dict) or set(turn) != {'role', 'content'}
                or turn['role'] not in ('user', 'assistant')
                or not isinstance(turn['content'], str) or len(turn['content']) > 4000):
            raise DomainError('INVALID_HISTORY')
        total_chars += len(turn['content'])
        if total_chars > 16000:
            raise DomainError('HISTORY_TOO_LARGE')
        clean_history.append(dict(turn))
    validate_state(state, menu)
    prompt = (PROMPT_DIR / ('prompt_' + version + '.txt')).read_text(encoding='utf-8')
    context = {'MENU_CONTEXT': menu.snapshot(), 'MEAL_STATE': state,
               'ACTION_SCHEMA': action_schema(menu), 'ACTION_POLICY': policy or {
                   'mode': 'composition', 'authorized_protected_actions': [], 'confirmation_must_be_final': True}}
    return [{'role': 'system', 'content': prompt + '\n' + json.dumps(context, ensure_ascii=False)},
            *clean_history[-40:], {'role': 'user', 'content': message}]
