from __future__ import annotations

import hashlib
import hmac
import time


def _signature_payload(body: bytes, timestamp: str | None) -> bytes:
    if timestamp:
        return f"{timestamp}.".encode("utf-8") + body
    return body


def compute_hmac_signature(
    secret: str,
    body: bytes,
    timestamp: str | None = None,
    algorithm: str = "sha256",
) -> str:
    """Return a provider-style HMAC header value such as ``sha256=abc``.

    Webhook verification must use ``hmac.compare_digest`` and the exact raw
    request body. Parsing JSON before verification is a security footgun because
    key ordering or whitespace changes would alter the bytes being signed.
    """

    if algorithm != "sha256":
        raise ValueError("Only sha256 signatures are supported in the MVP")

    digest = hmac.new(
        secret.encode("utf-8"),
        _signature_payload(body, timestamp),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _candidate_values(signature_header: str) -> list[str]:
    candidates: list[str] = []
    for part in signature_header.split(","):
        value = part.strip()
        if not value:
            continue
        candidates.append(value)
        if "=" in value:
            candidates.append(value.split("=", 1)[1])
    return candidates


def _signature_fields(signature_header: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in signature_header.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def verify_hmac_signature(
    secret: str,
    body: bytes,
    signature_header: str | None,
    timestamp_header: str | None = None,
    tolerance_seconds: int = 300,
    now: float | None = None,
    require_timestamp: bool = False,
) -> bool:
    """Validate an inbound webhook signature.

    ``timestamp_header`` is optional for broad provider compatibility. When it is
    present, or ``require_timestamp`` is true, the verifier rejects stale payloads
    to reduce replay risk. Production deployments should require timestamps when
    their webhook provider supports them.
    """

    if not secret or not signature_header:
        return False

    fields = _signature_fields(signature_header)
    effective_timestamp = timestamp_header or fields.get("t")

    if effective_timestamp:
        try:
            timestamp = float(effective_timestamp)
        except ValueError:
            return False
        current_time = now if now is not None else time.time()
        if abs(current_time - timestamp) > tolerance_seconds:
            return False
    elif require_timestamp:
        return False

    expected = compute_hmac_signature(secret, body, effective_timestamp)
    expected_digest = expected.split("=", 1)[1]
    return any(
        hmac.compare_digest(candidate, expected)
        or hmac.compare_digest(candidate, expected_digest)
        for candidate in _candidate_values(signature_header)
    )
