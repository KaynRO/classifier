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

        # Handle cookie consent banner
        try:
            cookie_btns = [
                "button:has-text('Accept All Cookies')",
                "button:has-text('Accept All')",
                "button#onetrust-accept-btn-handler",
            ]
            for sel in cookie_btns:
                if count_elements(driver, sel) > 0:
                    wait_and_click_on_element(driver, sel)
                    self.logger.info("[*] Accepted cookie consent")
                    time.sleep(1)
                    break
        except Exception:
            self.logger.debug("[*] No cookie consent banner found")

        # Click the URL tab to ensure it's active
        try:
            url_tab_selectors = [
                "span:has-text('URL')",
                ".p-tabview-nav-link:has-text('URL')",
            ]
            for sel in url_tab_selectors:
                if count_elements(driver, sel) > 0:
                    wait_and_click_on_element(driver, sel)
                    self.logger.info("[*] Clicked URL tab")
                    time.sleep(1)
                    break
        except Exception:
            self.logger.debug("[*] URL tab click failed, may already be active")

        # Fill the URL input — use the specific #urlbox input
        url_input = "input#urlbox"
        try:
            wait_for_selector(driver, url_input, timeout=5000)
            clear_element(driver, url_input)
            wait_and_input_on_element(driver, url_input, target_url)
            self.logger.info(f"[*] Entered URL in #urlbox")
        except Exception:
            fallback = "input[placeholder*='intelix'], input[placeholder*='http']"
            wait_and_input_on_element(driver, fallback, target_url)
            self.logger.info(f"[*] Entered URL via fallback selector")

        time.sleep(1)

        # Check if sign-in is required (Guest mode = Analyze disabled)
        body_pre = get_text(driver, "body")
        if "guest" in body_pre.lower() and "sign in" in body_pre.lower():
            self.logger.warning("[!] Sophos Intelix requires authentication — running as Guest")
            # Try clicking Analyze anyway in case it works for some URLs
            pass

        # Click the Analyze button — wait for it to become enabled
        analyze_btn = "button:has-text('Analyze')"
        try:
            btns = driver.find_elements("css selector", "button.submit-button")
            enabled = False
            for _ in range(10):
                if btns and btns[0].is_enabled():
                    enabled = True
                    break
                time.sleep(0.5)
                btns = driver.find_elements("css selector", "button.submit-button")

            if not enabled:
                self.logger.error("[-] Analyze button is disabled — sign-in required to use Sophos Intelix")
                return "Requires Sign-In"

            wait_and_click_on_element(driver, analyze_btn)
            self.logger.info("[*] Clicked Analyze button")
        except Exception as e:
            self.logger.error(f"[-] Could not click Analyze: {e}")
            try:
                press_key(driver, url_input, "Enter")
                self.logger.info("[*] Pressed Enter as fallback")
            except Exception:
                raise Exception("Could not submit URL for analysis")

        # Wait for results (analysis can take 10-20 seconds)
        self.logger.info("[*] Waiting for analysis results...")
        time.sleep(15)

        body_text = get_text(driver, "body")

        # Extract category and security info
        cat = self.extract_field(body_text, ["category", "categorization"])
        sec = self.extract_field(body_text, ["security", "risk level", "risk"])
        analysis = self.extract_field(body_text, ["overall analysis", "overall risk"])

        # Try structured elements if text extraction failed
        if not cat:
            try:
                for sel in [".result-category", "[class*='category'] [class*='value']", ".p-card .category"]:
                    if count_elements(driver, sel) > 0:
                        cat = get_text(driver, sel).strip()
                        if cat:
                            break
            except Exception:
                pass

        if cat and cat.lower() not in ["", "category", "categorization"]:
            self.logger.success(f"[+] Category: {cat}")
        else:
            if "submit url for analysis" in body_text.lower() and "url report" in body_text.lower():
                self.logger.warning("[-] Analysis did not start — may require sign-in")
                cat = "Requires Sign-In"
            else:
                cat = "Not Found"
                self.logger.warning("[-] Could not extract category")

        if sec:
            self.logger.success(f"[+] Security: {sec}")
        if analysis:
            self.logger.success(f"[+] Analysis: {analysis}")

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
