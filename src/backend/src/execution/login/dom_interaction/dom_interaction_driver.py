import os

import mycdp
from seleniumbase import SB
from execution.login.dom_interaction.interfaces.dom_interaction_interface import DomInteractionInterface

# XewdyCaptcha (https://github.com/Xewdy444) renders a checkbox in a closed shadow root and
# writes the solved token into a hidden "passage-token" field that the login form submits.
XEWDY_PRESENT_JS = "!!document.querySelector('script[src*=\"xewdy.systems\"], [data-passage-container]')"
XEWDY_TOKEN_JS = "(document.querySelector('#passage-token, [name=\"passage_token\"]') || {}).value || ''"
XEWDY_TIMEOUT = 20


class DomInteractionDriver(DomInteractionInterface):

    def __enter__(self):
        self._sb_instance = SB(uc=True, headed=True, window_size="1920,953")
        self._sb = self._sb_instance.__enter__()

        self._sb.activate_cdp_mode(self._url)
        self._sb.uc_gui_handle_captcha()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._sb_instance.__exit__(exc_type, exc, tb)
        return False

    def disconnect_driver(self):
        self._sb.reconnect()
        self._sb.driver.quit()

    def get_current_url(self) -> str:
        return self._sb.cdp.get_current_url()

    def get_page_html(self) -> str:
        return self._sb.cdp.get_element_html("html")

    def is_element_visible(self, xpath: str) -> bool:
        return self._sb.cdp.is_element_visible(xpath)

    def save_screenshot(self, screenshot_id: str):
        if screenshot_id is None:
            return
        dev_mode = os.getenv("RUN_MODE") != "production"

        if dev_mode:
            path = f"../config/images"
        else:
            path = f"/config/images"
        self._sb.cdp.save_screenshot(os.path.join(path, f"{screenshot_id}.png"), selector="body")

    def find_element(self, xpath: str) -> bool:
        return self._sb.cdp.find_element(xpath) is not None

    def solve_captcha(self):
        self._sb.uc_gui_click_captcha()
        self._solve_xewdy_captcha()

    def _solve_xewdy_captcha(self):
        cdp = self._sb.cdp
        if not cdp.evaluate(XEWDY_PRESENT_JS):
            return
        clicked = False
        for _ in range(XEWDY_TIMEOUT):
            if cdp.evaluate(XEWDY_TOKEN_JS):
                return
            if not clicked:
                point = self._xewdy_checkbox_screen_point()
                if point is not None:
                    # A real OS click is required: CDP-dispatched mouse events get the challenge denied.
                    cdp.gui_click_x_y(*point)
                    clicked = True
            self._sb.sleep(1)
        # Failed or stuck: start a fresh challenge so the next call can try again.
        cdp.evaluate("window.passage && window.passage.reset()")

    def _xewdy_checkbox_screen_point(self) -> tuple[float, float] | None:
        """Screen coordinates of the checkbox center, or None while it is not rendered yet."""
        cdp = self._sb.cdp
        run = cdp.loop.run_until_complete
        document = run(cdp.page.send(mycdp.dom.get_document(depth=-1, pierce=True)))
        checkbox = _find_node_by_class(document, "checkbox-box")
        if checkbox is None:
            return None
        try:
            run(cdp.page.send(mycdp.dom.scroll_into_view_if_needed(backend_node_id=checkbox.backend_node_id)))
            quads = run(cdp.page.send(mycdp.dom.get_content_quads(backend_node_id=checkbox.backend_node_id)))
        except Exception:
            return None  # Not laid out yet
        if not quads:
            return None
        quad = quads[0]
        x, y = sum(quad[0::2]) / 4, sum(quad[1::2]) / 4  # viewport coordinates
        window = cdp.get_window_rect()
        return window["x"] + x, window["y"] + window["height"] - window["innerHeight"] + y

    def fill_text(self, xpath: str, value: str):
        self._sb.cdp.send_keys(xpath, value)

    def click_button(self, xpath: str):
        self._sb.cdp.click(xpath)

    def open_url(self, url: str):
        self._sb.cdp.open(url)

    def wait(self, ms: int):
        self._sb.sleep(ms / 1000)


def _find_node_by_class(node, class_name: str):
    """Depth-first search of a CDP DOM tree, including (closed) shadow roots."""
    attributes = node.attributes or []
    if class_name in dict(zip(attributes[::2], attributes[1::2])).get("class", "").split():
        return node
    for child in (node.shadow_roots or []) + (node.children or []):
        found = _find_node_by_class(child, class_name)
        if found is not None:
            return found
    return None
