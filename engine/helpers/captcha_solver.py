import logging, re, time, random, threading
from typing import Optional, Dict, Any, Tuple
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from helpers.constants import *


# Register custom SUCCESS log level
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def success(self, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


if not hasattr(logging.Logger, 'success'):
    logging.Logger.success = success


captcha_logger_local = threading.local()


def get_captcha_logger():
    if not hasattr(captcha_logger_local, 'logger'):
        from helpers.logger import Logger
        captcha_logger_local.logger = Logger(__name__)
    return captcha_logger_local.logger


class CaptchaLoggerProxy:
    def __getattr__(self, name: str):
        try:
            from helpers.utils import get_logger
            return getattr(get_logger(), name)
        except ImportError:
            return getattr(get_captcha_logger(), name)


logger = CaptchaLoggerProxy()


def safe_find(driver_or_el, by: str, selector: str) -> Optional[Any]:
    try:
        return driver_or_el.find_element(by, selector)
    except (NoSuchElementException, StaleElementReferenceException):
        return None


def safe_find_all(driver_or_el, by: str, selector: str) -> list:
    try:
        return driver_or_el.find_elements(by, selector)
    except (NoSuchElementException, StaleElementReferenceException):
        return []


class CaptchaSolver:
    def __init__(self, api_key: str = None) -> None:
        self.api_key = api_key
        self.solver = TwoCaptcha(self.api_key, defaultTimeout=120, pollingInterval=2) if self.api_key else None


    def detect_captcha(self, driver) -> Optional[Dict[str, Any]]:
        for name, detector in [
            ("turnstile", self.detect_turnstile),
            ("cloudflare_challenge", lambda d: self.detect_cloudflare_challenge(d)),
            ("recaptcha_enterprise", self.detect_recaptcha_enterprise),
            ("recaptcha_v3", self.detect_recaptcha_v3),
            ("recaptcha_v2", self.detect_recaptcha_v2),
        ]:
            result = detector(driver)
            if result:
                return result

        return None


    def detect_recaptcha_v2(self, driver) -> Optional[Dict[str, Any]]:
        data = driver.execute_script(DETECT_JS["recaptcha_v2"])
        if data and data.get("sitekey"):
            is_invisible = data.get("invisible", False)
            return {"type": "recaptcha_v2_invisible" if is_invisible else "recaptcha_v2", "sitekey": data["sitekey"], "url": driver.current_url, "callback": data.get("callback"), "element_selector": "div.g-recaptcha"}

        # Fallback: check iframe src attributes for sitekey
        for selector in CAPTCHA_PATTERNS["recaptcha_v2"].get("iframe_selectors", []):
            iframe = safe_find(driver, By.CSS_SELECTOR, selector)
            if iframe:
                src = iframe.get_attribute("src") or ""
                match = re.search(r'k=([^&]+)', src)
                if match:
                    return {"type": "recaptcha_v2", "sitekey": match.group(1), "url": driver.current_url, "callback": None, "element_selector": selector}

        return None


    def detect_recaptcha_v3(self, driver) -> Optional[Dict[str, Any]]:
        patterns = CAPTCHA_PATTERNS["recaptcha_v3"]

        # Check for v3 badge element
        for selector in patterns.get("badge_selectors", []):
            if safe_find(driver, By.CSS_SELECTOR, selector):
                sitekey = driver.execute_script(DETECT_JS["recaptcha_v3_sitekey"])
                if not sitekey:
                    sitekey = driver.execute_script('''var e = document.querySelector('.g-recaptcha[data-sitekey]'); if (e && e.getAttribute('data-size') !== 'invisible') return null; return e ? e.getAttribute('data-sitekey') : null;''')
                if sitekey and len(sitekey) >= 30:
                    action = driver.execute_script('''for (var f of document.querySelectorAll('form')) { var a = f.querySelector('input[name="action"]'); if (a) return a.value; } return 'verify';''')
                    return {"type": "recaptcha_v3", "sitekey": sitekey, "url": driver.current_url, "action": action, "min_score": 0.3}

        # Fallback: scan page source for v3 script patterns
        page_source = driver.page_source
        for pattern in patterns.get("script_patterns", []):
            if re.search(pattern, page_source):
                match = re.search(r'render[=:][\s"\']*([a-zA-Z0-9_-]{40,})', page_source)
                if match and match.group(1) != 'explicit':
                    return {"type": "recaptcha_v3", "sitekey": match.group(1), "url": driver.current_url, "action": "verify", "min_score": 0.3}

        return None


    def detect_recaptcha_enterprise(self, driver) -> Optional[Dict[str, Any]]:
        data = driver.execute_script(DETECT_JS["recaptcha_enterprise"])
        if data and data.get("sitekey"):
            if data.get("isV3"):
                return {"type": "recaptcha_v3_enterprise", "sitekey": data["sitekey"], "url": driver.current_url, "action": data.get("action", "verify"), "min_score": 0.3, "enterprise": True}
            else:
                return {"type": "recaptcha_v2_enterprise", "sitekey": data["sitekey"], "url": driver.current_url, "enterprise": True}

        return None


    def detect_turnstile(self, driver) -> Optional[Dict[str, Any]]:
        data = driver.execute_script(DETECT_JS["turnstile"])
        if data and data.get("sitekey"):
            return {"type": "turnstile", "sitekey": data["sitekey"], "url": driver.current_url, "callback": data.get("callback"), "action": data.get("action"), "cdata": data.get("cdata"), "element_selector": ".cf-turnstile"}

        # Extended detection: scan iframes, data-sitekey elements, and inline scripts
        sitekey = driver.execute_script('''
            var iframes = document.querySelectorAll('iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]');
            for (var i = 0; i < iframes.length; i++) {
                var src = iframes[i].src || '';
                var match = src.match(/[?&]k=([^&]+)/);
                if (match) return match[1];
            }
            var elements = document.querySelectorAll('[data-sitekey]');
            for (var i = 0; i < elements.length; i++) {
                var el = elements[i];
                if (el.classList.contains('g-recaptcha') || el.classList.contains('h-captcha')) continue;
                if (el.querySelector('iframe[src*="recaptcha"]') || el.querySelector('iframe[src*="hcaptcha"]')) continue;
                var key = el.getAttribute('data-sitekey');
                if (key && key.length > 20) return key;
            }
            var scripts = document.querySelectorAll('script');
            for (var i = 0; i < scripts.length; i++) {
                if (scripts[i].textContent && scripts[i].textContent.indexOf('turnstile') >= 0) {
                    var match = scripts[i].textContent.match(/sitekey['"]?\\s*[:=]\\s*['"]([0-9a-zA-Z_-]{30,})['"]/);
                    if (match) return match[1];
                }
            }
            return null;
        ''')

        if sitekey:
            logger.debug(f"[*] Found turnstile sitekey via extended detection: {sitekey[:20]}...")
            return {"type": "turnstile", "sitekey": sitekey, "url": driver.current_url, "callback": None, "action": None, "cdata": None, "element_selector": "iframe[src*='challenges.cloudflare.com']"}

        return None


    def detect_cloudflare_challenge(self, driver) -> Optional[Dict[str, Any]]:
        patterns = CAPTCHA_PATTERNS["cloudflare_challenge"]
        title = driver.title.lower()
        if not any(re.search(p, title) for p in patterns.get("title_patterns", [])):
            return None

        # Try to extract the Cloudflare Ray ID
        ray_id = None
        for selector in patterns.get("ray_id_selectors", []):
            element = safe_find(driver, By.CSS_SELECTOR, selector)
            if element:
                ray_id = element.text
                break

        if not ray_id:
            match = re.search(r"cRay['\"]?:\s*['\"]([^'\"]+)['\"]", driver.page_source)
            if match:
                ray_id = match.group(1)

        return {"type": "cloudflare_challenge", "url": driver.current_url, "ray_id": ray_id, "sitekey": None}


    def solve_captcha(self, captcha_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.solver:
            logger.error("[-] 2Captcha solver not initialized")
            return None

        ctype = captcha_info.get("type")
        try:
            if ctype in ("recaptcha_v2", "recaptcha_v2_invisible"):
                result = self.solver.recaptcha(sitekey=captcha_info["sitekey"], url=captcha_info["url"], invisible=1 if ctype == "recaptcha_v2_invisible" else 0)
                return {"token": result["code"], "type": ctype, "callback": captcha_info.get("callback")}

            elif ctype == "recaptcha_v3":
                result = self.solver.recaptcha(sitekey=captcha_info["sitekey"], url=captcha_info["url"], version="v3", action=captcha_info.get("action", "verify"), score=captcha_info.get("min_score", 0.3))
                return {"token": result["code"], "type": "recaptcha_v3"}

            elif ctype == "recaptcha_v2_enterprise":
                result = self.solver.recaptcha(sitekey=captcha_info["sitekey"], url=captcha_info["url"], enterprise=1)
                return {"token": result["code"], "type": "recaptcha_v2_enterprise"}

            elif ctype == "recaptcha_v3_enterprise":
                result = self.solver.recaptcha(sitekey=captcha_info["sitekey"], url=captcha_info["url"], version="v3", enterprise=1, action=captcha_info.get("action", "verify"), score=captcha_info.get("min_score", 0.3))
                return {"token": result["code"], "type": "recaptcha_v3_enterprise"}

            elif ctype == "turnstile":
                kwargs = {"sitekey": captcha_info["sitekey"], "url": captcha_info["url"]}
                if captcha_info.get("action"):
                    kwargs["action"] = captcha_info["action"]
                if captcha_info.get("cdata"):
                    kwargs["data"] = captcha_info["cdata"]
                result = self.solver.turnstile(**kwargs)
                return {"token": result["code"], "type": "turnstile", "callback": captcha_info.get("callback")}

            else:
                logger.error(f"[-] Unknown captcha type: {ctype}")
                return None

        except Exception as e:
            logger.error(f"[-] Error solving captcha: {e}")
            return None


    def inject_solution(self, driver, captcha_info: Dict[str, Any], solution: Dict[str, Any]) -> bool:
        ctype = solution.get("type")
        try:
            if ctype in ("recaptcha_v2", "recaptcha_v2_invisible"):
                driver.execute_script(INJECT_JS["recaptcha_v2"], solution["token"])
                if solution.get("callback"):
                    driver.execute_script(f'var token = arguments[0]; if (typeof {solution["callback"]} === "function") {solution["callback"]}(token);', solution["token"])

            elif ctype == "recaptcha_v3":
                driver.execute_script(INJECT_JS["recaptcha_v3"], solution["token"])

            elif ctype in ("recaptcha_v2_enterprise", "recaptcha_v3_enterprise"):
                driver.execute_script(INJECT_JS["recaptcha_enterprise"], solution["token"])

            elif ctype == "turnstile":
                driver.execute_script(INJECT_JS["turnstile"], solution["token"])
                if solution.get("callback"):
                    cb = solution["callback"]
                    driver.execute_script(f'var token = arguments[0]; if (typeof {cb} === "function") {cb}(token); else if (typeof window["{cb}"] === "function") window["{cb}"](token);', solution["token"])

            else:
                logger.error(f"[-] Unknown captcha type for injection: {ctype}")
                return False

            return True

        except Exception as e:
            logger.error(f"[-] Error injecting solution: {e}")
            return False


    def detect_and_solve(self, driver) -> Tuple[bool, Optional[str]]:
        captcha_info = self.detect_captcha(driver)
        if not captcha_info:
            return False, None

        solution = self.solve_captcha(captcha_info)
        if not solution:
            return True, f"Failed to solve {captcha_info['type']} captcha"

        if not self.inject_solution(driver, captcha_info, solution):
            return True, f"Failed to inject {captcha_info['type']} solution"

        time.sleep(1)
        return True, None


    def try_click_checkbox(self, driver, captcha_type: str = None) -> bool:
        types_to_try = [captcha_type] if captcha_type else list(CAPTCHA_SELECTORS["checkbox"].keys())

        for ctype in types_to_try:
            selectors = CAPTCHA_SELECTORS["checkbox"].get(ctype, [])
            for selector in selectors:
                try:
                    element = safe_find(driver, By.CSS_SELECTOR, selector)
                    if element:
                        try:
                            if not element.is_displayed():
                                continue
                        except Exception:
                            continue

                        # Click with randomized offset to simulate human behavior
                        size = element.size
                        if size and size['width'] > 0 and size['height'] > 0:
                            actions = ActionChains(driver)
                            offset_x = int(size['width'] * (0.3 + random.random() * 0.4)) - size['width'] // 2
                            offset_y = int(size['height'] * (0.3 + random.random() * 0.4)) - size['height'] // 2
                            time.sleep(random.uniform(0.2, 0.5))
                            actions.move_to_element_with_offset(element, offset_x, offset_y)
                            time.sleep(random.uniform(0.05, 0.15))
                            actions.click().perform()
                            return True
                except Exception:
                    continue

        logger.debug(f"[*] Could not find clickable checkbox for {captcha_type}")
        return False


    def is_captcha_verified(self, driver, captcha_type: str = None) -> bool:
        types_to_check = [captcha_type] if captcha_type else list(CAPTCHA_SELECTORS["verified"].keys())

        for ctype in types_to_check:
            for selector in CAPTCHA_SELECTORS["verified"].get(ctype, []):
                try:
                    if safe_find(driver, By.CSS_SELECTOR, selector):
                        return True
                except Exception:
                    continue

        # Check for token presence as a final verification
        if driver.execute_script(DETECT_JS["token_check"]):
            return True

        return False


    def has_image_challenge(self, driver, captcha_type: str = None) -> bool:
        types_to_check = [captcha_type] if captcha_type else list(CAPTCHA_SELECTORS["challenge"].keys())

        for ctype in types_to_check:
            for selector in CAPTCHA_SELECTORS["challenge"].get(ctype, []):
                try:
                    element = safe_find(driver, By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        return True
                except Exception:
                    continue

        return False


    def dismiss_challenge(self, driver, captcha_type: str = None) -> bool:
        try:
            ActionChains(driver).send_keys('\ue00c').perform()
            time.sleep(0.3)

            # Hide reCAPTCHA challenge overlays
            driver.execute_script('''
                var overlays = document.querySelectorAll('iframe[src*="recaptcha"][src*="bframe"]');
                overlays.forEach(function(f) { if (f.parentElement) f.parentElement.style.display = 'none'; });
                var recaptchaOverlay = document.querySelector('.rc-imageselect, .rc-audiochallenge');
                if (recaptchaOverlay) recaptchaOverlay.style.display = 'none';
                var backdrop = document.querySelector('div[style*="z-index"][style*="position: fixed"]');
                if (backdrop && backdrop.querySelector('iframe[src*="recaptcha"]')) backdrop.style.display = 'none';
            ''')

            ActionChains(driver).move_by_offset(10, 10).click().perform()
            time.sleep(0.2)
            return True
        except Exception as e:
            logger.debug(f"[*] Failed to dismiss challenge: {e}")
            return False


    def remove_overlays(self, driver) -> None:
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
                document.querySelectorAll('div').forEach(function(d) {
                    var s = d.style;
                    if (s.position === 'fixed' && s.zIndex && parseInt(s.zIndex) > 1000000 && parseFloat(s.opacity) < 0.5) d.remove();
                });
            ''')
        except Exception:
            pass


    def handle_captcha_with_click_first(self, driver, wait_after_click: float = 3.0, max_click_attempts: int = 2) -> Tuple[bool, Optional[str]]:
        captcha_info = self.detect_captcha(driver)
        if not captcha_info:
            return False, None

        ctype = captcha_info.get("type")
        logger.info(f"[*] Captcha detected ({ctype}). Attempting to solve...")

        if ctype == "cloudflare_challenge":
            return False, None

        # Map captcha types to their checkbox equivalents
        checkbox_map = {
            "recaptcha_v2": "recaptcha_v2",
            "recaptcha_v2_enterprise": "recaptcha_v2",
            "turnstile": "turnstile",
        }
        checkbox_type = checkbox_map.get(ctype)
        had_image_challenge = False

        # Attempt click-based solving for checkbox-style CAPTCHAs
        if checkbox_type:
            logger.debug(f"[*] Attempting click-first for {ctype}")
            for attempt in range(max_click_attempts):
                if self.is_captcha_verified(driver, checkbox_type):
                    logger.debug(f"[+] {ctype} already verified")
                    return True, None

                if self.try_click_checkbox(driver, checkbox_type):
                    time.sleep(wait_after_click)

                    if self.is_captcha_verified(driver, checkbox_type):
                        logger.debug(f"[+] {ctype} verified via click")
                        return True, None

                    if self.has_image_challenge(driver, checkbox_type):
                        had_image_challenge = True
                        break

                    if attempt < max_click_attempts - 1:
                        time.sleep(1)
                else:
                    break

        # Dismiss image challenge overlay if it appeared
        if had_image_challenge:
            logger.debug(f"[*] Image challenge appeared, dismissing overlay")
            self.dismiss_challenge(driver, checkbox_type)

        if not self.solver:
            return True, "Captcha detected but no API key configured"

        # Retry loop for 2Captcha API solving
        max_solve_retries = 3
        for solve_attempt in range(max_solve_retries):
            logger.debug(f"[*] Trying to solve challenge using 2Captcha API (attempt {solve_attempt + 1}/{max_solve_retries})")

            solution = self.solve_captcha(captcha_info)
            if not solution:
                if solve_attempt < max_solve_retries - 1:
                    logger.debug(f"[*] 2Captcha failed, re-detecting captcha and retrying...")
                    time.sleep(2)
                    captcha_info = self.detect_captcha(driver)
                    if not captcha_info:
                        return True, f"Failed to solve {ctype} via API and captcha disappeared on retry"
                    ctype = captcha_info.get("type")
                    continue
                return True, f"Failed to solve {ctype} via API after {max_solve_retries} attempts"

            if not self.inject_solution(driver, captcha_info, solution):
                if solve_attempt < max_solve_retries - 1:
                    logger.debug(f"[*] Injection failed, re-detecting captcha and retrying...")
                    time.sleep(2)
                    captcha_info = self.detect_captcha(driver)
                    if not captcha_info:
                        return True, f"Failed to inject {ctype} solution and captcha disappeared on retry"
                    ctype = captcha_info.get("type")
                    continue
                return True, f"Failed to inject {ctype} solution after {max_solve_retries} attempts"

            time.sleep(1)
            self.remove_overlays(driver)
            logger.debug(f"[+] {ctype} solution injected successfully")
            return True, None

        return True, f"Failed to solve {ctype} after {max_solve_retries} attempts"


    def handle_cloudflare_with_click_first(self, driver, max_wait: float = 15.0) -> Tuple[bool, Optional[str]]:
        title = driver.title.lower()
        if 'just a moment' not in title and 'attention required' not in title:
            return False, None

        logger.debug("[*] Cloudflare challenge detected, using UC mode to bypass")

        # First attempt with UC gui handler
        try:
            driver.uc_gui_handle_captcha()
            time.sleep(3)
        except Exception as e:
            logger.debug(f"[*] uc_gui_handle_captcha raised: {e}")

        title = driver.title.lower()
        if 'just a moment' not in title and 'attention required' not in title:
            logger.debug("[+] Cloudflare challenge bypassed via UC mode")
            return True, None

        # Second attempt with longer wait
        try:
            driver.uc_gui_handle_captcha()
            time.sleep(5)
        except Exception:
            pass

        title = driver.title.lower()
        if 'just a moment' not in title and 'attention required' not in title:
            logger.debug("[+] Cloudflare challenge bypassed via UC mode (retry)")
            return True, None

        return True, "Cloudflare challenge could not be bypassed"


def create_captcha_solver(api_key: str = None) -> CaptchaSolver:
    return CaptchaSolver(api_key)

