"""Provider -> schema -> trusted action policy -> atomic engine -> safe presentation."""
from copy import deepcopy
from .errors import DomainError
from .llm.providers import ProviderError
from .llm.prompts import build_messages
from .meal_engine import apply_response
from .price_engine import quote
from .action_policy import action_kind, policy_context
from .presentation import presentation
from ..schemas.actions import validate_response


def run_turn(provider, menu, state, message, history=(), version='v3', *,
             authorization=None, mode='composition', locale='fr', compact_context=False, cart=None):
    raw = None
    response = None
    try:
        if locale not in ('fr', 'en') or mode not in ('composition', 'information'):
            raise DomainError('INVALID_POLICY')
        messages = build_messages(version, menu, state, message, history,
                                  policy=policy_context(state, authorization, mode))
        if cart is not None:
            import json
            prefix, encoded = messages[0]['content'].rsplit('\n', 1)
            context = json.loads(encoded)
            context['CART_CONTEXT'] = {'lines': cart, 'rules':
                'Independent cart enabled. Each ADD_ITEM drink creates a separate complete drink draft and immediately adds it to the cart. The next drink starts a fresh draft: never replace another drink. SET_CATEGORY drink before drink additions. REMOVE_ITEM of a cart drink needs exact ACTION_POLICY authorization; duplicate drinks require the UI line removal button. Food drafts are added to the cart by the application button. Cart prices and confirmation are managed by the application; never claim external order submission.'}
            messages[0]['content'] = prefix + '\n' + json.dumps(context, ensure_ascii=False)
        if compact_context:
            from .llm.production_context import compact_messages
            messages = compact_messages(messages)
        try:
            raw = provider.complete(messages)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError('PROVIDER_UNEXPECTED_ERROR') from None
        # Protocol requires bounded text; non-text objects must never enter diagnostics.
        if not isinstance(raw, str):
            raw = None
            raise ProviderError('PROVIDER_INVALID_RESPONSE')
        if len(raw) > 100_000:
            raw = None
            raise ProviderError('PROVIDER_RESPONSE_TOO_LARGE')
        response = validate_response(raw, menu)
        cart_result, confirmed = cart, False
        if cart is None:
            candidate = apply_response(state, response, menu, authorization=authorization, mode=mode)
        else:
            from .cart import execute
            candidate, cart_result, confirmed = execute(state, cart, response, menu, authorization, mode)
        pricing = quote(candidate, menu)
        return {'cart': cart_result, 'cart_confirmed': confirmed, 'accepted': True, 'response': response, 'raw_response': raw,
                'model_text_trusted': False, 'action_kind': action_kind(response['actions']),
                'display': presentation(candidate, pricing, response, menu, accepted=True, locale=locale),
                'state': candidate, 'quote': pricing, 'error': None}
    except (DomainError, ProviderError) as exc:
        return {'accepted': False, 'response': response, 'raw_response': raw,
                'model_text_trusted': False, 'action_kind': None,
                'display': presentation(state, None, None, menu, accepted=False, locale=locale),
                'state': deepcopy(state), 'quote': None,
                'error': exc.as_dict() if isinstance(exc, DomainError) else {'code': exc.code, 'details': exc.details}}
