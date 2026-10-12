import pytest

from execution.login.constants import LoginStatusCode
from execution.login.find_form_automatically import XPaths
from execution.login.login import login

URL = "https://example.com/login"
SUCCESS_URL = "https://example.com/home"


@pytest.fixture(autouse=True)
def short_timeout(mocker):
    mocker.patch("execution.login.login.TIMEOUT", 2)


@pytest.fixture
def driver_cls(mocker):
    return mocker.patch("execution.login.login.DomInteractionDriver")


@pytest.fixture
def driver(driver_cls):
    driver = driver_cls.return_value.__enter__.return_value
    driver.find_element.return_value = True
    driver.get_current_url.return_value = SUCCESS_URL
    return driver


@pytest.fixture
def form_finder(mocker):
    finder = mocker.patch("execution.login.login.LoginFormFinder")
    finder.return_value.find_login_automatically.return_value = XPaths(
        "//input[@id='user']", "//input[@id='pass']", "//button"
    )
    return finder.return_value


TOTP_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def _login(custom_login_script=None, totp_secret=None):
    return login(
        url=URL,
        success_url=SUCCESS_URL,
        username="alice",
        password="secret",
        custom_login_script=custom_login_script,
        screenshot_id="screenshot-id",
        totp_secret=totp_secret,
    )


def test_login_success_with_automatic_form_detection(driver_cls, driver, form_finder):
    assert _login() == (LoginStatusCode.SUCCESS, None)

    driver_cls.assert_called_once_with(url=URL)
    driver.fill_text.assert_any_call("//input[@id='user']", "alice")
    driver.fill_text.assert_any_call("//input[@id='pass']", "secret")
    driver.click_button.assert_called_once_with("//button")
    driver.open_url.assert_called_once_with(SUCCESS_URL)
    driver.save_screenshot.assert_called_with("screenshot-id")


def test_login_username_field_not_found(driver, form_finder):
    form_finder.find_login_automatically.return_value = XPaths(
        None, "//input[@id='pass']", "//button"
    )

    assert _login() == (LoginStatusCode.USERNAME_FIELD_NOT_FOUND, None)

    driver.fill_text.assert_not_called()
    driver.save_screenshot.assert_called_once_with("screenshot-id")


def test_login_form_not_detected(driver, form_finder):
    form_finder.find_login_automatically.return_value = None

    assert _login() == (LoginStatusCode.USERNAME_FIELD_NOT_FOUND, None)


def test_login_xpath_not_present_on_page(driver, form_finder):
    driver.find_element.side_effect = lambda xpath: xpath != "//button"

    assert _login() == (LoginStatusCode.SUBMIT_BUTTON_NOT_FOUND, None)


def test_login_success_url_did_not_match(driver, form_finder):
    driver.get_current_url.return_value = URL

    assert _login() == (
        LoginStatusCode.SUCCESS_URL_DID_NOT_MATCH,
        f'Expected: "{SUCCESS_URL}", Found: "{URL}"',
    )


def test_login_driver_error_during_interaction(driver, form_finder):
    driver.open_url.side_effect = RuntimeError("browser crashed")

    assert _login() == (LoginStatusCode.UNKNOWN_EXECUTION_ERROR, None)
    driver.disconnect_driver.assert_called_once()
    driver.save_screenshot.assert_called_with("screenshot-id")


def test_login_driver_cannot_start(driver_cls):
    driver_cls.side_effect = RuntimeError("no browser")

    assert _login() == (LoginStatusCode.UNKNOWN_EXECUTION_ERROR, None)


def test_login_custom_script(driver, form_finder):
    script = """
    fillUsername()
    fillPassword()
    clickButton("//button[@id='next']")
    """

    assert _login(script) == (LoginStatusCode.SUCCESS, None)
    driver.click_button.assert_called_once_with("//button[@id='next']")


def test_login_custom_script_button_not_found(driver, form_finder):
    driver.click_button.side_effect = Exception("not found")

    assert _login('clickButton("//missing")') == (
        LoginStatusCode.BUTTON_NOT_FOUND,
        'XPath "//missing" not found on page.',
    )
    driver.open_url.assert_not_called()


@pytest.fixture(autouse=True)
def no_totp_wait(mocker):
    mocker.patch(
        "execution.login.custom_login.custom_login_methods_driver.seconds_remaining",
        return_value=30,
    )


def test_login_default_script_fills_totp_when_field_appears(driver, form_finder, mocker):
    # No OTP field on the login form; one appears after the first submit.
    mocker.patch("execution.login.login.compare_urls", side_effect=[False, True])
    mocker.patch(
        "execution.login.custom_login.custom_login_methods_driver.LoginFormFinder",
        return_value=form_finder,
    )
    form_finder.find_totp_field.side_effect = [None, "//input[@id='otp']", "//input[@id='otp']"]

    assert _login(totp_secret=TOTP_SECRET) == (LoginStatusCode.SUCCESS, None)

    otp_fills = [c for c in driver.fill_text.call_args_list if c.args[0] == "//input[@id='otp']"]
    assert len(otp_fills) == 1 and len(otp_fills[0].args[1]) == 6
    assert driver.click_button.call_count == 2


def test_login_default_script_no_mfa_field_is_not_an_error(driver, form_finder):
    form_finder.find_totp_field.return_value = None

    assert _login(totp_secret=TOTP_SECRET) == (LoginStatusCode.SUCCESS, None)

    assert driver.click_button.call_count == 1


def test_login_default_script_fills_totp_on_login_form(driver, form_finder, mocker):
    form_finder.find_totp_field.return_value = "//input[@id='twofa']"
    mocker.patch(
        "execution.login.custom_login.custom_login_methods_driver.LoginFormFinder",
        return_value=form_finder,
    )

    assert _login(totp_secret=TOTP_SECRET) == (LoginStatusCode.SUCCESS, None)

    assert driver.click_button.call_count == 1
    assert any(c.args[0] == "//input[@id='twofa']" for c in driver.fill_text.call_args_list)


def test_fill_totp_without_secret(driver, form_finder):
    status, message = _login("fillTotp('//input')")
    assert status == LoginStatusCode.TEXT_FIELD_NOT_FOUND
    assert "No TOTP secret" in message
