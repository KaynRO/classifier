import os, time, base64, traceback
from typing import Optional
from helpers.constants import *
from helpers.utils import *
from helpers.logger import *


SBR_WS = os.environ.get(
    "BRIGHTDATA_BROWSER_WS",
    "wss://brd-customer-hl_f2aa9202-zone-browser:v6hzqppm9838@brd.superproxy.io:9222",
)
TARGET_URL = "https://www.fortiguard.com/webfilter"


def _ocr_captcha(image_path: str, logger: Logger) -> Optional[str]:
    """OCR the captcha image with multi-strategy preprocessing.
    Returns the most frequently detected code, or None."""
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageEnhance
        import numpy as np
        from collections import Counter
    except ImportError as e:
        logger.error(f"[-] Missing OCR dependencies: {e}")
        return None

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        logger.error(f"[-] Cannot open captcha image: {e}")
        return None

    results = []
    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

    # Strategy 1: Per-channel thresholding
    r, g, b = img.split()
    for channel in [r, g, b, img.convert("L")]:
        enhanced = ImageEnhance.Contrast(channel).enhance(5.0)
        for thresh in [80, 100, 120, 140, 160]:
            binary = enhanced.point(lambda x: 0 if x < thresh else 255)
            scaled = binary.resize((binary.width * 3, binary.height * 3), Image.NEAREST)
            for psm in [7, 8, 13, 6]:
                cfg = f"--psm {psm} -c tessedit_char_whitelist={whitelist}"
                try:
                    text = pytesseract.image_to_string(scaled, config=cfg).strip()
                    text = text.replace(" ", "").replace("\n", "")
                    if 3 <= len(text) <= 8:
                        results.append(text)
                except Exception:
                    pass

    # Strategy 2: Saturation-based text isolation
    try:
        arr = np.array(img)
        max_c = arr.max(axis=2)
        min_c = arr.min(axis=2)
        saturation = max_c.astype(int) - min_c.astype(int)
        brightness = arr.mean(axis=2)
        text_mask = ((saturation > 30) & (brightness < 200)).astype(np.uint8) * 255
        mask_img = Image.fromarray(text_mask).filter(ImageFilter.MaxFilter(3))
        mask_scaled = mask_img.resize((mask_img.width * 3, mask_img.height * 3), Image.NEAREST)
        for psm in [7, 8, 13, 6]:
            cfg = f"--psm {psm} -c tessedit_char_whitelist={whitelist}"
            try:
                text = pytesseract.image_to_string(mask_scaled, config=cfg).strip()
                text = text.replace(" ", "").replace("\n", "")
                if 3 <= len(text) <= 8:
                    results.append(text)
            except Exception:
                pass
    except Exception:
        pass

    if results:
        counter = Counter(results)
        best = counter.most_common(1)[0][0]
        logger.debug(f"[*] OCR candidates: {counter.most_common(5)}")
        return best.upper()
    return None


def _extract_captcha_image(page) -> Optional[str]:
    """Extract captcha image from shadow DOM, return base64-encoded PNG bytes path."""
    img_src = page.evaluate("""() => {
        const cw = document.querySelector('captcha-widget, #captcha_widget');
        if (!cw || !cw.shadowRoot) return null;
        const img = cw.shadowRoot.querySelector('img');
        if (!img) return null;
        return img.src;
    }""")
    if img_src and img_src.startswith("data:image"):
        b64_data = img_src.split(",")[1]
        path = "/tmp/fortiguard_captcha.png"
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64_data))
        return path
    return None


def _enter_captcha_and_submit(page, code: str):
    """Enter captcha code into shadow DOM input and click submit."""
    return page.evaluate("""(code) => {
        const cw = document.querySelector('captcha-widget, #captcha_widget');
        if (!cw || !cw.shadowRoot) return 'no shadow root';
        const input = cw.shadowRoot.querySelector('.captcha-input, input[type="text"], input:not([type="hidden"])');
        if (!input) return 'no input found';
        input.value = '';
        input.focus();
        input.value = code;
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
        const hiddenCode = document.querySelector('#captcha_code');
        if (hiddenCode) hiddenCode.value = code;
        const buttons = cw.shadowRoot.querySelectorAll('button');
        for (const btn of buttons) {
            if (btn.textContent.toLowerCase().includes('submit') || btn.classList.contains('captcha-submit')) {
                btn.click();
                return 'submitted: ' + code;
            }
        }
        if (buttons.length > 0) { buttons[buttons.length - 1].click(); return 'submitted (last): ' + code; }
        return 'no submit button';
    }""", code)


def _extract_category(body_text: str) -> str:
    for line in body_text.split("\n"):
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("category:") or lower.startswith("category :"):
            val = stripped.split(":", 1)[1].strip()
            if val and val.lower() not in ["", "category"]:
                return val
    # Check for "Newly Registered Domain" in history
    if "newly registered" in body_text.lower():
        return "Newly Registered Domain"
    return "Not Found"


def _fill_form(page, domain: str, logger: Logger) -> bool:
    """Fill URL input and solve ALTCHA. Returns True if ALTCHA verified."""
    url_input = page.query_selector('input[name="url"]')
    if not url_input:
        logger.error("[-] URL input not found")
        return False
    url_input.click()
    url_input.fill(domain)
    logger.info(f"[*] Entered domain: {domain}")

    altcha = page.query_selector('input[id*="altcha_checkbox"]')
    if altcha:
        altcha.click(force=True)
        logger.info("[*] Clicked ALTCHA checkbox")

    # Wait up to 30s for ALTCHA proof-of-work
    for i in range(30):
        time.sleep(1)
        plen = page.evaluate('() => { const h = document.querySelector(\'input[name="altcha"]\'); return h ? h.value.length : 0; }')
        if plen > 10:
            logger.info(f"[*] ALTCHA verified after {i+1}s")
            return True
    logger.warning("[!] ALTCHA did not verify in 30s")
    return False


class FortiGuard:
    def __init__(self) -> None:
        self.logger = Logger(__name__)
        self.url = TARGET_URL

    def check(self, driver, target_url: str, return_reputation_only: bool = False) -> Optional[str]:
        """Check URL category on FortiGuard via BrightData Scraping Browser.
        The `driver` argument is ignored — we use Playwright instead."""
        self.logger.info(f" Targeting fortiguard ".center(60, "="))
        self.logger.info(f"[*] Using BrightData Scraping Browser")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.error("[-] playwright not installed")
            return "Playwright Missing"

        clean_domain = target_url.replace("https://", "").replace("http://", "").strip("/")

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(SBR_WS)
                page = browser.new_page()
                page.set_default_timeout(60000)

                self.logger.info(f"[*] Navigating to {self.url}")
                page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(4)

                if not _fill_form(page, clean_domain, self.logger):
                    browser.close()
                    return "ALTCHA Failed"

                # First submit — triggers image captcha
                page.evaluate('() => { var b = document.querySelectorAll("#webfilter_search_form_submit"); if(b.length>0) b[b.length-1].click(); }')
                self.logger.info("[*] First submit clicked")
                time.sleep(4)

                # Quick check — maybe results appeared immediately
                body = page.inner_text("body")
                if "category:" in body.lower():
                    category = _extract_category(body)
                    self.logger.success(f"[+] Category: {category}")
                    browser.close()
                    return category

                # Captcha solving loop — 3 attempts
                for attempt in range(1, 4):
                    self.logger.info(f"[*] Captcha attempt {attempt}/3")

                    # If on failure page, restart
                    body = page.inner_text("body")
                    if "security check failed" in body.lower():
                        self.logger.info("[*] On failure page, restarting...")
                        page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(4)
                        if not _fill_form(page, clean_domain, self.logger):
                            continue
                        page.evaluate('() => { var b = document.querySelectorAll("#webfilter_search_form_submit"); if(b.length>0) b[b.length-1].click(); }')
                        time.sleep(4)

                    captcha_path = _extract_captcha_image(page)
                    if not captcha_path:
                        self.logger.warning("[!] No captcha image found")
                        continue

                    code = _ocr_captcha(captcha_path, self.logger)
                    if not code:
                        self.logger.warning("[!] OCR failed")
                        continue

                    self.logger.info(f"[*] OCR code: {code}")
                    _enter_captcha_and_submit(page, code)
                    time.sleep(5)

                    body = page.inner_text("body")
                    if "category:" in body.lower():
                        category = _extract_category(body)
                        self.logger.success(f"[+] Category: {category}")
                        browser.close()
                        return category
                    elif "security check failed" in body.lower():
                        self.logger.warning(f"[!] Wrong captcha code on attempt {attempt}")
                    else:
                        self.logger.debug(f"[*] Unknown state after attempt {attempt}")

                browser.close()
                self.logger.error("[-] All captcha attempts failed")
                return "Captcha Failed"

        except Exception as e:
            self.logger.error(f"[-] FortiGuard check failed: {e}")
            self.logger.error(traceback.format_exc())
            return "Error"

    def submit(self, driver, url: str, email: str, category: str) -> None:
        """Submit URL recategorization request to FortiGuard.
        The `driver` argument is ignored — we use Playwright instead."""
        self.logger.info(f" Targeting fortiguard (submit) ".center(60, "="))

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("playwright not installed")

        clean_domain = url.replace("https://", "").replace("http://", "").strip("/")
        reason = construct_reason_for_review_comment(url, category, simple_message=True)

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(SBR_WS)
                page = browser.new_page()
                page.set_default_timeout(60000)

                # FortiGuard submission form is the same page but different flow
                # After a lookup, click "Request Review" / "Submit a site for categorization"
                page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)

                # First do a lookup to reach the "Request Review" button
                _fill_form(page, clean_domain, self.logger)
                page.evaluate('() => { var b = document.querySelectorAll("#webfilter_search_form_submit"); if(b.length>0) b[b.length-1].click(); }')
                time.sleep(4)

                # Solve image captcha if present
                for attempt in range(3):
                    body = page.inner_text("body")
                    if "category:" in body.lower() or "request review" in body.lower():
                        break
                    captcha_path = _extract_captcha_image(page)
                    if not captcha_path:
                        break
                    code = _ocr_captcha(captcha_path, self.logger)
                    if not code:
                        continue
                    _enter_captcha_and_submit(page, code)
                    time.sleep(5)

                # Click "Request Review" link
                try:
                    page.click('a:has-text("Request Review")', timeout=5000)
                    self.logger.info("[*] Clicked Request Review")
                    time.sleep(3)
                except Exception:
                    self.logger.warning("[!] Could not find Request Review link")
                    browser.close()
                    return

                # Fill the submission form
                try:
                    # Email
                    email_input = page.query_selector('input[type="email"], input[name*="email"]')
                    if email_input and email:
                        email_input.fill(email)
                        self.logger.info(f"[*] Entered email: {email}")

                    # Category selection (FortiGuard has dropdowns for suggested category)
                    vendor_category = categories_map.get(category, {}).get("FortiGuard", category)
                    cat_select = page.query_selector('select[name*="category"], select[name*="rating"]')
                    if cat_select:
                        page.select_option('select[name*="category"], select[name*="rating"]', label=vendor_category)
                        self.logger.info(f"[*] Selected category: {vendor_category}")

                    # Comment
                    comment = page.query_selector('textarea[name*="comment"], textarea')
                    if comment:
                        comment.fill(reason)

                    # Submit button
                    page.click('button[type="submit"], input[type="submit"]')
                    self.logger.success("[+] Submission sent to FortiGuard")
                    time.sleep(3)
                except Exception as e:
                    self.logger.error(f"[-] Submission form error: {e}")

                browser.close()

        except Exception as e:
            self.logger.error(f"[-] FortiGuard submit failed: {e}")
            raise
