import traceback, time
from typing import Optional
from helpers.utils import *
from helpers.logger import *
from helpers.captcha_dual_solver import get_dual_solver


class Intelixsophos:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = "https://intelix.sophos.com/url"
        self.hcaptcha_sitekey = "2fe029e7-318b-44ee-8ae0-ced519d390da"


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

        # Solve hCaptcha using dual solver (2Captcha → CapSolver fallback)
        self.logger.info("[*] Solving hCaptcha...")
        solver = get_dual_solver()
        token = solver.solve_hcaptcha(self.hcaptcha_sitekey, self.url)

        if not token:
            self.logger.error("[-] hCaptcha could not be solved by any provider")
            return "hCaptcha Unsolved"

        # Inject token into the page
        self.logger.info(f"[*] Injecting hCaptcha token ({len(token)} chars)...")
        driver.execute_script("""
            // Inject into h-captcha-response and g-recaptcha-response (compat mode)
            document.querySelectorAll(
                'textarea[name="h-captcha-response"], textarea[name="g-recaptcha-response"]'
            ).forEach(function(el) {
                el.value = arguments[0];
                el.innerHTML = arguments[0];
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            });

            // Try triggering hcaptcha verified callback
            if (typeof hcaptcha !== 'undefined') {
                try { hcaptcha.execute(); } catch(e) {}
            }
        """, token)
        time.sleep(3)

        # Check if button enabled
        btns = driver.find_elements("css selector", "button.submit-button")
        if btns and btns[0].is_enabled():
            self.logger.success("[+] hCaptcha token accepted — button enabled")
        else:
            # Try force-enabling and submitting
            self.logger.warning("[!] Button still disabled — trying force submit")
            driver.execute_script("""
                var btn = document.querySelector('button.submit-button');
                if (btn) { btn.disabled = false; btn.classList.remove('p-disabled'); btn.click(); }
            """)
            time.sleep(15)
            body_text = get_text(driver, "body")
            cat = self._extract_category(body_text)
            if cat:
                return cat
            return "hCaptcha Token Rejected"

        # Click Analyze
        try:
            wait_and_click_on_element(driver, "button:has-text('Analyze')")
            self.logger.info("[*] Clicked Analyze")
        except Exception:
            driver.execute_script("document.querySelector('button.submit-button')?.click()")

        # Wait for results
        self.logger.info("[*] Waiting for analysis results...")
        time.sleep(15)

        body_text = get_text(driver, "body")
        cat = self._extract_category(body_text)

        if cat:
            self.logger.success(f"[+] Category: {cat}")
        else:
            cat = "Not Found"
            self.logger.warning("[-] Could not extract category from results page")

        return cat


    def _extract_category(self, body_text: str) -> Optional[str]:
        skip = ["find out what", "submit your file", "machine learning", "decades of threat"]
        for i, line in enumerate(body_text.split("\n")):
            stripped = line.strip().lower()
            if any(p in stripped for p in skip):
                continue
            for label in ["category", "categorization"]:
                if label in stripped:
                    if ":" in line:
                        val = line.split(":", 1)[1].strip()
                        if val and len(val) < 100:
                            return val
                    if i + 1 < len(body_text.split("\n")):
                        next_line = body_text.split("\n")[i + 1].strip()
                        if next_line and len(next_line) < 100 and not any(p in next_line.lower() for p in skip):
                            return next_line
        return None
