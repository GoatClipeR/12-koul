"""Bounded provider boundary. Redirects are disabled for authenticated requests."""
import json
import math
import os
import socket
import threading
import queue
import time
from copy import deepcopy
from http.client import HTTPException
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from ..json_guard import safe_loads


class ProviderError(RuntimeError):
    def __init__(self, code, details=None):
        self.code, self.details = code, details or {}
        super().__init__(code)


class Provider(Protocol):
    def complete(self, messages):
        ...


class MockProvider:
    def __init__(self, response=None):
        self.response = response if response is not None else {
            'message': 'Bienvenue chez 12-KOUL ! Que souhaitez-vous composer ?', 'actions': []}
        self.calls = []

    def complete(self, messages):
        self.calls.append(deepcopy(messages))
        return self.response if isinstance(self.response, str) else json.dumps(self.response, ensure_ascii=False)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if fp is not None:
            fp.close()
        raise ProviderError('PROVIDER_REDIRECT_BLOCKED', {'http_status': code})


def http_transport(url, payload, headers, timeout):
    if urlparse(url).scheme != 'https':
        raise ProviderError('PROVIDER_CONFIGURATION')
    # Identify the application explicitly: Groq rejected urllib's default client with HTTP 403.
    request = Request(url, data=json.dumps(payload).encode(),
                      headers={'User-Agent': '12-KOUL/0.3', **headers}, method='POST')
    # No default opener: all redirects, including same-origin redirects, are rejected.
    with build_opener(NoRedirects()).open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ProviderError('PROVIDER_HTTP_ERROR', {'http_status': response.status})
        deadline, body = time.monotonic() + timeout, bytearray()
        while len(body) <= 1_000_000:
            if time.monotonic() >= deadline:
                raise ProviderError('PROVIDER_TIMEOUT')
            chunk = response.read1(min(65536, 1_000_001 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if len(body) > 1_000_000:
            raise ProviderError('PROVIDER_RESPONSE_TOO_LARGE')
        return safe_loads(bytes(body), max_bytes=1_000_000, max_depth=24)


# A caller deadline also covers DNS, slow bodies and injected transports. Python
# cannot forcibly kill a blocked thread. At most four transport calls can remain
# outstanding; saturation fails closed and no unbounded work queue is created.
_TRANSPORT_SLOTS = threading.BoundedSemaphore(4)


def deadline_call(fn, args, timeout):
    slots = _TRANSPORT_SLOTS
    if not slots.acquire(blocking=False):
        raise ProviderError('PROVIDER_BUSY')
    result = queue.Queue(maxsize=1)
    def worker():
        try:
            result.put((True, fn(*args)))
        except Exception as exc:
            result.put((False, exc))
        finally:
            slots.release()
    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception:
        slots.release()
        raise ProviderError('PROVIDER_UNAVAILABLE') from None
    try:
        success, value = result.get(timeout=timeout)
    except queue.Empty:
        raise ProviderError('PROVIDER_TIMEOUT') from None
    if not success:
        raise value
    return value


class CompatibleProvider:
    def __init__(self, *, api_key, model, base_url, timeout=20, max_retries=1,
                 transport=http_transport, overall_timeout=30):
        try:
            parsed = urlparse(base_url)
            valid = (isinstance(api_key, str) and api_key.strip() and isinstance(model, str)
                     and model.strip() and parsed.scheme == 'https' and parsed.hostname
                     and not parsed.username and not parsed.password and not parsed.query
                     and not parsed.fragment and (parsed.port is None or 0 < parsed.port <= 65535))
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise ProviderError('PROVIDER_CONFIGURATION')
        if any(type(t) not in (int, float) or not math.isfinite(t) or not 0 < t <= 120
               for t in (timeout, overall_timeout)):
            raise ProviderError('PROVIDER_CONFIGURATION')
        if type(max_retries) is not int or not 0 <= max_retries <= 3:
            raise ProviderError('PROVIDER_CONFIGURATION')
        self._api_key = api_key
        self.model, self.base_url = model, base_url.rstrip('/')
        self.timeout, self.max_retries, self.transport = timeout, max_retries, transport
        self.overall_timeout = overall_timeout

    def complete(self, messages):
        payload = {'model': self.model, 'messages': deepcopy(messages),
                   'temperature': 0, 'response_format': {'type': 'json_object'}}
        deadline = time.monotonic() + self.overall_timeout
        for attempt in range(self.max_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderError('PROVIDER_TIMEOUT')
            budget = min(self.timeout, remaining)
            details = {'attempts': attempt + 1}
            try:
                data = deadline_call(self.transport, (self.base_url + '/chat/completions', payload,
                    {'Authorization': 'Bearer ' + self._api_key, 'Content-Type': 'application/json'}, budget), budget)
                if time.monotonic() >= deadline:
                    raise ProviderError('PROVIDER_TIMEOUT')
                content = data['choices'][0]['message']['content']
                if not isinstance(content, str):
                    raise ValueError('content must be text')
                if len(content) > 100_000:
                    raise ProviderError('PROVIDER_RESPONSE_TOO_LARGE')
                return content
            except ProviderError as exc:
                if exc.code != 'PROVIDER_TIMEOUT':
                    raise
                code, retryable = exc.code, False  # timed-out work may still be unwinding
            except HTTPError as exc:
                details['http_status'] = exc.code
                code = 'PROVIDER_REDIRECT_BLOCKED' if 300 <= exc.code < 400 else 'PROVIDER_HTTP_ERROR'
                retryable = exc.code >= 500
                if exc.code == 429:
                    # Retrying after 100 ms cannot resolve a provider quota. Preserve
                    # only safe metadata; raw bodies and credentials never reach clients.
                    code = 'PROVIDER_RATE_LIMITED'
                    try:
                        seconds = float((exc.headers or {}).get('retry-after', ''))
                        if math.isfinite(seconds) and 0 <= seconds <= 604800:
                            details['retry_after_seconds'] = math.ceil(seconds)
                    except (ValueError, TypeError):
                        pass
                    try:
                        if exc.fp is not None:
                            body = safe_loads(exc.read(16384), max_bytes=16384, max_depth=8)
                            message = body.get('error', {}).get('message', '')
                            if isinstance(message, str):
                                if 'tokens per day' in message:
                                    details['quota'] = 'daily_tokens'
                                elif 'tokens per minute' in message:
                                    details['quota'] = 'minute_tokens'
                    except Exception:
                        pass  # A malformed error body must still produce HTTP 429.

                if exc.fp is not None:
                    try:
                        exc.fp.close()
                    except Exception:
                        pass  # cleanup must not replace the original structured failure
            except (TimeoutError, socket.timeout):
                code, retryable = 'PROVIDER_TIMEOUT', True
            except URLError as exc:
                code = 'PROVIDER_TIMEOUT' if isinstance(exc.reason, (TimeoutError, socket.timeout)) else 'PROVIDER_UNAVAILABLE'
                retryable = True
            except (OSError, ConnectionError):
                code, retryable = 'PROVIDER_UNAVAILABLE', True
            except (HTTPException, ValueError, KeyError, IndexError, TypeError, RecursionError):
                code, retryable = 'PROVIDER_INVALID_RESPONSE', False
            except Exception:
                code, retryable = 'PROVIDER_UNEXPECTED_ERROR', False
            if not retryable or attempt == self.max_retries:
                raise ProviderError(code, details) from None
            delay = min(0.1 * 2 ** attempt, 1.0)
            if time.monotonic() + delay >= deadline:
                raise ProviderError('PROVIDER_TIMEOUT', details)
            time.sleep(delay)


def provider_name_from_env():
    # An explicit offline mode is honored; missing selection uses the available key.
    configured = os.getenv('LLM_PROVIDER', '').strip()
    return configured or ('groq' if os.getenv('GROQ_API_KEY', '').strip() else 'mock')


def provider_from_env():
    name = provider_name_from_env()
    if name == 'mock':
        return MockProvider()
    if name not in ('groq', 'compatible'):
        raise ProviderError('PROVIDER_CONFIGURATION')
    try:
        return CompatibleProvider(
            api_key=os.getenv('GROQ_API_KEY' if name == 'groq' else 'LLM_API_KEY', ''),
            model=os.getenv('LLM_MODEL', ''), base_url=os.getenv('LLM_BASE_URL', ''),
            timeout=float(os.getenv('LLM_TIMEOUT_SECONDS', '20')),
            overall_timeout=float(os.getenv('LLM_OVERALL_TIMEOUT_SECONDS', '30')),
            max_retries=int(os.getenv('LLM_MAX_RETRIES', '1')))
    except ValueError:
        raise ProviderError('PROVIDER_CONFIGURATION') from None
