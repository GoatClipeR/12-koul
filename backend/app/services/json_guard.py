"""Bounded JSON parsing shared by untrusted provider and action boundaries."""
import json
import math


class JSONGuardError(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise JSONGuardError('duplicate key')
        result[key] = value
    return result


def _constant(value):
    raise JSONGuardError('non-finite number')


def _integer(value):
    if len(value) > 128:
        raise JSONGuardError('numeric token too long')
    return int(value)


def _float(value):
    if len(value) > 128:
        raise JSONGuardError('numeric token too long')
    result = float(value)
    if not math.isfinite(result):
        raise JSONGuardError('non-finite number')
    return result


def safe_loads(raw, max_bytes=100_000, max_depth=16):
    if not isinstance(raw, (str, bytes)) or len(raw) > max_bytes:
        raise JSONGuardError('invalid type or size')
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    if len(raw.encode('utf-8')) > max_bytes:
        raise JSONGuardError('oversized JSON')
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > max_depth:
                raise JSONGuardError('JSON depth exceeded')
        elif char in ']}':
            depth -= 1
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=_constant,
                          parse_int=_integer, parse_float=_float)
    except (ValueError, RecursionError) as exc:
        raise JSONGuardError('invalid JSON') from exc
