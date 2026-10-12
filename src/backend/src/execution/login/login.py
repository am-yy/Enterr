import traceback
from typing import Tuple
from utils.utils import compare_urls
from .constants import (
    LoginStatusCode,
    CustomFailedDetailsMessage,
    NAVIGATION_TIMEOUT,
    TIMEOUT,
)
from .custom_login.custom_login_methods_driver import CustomLoginMethodsDriver
from .custom_login.parser import CustomLoginScriptParser
from execution.login.dom_interaction.interfaces.dom_interaction_interface import (
    DomInteractionInterface,
)
from .dom_interaction.dom_interaction_driver import DomInteractionDriver
from .find_form_automatically import XPaths, LoginFormFinder


def login(
    url: str,
    success_url: str,
    username: str,
    password: str,
    custom_login_script: str | None = None,
    screenshot_id: str | None = None,
    totp_secret: str | None = None,
) -> Tuple[LoginStatusCode, CustomFailedDetailsMessage]:
    try:
        with DomInteractionDriver(url=url) as driver:
            try:
                url_before = driver.get_current_url()
                status = _execute_interaction(
                    driver,
                    custom_login_script,
                    username,
                    password,
                    success_url,
                    totp_secret,
                )

                if status is not None:
                    driver.save_screenshot(screenshot_id)
                    return status

                _wait_for_navigation(driver, url_before)

                # Redirect to success url
                driver.open_url(success_url)

                # Wait for expected url
                for i in range(TIMEOUT):
                    driver.solve_captcha()
                    driver.wait(1000)
                    if compare_urls(driver.get_current_url(), success_url):
                        driver.save_screenshot(screenshot_id)
                        return LoginStatusCode.SUCCESS, None
                driver.save_screenshot(screenshot_id)

            except Exception:
                traceback.print_exc()
                driver.save_screenshot(screenshot_id)
                driver.disconnect_driver()
                return LoginStatusCode.UNKNOWN_EXECUTION_ERROR, None

            current_url = driver.get_current_url()
            success_url_not_matching_custom_failed_details_message = (
                f'Expected: "{success_url}", Found: "{current_url}"'
            )
            return (
                LoginStatusCode.SUCCESS_URL_DID_NOT_MATCH,
                success_url_not_matching_custom_failed_details_message,
            )
    except Exception:
        traceback.print_exc()
        return LoginStatusCode.UNKNOWN_EXECUTION_ERROR, None


def _wait_for_navigation(driver: DomInteractionInterface, url_before: str) -> None:
    """
    Let the submitted login finish before leaving the page. Navigating away right after the
    click aborts a slow login request before the session cookie is set.
    """
    for _ in range(NAVIGATION_TIMEOUT):
        if driver.get_current_url() != url_before:
            break
        driver.wait(1000)
    driver.wait(1000)


def _execute_interaction(
    driver: DomInteractionInterface,
    custom_login_script: str | None,
    username: str,
    password: str,
    success_url: str,
    totp_secret: str | None = None,
) -> Tuple[LoginStatusCode, CustomFailedDetailsMessage] | None:
    default_script = custom_login_script is None
    totp_on_login_form = False
    xpaths = None
    xpath_not_found_error = None
    if custom_login_script is None:
        custom_login_script = """
        fillUsername()
        fillPassword()
        clickSubmitButton()
        """
        # Wait for all elements to be visible when no custom login script found
        for i in range(0, TIMEOUT, 5):
            driver.solve_captcha()
            xpaths = _find_elements(driver=driver)
            xpath_not_found_error = _xpath_not_found_error(xpaths)
            if xpath_not_found_error is None:
                break
            driver.wait(5000)
        if xpath_not_found_error is not None:
            return xpath_not_found_error, None
        # Some sites (e.g. Gazelle trackers) put an optional 2FA field on the login form itself.
        if totp_secret and LoginFormFinder(driver=driver).find_totp_field():
            totp_on_login_form = True
            custom_login_script = """
            fillUsername()
            fillPassword()
            fillTotp()
            clickSubmitButton()
            """
    else:
        xpaths = _find_elements(driver=driver)
    custom_login_seleniumbase = CustomLoginMethodsDriver(
        driver=driver,
        x_paths=xpaths,
        username=username,
        password=password,
        totp_secret=totp_secret,
    )
    parser = CustomLoginScriptParser(custom_login_seleniumbase)
    exception = parser.execute(custom_login_script)
    if exception is not None:
        return exception.status, exception.message
    if default_script and totp_secret and not totp_on_login_form:
        return _execute_totp_step(driver, username, password, success_url, totp_secret)
    return None


def _execute_totp_step(
    driver: DomInteractionInterface,
    username: str,
    password: str,
    success_url: str,
    totp_secret: str,
) -> Tuple[LoginStatusCode, CustomFailedDetailsMessage] | None:
    """
    Default-script MFA: wait for a one-time-code field to appear after submit, fill it and submit.
    No field appearing is not an error (the site may not ask for MFA); the success URL check decides.
    """
    for _ in range(TIMEOUT):
        if compare_urls(driver.get_current_url(), success_url):
            return None
        if LoginFormFinder(driver=driver).find_totp_field() is not None:
            break
        driver.wait(1000)
    else:
        return None
    methods = CustomLoginMethodsDriver(
        driver=driver,
        x_paths=_find_elements(driver=driver),
        username=username,
        password=password,
        totp_secret=totp_secret,
    )
    exception = CustomLoginScriptParser(methods).execute("fillTotp()\nclickSubmitButton()")
    if exception is not None:
        return exception.status, exception.message
    return None


def _xpath_not_found_error(xpaths: XPaths) -> LoginStatusCode | None:
    if xpaths.username is None:
        return LoginStatusCode.USERNAME_FIELD_NOT_FOUND
    if xpaths.password is None:
        return LoginStatusCode.PASSWORD_FIELD_NOT_FOUND
    if xpaths.submit_button is None:
        return LoginStatusCode.SUBMIT_BUTTON_NOT_FOUND
    return None


def _find_elements(driver: DomInteractionInterface) -> XPaths:
    login_form_finder = LoginFormFinder(driver=driver)
    x_paths_automatic = login_form_finder.find_login_automatically()

    if x_paths_automatic is None:
        return XPaths(None, None, None)

    username_xpath = x_paths_automatic.username
    password_xpath = x_paths_automatic.password
    submit_button_xpath = x_paths_automatic.submit_button

    if username_xpath is None or not driver.find_element(username_xpath):
        username_xpath = None

    if password_xpath is None or not driver.find_element(password_xpath):
        password_xpath = None

    if submit_button_xpath is None or not driver.find_element(submit_button_xpath):
        submit_button_xpath = None
    return XPaths(username_xpath, password_xpath, submit_button_xpath)
