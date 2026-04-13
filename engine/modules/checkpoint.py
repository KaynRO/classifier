import traceback, time, pyotp
from typing import Optional
from urllib.parse import quote
from helpers.utils import *
from helpers.logger import *
from helpers import credentials


LOGIN_URL = "https://usercenter.checkpoint.com/ucapps/urlcat/"
APP_URL = "https://usercenter.checkpoint.com/ucapps/urlcat/"
URL_DETAILS_URL = "https://usercenter.checkpoint.com/ucapps/urlcat/url-details?q={domain}"


def react_set_value(driver, selector: str, value: str) -> None:
    # React's synthetic events ignore raw element.value assignments, so we have
    # to reach through the native prototype setter and then fire an input event.
    script = (
        "var el = document.querySelector(arguments[0]);"
        "if (!el) return false;"
        "var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;"
        "setter.call(el, arguments[1]);"
        "el.dispatchEvent(new Event('input', {bubbles:true}));"
        "el.dispatchEvent(new Event('change', {bubbles:true}));"
        "return true;"
    )
    driver.execute_script(script, selector, value)


def get_checkpoint_totp() -> Optional[str]:
    secret = (getattr(credentials, "checkpoint_totp_secret", "") or "").strip()
    if not secret:
        return None
    try:
        return pyotp.TOTP(secret).now()
    except Exception:
        return None


class CheckPoint:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.username = (getattr(credentials, "checkpoint_username", "") or "").strip()
        self.password = (getattr(credentials, "checkpoint_password", "") or "").strip()
        self.url = APP_URL


    def current_totp(self) -> Optional[str]:
        return get_checkpoint_totp()


    def login(self, driver) -> bool:
        if not self.username or not self.password:
            self.logger.warning("[!] No CheckPoint credentials configured")
            return False

        self.logger.info("[*] Logging in to CheckPoint UserCenter (Auth0)...")
        driver.uc_open_with_reconnect(LOGIN_URL, reconnect_time=6)
        time.sleep(8)

        if "usercenter.checkpoint.com/ucapps/urlcat" in (driver.current_url or "") and "login.checkpoint.com" not in (driver.current_url or ""):
            self.logger.info("[*] Already authenticated")
            return True

        try:
            wait_for_selector(driver, "#username", state="visible", timeout=15000)
        except Exception:
            self.logger.error("[-] Auth0 login page did not load")
            return False

        react_set_value(driver, "#username", self.username)
        time.sleep(1)
        driver.click("button[type='submit']")
        self.logger.debug("[*] Submitted username")

        try:
            wait_for_selector(driver, "#password", state="visible", timeout=15000)
        except Exception:
            self.logger.error("[-] Password field did not appear")
            return False

        react_set_value(driver, "#password", self.password)
        time.sleep(1)
        driver.click("button[type='submit']")
        self.logger.debug("[*] Submitted password")

        try:
            wait_for_selector(driver, "#code", state="visible", timeout=15000)
        except Exception:
            if "usercenter.checkpoint.com/ucapps/urlcat" in (driver.current_url or ""):
                self.logger.info("[*] Logged in without MFA prompt")
                return True
            self.logger.error("[-] MFA prompt did not appear")
            return False

        code = get_checkpoint_totp()
        if not code:
            self.logger.error("[-] No TOTP secret configured — cannot pass MFA")
            return False

        react_set_value(driver, "#code", code)
        time.sleep(1)
        driver.click("button[type='submit']")
        self.logger.debug(f"[*] Submitted TOTP code")

        try:
            wait_for_url(driver, lambda u: "usercenter.checkpoint.com/ucapps/urlcat" in (u or "") and "login.checkpoint.com" not in (u or ""), timeout=25000)
            self.logger.info("[*] Login successful")
            return True
        except Exception:
            self.logger.error(f"[-] Login did not complete, stuck at: {driver.current_url}")
            return False


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting checkpoint ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        try:
            clean_domain = target_url.replace("https://", "").replace("http://", "").strip("/")

            if not self.login(driver):
                return "Login Failed"

            details_url = URL_DETAILS_URL.format(domain=quote(clean_domain, safe=""))
            self.logger.info(f"[*] Fetching category for {clean_domain}")
            driver.get(details_url)
            time.sleep(8)

            body_text = driver.execute_script("return document.body.innerText || ''") or ""
            category = self.extract_category(body_text)

            if return_reputation_only:
                return None

            self.logger.success(f"[+] Category: {category}")
            return category

        except Exception as e:
            self.logger.error(f"[-] Check Point check failed: {e}")
            self.logger.error(traceback.format_exc())
            return "Error"


    def extract_category(self, body_text: str) -> str:
        # Page format: "Current Categories: <cat1>, <cat2>, <risk level>"
        for raw in body_text.split("\n"):
            line = raw.strip()
            lower = line.lower()
            if lower.startswith("current categories:") or lower.startswith("current categories :"):
                val = line.split(":", 1)[1].strip()
                if val:
                    return val
        for raw in body_text.split("\n"):
            line = raw.strip()
            lower = line.lower()
            if "category" in lower and ":" in line:
                val = line.split(":", 1)[1].strip()
                if val and val.lower() not in ("", "n/a", "category"):
                    return val
        return "NOT FOUND"
