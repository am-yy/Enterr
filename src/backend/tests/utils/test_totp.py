import pytest

from utils.totp import is_valid_secret, normalize_secret, totp_code

# RFC 6238 test secret "12345678901234567890"; 6-digit truncation of the SHA1 vectors.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


@pytest.mark.parametrize(
    "now, code",
    [(59, "287082"), (1111111109, "081804"), (1234567890, "005924")],
)
def test_totp_rfc6238_vectors(now, code):
    assert totp_code(RFC_SECRET, now) == code


def test_secret_normalization():
    spaced = "gezd gnbv gy3t qojq gezd gnbv gy3t qojq"
    uri = f"otpauth://totp/Site:alice?secret={RFC_SECRET}&issuer=Site"
    assert normalize_secret(spaced) == normalize_secret(uri) == RFC_SECRET
    assert totp_code(spaced, 59) == "287082"


@pytest.mark.parametrize("secret", ["", "not base32!", "otpauth://totp/x?issuer=y"])
def test_invalid_secret(secret):
    assert not is_valid_secret(secret)
