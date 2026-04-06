import traceback, time
from typing import Optional
from helpers.utils import *
from helpers.logger import *


class Intelixsophos:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://intelix.sophos.com/url"


    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        self.logger.info(f" Targeting intelixsophos ".center(60, "="))
        self.logger.info(f"[*] Using vendor endpoint at: {self.url}")

        load_url_and_wait_until_it_is_fully_loaded(driver, self.url)
        time.sleep(3)

        # Handle cookie consent
        try:
            for b in driver.find_elements("tag name", "button"):
                if "accept all" in b.text.lower() and b.is_displayed():
                    b.click()
                    self.logger.info("[*] Accepted cookie consent")
                    time.sleep(1)
                    break
        except Exception:
            pass

        # Click URL tab
        try:
            for s in driver.find_elements("tag name", "span"):
                if s.text == "URL" and s.is_displayed():
                    s.click()
                    self.logger.info("[*] Clicked URL tab")
                    time.sleep(1)
                    break
        except Exception:
            pass

        # Enter URL
        try:
            urlbox = driver.find_element("css selector", "input#urlbox")
            urlbox.clear()
            urlbox.send_keys(target_url)
            self.logger.info(f"[*] Entered URL in #urlbox")
        except Exception:
            raise Exception("Could not find URL input #urlbox")

        time.sleep(1)

        # Solve hCaptcha using 2Captcha
        self.logger.info("[*] Attempting to solve hCaptcha via 2Captcha...")
        captcha_solved = False
        try:
            solver = get_captcha_solver()
            if solver and solver.solver:
                result = solver.solver.recaptcha(
                    sitekey="2fe029e7-318b-44ee-8ae0-ced519d390da",
                    url=self.url,
                )
                token = result.get("code") if isinstance(result, dict) else str(result)
                self.logger.info(f"[*] Captcha token received ({len(token)} chars)")

                # Inject token into both h-captcha-response and g-recaptcha-response (compat mode)
                driver.execute_script(f"""
                    document.querySelectorAll('textarea[name="h-captcha-response"], textarea[name="g-recaptcha-response"]').forEach(function(el) {{
                        el.value = "{token}";
                        el.innerHTML = "{token}";
                    }});
                """)
                time.sleep(2)

                # Check if button enabled
                btns = driver.find_elements("css selector", "button.submit-button")
                if btns and btns[0].is_enabled():
                    captcha_solved = True
                    self.logger.success("[+] hCaptcha solved — button enabled")
                else:
                    self.logger.warning("[!] Token injected but button still disabled")
        except Exception as e:
            self.logger.warning(f"[!] 2Captcha hCaptcha failed: {e}")

        if not captcha_solved:
            self.logger.error("[-] hCaptcha could not be solved — 2Captcha may not support hCaptcha on current plan")
            self.logger.info("[*] Tip: Upgrade 2Captcha plan to include hCaptcha support")
            return "hCaptcha Unsolved"

        # Click Analyze
        try:
            wait_and_click_on_element(driver, "button:has-text('Analyze')")
            self.logger.info("[*] Clicked Analyze")
        except Exception:
            driver.execute_script("document.querySelector('button.submit-button')?.click()")
            self.logger.info("[*] Clicked Analyze via JS")

        # Wait for results
        self.logger.info("[*] Waiting for analysis results...")
        time.sleep(15)

        body_text = get_text(driver, "body")
        cat = self.extract_field(body_text, ["category", "categorization"])

        if cat and cat.lower() not in ["", "category"]:
            self.logger.success(f"[+] Category: {cat}")
        else:
            cat = "Not Found"
            self.logger.warning("[-] Could not extract category")

        return cat


    def extract_field(self, body_text: str, labels: list) -> Optional[str]:
        lines = body_text.split("\n")
        skip = ["find out what", "submit your file", "machine learning", "decades of threat"]
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if any(p in stripped for p in skip):
                continue
            for label in labels:
                if label in stripped:
                    if ":" in line:
                        val = line.split(":", 1)[1].strip()
                        if val and len(val) < 100:
                            return val
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and len(next_line) < 100 and not any(p in next_line.lower() for p in skip):
                            return next_line
        return None
