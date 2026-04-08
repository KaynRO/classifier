import os, time, traceback
from typing import Optional
from helpers.utils import *
from helpers.logger import *
from helpers.captcha_dual_solver import get_dual_solver


HCAPTCHA_SITEKEY = "2fe029e7-318b-44ee-8ae0-ced519d390da"


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

        # Retry up to 8 times — BrightData's hCaptcha auto-solver has ~17% success rate
        for attempt in range(1, 9):
            self.logger.info(f"[*] Attempt {attempt}/8")
            try:
                result = self._try_check(clean_url, attempt)
                if result and result not in ["Captcha Failed", "Timeout"]:
                    return result
            except Exception as e:
                self.logger.warning(f"[!] Attempt {attempt} error: {e}")

        self.logger.error("[-] All 8 attempts exhausted")
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

                # Enter URL first
                try:
                    page.fill("input#urlbox", clean_url)
                    self.logger.info(f"[*] Entered URL: {clean_url}")
                except Exception as e:
                    self.logger.warning(f"[!] URL input failed: {e}")
                    return None
                time.sleep(2)

                # Cloud solver chain: 2Captcha → CapSolver
                btn_enabled = False
                self.logger.info("[*] Trying cloud hCaptcha solvers (2Captcha → CapSolver)...")
                solver = get_dual_solver()
                token = solver.solve_hcaptcha_chain(HCAPTCHA_SITEKEY, self.url)
                if token:
                    self.logger.info(f"[*] Got cloud token ({len(token)} chars), injecting...")
                    page.evaluate("""(token) => {
                        document.querySelectorAll('textarea[name="h-captcha-response"], textarea[name="g-recaptcha-response"]').forEach(el => {
                            el.value = token;
                            el.innerHTML = token;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                        });
                    }""", token)
                    time.sleep(3)
                    btn_enabled = page.evaluate(
                        '() => { const b = document.querySelector("button.submit-button"); return b && !b.disabled && !b.classList.contains("p-disabled"); }'
                    )
                    if btn_enabled:
                        self.logger.success("[+] Cloud token accepted, button enabled")

                # Priority 3 (fallback): BrightData Captcha.solve
                if not btn_enabled:
                    self.logger.info("[*] Cloud solvers failed, falling back to BrightData Captcha.solve...")
                    try:
                        client = page.context.new_cdp_session(page)
                        result = client.send("Captcha.solve", {"detectTimeout": 60000})
                        self.logger.info(f"[*] Captcha.solve returned: {result}")
                    except Exception as e:
                        self.logger.warning(f"[!] BrightData Captcha.solve error: {e}")

                    # Poll for button enable
                    for i in range(30):
                        time.sleep(1)
                        btn_enabled = page.evaluate(
                            '() => { const b = document.querySelector("button.submit-button"); return b && !b.disabled && !b.classList.contains("p-disabled"); }'
                        )
                        if btn_enabled:
                            self.logger.success(f"[+] BrightData solved after {i+1}s")
                            break

                if not btn_enabled:
                    self.logger.warning("[!] Button still disabled after all solvers")
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
        """Submit URL recategorization request via Sophos support form.
        Uses https://support.sophos.com/support/s/filesubmission (Web Address tab).
        Salesforce Lightning form — requires Playwright."""
        self.logger.info(f" Targeting intelixsophos (submit) ".center(60, "="))

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("playwright not installed")

        submit_url = "https://support.sophos.com/support/s/filesubmission?language=en_US"
        clean_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        reason = f"Please recategorize {clean_url} as {category}. " + construct_reason_for_review_comment(clean_url, category, simple_message=True)

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(SBR_WS)
                page = browser.new_page()
                page.set_default_timeout(60000)

                self.logger.info(f"[*] Navigating to {submit_url}")
                page.goto(submit_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(8)  # Wait for Lightning to hydrate

                # Dismiss OneTrust cookie banner
                try:
                    page.click("#accept-recommended-btn-handler", timeout=3000)
                    self.logger.info("[*] Dismissed cookie banner")
                    time.sleep(1)
                except Exception:
                    pass

                # Click "Web Address (URL)" tab
                try:
                    page.get_by_text("Web Address (URL)", exact=False).first.click()
                    self.logger.info("[*] Clicked Web Address (URL) tab")
                    time.sleep(3)
                except Exception as e:
                    self.logger.warning(f"[!] Could not click URL tab: {e}")

                # Fill the form via labels (shadow DOM — must use get_by_label)
                try:
                    page.get_by_label("Web Address (URL)").fill(clean_url)
                    self.logger.info(f"[*] Entered URL: {clean_url}")

                    page.get_by_label("First Name").fill("URL")
                    page.get_by_label("Last Name").fill("Classifier")
                    page.get_by_label("Email Address").fill(email or "admin@example.com")
                    self.logger.info(f"[*] Entered contact details")

                    # Product/Services dropdown — select "Sophos Web Appliance"
                    try:
                        page.click('button[id*="combobox-button"]', timeout=5000)
                        time.sleep(1)
                        page.get_by_text("Sophos Web Appliance", exact=True).first.click()
                        self.logger.info("[*] Selected product: Sophos Web Appliance")
                        time.sleep(1)
                    except Exception as e:
                        self.logger.warning(f"[!] Product dropdown failed: {e}")

                    # Comments
                    page.get_by_label("Comments").fill(reason)
                    self.logger.info(f"[*] Entered comments")

                    # Click Submit URL button
                    page.get_by_role("button", name="Submit URL").click()
                    self.logger.info("[*] Clicked Submit URL")
                    time.sleep(5)

                    # Verify success
                    body = page.inner_text("body").lower()
                    if "success" in body or "thank" in body or "received" in body or "submitted" in body:
                        self.logger.success("[+] Sophos submission accepted")
                    else:
                        self.logger.warning("[!] Success confirmation not detected — submission may still have worked")

                except Exception as e:
                    self.logger.error(f"[-] Form fill/submit failed: {e}")
                    raise

                browser.close()

        except Exception as e:
            self.logger.error(f"[-] Sophos submit failed: {e}")
            raise
