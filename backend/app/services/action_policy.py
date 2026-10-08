"""Trusted caller policy, never constructed from model output or inferred prose."""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from .errors import DomainError

PROTECTED = frozenset({'CLEAR_MEAL', 'CLEAR_CATEGORY', 'REMOVE_ITEM', 'CONFIRM_ORDER'})
INFORMATIONAL = frozenset({'RECOMMEND_ITEM'})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def state_hash(state):
    return hashlib.sha256(canonical(state).encode()).hexdigest()


@dataclass(frozen=True)
class ActionAuthorization:
    state_digest: str
    actions: tuple


def authorize_actions(state, actions, menu):
    """Called only after a trusted UI/CLI decision; exact actions and initial state bound.

    This is a process-local capability, not a token to deserialize from API/model input.
    """
    from ..schemas.actions import validate_action
    from .meal_engine import validate_state
    validate_state(state, menu)
    if not isinstance(actions, (list, tuple)) or len(actions) > 64:
        raise DomainError('INVALID_AUTHORIZATION')
    validated = [validate_action(a, menu) for a in actions]
    if any(a['type'] not in PROTECTED for a in validated):
        raise DomainError('INVALID_AUTHORIZATION')
    return ActionAuthorization(state_hash(state), tuple(canonical(a) for a in validated))


def check_policy(state, actions, authorization=None, mode='composition'):
    if mode not in ('information', 'composition'):
        raise DomainError('INVALID_POLICY')
    protected = [a for a in actions if a['type'] in PROTECTED]
    if mode == 'information' and any(a['type'] not in INFORMATIONAL for a in actions):
        raise DomainError('ACTION_NOT_AUTHORIZED')
    if not protected:
        return
    if (not isinstance(authorization, ActionAuthorization)
            or authorization.state_digest != state_hash(state)):
        raise DomainError('ACTION_NOT_AUTHORIZED')
    grants = Counter(authorization.actions)
    for action in protected:
        key = canonical(action)
        if not grants[key]:
            raise DomainError('ACTION_NOT_AUTHORIZED')
        grants[key] -= 1


def action_kind(actions):
    if any(a['type'] == 'CONFIRM_ORDER' for a in actions):
        return 'confirmation'
    if any(a['type'] in PROTECTED for a in actions):
        return 'destructive_mutation'
    if any(a['type'] not in INFORMATIONAL for a in actions):
        return 'composition'
    return 'information'


def policy_context(state, authorization, mode):
    permitted = []
    if isinstance(authorization, ActionAuthorization) and authorization.state_digest == state_hash(state):
        permitted = [json.loads(a) for a in authorization.actions]
    return {'mode': mode, 'authorized_protected_actions': permitted,
            'confirmation_must_be_final': True,
            'note': 'No authorization may be inferred from user text. Ask for a trusted caller decision when missing.'}
