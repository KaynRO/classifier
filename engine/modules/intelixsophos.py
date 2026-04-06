import traceback, time
from typing import Optional
from helpers.utils import *
from helpers.logger import *


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

        # Handle cookie consent banner
        try:
            cookie_btns = [
                "button:has-text('Accept All Cookies')",
                "button:has-text('Accept All')",
            ]
            for sel in cookie_btns:
                if count_elements(driver, sel) > 0:
                    wait_and_click_on_element(driver, sel)
                    self.logger.info("[*] Accepted cookie consent")
                    time.sleep(1)
                    break
        except Exception:
            pass

        # Click the URL tab to ensure it's active
        try:
            if count_elements(driver, "span:has-text('URL')") > 0:
                wait_and_click_on_element(driver, "span:has-text('URL')")
                self.logger.info("[*] Clicked URL tab")
                time.sleep(1)
        except Exception:
            pass

        # Fill the URL input
        url_input = "input#urlbox"
        try:
            wait_for_selector(driver, url_input, timeout=5000)
            clear_element(driver, url_input)
            wait_and_input_on_element(driver, url_input, target_url)
            self.logger.info(f"[*] Entered URL in #urlbox")
        except Exception:
            raise Exception("Could not find URL input #urlbox")

        time.sleep(1)

        # Solve hCaptcha — the Analyze button is disabled until this is done
        self.logger.info("[*] Solving hCaptcha...")
        try:
            solver = get_captcha_solver()
            if solver and solver.solver:
                result = solver.solver.hcaptcha(
                    sitekey=self.hcaptcha_sitekey,
                    url=self.url,
                )
                token = result.get("code") if isinstance(result, dict) else str(result)
                self.logger.info(f"[*] hCaptcha solved, injecting token...")

                # Inject the token into the page
                driver.execute_script(f'''
                    // Set hcaptcha response
                    var textarea = document.querySelector('[name="h-captcha-response"]') ||
                                   document.querySelector('textarea[name="h-captcha-response"]');
                    if (textarea) textarea.value = "{token}";

                    // Also try the g-recaptcha-response (some sites use this alias)
                    var grecaptcha = document.querySelector('[name="g-recaptcha-response"]');
                    if (grecaptcha) grecaptcha.value = "{token}";

                    // Trigger hcaptcha callback if available
                    if (typeof hcaptcha !== 'undefined') {{
                        try {{ hcaptcha.execute(); }} catch(e) {{}}
                    }}
                ''')
                time.sleep(2)

                # Check if the callback triggered and enabled the button
                # Some Vue apps listen for the hcaptcha event — try dispatching it
                driver.execute_script(f'''
                    // Try to find and call the hcaptcha callback directly
                    var iframes = document.querySelectorAll('iframe[src*="hcaptcha"]');
                    if (iframes.length > 0) {{
                        window.postMessage({{type: "hcaptcha-verified", token: "{token}"}}, "*");
                    }}
                ''')
                time.sleep(2)
                self.logger.success("[+] hCaptcha token injected")
            else:
                self.logger.warning("[!] No captcha solver available — trying without")
        except Exception as e:
            self.logger.error(f"[-] hCaptcha solve failed: {e}")

        # Wait for button to become enabled
        analyze_btn = "button.submit-button"
        btns = driver.find_elements("css selector", analyze_btn)
        enabled = False
        for i in range(20):
            if btns and btns[0].is_enabled():
                enabled = True
                self.logger.info(f"[*] Analyze button enabled after {i*0.5}s")
                break
            time.sleep(0.5)
            btns = driver.find_elements("css selector", analyze_btn)

        if not enabled:
            # Try clicking the hcaptcha checkbox directly
            try:
                iframes = driver.find_elements("css selector", "iframe[title*='hCaptcha']")
                if iframes:
                    driver.switch_to.frame(iframes[0])
                    checkbox = driver.find_elements("css selector", "#checkbox")
                    if checkbox:
                        checkbox[0].click()
                        self.logger.info("[*] Clicked hCaptcha checkbox")
                    driver.switch_to.default_content()
                    time.sleep(5)
                    btns = driver.find_elements("css selector", analyze_btn)
                    if btns and btns[0].is_enabled():
                        enabled = True
            except Exception as e:
                self.logger.debug(f"[*] hCaptcha checkbox click failed: {e}")
                driver.switch_to.default_content()

        if not enabled:
            self.logger.error("[-] Analyze button still disabled after captcha attempt")
            return "Captcha Failed"

        # Click Analyze
        wait_and_click_on_element(driver, "button:has-text('Analyze')")
        self.logger.info("[*] Clicked Analyze button")

        # Wait for results
        self.logger.info("[*] Waiting for analysis results...")
        time.sleep(15)

        body_text = get_text(driver, "body")

        # Extract results
        cat = self.extract_field(body_text, ["category", "categorization"])
        sec = self.extract_field(body_text, ["security", "risk level", "risk"])

        if cat and cat.lower() not in ["", "category", "categorization"]:
            self.logger.success(f"[+] Category: {cat}")
        else:
            cat = "Not Found"
            self.logger.warning("[-] Could not extract category")

        if sec:
            self.logger.success(f"[+] Security: {sec}")

        return cat


    def extract_field(self, body_text: str, labels: list) -> Optional[str]:
        lines = body_text.split("\n")
        skip_phrases = ["find out what", "submit your file", "machine learning", "decades of threat"]

        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if any(p in stripped for p in skip_phrases):
                continue
            for label in labels:
                if label in stripped:
                    if ":" in line:
                        val = line.split(":", 1)[1].strip()
                        if val and len(val) < 100:
                            return val
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and len(next_line) < 100 and not any(p in next_line.lower() for p in skip_phrases):
                            return next_line
        return None
