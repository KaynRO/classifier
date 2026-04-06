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
        time.sleep(2)

        # Handle cookie consent banner
        try:
            cookie_btns = [
                "button:has-text('Accept All')",
                "button:has-text('Accept All Cookies')",
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

        # Find and fill the URL input
        input_selectors = [
            "input[placeholder*='URL']",
            "input[placeholder*='url']",
            "input[type='text']",
            "input[type='url']",
        ]
        input_filled = False
        for sel in input_selectors:
            try:
                if count_elements(driver, sel) > 0:
                    wait_and_input_on_element(driver, sel, target_url)
                    input_filled = True
                    self.logger.info(f"[*] Entered URL using selector: {sel}")
                    break
            except Exception:
                continue

        if not input_filled:
            raise Exception("Could not find URL input field")

        # Click Analyze/Submit button
        submit_selectors = [
            "button:has-text('Analyze')",
            "button:has-text('Submit')",
            "button[type='submit']",
        ]
        submitted = False
        for sel in submit_selectors:
            try:
                if count_elements(driver, sel) > 0:
                    wait_and_click_on_element(driver, sel)
                    submitted = True
                    self.logger.info(f"[*] Clicked submit: {sel}")
                    break
            except Exception:
                continue

        if not submitted:
            raise Exception("Could not find submit button")

        # Wait for results
        time.sleep(8)

        body_text = get_text(driver, "body")

        # Extract category and security info from page text
        cat = self.extract_field(body_text, ["category", "categorization"])
        sec = self.extract_field(body_text, ["security", "risk level", "risk"])
        analysis = self.extract_field(body_text, ["overall analysis", "analysis"])

        if cat:
            self.logger.success(f"[+] Category: {cat}")
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
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            for label in labels:
                if label in stripped:
                    # Value might be on same line after colon
                    if ":" in line:
                        val = line.split(":", 1)[1].strip()
                        if val:
                            return val
                    # Or on the next line
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        return lines[i + 1].strip()
        return None
