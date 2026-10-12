import base64
import hmac
import struct
import time
from urllib.parse import parse_qs, urlparse

PERIOD = 30


def normalize_secret(secret: str) -> str:
    """Accepts a bare base32 secret (spaces/case ignored) or an otpauth:// URI."""
    secret = secret.strip()
    if secret.lower().startswith("otpauth://"):
        secret = parse_qs(urlparse(secret).query).get("secret", [""])[0]
    return "".join(secret.split()).upper()


def _key(secret: str) -> bytes:
    secret = normalize_secret(secret)
    return base64.b32decode(secret + "=" * (-len(secret) % 8))


def is_valid_secret(secret: str) -> bool:
    try:
        return len(_key(secret)) > 0
    except ValueError:
        return False


def seconds_remaining(now: float | None = None) -> float:
    return PERIOD - (time.time() if now is None else now) % PERIOD


def totp_code(secret: str, now: float | None = None) -> str:
    """RFC 6238 TOTP: HMAC-SHA1, 30s step, 6 digits."""
    counter = int((time.time() if now is None else now) // PERIOD)
    digest = hmac.digest(_key(secret), struct.pack(">Q", counter), "sha1")
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"
