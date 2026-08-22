from __future__ import annotations

import hmac


def is_authorized(authorization: str | None, api_key: str | None) -> bool:
    if api_key is None:
        return True
    if authorization is None:
        return False

    scheme, separator, supplied = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not supplied:
        return False
    return hmac.compare_digest(supplied, api_key)