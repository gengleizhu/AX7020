"""Authenticated payload helpers shared by management daemon and host SDK."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import time

MANAGEMENT_ABI = 0x00010000
ALGORITHMS = {
    1: "bcrypt8", 2: "descrypt8", 3: "md5crypt8",
    4: "sha256crypt8", 5: "sha512crypt4",
}


def load_key(value):
    if isinstance(value, (str, Path)):
        raw = Path(value).read_bytes().strip()
    elif isinstance(value, bytes):
        raw = value.strip()
    else:
        raise TypeError("management key must be bytes or a file path")
    try:
        text = raw.decode("ascii")
        key = bytes.fromhex(text) if len(text) == 64 else raw
    except (UnicodeDecodeError, ValueError):
        key = raw
    if len(key) < 32:
        raise ValueError("management key must contain at least 256 bits")
    return key


def _canonical(values):
    return json.dumps(values, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def encode(values, key, session, sequence):
    body = dict(values)
    body.update({
        "management_abi": MANAGEMENT_ABI,
        "session": session,
        "sequence": sequence,
    })
    body["hmac"] = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    return _canonical(body)


def decode(payload, key, session, sequence, *, max_age=None):
    try:
        values = json.loads(payload.decode("ascii"))
        supplied = values.pop("hmac")
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("invalid management payload") from exc
    if (values.get("management_abi") != MANAGEMENT_ABI or
            values.get("session") != session or values.get("sequence") != sequence):
        raise ValueError("management identity mismatch")
    expected = hmac.new(key, _canonical(values), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise PermissionError("management authentication failed")
    if max_age is not None:
        timestamp = values.get("timestamp")
        if not isinstance(timestamp, int) or abs(int(time.time()) - timestamp) > max_age:
            raise PermissionError("management request expired")
    return values
