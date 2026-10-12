from datetime import timedelta

from dataAccess.database.database import Website
from endpoints.models.website_model import EditWebsite


def _website() -> Website:
    return Website(
        url="u",
        success_url="s",
        name="n",
        username="a",
        password="p",
        custom_login_script="clickSubmitButton()",
        totp_secret="GEZDGNBVGY3TQOJQ",
        expiration_interval=timedelta(days=3),
        paused=False,
    )


def test_pause_only_keeps_script_secret_and_expiration():
    website = EditWebsite(paused=True).edit_existing_model(_website())

    assert website.paused
    assert website.custom_login_script == "clickSubmitButton()"
    assert website.totp_secret == "GEZDGNBVGY3TQOJQ"
    assert website.expiration_interval == timedelta(days=3)


def test_explicit_null_or_blank_clears():
    website = EditWebsite(
        paused=True,
        totp_secret="",
        custom_login_script=None,
        expiration_interval_minutes=None,
    ).edit_existing_model(_website())

    assert website.totp_secret is None
    assert website.custom_login_script is None
    assert website.expiration_interval is None


def test_explicit_values_are_set():
    website = EditWebsite(
        paused=True,
        totp_secret="gezd gnbv gy3t qojq",
        expiration_interval_minutes=60,
    ).edit_existing_model(_website())

    assert website.totp_secret == "GEZDGNBVGY3TQOJQ"
    assert website.expiration_interval == timedelta(minutes=60)
