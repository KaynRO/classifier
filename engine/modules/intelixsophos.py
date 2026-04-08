import os, time, traceback
from typing import Optional
from helpers.utils import *
from helpers.logger import *


SBR_WS = os.environ.get(
    "BRIGHTDATA_BROWSER_WS",
    "wss://brd-customer-hl_f2aa9202-zone-browser:v6hzqppm9838@brd.superproxy.io:9222",
)
TARGET_URL = "https://intelix.sophos.com/url"


class Intelixsophos:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = TARGET_URL

    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        """Check URL on Sophos Intelix via BrightData Scraping Browser.
        BrightData auto-solves hCaptcha. Retries up to 6 times due to ~17% success rate."""
        self.logger.info(f" Targeting intelixsophos ".center(60, "="))
        self.logger.info("[*] Using BrightData Scraping Browser")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.error("[-] playwright not installed")
            return "Playwright Missing"

        # Normalize URL
        clean_url = target_url
        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"

        # Retry up to 6 times because BrightData's hCaptcha auto-solver has ~17% success rate
        for attempt in range(1, 7):
            self.logger.info(f"[*] Attempt {attempt}/6")
            try:
                result = self._try_check(clean_url, attempt)
                if result and result not in ["Captcha Failed", "Timeout"]:
                    return result
            except Exception as e:
                self.logger.warning(f"[!] Attempt {attempt} error: {e}")

        self.logger.error("[-] All 6 attempts exhausted")
        return "Captcha Failed"

    def _try_check(self, clean_url: str, attempt: int) -> Optional[str]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(SBR_WS)
            page = browser.new_page()
            page.set_default_timeout(60000)

            try:
                self.logger.info(f"[*] Navigating to {self.url}")
                page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(8)  # Let hCaptcha iframes fully load

                # Accept cookies
                try:
                    page.click('button:has-text("Accept All Cookies")', timeout=3000)
                    self.logger.info("[*] Accepted cookies")
                    time.sleep(1)
                except Exception:
                    pass

                # Click URL tab
                try:
                    page.click('span:has-text("URL")', timeout=3000)
                    time.sleep(1)
                except Exception:
                    pass

                # Call Captcha.solve BEFORE entering URL — let BrightData detect and solve on page load
                self.logger.info("[*] Calling BrightData Captcha.solve (pre-fill)...")
                try:
                    client = page.context.new_cdp_session(page)
                    result = client.send("Captcha.solve", {"detectTimeout": 60000})
                    self.logger.info(f"[*] Captcha.solve returned: {result}")
                except Exception as e:
                    self.logger.warning(f"[!] Captcha.solve error: {e}")

                time.sleep(3)

                # Enter URL
                try:
                    page.fill("input#urlbox", clean_url)
                    self.logger.info(f"[*] Entered URL: {clean_url}")
                except Exception as e:
                    self.logger.warning(f"[!] URL input failed: {e}")
                    return None

                # Poll for button enable over 30 seconds
                btn_enabled = False
                for i in range(30):
                    time.sleep(1)
                    btn_enabled = page.evaluate(
                        '() => { const b = document.querySelector("button.submit-button"); return b && !b.disabled && !b.classList.contains("p-disabled"); }'
                    )
                    # Also check hCaptcha response value
                    hc_value = page.evaluate(
                        '() => { const el = document.querySelector("textarea[name=\\"h-captcha-response\\"]"); return el ? el.value.length : 0; }'
                    )
                    if i % 5 == 0:
                        self.logger.debug(f"[*] Poll {i+1}s: btn={btn_enabled} hc_response_len={hc_value}")
                    if btn_enabled:
                        self.logger.success(f"[+] Button enabled after {i+1}s")
                        break

                if not btn_enabled:
                    self.logger.warning("[!] Button still disabled after 30s polling")
                    return None

                # Click Analyze
                page.click('button:has-text("Analyze")', force=True)
                self.logger.info("[*] Clicked Analyze")

                # Handle TOS dialog if it appears
                try:
                    page.click('button:has-text("I Agree")', timeout=3000)
                    time.sleep(1)
                except Exception:
                    pass

                # Wait for results page (navigates to /report/{id}/...)
                self.logger.info("[*] Waiting for analysis results...")
                try:
                    page.wait_for_url("**/report/**", timeout=30000)
                    self.logger.info(f"[*] Navigated to report: {page.url}")
                except Exception:
                    self.logger.warning("[!] Did not navigate to report page")

                time.sleep(5)
                body_text = page.inner_text("body")

                # Extract category from page
                category = self._extract_category(page, body_text)
                if category:
                    self.logger.success(f"[+] Category: {category}")
                    return category

                self.logger.warning("[-] Could not extract category from report page")
                return None

            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    def _extract_category(self, page, body_text: str) -> Optional[str]:
        """Extract category from the Sophos report page."""
        # Try to find the category tag/badge in the header
        try:
            tags = page.query_selector_all('.p-tag, .verdict-tag, [class*="category"]')
            for t in tags:
                text = t.inner_text().strip()
                if text and len(text) < 50 and text.lower() not in ["", "url report", "file report"]:
                    return text
        except Exception:
            pass

        # Fall back to text parsing
        lines = body_text.split("\n")
        skip = ["find out what", "submit your file", "machine learning", "decades of threat"]
        for i, line in enumerate(lines):
            stripped = line.strip()
            lower = stripped.lower()
            if any(p in lower for p in skip):
                continue
            for label in ["productivity category", "category", "categorization"]:
                if label in lower and ":" in stripped:
                    val = stripped.split(":", 1)[1].strip()
                    if val and len(val) < 100:
                        return val
        return None

    def submit(self, driver, url: str, email: str, category: str) -> None:
        """Sophos Intelix doesn't have a category submission form — it's an analysis tool.
        The /disagreement endpoint exists but requires authentication."""
        self.logger.warning("[!] Sophos Intelix does not support anonymous category submission")
        self.logger.warning("[!] The disagreement feature requires an authenticated Sophos ID session")
        raise NotImplementedError("Sophos Intelix does not support anonymous category submission")
