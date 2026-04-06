import re, time, random, threading
from typing import Optional, List, Any
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException,
    ElementNotInteractableException, TimeoutException,
)
from helpers.logger import *
from helpers.constants import *


default_logger = Logger(__name__)
thread_local = threading.local()
captcha_api_key = None


def get_captcha_api_key() -> Optional[str]:
    return captcha_api_key


def set_captcha_api_key(api_key: str) -> None:
    global captcha_api_key
    captcha_api_key = api_key


def get_logger() -> Logger:
    return getattr(thread_local, 'logger', default_logger)


def set_active_logger(logger_instance: Logger) -> None:
    thread_local.logger = logger_instance


def clear_active_logger() -> None:
    if hasattr(thread_local, 'logger'):
        delattr(thread_local, 'logger')


class LoggerProxy:
    def __getattr__(self, name: str):
        return getattr(get_logger(), name)


logger = LoggerProxy()


KEY_MAP = {
    "Enter": Keys.ENTER, "Escape": Keys.ESCAPE, "Tab": Keys.TAB,
    "Backspace": Keys.BACKSPACE, "Delete": Keys.DELETE,
    "ArrowUp": Keys.ARROW_UP, "ArrowDown": Keys.ARROW_DOWN,
    "ArrowLeft": Keys.ARROW_LEFT, "ArrowRight": Keys.ARROW_RIGHT,
}


def css_base_to_xpath(css: str) -> str:
    if not css or css == '*':
        return '*'

    if '.' in css:
        parts = css.split('.')
        tag = parts[0] or '*'
        preds = ' and '.join(f"contains(@class, '{c}')" for c in parts[1:] if c)
        return f"{tag}[{preds}]"

    if '#' in css:
        parts = css.split('#', 1)
        tag = parts[0] or '*'
        return f"{tag}[@id='{parts[1]}']"

    return css


def parse_selector(selector: str) -> tuple:
    if selector.startswith('xpath='):
        return By.XPATH, selector[6:]

    if selector.startswith('/') or selector.startswith('('):
        return By.XPATH, selector

    # Handle :has-text() pseudo-selector
    ht = re.search(r':has-text\(["\'](.+?)["\']\)\s*$', selector)
    if ht:
        text = ht.group(1)
        base = selector[:ht.start()]

        # Handle nested :has() with :has-text() inside
        hm = re.search(r':has\((.+)\)\s*$', base)
        if hm:
            inner_sel = hm.group(1)
            outer_base = base[:hm.start()]
            iht = re.search(r':has-text\(["\'](.+?)["\']\)\s*$', inner_sel)
            if iht:
                inner_text = iht.group(1)
                inner_base = inner_sel[:iht.start()]
                return By.XPATH, f"//{css_base_to_xpath(outer_base)}[.//{css_base_to_xpath(inner_base)}[contains(., '{inner_text}')]]"
            return By.XPATH, f"//{css_base_to_xpath(outer_base)}[.//{css_base_to_xpath(inner_sel)}]"

        return By.XPATH, f"//{css_base_to_xpath(base)}[contains(., '{text}')]"

    # Handle :has() pseudo-selector
    hm = re.search(r':has\((.+)\)\s*$', selector)
    if hm:
        inner_sel = hm.group(1)
        outer_base = selector[:hm.start()]
        by, val = parse_selector(inner_sel)
        if by == By.XPATH:
            return By.XPATH, f"//{css_base_to_xpath(outer_base)}[.{val}]"

    return By.CSS_SELECTOR, selector


def split_comma(selector: str) -> List[str]:
    parts, depth, current = [], 0, ""
    for ch in selector:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += ch

    if current.strip():
        parts.append(current.strip())

    return parts


def safe_find_element(driver, selector: str) -> Optional[Any]:
    by, value = parse_selector(selector)
    try:
        return driver.find_element(by, value)
    except (NoSuchElementException, StaleElementReferenceException):
        return None


def safe_find_elements(driver, selector: str) -> list:
    by, value = parse_selector(selector)
    try:
        return driver.find_elements(by, value)
    except (NoSuchElementException, StaleElementReferenceException):
        return []


def get_text(driver, selector: str) -> str:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    return el.text.strip()


def count_elements(driver, selector: str) -> int:
    return len(safe_find_elements(driver, selector))


def clear_element(driver, selector: str) -> None:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    el.clear()


def fill_element(driver, selector: str, text: str) -> None:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    el.clear()
    el.send_keys(text)


def press_key(driver, selector: str, key: str) -> None:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    el.send_keys(KEY_MAP.get(key, key))


def click_element(driver, selector: str, force: bool = False) -> None:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    if force:
        driver.execute_script("arguments[0].click()", el)
    else:
        try:
            el.click()
        except ElementNotInteractableException:
            driver.execute_script("arguments[0].click()", el)


def select_option(driver, selector: str, value: Any = None, *, label: str = None) -> None:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    sel = Select(el)
    if label is not None:
        sel.select_by_visible_text(label)
    elif value is not None:
        try:
            sel.select_by_value(str(value))
        except Exception:
            sel.select_by_visible_text(str(value))
    else:
        raise ValueError("select_option needs value or label")


def evaluate_on_element(driver, selector: str, js: str, *args) -> Any:
    el = safe_find_element(driver, selector)
    if el is None:
        raise NoSuchElementException(f"Element not found: {selector}")
    stripped = js.strip()
    if stripped.startswith("(") or "=>" in stripped:
        extra = ''.join(f', arguments[{i+1}]' for i in range(len(args)))
        return driver.execute_script(f"return ({js})(arguments[0]{extra})", el, *args)
    return driver.execute_script(js, el, *args)


def is_element_visible(driver, selector: str) -> bool:
    try:
        el = safe_find_element(driver, selector)
        return el is not None and el.is_displayed()
    except Exception:
        return False


def is_element_checked(driver, selector: str) -> bool:
    try:
        el = safe_find_element(driver, selector)
        return el is not None and el.is_selected()
    except Exception:
        return False


def get_element_bounding_box(driver, element) -> Optional[dict]:
    try:
        loc = element.location
        size = element.size
        if loc and size:
            return {"x": loc["x"], "y": loc["y"],
                    "width": size["width"], "height": size["height"]}
    except Exception:
        pass
    return None


def mouse_move_to(driver, x: float, y: float) -> None:
    try:
        driver.execute_script("""
            var el = document.elementFromPoint(arguments[0], arguments[1]);
            if (el) {
                el.dispatchEvent(new MouseEvent('mouseover', {clientX: arguments[0], clientY: arguments[1], bubbles: true}));
                el.dispatchEvent(new MouseEvent('mousemove', {clientX: arguments[0], clientY: arguments[1], bubbles: true}));
            }
        """, int(x), int(y))
    except Exception:
        pass


def wait_for_selector(driver, selector: str, state: str = "visible", timeout: int = 30000) -> Optional[Any]:
    parts = split_comma(selector)
    deadline = time.time() + timeout / 1000.0

    while time.time() < deadline:
        for p in parts:
            try:
                el = safe_find_element(driver, p)

                if el is None:
                    if state in ("detached", "hidden"):
                        return el
                    continue

                if state == "visible" and el.is_displayed():
                    return el

                if state == "attached":
                    return el

                if state in ("detached", "hidden") and not el.is_displayed():
                    return el
            except (StaleElementReferenceException, NoSuchElementException):
                if state in ("detached", "hidden"):
                    return None

        time.sleep(0.3)

    raise TimeoutException(f"Timeout waiting for selector: {selector}")


def wait_for_function(driver, js: str, timeout: int = 30000) -> None:
    deadline = time.time() + timeout / 1000.0
    while time.time() < deadline:
        try:
            if driver.execute_script(f"return !!({js})"):
                return
        except Exception:
            pass
        time.sleep(0.5)

    raise TimeoutException(f"Timeout in wait_for_function")


def wait_for_load_state(driver, state: str = "load", timeout: int = 30000) -> None:
    if state == "networkidle":
        time.sleep(3)
    else:
        WebDriverWait(driver, timeout / 1000).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )


def wait_for_url(driver, predicate: Any, timeout: int = 30000) -> None:
    deadline = time.time() + timeout / 1000.0
    while time.time() < deadline:
        url = driver.current_url
        if callable(predicate) and predicate(url):
            return
        if isinstance(predicate, str) and predicate in url:
            return
        time.sleep(0.5)

    raise TimeoutException("Timeout waiting for URL change")


def prepare_urls_for_submission(domain: str) -> List[str]:
    clean_domain = domain.replace('https://', '').replace('http://', '')
    return [f'https://{clean_domain}']


def randomize_user_agent() -> str:
    browsers = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    return random.choice(browsers)


def construct_reason_for_review_comment(target_url: str, category: str, simple_message: bool = False) -> str:
    messages = [
        f'Dear,\n\nI am writing to discuss my website, {target_url}, and why I believe it should be categorized under {category}.\n\nI kindly request your consideration in reviewing my website and including it in the relevant category on your platform.',
        f'Hello,\n\n I am reaching out to propose the categorization of my website, {target_url}, as {category}.',
        f'Hello,\n\n I wanted to present my website, {target_url}, for consideration in the {category} category on your platform.'
    ]

    if simple_message:
        return f'I believe that my website {target_url} goes under {category} category.'

    return random.choice(messages)


def parse_date(date_string: str) -> datetime:
    if 'ago' in date_string:
        time_units = {
            'sec': 'seconds', 'secs': 'seconds', 'min': 'minutes', 'mins': 'minutes',
            'minute': 'minutes', 'hour': 'hours', 'hours': 'hours', 'day': 'days',
            'days': 'days', 'week': 'weeks', 'weeks': 'weeks', 'month': 'months',
            'months': 'months', 'year': 'years', 'years': 'years'
        }
        pattern = r'(\d+)\s+(\w+)'
        match = re.match(pattern, date_string)

        if match:
            count, unit = int(match.group(1)), match.group(2).lower()
            if unit in time_units:
                delta = timedelta(**{time_units[unit]: count})
                return datetime.now() - delta

    raise ValueError(f'Invalid date string: {date_string}')


def load_url_and_wait_until_it_is_fully_loaded(driver, url: str) -> None:
    for retry in range(3):
        try:
            try:
                driver.set_page_load_timeout(global_wait_time)
            except Exception:
                pass
            driver.get(url)
            break
        except Exception as e:
            logger.error(f'[-] Network error occurred: {str(e)}')
            logger.error(f'[-] Retrying... Attempt {retry + 1}')


def wait_for_element_by_xpath(driver, element: str):
    wait_for_selector(driver, element, state='visible', timeout=global_wait_time * 1000)
    return safe_find_element(driver, element)


def wait_for_element_by_name(driver, element: str):
    selector = f'[name="{element}"]'
    wait_for_selector(driver, selector, state='visible', timeout=global_wait_time * 1000)
    return safe_find_element(driver, selector)


def wait_for_element_and_fetch_value(driver, element: str) -> str:
    try:
        el = wait_for_element_by_xpath(driver, element)
        return el.text.strip()
    except Exception:
        return 'Failed to view the element'


def human_click(driver, element_locator) -> None:
    if isinstance(element_locator, str):
        try:
            wait_for_selector(driver, element_locator, state="visible", timeout=10000)
        except TimeoutException:
            pass
        el = safe_find_element(driver, element_locator)
        if el is None:
            raise NoSuchElementException(f"Element not found: {element_locator}")
    else:
        el = element_locator

    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click()", el)


def human_type(driver, element_locator, text: str) -> None:
    if isinstance(element_locator, str):
        try:
            wait_for_selector(driver, element_locator, state="visible", timeout=10000)
        except TimeoutException:
            pass
        el = safe_find_element(driver, element_locator)
        if el is None:
            raise NoSuchElementException(f"Element not found: {element_locator}")
    else:
        el = element_locator

    try:
        el.click()
    except Exception:
        pass
    el.clear()
    el.send_keys(str(text))


def wait_and_click_on_element(driver, element: str) -> None:
    human_click(driver, element)


def wait_and_input_on_element(driver, element: str, input_value) -> None:
    human_type(driver, element, str(input_value))


def wait_and_input_on_element_then_press_enter(driver, element: str, input_value) -> None:
    human_type(driver, element, str(input_value))
    ActionChains(driver).send_keys(Keys.ENTER).perform()


def get_captcha_solver():
    from helpers.captcha_solver import CaptchaSolver
    api_key = get_captcha_api_key()
    return CaptchaSolver(api_key)


def remove_captcha_overlays(driver) -> None:
    try:
        driver.execute_script('''
            document.querySelectorAll('iframe[src*="recaptcha"][src*="bframe"]').forEach(function(f) {
                var p = f.parentElement;
                while (p && p !== document.body) {
                    var cs = getComputedStyle(p);
                    if (cs.position === 'fixed' || cs.position === 'absolute' || parseInt(cs.zIndex) > 1000) {
                        p.remove(); return;
                    }
                    p = p.parentElement;
                }
                f.style.display = 'none';
            });
            document.querySelectorAll('iframe[src*="recaptcha"][src*="anchor"]').forEach(function(f) {
                var p = f.parentElement;
                while (p && p !== document.body) {
                    var cs = getComputedStyle(p);
                    if (cs.position === 'fixed' || cs.position === 'absolute') {
                        p.remove(); return;
                    }
                    p = p.parentElement;
                }
            });
            document.querySelectorAll('.rc-imageselect, .rc-audiochallenge').forEach(function(e) { e.remove(); });
        ''')
    except Exception:
        pass


def solve_google_recaptcha(driver, xpath: str = None) -> bool:
    try:
        solver = get_captcha_solver()
        detected, error = solver.handle_captcha_with_click_first(driver)

        if detected and not error:
            logger.info('[+] reCAPTCHA solved!')
            remove_captcha_overlays(driver)
            return True

        if detected and error:
            logger.error(f'[-] reCAPTCHA solving failed: {error}')
    except Exception as e:
        logger.error(f'[-] reCAPTCHA error: {e}')

    return False


def solve_cloudflare_turnstile(driver) -> bool:
    try:
        solver = get_captcha_solver()

        # First: try UC mode for full-page Cloudflare challenges ("Just a moment")
        cf_detected, cf_error = solver.handle_cloudflare_with_click_first(driver)
        if cf_detected and not cf_error:
            logger.info('[+] Cloudflare challenge bypassed!')
            return True

        # Then: try Turnstile widget detection + 2Captcha API
        detected, error = solver.handle_captcha_with_click_first(driver)
        if detected and not error:
            logger.info('[+] Cloudflare Turnstile solved!')
            return True

        if detected and error:
            logger.error(f'[-] Turnstile solving failed: {error}')
    except Exception as e:
        logger.error(f'[-] Turnstile error: {e}')

    return False


def handle_cookie_consent(driver, timeout: int = 5) -> bool:
    selectors = [
        '#onetrust-accept-btn-handler',
        '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "accept")]',
        '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "allow")]',
        '//a[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "accept")]',
        '//a[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "allow")]',
        '.cc-btn.cc-dismiss',
        '.cc-btn.cc-allow',
        '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "accept all")]',
        '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "accept cookies")]',
    ]

    try:
        for selector in selectors:
            try:
                el = safe_find_element(driver, selector)
                if el and el.is_displayed():
                    logger.debug(f"[*] Found cookie consent with selector: {selector}")
                    el.click()
                    time.sleep(1)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def handle_human_verification_checkbox(driver, timeout: int = 5) -> bool:
    xpaths = [
        '//input[@type="checkbox" and contains(@aria-label, "not a robot")]',
        '//input[@type="checkbox" and contains(@title, "not a robot")]',
        '//input[@type="checkbox" and contains(@id, "human")]',
        '//input[@type="checkbox" and contains(@id, "verify")]',
        '//input[@type="checkbox" and contains(@name, "human")]',
        '//input[@type="checkbox" and contains(@name, "verify")]',
        '//span[contains(@class, "checkbox") and contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "human")]',
        '//div[contains(@class, "checkbox") and contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "robot")]',
    ]

    try:
        for xpath in xpaths:
            try:
                el = safe_find_element(driver, xpath)
                if el and el.is_displayed():
                    if not el.is_selected():
                        el.click()
                        time.sleep(1)
                        logger.debug('[*] Human verification checkbox handled successfully')
                        return True
            except Exception:
                continue
    except Exception:
        pass

    return False
