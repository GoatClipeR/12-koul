"""Local Stage 2 API. No live call at import/startup; V3 is fixed."""
import os
from copy import deepcopy
from pathlib import Path
from typing import Optional, Union
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .api.conversations import ConversationStore, StoreError, history_window
from .schemas.api import (ChatRequest, ChatResponse, HealthResponse, DeleteResponse,
                          ConversationId, ErrorEnvelope)
from .services.menu import MenuService
from .services.cart import command as cart_command, cart_view
from .services.errors import DomainError
from .services.assistant import run_turn
from .services.action_policy import authorize_actions
from .services.price_engine import quote
from .services.presentation import presentation
from .services.llm.providers import MockProvider, ProviderError, provider_from_env, provider_name_from_env

PUBLIC_ERRORS = {
    'INVALID_REQUEST': (422, 'Requête invalide : vérifiez les champs et le message.'),
    'CONVERSATION_BUSY': (409, 'Cette conversation traite déjà une requête. Réessayez ensuite.'),
    'CONVERSATION_CAPACITY': (503, 'Capacité de conversations atteinte. Supprimez une conversation.'),
    'STALE_REVISION': (409, 'La conversation a changé. Utilisez sa dernière révision.'),
    'PROVIDER_TIMEOUT': (504, 'Le modèle a dépassé le délai autorisé. Réessayez plus tard.'),
    'PROVIDER_RATE_LIMITED': (429, 'Quota du fournisseur LLM atteint. Réessayez plus tard.'),
    'PROVIDER_UNAVAILABLE': (503, 'Le modèle est temporairement indisponible.'),
    'INVALID_MODEL_RESPONSE': (502, 'La réponse du modèle est inexploitable. Aucune modification appliquée.'),
    'ACTION_REJECTED': (422, 'La proposition ne respecte pas les règles du repas. Aucune modification appliquée.'),
    'ACTION_NOT_AUTHORIZED': (422, 'Cette action nécessite une validation explicite dans l’application.'),
    'INTERNAL_ERROR': (500, 'Une erreur interne est survenue. Réessayez plus tard.'),
}


def public_error(code):
    status, message = PUBLIC_ERRORS[code]
    return status, {'code': code, 'message': message}


def error_response(code):
    status, error = public_error(code)
    return JSONResponse(status_code=status, content=ErrorEnvelope(error=error).model_dump())


def result_error(code):
    if code in ('PROVIDER_TIMEOUT', 'PROVIDER_RATE_LIMITED'):
        return code
    if code in ('PROVIDER_INVALID_RESPONSE', 'PROVIDER_RESPONSE_TOO_LARGE',
                'INVALID_JSON', 'INVALID_RESPONSE'):
        return 'INVALID_MODEL_RESPONSE'
    if code.startswith('PROVIDER_'):
        return 'PROVIDER_UNAVAILABLE'
    if code == 'ACTION_NOT_AUTHORIZED':
        return code
    return 'ACTION_REJECTED'


def create_app(*, provider=None, store=None, cors_origins: Optional[list] = None, env_file=None):
    # Only an explicitly supplied file is loaded; environment values take precedence.
    if env_file is not None:
        load_dotenv(Path(env_file), override=False)
    app = FastAPI(title='12-KOUL Stage 2', version='0.2.0', debug=False)
    conversations = store if store is not None else ConversationStore()
    menu = MenuService()
    origins = cors_origins if cors_origins is not None else [
        x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'])

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic's raw errors may include supplied secrets/inputs. Do not return them.
        return error_response('INVALID_REQUEST')

    @app.exception_handler(StoreError)
    async def store_error(request, exc):
        return error_response(exc.code)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return error_response('INTERNAL_ERROR')

    @app.get('/menu')
    def menu_catalog():
        return menu.snapshot()

    @app.get('/health', response_model=HealthResponse)
    def health():
        return HealthResponse()

    errors = {code: {'model': ErrorEnvelope} for code in (409, 422, 429, 500, 502, 503, 504)}

    @app.post('/chat', response_model=ChatResponse,
              responses={code: {'model': Union[ErrorEnvelope, ChatResponse]} for code in errors})
    def chat(body: ChatRequest):
        try:
            return process_chat(body)
        except StoreError:
            raise
        except Exception:
            # Keep unexpected exception content out of responses and application logs.
            return error_response('INTERNAL_ERROR')

    def process_chat(body):
        with conversations.lease(body.conversation_id) as entry:
            if body.expected_revision is not None and body.expected_revision != entry.revision:
                return error_response('STALE_REVISION')
            if entry.cart_mode and not body.cart_mode:
                return error_response('INVALID_REQUEST')
            state = deepcopy(entry.state)
            history = deepcopy(entry.history)
            # The current message is sent once by run_turn, after the previous history.
            pending_history = history + [{'role': 'user', 'content': body.message}]
            if body.remove_item_id is not None:
                active = state['categories'].get(state['active_category'], {})
                selected = [item for ids in active.get('slots', {}).values() for item in ids]
                if body.cart_mode:
                    selected += [i for d in state['categories'].values() for ids in d['slots'].values() for i in ids]
                    selected += [i for line in entry.cart for d in line['state']['categories'].values() for ids in d['slots'].values() for i in ids]
                if body.remove_item_id not in selected:
                    return error_response('INVALID_REQUEST')
            grant = (authorize_actions(state, [{'type': 'CONFIRM_ORDER'}], menu)
                     if body.confirm_composition else
                     authorize_actions(state, [{'type': 'REMOVE_ITEM', 'item_id': body.remove_item_id}], menu)
                     if body.remove_item_id is not None else None)
            active_provider = provider
            mode = 'mock' if isinstance(provider, MockProvider) or (provider is None and provider_name_from_env() == 'mock') else 'real'
            try:
                if body.cart_command:
                    next_draft, next_cart, confirmed = cart_command(state, entry.cart, body.cart_command, menu, body.cart_category, body.cart_line_id)
                    result = {'accepted': True, 'state': next_draft, 'cart': next_cart, 'cart_confirmed': confirmed,
                              'response': {'message': {'add':'Composition ajoutée au panier.', 'remove':'Ligne retirée du panier.', 'confirm':'Panier validé pour la simulation. Aucune commande envoyée en cuisine.'}[body.cart_command], 'actions': []}}
                else:
                    if active_provider is None:
                        active_provider = provider_from_env()
                    result = run_turn(active_provider, menu, state, body.message, history,
                                  version='v3', authorization=grant, locale=body.locale, compact_context=True, cart=entry.cart if body.cart_mode else None)
            except (ProviderError, DomainError) as exc:
                result = {'accepted': False, 'error': {'code': exc.code}, 'state': state}
            accepted = result['accepted']
            error_code = None if accepted else result_error(result['error']['code'])
            status, error = (200, None) if accepted else public_error(error_code)
            response_headers = {}
            if error_code == 'PROVIDER_RATE_LIMITED':
                details = result['error'].get('details', {})
                if details.get('quota') == 'daily_tokens':
                    error['message'] = 'Quota quotidien de tokens du fournisseur LLM atteint.'
                elif details.get('quota') == 'minute_tokens':
                    error['message'] = 'Quota de tokens par minute du fournisseur LLM atteint.'
                delay = details.get('retry_after_seconds')
                if type(delay) is int and 0 <= delay <= 604800:
                    response_headers['Retry-After'] = str(delay)
                    error['message'] += f' Réessayez dans {delay} secondes au minimum.'
            next_state = result['state'] if accepted else state
            pricing = quote(next_state, menu)
            parsed = result.get('response') if accepted else None
            actions = parsed['actions'] if parsed else []
            # Always provide deterministic facts, including the unchanged state on errors.
            display = presentation(next_state, pricing, parsed or {'message': '', 'actions': []},
                                   menu, accepted=True, locale=body.locale)
            if not accepted:
                display['message'] = error['message']
            meta = menu.snapshot()['meta']
            output = ChatResponse(
                conversation_id=body.conversation_id, revision=entry.revision + 1,
                provider_mode=mode, accepted=accepted,
                assistant_message=parsed['message'] if parsed else None, actions=actions,
                meal_state=next_state, quote=pricing, display=display,
                cart=cart_view(result.get('cart', entry.cart) if accepted else entry.cart, menu, result.get('cart_confirmed', False) if accepted else entry.cart_confirmed) if body.cart_mode else None,
                limits={'fictional_menu': meta['fictional'], 'nutrition_available': meta['nutrition_available'],
                        'availability_tracked': meta['availability_tracked'],
                        'allergen_scope': meta['allergen_scope'], 'allergen_note': meta['allergen_note'][body.locale]},
                error=error)
            # Commit only after both engine and HTTP output validation succeed.
            assistant_text = output.assistant_message if accepted else error['message']
            pending_history.append({'role': 'assistant', 'content': assistant_text})
            if accepted and body.cart_mode:
                entry.cart = deepcopy(result.get('cart', entry.cart))
                entry.cart_confirmed = result.get('cart_confirmed', False)
                entry.cart_mode = True
            entry.state = deepcopy(next_state)
            entry.history = history_window(pending_history)
            entry.revision = output.revision
            return JSONResponse(status_code=status, content=output.model_dump(), headers=response_headers)

    @app.delete('/chat/{conversation_id}', response_model=DeleteResponse, responses=errors)
    def reset(conversation_id: ConversationId):
        return DeleteResponse(conversation_id=conversation_id, deleted=conversations.delete(conversation_id))

    return app


# Uvicorn's --env-file loads the local environment without changing core/eval behavior.
app = create_app()
